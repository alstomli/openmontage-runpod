"""Operator CLI: local execution, explicit approvals and reproducible smoke test."""

import argparse
from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import struct
import sys
import urllib.error
import urllib.request
import wave
import zlib

# Permit direct execution from a source checkout before editable installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openmontage_worker.runner import Runner, execute
from openmontage_worker.schema import IDENTIFIER
from openmontage_worker.storage import configured_store, LocalStore


def png():
    width, height = 320, 180
    rows = b"".join(b"\x00" + bytes([25 + y // 3, 60, 130]) * width for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def fixture(directory):
    directory.mkdir(parents=True, exist_ok=True)
    image = directory / "scene.png"
    audio = directory / "test-tone.wav"
    image.write_bytes(png())
    with wave.open(str(audio), "wb") as handle:
        handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        handle.writeframes(b"".join(struct.pack("<h", round(1200 * math.sin(2 * math.pi * 220 * n / 16000))) for n in range(64000)))
    return image, audio


def stage_file(store, project, source):
    data = source.read_bytes()
    if len(data) > 100 * 1024 * 1024:
        raise ValueError("Input exceeds 100 MiB.")
    checksum = sha256(data).hexdigest()
    suffix = source.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".m4a", ".ogg"):
        raise ValueError("Unsupported input extension.")
    key = f"inputs/{project}/{checksum}{suffix}"
    store.write(key, data)
    return {"key": key, "sha256": checksum}


def smoke(output):
    """Exercise real rendering with test media, not AI generation or speech."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    store = LocalStore(output / "storage")
    runner = Runner(store=store, work_root=output / "scratch")
    project = "smoke-test"
    image, audio = fixture(output / "inputs")
    image_ref, audio_ref = stage_file(store, project, image), stage_file(store, project, audio)
    board = {"title": "OpenMontage integration smoke test", "scenes": [{"text": "OpenMontage on Runpod", "subtitle": "Supplied media, reviewed versions", "duration": 2, "image": image_ref}, {"text": "Approved assets. Reproducible render.", "duration": 2, "image": image_ref}], "narration": audio_ref, "captions": [{"text": "Synthetic test audio, not speech narration.", "start": 0, "end": 2}, {"text": "Supplied media integration fixture.", "start": 2, "end": 4}]}
    records = []
    def call(op, **kwargs):
        request = {"input": {"operation": op, "project_id": project, "idempotency_key": f"smoke-{len(records)}", **kwargs}}
        response = execute(request, runner)
        records.append({"request": request, "response": response})
        (output / "smoke-results.json").write_text(json.dumps({"fixture_audio": "synthetic 220 Hz tone; no speech-quality claim", "steps": records}, indent=2), encoding="utf-8")
        if response["status"] == "failed":
            raise RuntimeError(json.dumps(response["error"]))
        return response
    plan = call("prepare", storyboard=board)
    call("approve", stage="plan", artifact_hash=plan["artifact_hash"], approved=True)
    assets = call("generate_assets", artifact_hash=plan["artifact_hash"])
    call("approve", stage="assets", artifact_hash=assets["artifact_hash"], approved=True)
    result = call("compose", artifact_hash=assets["artifact_hash"])
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Execute one Runpod-format request locally.")
    run.add_argument("request", type=Path)
    upload = sub.add_parser("upload", help="Import an operator-selected file into configured storage.")
    upload.add_argument("--project", required=True)
    upload.add_argument("file", type=Path)
    approve = sub.add_parser("approve", help="Explicitly approve a reviewed content version.")
    approve.add_argument("--project", required=True)
    approve.add_argument("--stage", choices=("plan", "assets"), required=True)
    approve.add_argument("--hash", required=True)
    approve.add_argument("--yes", action="store_true", help="Required attestation that the exact artifact was reviewed.")
    smoke_parser = sub.add_parser("smoke", help="Real four-second Remotion render with synthetic integration media.")
    smoke_parser.add_argument("--output", type=Path, default=Path("evidence/render-smoke"))
    submit = sub.add_parser("submit", help="Submit an existing request to an existing Runpod endpoint (starts billable work).")
    submit.add_argument("request", type=Path)
    submit.add_argument("--endpoint", required=True)
    status = sub.add_parser("status", help="Read an existing Runpod job status.")
    status.add_argument("--endpoint", required=True)
    status.add_argument("--job", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command in ("submit", "status"):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", args.endpoint):
            parser.error("Invalid endpoint ID.")
        secret = os.getenv("RUNPOD_API_KEY")
        if not secret:
            parser.error("RUNPOD_API_KEY must be configured.")
        if args.command == "submit":
            payload = json.loads(args.request.read_text(encoding="utf-8"))
            from openmontage_worker.schema import request as validate_request
            validate_request(payload.get("input"))
            suffix, data, method = "run", json.dumps(payload).encode(), "POST"
        else:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", args.job):
                parser.error("Invalid job ID.")
            suffix, data, method = "status/" + args.job, None, "GET"
        req = urllib.request.Request(f"https://api.runpod.ai/v2/{args.endpoint}/{suffix}", data=data, method=method, headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                print(json.dumps(json.load(response), indent=2))
        except urllib.error.HTTPError as exc:
            parser.exit(1, f"Runpod request failed with HTTP {exc.code}.\n")
        except urllib.error.URLError:
            parser.exit(1, "Runpod request failed; check network connectivity.\n")
        return 0
    if args.command == "smoke":
        smoke(args.output)
        return 0
    if args.command in ("upload", "approve") and not IDENTIFIER.fullmatch(args.project):
        parser.error("Invalid project identifier.")
    if args.command == "upload":
        print(json.dumps(stage_file(configured_store(), args.project, args.file), indent=2))
        return 0
    if args.command == "approve":
        if not args.yes:
            parser.error("Review the exact artifact, then use --yes to approve it.")
        job = {"input": {"operation": "approve", "project_id": args.project, "idempotency_key": f"approve-{args.stage}-{args.hash}", "stage": args.stage, "artifact_hash": args.hash, "approved": True}}
    else:
        job = json.loads(args.request.read_text(encoding="utf-8"))
    result = execute(job)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

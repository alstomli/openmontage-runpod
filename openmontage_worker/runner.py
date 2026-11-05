"""Bounded supplied-asset stages with durable approval and retry contracts."""

from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import tempfile
import time

from . import UPSTREAM_COMMIT, __version__, media, schema
from .errors import WorkerError
from .storage import canonical, configured_store, digest

LOG = logging.getLogger("openmontage_worker")


def event(name, **fields):
    LOG.info(json.dumps({"event": name, **fields}, sort_keys=True))


class Runner:
    def __init__(self, store=None, work_root=None):
        self.store = store or configured_store()
        self.work_root = Path(work_root or os.getenv("WORK_ROOT", ".work")).resolve()
        self.work_root.mkdir(parents=True, exist_ok=True)

    def key(self, project, stage, version):
        return f"projects/{project}/{stage}/{version}.json"

    def load(self, project, stage, version):
        artifact = self.store.read_json(self.key(project, stage, version))
        if digest(artifact) != version:
            raise WorkerError("corrupt_artifact", "Artifact does not match its approved content hash.")
        return artifact

    def approved(self, project, stage, version):
        key = f"projects/{project}/approvals/{stage}/{version}.json"
        try:
            approval = self.store.read_json(key)
        except WorkerError as exc:
            if exc.code == "not_found":
                raise WorkerError("approval_required", f"Explicit approval required for {stage} version {version}.") from exc
            raise
        if approval != {"stage": stage, "artifact_hash": version, "approved": True}:
            raise WorkerError("approval_required", "Approval record does not bind the requested artifact.")

    def blob(self, key, data):
        if len(data) > 100 * 1024 * 1024:
            raise WorkerError("asset_too_large", "Artifact exceeds 100 MiB.")
        self.store.write(key, data)
        return {"key": key, "sha256": sha256(data).hexdigest(), "bytes": len(data)}

    def intact(self, artifacts):
        try:
            return all(sha256(self.store.read(a["key"])).hexdigest() == a["sha256"] for a in artifacts)
        except WorkerError as exc:
            if exc.code == "not_found":
                return False
            raise

    def present(self, result):
        return {**result, "artifacts": [{**a, **self.store.location(a["key"])} for a in result.get("artifacts", [])]}

    def run(self, value):
        req = schema.request(value)
        project, op = req["project_id"], req["operation"]
        request_hash = digest(req)
        receipt_key = f"projects/{project}/requests/{op}/{sha256(req['idempotency_key'].encode()).hexdigest()}.json"
        started = time.monotonic()
        event("stage_started", project_id=project, operation=op)
        with self.store.lock(project):
            try:
                receipt = self.store.read_json(receipt_key)
            except WorkerError as exc:
                if exc.code != "not_found":
                    raise
                receipt = None
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise WorkerError("idempotency_conflict", "Idempotency key was already used with different input.")
                if self.intact(receipt["result"].get("artifacts", [])):
                    event("stage_cached", project_id=project, operation=op)
                    return self.present({**receipt["result"], "cached": True})
            # Each request workspace is isolated; no user-controlled host paths.
            with tempfile.TemporaryDirectory(prefix=f"{project}-", dir=self.work_root) as directory:
                result = getattr(self, op)(req, Path(directory))
            result.update(operation=op, project_id=project, cached=False)
            self.store.write_json(receipt_key, {"request_hash": request_hash, "result": result})
        event("stage_completed", project_id=project, operation=op, elapsed_seconds=round(time.monotonic() - started, 3))
        return self.present(result)

    def prepare(self, req, workspace):
        plan = req["storyboard"]
        version = digest(plan)
        key = self.key(req["project_id"], "plans", version)
        artifact = self.blob(key, canonical(plan))
        return {"status": "awaiting_approval", "approval_stage": "plan", "artifact_hash": version, "duration": plan["duration"], "artifacts": [artifact], "capabilities": {"supplied_assets": True, "plain_script_planning": False, "image_generation": False, "tts_generation": False, "render_runtime": "remotion", "composition_mode": "templated"}}

    def approve(self, req, workspace):
        stage, version, project = req["stage"], req["artifact_hash"], req["project_id"]
        self.load(project, "plans" if stage == "plan" else "assets", version)
        key = f"projects/{project}/approvals/{stage}/{version}.json"
        record = {"stage": stage, "artifact_hash": version, "approved": True}
        artifact = self.blob(key, canonical(record))
        return {"status": "approved", "approval_stage": stage, "artifact_hash": version, "artifacts": [artifact]}

    def generate_assets(self, req, workspace):
        project, version = req["project_id"], req["artifact_hash"]
        plan = self.load(project, "plans", version)
        self.approved(project, "plan", version)
        refs = [(plan["narration"], "narration")]
        refs.extend((s["image"], "image") for s in plan["scenes"] if "image" in s)
        seen, files, artifacts = set(), [], []
        for ref, kind in refs:
            if ref["key"] in seen:
                continue
            seen.add(ref["key"])
            data = self.store.read(ref["key"])
            if sha256(data).hexdigest() != ref["sha256"]:
                raise WorkerError("asset_hash_mismatch", "Supplied asset contents do not match the approved storyboard.")
            extension = ref["key"].rsplit(".", 1)[-1].lower()
            path = workspace / (ref["sha256"] + "." + extension)
            path.write_bytes(data)
            media.validate_media(path, kind, plan["duration"])
            key = f"projects/{project}/blobs/{ref['sha256']}.{extension}"
            artifact = self.blob(key, data)
            artifacts.append(artifact)
            files.append({**artifact, "kind": kind, "source_key": ref["key"], "extension": extension})
            event("asset_staged", project_id=project, kind=kind, sha256=artifact["sha256"])
        manifest = {"schema_version": 1, "plan_hash": version, "files": files, "provider": "supplied"}
        asset_version = digest(manifest)
        artifacts.append(self.blob(self.key(project, "assets", asset_version), canonical(manifest)))
        return {"status": "awaiting_approval", "approval_stage": "assets", "artifact_hash": asset_version, "plan_hash": version, "artifacts": artifacts}

    def compose(self, req, workspace):
        project, version = req["project_id"], req["artifact_hash"]
        manifest = self.load(project, "assets", version)
        self.approved(project, "assets", version)
        self.approved(project, "plan", manifest["plan_hash"])
        plan = self.load(project, "plans", manifest["plan_hash"])
        files = media.render(plan, manifest, self.store, workspace)
        render_version = digest({"asset_hash": version, "wrapper_version": __version__, "upstream_commit": UPSTREAM_COMMIT})
        artifacts = []
        for kind, path in files.items():
            key = f"projects/{project}/renders/{render_version}/{path.name}"
            artifacts.append({**self.blob(key, path.read_bytes()), "kind": kind})
        report = {"schema_version": 1, "asset_hash": version, "plan_hash": manifest["plan_hash"], "duration": plan["duration"], "width": plan["width"], "height": plan["height"], "runtime": "remotion", "wrapper_version": __version__, "upstream_commit": UPSTREAM_COMMIT, "artifacts": artifacts}
        artifacts.append({**self.blob(f"projects/{project}/renders/{render_version}/manifest.json", canonical(report)), "kind": "manifest"})
        return {"status": "completed", "artifact_hash": render_version, "artifacts": artifacts}


def execute(job, runner=None):
    """Stable application response contract; never expose raw exceptions.

    The Runpod adapter encodes failed errors as platform-compatible strings.
    """
    try:
        schema.require(isinstance(job, dict) and set(job) <= {"id", "input"} and "input" in job, "Job must contain an input object.")
        return (runner or Runner()).run(job["input"])
    except WorkerError as exc:
        event("stage_failed", code=exc.code)
        return {"status": "failed", "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
        event("stage_failed", code="internal_error", exception_type=type(exc).__name__)
        return {"status": "failed", "error": {"code": "internal_error", "message": "Unexpected worker failure; inspect worker logs."}}

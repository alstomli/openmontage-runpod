"""Small strict request contract. No executable code, URLs or worker paths."""

import math
import re

from .errors import WorkerError
from .storage import safe_key

IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


def require(condition, message):
    if not condition:
        raise WorkerError("invalid_input", message)


def fields(value, allowed, name):
    require(isinstance(value, dict), f"{name} must be an object.")
    require(not (set(value) - set(allowed)), f"{name} contains unsupported fields.")


def text(value, name, limit=500):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit, f"{name} must be nonempty text, at most {limit} characters.")
    require(not any(ord(c) < 32 and c not in "\n\t" for c in value), f"{name} contains control characters.")
    return value


def number(value, name):
    require(type(value) in (float, int) and math.isfinite(value), f"{name} must be a finite number.")
    return float(value)


def artifact_hash(value):
    require(isinstance(value, str) and HASH.fullmatch(value), "artifact_hash must be a lowercase SHA-256 digest.")
    return value


def asset(ref, project, kind):
    fields(ref, ("key", "sha256"), kind)
    key = safe_key(ref.get("key"))
    require(key.startswith(f"inputs/{project}/"), f"{kind} key must be under inputs/{project}/.")
    ext = key.rsplit(".", 1)[-1].lower()
    require(ext in (("png", "jpg", "jpeg", "webp") if kind == "image" else ("wav", "mp3", "m4a", "ogg")), f"Unsupported {kind} extension.")
    return {"key": key, "sha256": artifact_hash(ref.get("sha256"))}


def storyboard(value, project):
    fields(value, ("title", "scenes", "narration", "captions", "width", "height", "theme"), "storyboard")
    scenes = value.get("scenes")
    require(isinstance(scenes, list) and 1 <= len(scenes) <= 8, "Storyboard requires 1–8 scenes.")
    plan = {"schema_version": 1, "runtime": "remotion", "composition_mode": "templated", "title": text(value.get("title"), "title", 120), "scenes": []}
    elapsed = 0.0
    for index, scene in enumerate(scenes):
        fields(scene, ("text", "subtitle", "duration", "image"), f"scene {index + 1}")
        duration = number(scene.get("duration"), "scene duration")
        require(1 <= duration <= 30, "Each scene must last 1–30 seconds.")
        require(abs(duration * 30 - round(duration * 30)) < 0.00001, "Scene duration must align to 30 fps.")
        normalized = {"id": f"scene-{index + 1}", "text": text(scene.get("text"), "scene text", 200), "duration": duration, "start": round(elapsed, 6)}
        if "subtitle" in scene:
            normalized["subtitle"] = text(scene["subtitle"], "subtitle", 120)
            require(len(normalized["text"]) <= 80, "Scenes with a subtitle support titles up to 80 characters.")
            require(all(len(word) <= 24 for word in normalized["subtitle"].split()), "Subtitle words cannot exceed 24 characters; add spaces or shorten long tokens.")
            require(duration * 30 >= len(normalized["text"]) * 1.2 + 20, "Scene duration is too short for the approved title and subtitle reveal.")
        if "image" in scene:
            normalized["image"] = asset(scene["image"], project, "image")
        plan["scenes"].append(normalized)
        elapsed += duration
    require(elapsed <= 90, "Total duration cannot exceed 90 seconds.")
    plan["duration"] = round(elapsed, 6)
    width, height = value.get("width", 1280), value.get("height", 720)
    require(type(width) is int and type(height) is int and (width, height) in ((1280, 720), (1920, 1080)), "Supported sizes are 1280×720 and 1920×1080.")
    plan.update(width=width, height=height)
    theme = value.get("theme", "flat-motion-graphics")
    require(theme in ("flat-motion-graphics", "clean-professional", "minimalist-diagram"), "Unsupported theme.")
    plan["theme"] = theme
    plan["narration"] = asset(value.get("narration"), project, "narration")
    ref_hashes = {}
    for ref in [plan["narration"], *(s["image"] for s in plan["scenes"] if "image" in s)]:
        require(ref["key"] not in ref_hashes or ref_hashes[ref["key"]] == ref["sha256"], "Repeated asset keys must specify the same content hash.")
        ref_hashes[ref["key"]] = ref["sha256"]
    cues = value.get("captions")
    require(isinstance(cues, list) and 1 <= len(cues) <= 300, "Supply 1–300 explicitly timed caption cues.")
    plan["captions"] = []
    previous_end = 0.0
    for cue in cues:
        fields(cue, ("text", "start", "end"), "caption")
        start, end = number(cue.get("start"), "caption start"), number(cue.get("end"), "caption end")
        require(previous_end <= start < end <= elapsed, "Caption cues must be ordered, nonoverlapping and inside the timeline.")
        caption_text = text(cue.get("text"), "caption text", 300)
        require(not any(c in caption_text for c in "{}<>\\"), "Caption markup and style-control characters ({ } < > backslash) are unsupported; provide plain caption text.")
        plan["captions"].append({"text": caption_text, "start": start, "end": end})
        previous_end = end
    return plan


def request(value):
    fields(value, ("operation", "project_id", "idempotency_key", "storyboard", "artifact_hash", "stage", "approved"), "input")
    project = value.get("project_id")
    require(isinstance(project, str) and IDENTIFIER.fullmatch(project), "project_id must use lowercase letters, digits, _ or - (1–64 characters).")
    text(value.get("idempotency_key"), "idempotency_key", 128)
    op = value.get("operation")
    require(op in ("prepare", "approve", "generate_assets", "compose"), "Unknown operation.")
    allowed = {"operation", "project_id", "idempotency_key"}
    if op == "prepare":
        allowed.add("storyboard")
        return {**value, "storyboard": storyboard(value.get("storyboard"), project)} if not (set(value) - allowed) else _bad_fields()
    artifact_hash(value.get("artifact_hash"))
    allowed.add("artifact_hash")
    if op == "approve":
        allowed.update(("stage", "approved"))
        require(value.get("stage") in ("plan", "assets"), "Approval stage must be plan or assets.")
        require(value.get("approved") is True, "Approval requires an explicit approved: true.")
    require(not (set(value) - allowed), "Operation contains unsupported fields.")
    return dict(value)


def _bad_fields():
    raise WorkerError("invalid_input", "Operation contains unsupported fields.")

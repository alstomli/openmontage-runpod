"""Render existing upstream Explainer components without changing upstream files."""

from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import textwrap

from .errors import WorkerError
from .storage import canonical


def command(args, cwd=None, timeout=120):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise WorkerError("dependency_missing", f"Executable unavailable: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkerError("stage_timeout", "Media operation exceeded its configured deadline.") from exc
    if result.returncode:
        # Only operator-controlled executables and locally staged media are used.
        # Keep bounded diagnostics in worker logs, never in the API response.
        logging.getLogger("openmontage_worker").error(json.dumps({"event": "media_command_failed", "executable": Path(args[0]).name, "exit_code": result.returncode, "diagnostic": (result.stderr or result.stdout)[-6000:]}))
        raise WorkerError("media_failed", f"Media command failed with exit code {result.returncode}; inspect worker logs.")
    return result.stdout


def probe(path):
    try:
        return json.loads(command([os.getenv("FFPROBE_BINARY", "ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", "image2,png_pipe,jpeg_pipe,webp_pipe,wav,mp3,mov,ogg", "-show_streams", "-show_format", "-of", "json", str(path)]))
    except (ValueError, TypeError) as exc:
        raise WorkerError("invalid_media", "ffprobe returned invalid metadata.") from exc


def validate_media(path, kind, duration):
    info = probe(path)
    streams = info.get("streams", [])
    if kind == "image":
        video = [s for s in streams if s.get("codec_type") == "video"]
        if not video or not (0 < video[0].get("width", 0) <= 4096 and 0 < video[0].get("height", 0) <= 4096):
            raise WorkerError("invalid_media", "Images must decode and be no larger than 4096 pixels per dimension.")
    else:
        if not any(s.get("codec_type") == "audio" for s in streams):
            raise WorkerError("invalid_media", "Narration must contain a decodable audio stream.")
        try:
            actual = float(info["format"]["duration"])
        except (ValueError, KeyError) as exc:
            raise WorkerError("invalid_media", "Narration duration is unavailable.") from exc
        if not math.isfinite(actual) or abs(actual - duration) > 1:
            raise WorkerError("invalid_media", "Narration duration must match the storyboard within one second.")


def srt(captions):
    def timestamp(seconds):
        value = round(seconds * 1000)
        hours, remainder = divmod(value, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
    # These are supplied phrases, not aligned words. Line breaks affect only
    # layout; the exact supplied start/end times remain unchanged. Break long
    # tokens as well so filenames/URLs cannot overflow the safe subtitle area.
    def caption_text(value):
        if any(c in value for c in "{}<>\\"):
            raise WorkerError("invalid_input", "Caption markup and style-control characters are unsupported; provide plain caption text.")
        return "\n".join(textwrap.wrap(value, width=32, break_long_words=True, break_on_hyphens=False))
    return "\n\n".join(f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{caption_text(cue['text'])}" for index, cue in enumerate(captions, 1)) + "\n"


def render(plan, manifest, store, workspace):
    upstream = Path(os.getenv("OPENMONTAGE_ROOT", str(Path(__file__).resolve().parent.parent / "vendor" / "OpenMontage"))).resolve()
    composer = upstream / "remotion-composer"
    cli = composer / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise WorkerError("dependency_missing", "Upstream Remotion dependencies are missing; install composer dependencies at build time.")
    public = workspace / "public"
    public.mkdir(parents=True, exist_ok=True)
    asset_names = {}
    for item in manifest["files"]:
        data = store.read(item["key"])
        if sha256(data).hexdigest() != item["sha256"]:
            raise WorkerError("corrupt_artifact", "Approved asset contents changed.")
        name = item["sha256"] + "." + item["extension"]
        (public / name).write_bytes(data)
        asset_names[item["source_key"]] = name
    cuts = []
    for scene in plan["scenes"]:
        cut = {"id": scene["id"], "type": "hero_title" if "subtitle" in scene else "text_card", "source": "", "in_seconds": scene["start"], "out_seconds": scene["start"] + scene["duration"], "text": scene["text"], "subtitle": scene.get("subtitle", "")}
        if "image" in scene:
            cut["backgroundImage"] = asset_names[scene["image"]["key"]]
            cut["backgroundOverlay"] = 0.55
        cuts.append(cut)
    # Upstream's word-caption overlay cannot safely lay out phrase cues: each
    # phrase becomes a nowrap inline block. Burn our timed SRT after base render.
    props = {"theme": plan["theme"], "cuts": cuts, "overlays": [], "captions": [], "audio": {"narration": {"src": asset_names[plan["narration"]["key"]], "volume": 1}}}
    props_file = workspace / "props.json"
    props_file.write_bytes(canonical(props))
    base = workspace / "base.mp4"
    output = workspace / "final.mp4"
    args = [os.getenv("NODE_BINARY", "node"), str(cli), "render", "src/index.tsx", "Explainer", str(base), "--props", str(props_file), "--public-dir", str(public), "--codec", "h264", "--width", str(plan["width"]), "--height", str(plan["height"]), "--frames", f"0-{round(plan['duration'] * 30) - 1}", "--concurrency", "1"]
    browser = os.getenv("COMPOSER_BROWSER_EXECUTABLE")
    if browser:
        args.extend(("--browser-executable", browser))
    command(args, cwd=composer, timeout=int(os.getenv("RENDER_TIMEOUT_SECONDS", "900")))
    captions_file = workspace / "captions.srt"
    captions_file.write_text(srt(plan["captions"]), encoding="utf-8")
    # Fixed basename + cwd avoids injecting host paths or user text into the
    # FFmpeg filter graph. Libass wraps within safe margins at either resolution.
    subtitle_filter = "subtitles=filename=captions.srt:force_style='FontName=DejaVu Sans,FontSize=14,Alignment=2,MarginL=16,MarginR=16,MarginV=18,Outline=1.2,Shadow=0,WrapStyle=0'"
    command([os.getenv("FFMPEG_BINARY", "ffmpeg"), "-v", "error", "-y", "-i", str(base), "-vf", subtitle_filter, "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "2", "-c:a", "copy", "-movflags", "+faststart", str(output)], cwd=workspace, timeout=int(os.getenv("RENDER_TIMEOUT_SECONDS", "900")))
    metadata = probe(output)
    video = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
    if not video or not audio or video[0].get("width") != plan["width"] or video[0].get("height") != plan["height"]:
        raise WorkerError("invalid_render", "Render lacks expected video dimensions or narration audio.")
    if abs(float(metadata["format"]["duration"]) - plan["duration"]) > 0.2:
        raise WorkerError("invalid_render", "Rendered duration differs from the approved timeline.")
    thumb = workspace / "thumbnail.png"
    command([os.getenv("FFMPEG_BINARY", "ffmpeg"), "-v", "error", "-y", "-i", str(output), "-ss", str(min(1, plan["duration"] / 2)), "-frames:v", "1", str(thumb)])
    return {"video": output, "captions": captions_file, "thumbnail": thumb, "props": props_file}

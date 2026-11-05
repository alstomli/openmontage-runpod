# Request contract and operator CLI

The authority for these fields is `openmontage_worker/schema.py`. The worker is a trusted single-account execution endpoint. Approval data binds a reviewed version; it is not a separate user-authentication or multi-tenant authorization system.

## Operations

Every request has an `input` object with `operation`, `project_id` and `idempotency_key`. `project_id` uses lowercase letters, digits, `_` or `-`, starts with a letter/digit and is at most 64 characters. Idempotency keys are nonempty text, at most 128 characters. Unknown fields/operations are rejected.

| Operation | Additional input | Successful application status |
|---|---|---|
| `prepare` | `storyboard` | `awaiting_approval`, `approval_stage: plan`, `artifact_hash` |
| `approve` | `stage: plan` or `assets`, `artifact_hash`, `approved: true` | `approved` |
| `generate_assets` | Approved plan `artifact_hash` | `awaiting_approval`, `approval_stage: assets`, new `artifact_hash` |
| `compose` | Approved assets `artifact_hash` | `completed`, render `artifact_hash` and artifact references |

`generate_assets` stages and validates supplied files; its name does not imply model generation in this release. Composition checks both asset and parent plan approvals.

Each artifact reference includes a storage `key`, SHA-256 and byte count. The deployed filesystem-on-network-volume profile adds a worker `local_path`; it does not return a public download URL. The optional generic S3 adapter adds an `s3://` URI and expiring presigned URL. Runpod's volume S3 API is used separately for authenticated file transfer, not as that generic adapter.

The worker returns an application `status`; Runpod's outer lifecycle status is separate. In 0.1.1, the handler's structured error dictionary passed intermediate SDK tests but the live provider dropped it and reported outer `COMPLETED` with application `status: failed`. In 0.1.2, the Runpod adapter returns a sanitized `{code,message}` serialized as a JSON **string** in `error`, while local `execute`/CLI keep a dictionary. Full SDK wire-path tests verify serialization. Actual live retests then returned provider `FAILED` with `{"code":"invalid_input","message":"Unknown operation."}` preserved as JSON text, and a fresh valid prepare returned `COMPLETED` / application `awaiting_approval`. Retest this boundary after relevant provider/SDK changes rather than inferring it from local checks alone.

## Storyboard limits

| Field | Contract |
|---|---|
| `title` | Nonempty, at most 120 characters |
| `scenes` | 1–8 entries |
| Scene `text` | Nonempty, at most 200 characters |
| Optional scene `subtitle` | Nonempty, at most 120 characters; each word at most 24 characters |
| Title when subtitle present | At most 80 characters; scene frames must be at least `len(title) * 1.2 + 20` to allow reveal |
| Scene `duration` | 1–30 seconds, aligned to 30 fps |
| Total duration | At most 90 seconds |
| `width`, `height` | 1280×720 default, or 1920×1080 |
| `theme` | `flat-motion-graphics` default, `clean-professional`, or `minimalist-diagram` |
| `narration` | Required supplied audio reference `{key, sha256}` |
| Optional scene `image` | Supplied image reference `{key, sha256}` |
| `captions` | 1–300 explicit `{text, start, end}` cues, ordered/nonoverlapping and inside the timeline; text at most 300 characters and no `{`, `}`, `<`, `>` or backslash style/markup controls |
| Media file size | At most 100 MiB per artifact |
| Image dimensions | Decodable, each dimension at most 4096 pixels |
| Narration duration | Must match storyboard duration within one second |

Supported image extensions: PNG, JPG/JPEG, WebP. Audio: WAV, MP3, M4A, OGG. Matching an extension is insufficient: the worker probes the media. The MP4 must have audio and video, expected dimensions, and duration within 0.2 seconds of the plan.

Input object keys must be under `inputs/{project_id}/…`; SHA-256 is a 64-character lowercase digest. Absolute paths, URLs, traversal, and conflicting hashes for the same repeated source key are rejected. The operator may import a selected host file through the CLI; job input itself does not have that host-file access.

## Local client sequence

Install the package in your development environment, or use the built Linux image, which includes it. Native local rendering additionally needs upstream npm dependencies, Node, FFmpeg/ffprobe, and a compatible browser; the Docker path is the tested runtime path.

```powershell
python -m pip install -e .
python scripts/client.py --help
python scripts/client.py upload --project demo path/to/narration.wav
python scripts/client.py upload --project demo path/to/scene.png
```

Save the returned `key` and `sha256` values in `examples/prepare.json`. Its zero hashes are intentional placeholders; replace both keys and hashes, narration timing, scene durations and captions with your actual supplied media. Use a new project ID or fresh idempotency keys for a distinct production.

```powershell
python scripts/client.py run examples/prepare.json
python scripts/client.py approve --project demo --stage plan --hash RETURNED_PLAN_HASH --yes
```

Review the stored plan at the returned location before approving. `--yes` explicitly attests to that review; it is not an instruction to skip it.

Put the returned plan hash in `examples/generate-assets.json`, then:

```powershell
python scripts/client.py run examples/generate-assets.json
python scripts/client.py approve --project demo --stage assets --hash RETURNED_ASSET_HASH --yes
```

Review the asset manifest/files before approving. Put the returned asset hash in `examples/compose.json`, then:

```powershell
python scripts/client.py run examples/compose.json
```

Outputs include `final.mp4`, `captions.srt`, `thumbnail.png`, `props.json` and `manifest.json`. The API returns references rather than embedding binary media in JSON. No VTT, downloadable project ZIP or automatic caption alignment is implemented in this baseline.

Wrapper 0.1.1 composes media in Remotion and burns supplied phrase captions afterward with FFmpeg/libass. SRT text wraps at 32 characters, including long tokens. The source timings remain authoritative; no transcription or synthetic word timing is introduced. A scene with a subtitle uses upstream's supported `hero_title` type and its reveal constraints above. Final visual acceptance must be checked against the evidence index.

## Existing Runpod endpoint

Configure `RUNPOD_API_KEY` in the calling process without committing or displaying it. For generic S3, configure the upload client and endpoint with the same bucket/prefix; `upload` writes directly to that storage, not through the Runpod API. For a mounted network volume, the local desktop filesystem is not the remote volume: import files into its `openmontage/inputs/{project_id}/…` namespace through authenticated volume tooling, retain their hashes, or execute the upload CLI in an environment with that volume mounted. Do not assume setting a Windows path to `/runpod-volume` transfers files to cloud storage.

```powershell
python scripts/client.py submit --endpoint EXISTING_ENDPOINT_ID examples/prepare.json
python scripts/client.py status --endpoint EXISTING_ENDPOINT_ID --job RETURNED_JOB_ID
```

Submission starts billable endpoint work. Follow the same prepare/approve/stage/approve/compose sequence using the example request files and returned hashes. The `approve` CLI command executes locally against configured storage; for a remote approval job use `submit` with `examples/approve-plan.json` or `examples/approve-assets.json` after reviewing and replacing its hash. The CLI currently does not expose cancellation or streaming commands.

## Configuration

| Variable | App default / role |
|---|---|
| `STORAGE_BACKEND` | `local`; cloud uses mounted durable `local` storage or compatible generic `s3` |
| `LOCAL_STORAGE_ROOT` | `.local-storage` locally; image sets `/data/openmontage` |
| `WORK_ROOT` | `.work` locally; image sets `/tmp/openmontage` |
| `OPENMONTAGE_ROOT` | `vendor/OpenMontage` relative to package checkout; image sets `/opt/openmontage` |
| `S3_BUCKET` | Required for `s3` |
| `S3_PREFIX` | `openmontage` |
| `S3_ENDPOINT_URL` | Optional provider endpoint |
| `AWS_DEFAULT_REGION`, AWS credential variables | Standard boto3 runtime configuration |
| `COMPOSER_BROWSER_EXECUTABLE` | Optional; image sets `/usr/bin/chromium` |
| `NODE_BINARY`, `FFPROBE_BINARY`, `FFMPEG_BINARY` | Operator-controlled executable overrides |
| `RENDER_TIMEOUT_SECONDS` | 900-second internal render subprocess deadline |
| `REQUIRE_NETWORK_VOLUME` | Startup guard; `1` requires an actual `/runpod-volume` mount and local root `/runpod-volume/openmontage` |
| `RUNPOD_API_KEY` | Remote client authentication, not needed for local execution |

`INPUT_ROOT` and `REMOTION_CONCURRENCY` are retained in container examples but do not change current application behavior: inputs are object keys and rendering is hardcoded to concurrency 1. A copied `.env` file is not automatically loaded by the worker. Supply variables through the process/container/endpoint environment.

For the deployed Runpod network volume, `STORAGE_BACKEND=local`, `LOCAL_STORAGE_ROOT=/runpod-volume/openmontage` and `REQUIRE_NETWORK_VOLUME=1` are configured. The normal `scripts/start_worker.py` entry point checks mount metadata, exact root and writability before starting the handler; it refuses a missing mount rather than silently writing to ephemeral disk. Directly invoking `handler.py` bypasses this startup check. The `/data/openmontage` image default is ephemeral unless explicitly mounted. Returned `local_path` values are inside the worker; authenticated external S3 transfer retrieved the actual cloud outputs. CPU/volume persistence was verified across observed worker IDs in the 0.1.1 run. Runpod's volume S3 API is not interchangeable with the optional generic adapter's presigned-download and conditional-create contract.

## Retry and release semantics

A matching request/idempotency key with intact result artifacts returns cached output. Changing input with the same key yields `idempotency_conflict`. Missing/corrupt referenced output is not treated as valid cached output. The receipt namespace is request-based, not build-based: after renderer/upstream changes bump the wrapper version and use fresh idempotency keys. Otherwise stable cached output is intentional.

The render manifest records wrapper version and upstream commit. Preserve these plus the image digest in release evidence. The output version includes wrapper/upstream identity; existing request receipts are still reused until a new request key is supplied.

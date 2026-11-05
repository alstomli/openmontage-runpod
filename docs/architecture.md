# Architecture

## Problem and first release

OpenMontage is an instruction-driven video-production toolkit: an agent normally reads its pipeline and stage instructions, makes creative decisions, calls tools, and asks for approval. Copying the repository into a container does not turn that interactive workflow into a queue worker.

This project introduces a narrow serverless boundary: execute an already specified and approved production task. The first release accepts a structured storyboard and supplied assets, stages the media, and renders through the existing Remotion `Explainer` composition. Plain-script planning and GPU-generated assets are separate capabilities, not assumptions hidden in a demo.

Proposed service envelope: up to eight scenes and 90 seconds. The schema and tests are the authority for the implemented limits.

## Request flow

```mermaid
flowchart LR
    A[Engineer or client] --> B[Prepare storyboard]
    B --> C[Review plan version]
    C --> D[Runpod queue: stage assets]
    D --> S[(Persistent artifact storage)]
    D --> E[Review asset version]
    E --> F[Runpod queue: compose]
    S --> F
    F --> S
    S --> G[MP4, captions, manifest]
```

The client holds no expensive worker while a person reviews a plan. Each submitted job performs bounded work and returns persistent artifact references. Runpod's queue manages scheduling; it is not the production database.

## Responsibilities and state

| Component | Responsibility | State |
|---|---|---|
| Preparation/client | Submit validated input and record explicit approval for a version | Request and approval metadata |
| Worker handler | Validate job, dispatch an allowed operation, produce structured output | Temporary job context |
| Production runner | Stage inputs, create composition props, invoke rendering, validate output | Recoverable checkpoints |
| Remotion composer | Turn approved props/media into frames and MP4 | Temporary rendering workspace |
| FFmpeg caption pass | Burn explicitly timed phrase subtitles with wrapping; preserve supplied audio | Temporary media output |
| Artifact storage | Keep plans, inputs, outputs and completion metadata across worker shutdowns | Durable |
| Runpod endpoint | Schedule container workers and enforce resource/time limits | Queue state with bounded retention |

Local filesystem storage is useful for development and can also use a persistent mounted network volume in cloud operation. The external S3 adapter is another option where the provider supports its conditional-create and presigned-download contract. A local directory inside a disposable container cannot establish recovery across worker replacement. For the user's existing Runpod storage, the proposed owned directory is `/runpod-volume/openmontage`; sibling model files must remain intact. Its actual mount and compute compatibility require cloud verification.

## Approval, retries, and concurrency

Approvals bind to the version or content hash reviewed. A changed storyboard needs a new approval. Asset approval identifies the staged assets, preventing a later composition from using an unrelated set.

Idempotency protects the same logical request from producing conflicting results when a client retries. Persisted completion metadata and artifact validation determine whether completed work can be reused. A project lock prevents overlapping writes. A test that mocks rendering can prove control flow; a real interruption/restart test is needed to prove recovery of media work.

Begin with one concurrent production per worker and one maximum worker in validation. This bounds resource contention and simplifies diagnosis. It does not establish multi-worker safety; distributed locking and a concurrent execution test must be verified before scaling.

## Runtime and security boundaries

The Linux image contains the application, pinned upstream source, Node, rendering browser, FFmpeg/ffprobe, Python dependencies, and fonts. After visual QA found phrase clipping, wrapper 0.1.1 adds an FFmpeg/libass caption burn pass after Remotion composition. It uses the supplied phrase timings, wraps long cues and does not fabricate word alignment. This is caption postprocessing, not a silent switch to another composition runtime. Final visual retest is recorded separately. Assets and optional model weights are separate from source code. Credentials are runtime configuration and must never be baked into image layers or committed to the public repository.

Inputs are data, not shell commands or arbitrary executable composition code. The worker must constrain file/object references, operation names, sizes, duration, and scene count. Network asset retrieval, if supported, needs explicit host/protocol and private-address protections. Do not claim those protections until tests cover the implementation.

## What must still be measured

Cold start, warm stage runtime, CPU/RAM/disk use, GPU VRAM when generation is added, cost per completed video, and visual/audio quality. A successful build or unit test is not evidence of retrieval quality, GPU compatibility, cloud availability, or cost savings.

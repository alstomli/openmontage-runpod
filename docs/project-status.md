# Project status and ownership

This is a working status record. A deliverable is complete only when its evidence exists; an assigned task or design decision is not completion.

## Ownership

| Role | Owns | Handoff |
|---|---|---|
| Developer | Application package, handler, schema, runner, storage behavior, client, functional tests | Supplies executable interfaces, limits and failure behavior |
| DevOps | Docker, CI, image publishing, endpoint configuration, infrastructure scripts | Supplies repeatable environments and release/rollback commands |
| SRE | Reliability review, recovery tests, observability requirements, performance/cost results, operational readiness | Supplies evidence and issues to owning implementers |
| Recorder | README, illustrated walkthrough, architecture, decisions, troubleshooting, interview reference, evidence index | Obtains owner review and separates tested facts from future work |
| Coordinator | Shared contracts, sequencing, cross-role decisions, repository setup, screenshots | Resolves overlap and tracks external blockers |

Each shared file has one owner. Other roles request changes through that owner rather than editing concurrently.

## Milestones

| Milestone | Acceptance | Status |
|---|---|---|
| Source baseline | Upstream exact commit available; environment inspected | Completed, based on coordinator's command results |
| Local execution contract | Structured input, approval enforcement, staging and composition interfaces covered by functional tests | 24 unit + 22 reliability checks passed in packaged image; regression additions may change count |
| Container render | Linux image builds; real MP4 produced and inspected | Four-second offline render passed; 30-second visual QA found caption clipping; fix/rebuild/retest in progress |
| Durable recovery | Retry and replacement-worker behavior verified with preserved artifacts | Local/new-runner recovery and SDK checks passed; hard-kill/S3-provider verification outstanding |
| Cloud validation | Endpoint deployed; async request completes; durable output downloaded | Pending credentials/configuration and deployment |
| GPU assets | Fixed model/voice version; real compatibility, VRAM and timing measurements | Future milestone |
| Hub publication | Proven endpoint, metadata/tests, release and required review | Future milestone |

## Initial environment observations

Coordinator observed Git 2.56.0, Python 3.13.2, Node 19.0.0, and Docker client/engine 29.9.2. Docker Desktop server reported 4.97.0. Node 22.14.0 is installed through NVM but was not selected. FFmpeg and ffprobe were not on the Windows PATH.

The initial sandboxed clone failed to resolve `github.com`; an approved elevated clone succeeded. The initial Docker engine query was denied through the sandboxed named pipe; an approved elevated query succeeded. These describe this assistant's execution restrictions, not requirements to disable security on a developer workstation.

The public GitHub repository [alstomli/openmontage-runpod](https://github.com/alstomli/openmontage-runpod) has been created and visually verified. Foundation commit `f905958` is published on `main`; implementation is on `feat/runpod-worker` awaiting final validation/push/review. Cloud deployment is a separate action.

## Verification results and remaining boundaries

- Coordinator retained 24 passing unit tests in `evidence/logs/003-unit-tests.txt`.
- DevOps tested packaged image `sha256:f33bf954aaa6859bbbd7ce82dccd013f307029361a1619dc4b58f24180ad2c20` without application source mounts: 24 unit and 22 reliability checks, zero skips, plus a fresh four-second render with networking disabled. Compose took 39.019 seconds; MP4 was 500,093 bytes, H.264 1280×720 at 30 fps with AAC audio. These are local fixture measurements, not cloud performance promises.
- A later 30-second supplied-speech fixture passed binary media checks but failed visual review: a phrase cue was rendered as one unwrapped word and clipped. This image is superseded for release acceptance pending a corrected build and visual retest.
- Live S3 read/write and conditional locking are not verified. Botocore model/mock tests do not prove a provider's behavior.
- A process killed while holding a project lock can leave an orphan lock. An operator must verify the original writer stopped before removal.
- The endpoint is for a trusted single account, not a multi-tenant service with independent identity/authorization.
- Request receipts intentionally reuse stable output. After renderer/upstream changes, bump wrapper version and use fresh idempotency keys.
- Windows Zira speech, where used in a fixture, is an offline input-generation aid. It is not a worker TTS feature. Supplied captions have manual phrase timing, not forced word alignment.

## Evidence discipline

- **Implemented:** Code exists, but no claim that all paths work.
- **Locally verified:** A named local test or real render passed and has retained output.
- **Cloud verified:** The same version ran on a deployed endpoint with retained job/output evidence.
- **Planned:** Agreed scope that has not passed its acceptance check.
- **Unverified:** A capability or result for which no adequate evidence is available.

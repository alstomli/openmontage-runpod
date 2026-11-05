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
| Local execution contract | Structured input, approval enforcement, staging and composition interfaces covered by functional tests | Corrected archive image: 28 unit + 22 reliability checks passed |
| Container render | Linux image builds; real MP4 produced and inspected | Corrected 0.1.1 packaged four-second render passed; 30-second supplied-speech test inspected at 5/15/25 seconds and accepted as technical prototype with title-wrapping limitation |
| Durable recovery | Retry and cross-job persistence verified with preserved artifacts | Cloud plans/assets consumed across observed worker IDs; matching prepare replay cached; hard-kill recovery and generic S3 locking still unverified |
| Cloud media validation | Source build completes; worker ready; async request completes; durable output downloaded | 0.1.1 workflow completed, all five artifacts downloaded/hash-verified; cloud video frames inspected |
| Cloud failure-status validation | Invalid input produces provider failure with sanitized diagnostic; success path remains usable | 0.1.2 exact image 31 unit + 23 reliability passed; live invalid input `FAILED` with safe diagnostic and fresh valid prepare `COMPLETED` |
| GPU assets | Fixed model/voice version; real compatibility, VRAM and timing measurements | Future milestone |
| Hub publication | Proven endpoint, metadata/tests, release and required review | Future milestone |

## Initial environment observations

Coordinator observed Git 2.56.0, Python 3.13.2, Node 19.0.0, and Docker client/engine 29.9.2. Docker Desktop server reported 4.97.0. Node 22.14.0 is installed through NVM but was not selected. FFmpeg and ffprobe were not on the Windows PATH.

The initial sandboxed clone failed to resolve `github.com`; an approved elevated clone succeeded. The initial Docker engine query was denied through the sandboxed named pipe; an approved elevated query succeeded. These describe this assistant's execution restrictions, not requirements to disable security on a developer workstation.

The public repository [alstomli/openmontage-runpod](https://github.com/alstomli/openmontage-runpod) has [draft PR #1](https://github.com/alstomli/openmontage-runpod/pull/1). Foundation is on `main`; successful cloud media used 0.1.1 commit `95f5ecd`. Fix commit `5a69307` (0.1.2) is deployed and passed live negative/normal-prepare retests. The connector could not create a PR because of integration permissions; the coordinator used the browser. GitHub push and PR checks succeeded for initial implementation; final documentation/evidence updates and their automatic CI/build are tracked as their own subsequent revisions.

## Verification results and remaining boundaries

- The current retained unit log `evidence/logs/003-unit-tests.txt` records 28 passing unit tests after visual-fix regressions were added; earlier development had 24.
- DevOps tested packaged image `sha256:f33bf954aaa6859bbbd7ce82dccd013f307029361a1619dc4b58f24180ad2c20` without application source mounts: 24 unit and 22 reliability checks, zero skips, plus a fresh four-second render with networking disabled. Compose took 39.019 seconds; MP4 was 500,093 bytes, H.264 1280×720 at 30 fps with AAC audio. These are local fixture measurements, not cloud performance promises.
- A later 30-second supplied-speech fixture passed binary media checks but failed visual review: a phrase cue was rendered as one unwrapped word and clipped. That initial output is superseded by the corrected test below.
- Real Runpod S3 upload/readback/download was verified for this volume's transfer API. The worker uses the mounted filesystem; the optional generic S3 adapter's conditional locking and presigned-download contract remain unverified. Do not conflate them.
- A process killed while holding a project lock can leave an orphan lock. An operator must verify the original writer stopped before removal.
- The endpoint is for a trusted single account, not a multi-tenant service with independent identity/authorization.
- Request receipts intentionally reuse stable output. After renderer/upstream changes, bump wrapper version and use fresh idempotency keys.
- Windows Zira speech, where used in a fixture, is an offline input-generation aid. It is not a worker TTS feature. Supplied captions have manual phrase timing, not forced word alignment.
- Corrected checksum-archive image `sha256:b8b0ca6c2f32910db67eda0232d9a262264760836728e2551bf19ae82b540806` passed 28 unit + 22 reliability checks with no skips and offline networking. Actual bind-mount startup check passed; missing required mount was rejected. Its fresh four-second tone render completed in 40.618 seconds with networking disabled, no source mounts and `cached=false`: MP4 362,842 bytes, H.264 1280×720 at 30 fps with AAC, duration 4.054 seconds. DevOps visually inspected wrapped captions. This is local fixture performance, not cloud throughput.
- Corrected 30-second supplied-speech rerender completed in 259.896 seconds (wall call 259.977), MP4 1,835,627 bytes, duration 30.059 seconds, H.264 1280×720 at 30 fps with AAC. It used mounted frozen 0.1.1 application source, so it is a separate visual integration test rather than proof of the exact packaged archive image. Coordinator inspected frames at 5, 15 and 25 seconds: phrase captions fit and subtitles render. Technical prototype acceptance is established; a cosmetic upstream `hero_title` per-character animation can still wrap within a word, so general polished-layout quality is not claimed.
- The live console verified existing NETWORK volume `l34ba8wnno` (60 GB, `EU-RO-1`) and authorized GitHub connection. The existing Runpod API key remains masked/unused. Separately, the user explicitly approved an S3 transfer key, stored only in ignored local `.env`; no credential values were printed, committed or captured.
- Endpoint `aocbogtvk098ds` completed source build `95f5ecd`, became ready, and ran the complete 0.1.1 workflow on CPU 4 vCPU / 16 GB General Purpose 5 GHz. Its mounted-volume settings and data were verified through worker execution and independent file readback. Existing model data was retained; only the `openmontage` namespace was used.
- Cloud compose job `1cdc79ce-3fbb-4458-b71c-3e66d4ba3852-u1` completed on `0lwirxhe7d9ph2`, execution 138,890 ms, delay 4,285 ms. Delay includes queue/scheduling/startup, not pure cold start. MP4 1,829,646 bytes, SHA-256 `74dcd3ea89dad436dfb14ad5d9562d5a964a0eec149ec68896dd7c9a42e3b29d`, H.264 1280×720 at 30 fps / AAC / 30.059 seconds. All five output hashes verified; cloud frames at 5/15/25 seconds inspected. Provenance is wrapper 0.1.1, not a 0.1.2 rerender.
- Invalid-operation live testing found outer `COMPLETED` with only application `status: failed` and lost diagnostics in 0.1.1. Wrapper 0.1.2 serializes sanitized error JSON as a string in the provider channel; local CLI retains a dictionary. Exact image `88cc4fe1…` passed 31 unit + 23 reliability checks including a full SDK wire-path test. After redeploy, job `f05f1304-0659-4c49-82a3-1fece3f50b1d-u2` returned provider `FAILED` and safe `invalid_input` / `Unknown operation.` JSON text, execution 235 ms, delay 4,806 ms. Fresh valid prepare `a426eee3-aaeb-4589-b031-775ccfcd9a49-u1` returned `COMPLETED`, application `awaiting_approval`, `cached: false`, expected plan hash, execution 206 ms and delay 56,462 ms on worker `64drlvc6ms55j7`. These pass the prototype's changed-boundary gate; no new 0.1.2 long media render is claimed.

## Evidence discipline

- **Implemented:** Code exists, but no claim that all paths work.
- **Locally verified:** A named local test or real render passed and has retained output.
- **Cloud verified:** The same version ran on a deployed endpoint with retained job/output evidence.
- **Planned:** Agreed scope that has not passed its acceptance check.
- **Unverified:** A capability or result for which no adequate evidence is available.

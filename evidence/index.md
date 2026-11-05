# Evidence index

This index links real artifacts and screenshots to claims. Missing evidence is stated explicitly. Screenshots supplement copyable commands and logs; they do not replace them.

## Current record

| ID | Important step | Evidence | What it proves | Status |
|---|---|---|---|---|
| E01 | Initial environment inspection | [Environment log](logs/001-environment.txt), [evidence-report screenshot](screenshots/001-local-baseline.jpg) | Observed versions and missing host tools | Retained; screenshot displays an evidence report, not terminal UI |
| E02 | Upstream clone and pin | `vendor/OpenMontage` HEAD `d21f5d4eaa08422b09c7091757a05affcbabb35b`, `UPSTREAM.json`, `.gitmodules` | Exact source baseline and submodule registration | Observed |
| E03 | Linux container build | [Build summary](logs/002-container-build.txt), `logs/docker-worker-archive-build.log`, [local evidence-report screenshot](screenshots/003-build-validation.jpg) | Corrected 0.1.1 checksum-archive runtime built | Verified image `b8b0ca6c…`; no source mount dependency |
| E04 | Input validation and approval tests | [28 unit tests](logs/003-unit-tests.txt), `logs/container-unit-tests.txt`, [22 container reliability checks](logs/005-reliability-tests.txt), [SRE review](logs/sre-review.txt) | Tested validation, approvals, cache/recovery and pinned SDK behavior | Corrected archive image 28 unit + 22 reliability checks passed, zero skips; mount guard also tested |
| E05 | Supplied-asset render | [Four-second render summary](logs/004-render-smoke.txt), `render-archive-final/smoke-results.json`, [initial 30-second run](logs/007-narrated-smoke.txt), [corrected 30-second rerun](logs/008-narrated-fixed.txt), [verification JSON](logs/009-narrated-verification.json) | Real offline render/media validity and visual defect discovery/correction | Corrected packaged four-second render passed; separate 30-second test visually inspected at 5/15/25 seconds, prototype accepted with cosmetic title-wrapping limitation |
| E06 | Retry and cross-job persistence | [Reliability suite](logs/005-reliability-tests.txt), [prepare replay](cloud/prepare-replay-response.json), [asset approval](cloud/approve-assets-response.json), [compose](cloud/compose-response.json) | Local recovery tests, live cache reuse and persisted data consumed across observed worker IDs | Verified observed cases; hard-killed writer recovery and generic S3 locking remain unverified |
| E07 | Repository creation/publication | [Public repository](https://github.com/alstomli/openmontage-runpod), [GitHub screenshot](screenshots/002-public-repository.jpg), [draft PR #1](https://github.com/alstomli/openmontage-runpod/pull/1), [PR screenshot](screenshots/005-draft-pull-request.jpg) | Public repository/code publication and draft review | Foundation `main` commit `f905958`; implementation `95f5ecd` pushed on `feat/runpod-worker`, draft PR created |
| E08 | Runpod endpoint/configuration/build | [Compute form](screenshots/006-runpod-compute-configuration.jpg), [volume form](screenshots/008-runpod-volume-configuration.jpg), [media build complete](screenshots/012-runpod-build-completed.jpg), [0.1.2 fix build](screenshots/016-runpod-error-fix-build.jpg), [build log](logs/011-runpod-build.log), [endpoint](https://console.runpod.io/serverless/user/endpoint/aocbogtvk098ds) | Mounted-volume CPU endpoint built/runs jobs; separate media and transport provenance | Verified 0.1.1 media build and 0.1.2 fix build; live checks below |
| E09 | Async cloud workflow | [Prepare response](cloud/prepare-response.json), [compose response](cloud/compose-response.json), [completed job screenshot](screenshots/013-live-compose-completed.jpg) | Full approved supplied-media stage chain completed in cloud | Verified 0.1.1 compose job `1cdc79ce-3fbb-4458-b71c-3e66d4ba3852-u1`, 138,890 ms execution; 4,285 ms delay is not pure cold start |
| E10 | Durable cloud outputs | [Download/hash verification](cloud/download-verification.json), [media verification](cloud/media-verification.json), [cloud frame](screenshots/cloud-render-15s.png), [local preview of downloaded cloud file](screenshots/015-cloud-output-preview.jpg) | Five artifacts retrieved independently and hashes matched; cloud caption/subtitle layout inspected | Verified 0.1.1 MP4 1,829,646 bytes / 30.059 seconds; known cosmetic title-word-wrap remains |
| E11 | Rollback/recovery demonstration | Version identifiers and before/after job result | Tested rollback procedure | Pending |
| E12 | Deployment dry-run | [Dry-run summary](logs/006-deployment-dry-run.txt), `logs/deployment-dry-run.json` | Plan generation with explicit dummy values; no API calls | Verified local script behavior, not resource provisioning |
| E13 | Remote CI | [Actual GitHub PR checks screenshot](screenshots/007-github-ci-passed.jpg) | Push and PR verification checks successful in GitHub | Two successful workflow checks; not a registry-publish or Runpod job result |
| E14 | Corrected local playback/visual review | [Browser video preview](screenshots/004-render-preview.jpg), [written visual review](logs/010-visual-review.txt) | Actual corrected local media preview and inspected frames | Technical prototype accepted; upstream title-word-wrap cosmetic issue retained |
| E15 | Approved cloud input transfer | [Transfer log](logs/012-cloud-input-transfer.txt), [input hashes](cloud/inputs-transfer.json), [worker plan readback](cloud/plan-storage-verification.json) | Two inputs uploaded/read back, worker-written plan persisted; scoped helper did not list/delete sibling model files | Verified authorized Runpod volume S3 transfer; credential values remain private |
| E16 | Live error-transport defect/correction | [Actual 0.1.1 response](cloud/invalid-operation-response.json), [before screenshot](screenshots/014-live-error-before.jpg), [0.1.2 negative response](cloud/invalid-operation-v012-response.json), [after screenshot](screenshots/017-live-error-corrected.jpg) | Earlier false outer-completion fixed at provider boundary | 0.1.2 job `f05f1304-…` returned `FAILED` with safe JSON-string diagnostic, 235 ms execution |
| E17 | 0.1.2 packaged transport regression | [Exact-image verification](logs/016-0.1.2-handler-verification.txt), `logs/unit-0.1.2-tests.txt`, `logs/sre-0.1.2-tests.txt` | 31 unit + 23 reliability checks including SDK serialized wire path passed offline | Local image `88cc4fe1…`; live negative/success checks also passed; media unchanged from 0.1.1 |
| E18 | 0.1.2 normal success after correction | [Fresh prepare request](cloud/prepare-v012.json), [actual response](cloud/prepare-v012-response.json), [success screenshot](screenshots/018-live-success-after-fix.jpg) | Success path remains usable, expected plan hash, `cached: false` | Job `a426eee3-…` outer `COMPLETED`, application `awaiting_approval`, execution 206 ms; lifecycle label not a steady-ready claim |
| E19 | Final review handoff | [Updated draft PR](https://github.com/alstomli/openmontage-runpod/pull/1), [review screenshot](screenshots/019-pull-request-verified.jpg) | Work and evidence presented for review | Draft PR exists; merge/Hub publication are separate actions |

## Visual QA finding: valid MP4 can still be wrong

The first 30-second narrated fixture exposed clipped captions in an actual frame despite valid ffprobe streams/dimensions/duration. The initial adapter passed entire phrase cues to upstream's word-caption component, whose no-wrap layout treated each phrase as one word. Wrapper 0.1.1 now burns wrapped supplied phrase cues with FFmpeg/libass and uses a supported scene type for subtitles. DevOps inspected the corrected packaged four-second output. Coordinator inspected the longer supplied-speech result at 5, 15 and 25 seconds: all phrase captions are contained and subtitles visible. This establishes the caption fix and a working media prototype, not universal layout quality. The upstream `hero_title` character animation can still break a word across lines (for example, `finish` / `ed`).

![Actual frame showing the caption-overflow defect before correction](screenshots/caption-overflow-before.png)

*Captured output frame before the fix. It proves this fixture's readability failure, not a general statement about every upstream composition.*

| Corrected output evidence | Purpose |
|---|---|
| [5-second frame](screenshots/narrated-fixed-05s.png) | Caption containment; remaining title-word-wrap cosmetic issue visible |
| [15-second frame](screenshots/narrated-fixed-15s.png) | Caption and scene subtitle visibility |
| [25-second frame](screenshots/narrated-fixed-25s.png) | Later phrase cue remains inside frame |

The corrected 30-second MP4 is 1,835,627 bytes, SHA-256 `e32bd13e7fa0a2aa4a1e5ba52d1f1c2429b726d5b9d49392b7138ea01f18d611`, duration 30.059 seconds. Its compose stage took 259.896 seconds locally. The longer test mounted frozen 0.1.1 application source; the separate four-second archive-image test used no application source mounts. These provenance differences matter when explaining what each check proves.

## Screenshot checklist

Capture the actual selected settings and successful results. Each image needs a short caption naming the step, why it matters, code/image version, and the specific claim it supports.

1. Source baseline showing pinned commit and wrapper/vendor separation.
2. Successful image build and immutable image identity.
3. Contract/reliability test summary.
4. Finished video and representative frame; keep captions/audio verification separate.
5. Storage layout/checkpoint and retry/recovery result.
6. Public GitHub repository with no secret configuration visible.
7. Runpod endpoint worker, timeout, storage and image settings; mask sensitive values before capture.
8. Submitted job and successful completion with output references.
9. Download/playback of persistent MP4.
10. Failure diagnosis or rollback result where the demonstration actually occurred.

Do not fabricate terminal screenshots from invented output. A generated architecture figure is an explanatory diagram, not execution evidence. If a real screenshot cannot be safely captured, retain a redacted text log and mark the screenshot missing.

## Capture metadata template

```text
Evidence ID:
Captured at (America/New_York):
Wrapper commit / upstream commit / image digest:
Action and exact command (secrets omitted):
Expected outcome:
Observed outcome:
Artifact and screenshot paths:
Limitations:
Technical reviewer:
```

# Decision log

Dates use the user's America/New_York context. Append a new entry when a decision changes; preserve the reason and impact of the earlier decision.

## ADR-001 — Separate deployment wrapper, pinned upstream

- **Date:** November 4, 2026
- **Status:** Adopted; upstream source cloned.
- **Problem:** We need serverless integration while retaining a clear relationship with the original project.
- **Decision:** Keep deployment/application wrapper files at the repository root and OpenMontage under `vendor/OpenMontage`, pinned to `d21f5d4eaa08422b09c7091757a05affcbabb35b`.
- **Alternatives:** Copy all upstream source into the wrapper; modify a fork directly; fetch a moving `main` branch during each deployment.
- **Reason:** Pinning separates wrapper defects from upstream changes and makes a build reproducible. A fork can be introduced if upstream changes become substantial.
- **Consequence:** Upgrades are deliberate compatibility work. Repository/submodule metadata and image build must agree on the exact commit.

## ADR-002 — Supplied assets before generation

- **Status:** Adopted for milestone 1.
- **Decision:** Prove structured storyboard → supplied assets → rendered MP4 before adding local model generation.
- **Reason:** This isolates container, browser, media, schema and persistence failures from model/VRAM/provider failures.
- **Tradeoff:** The first milestone is an execution substrate, not a full text-to-video creative service.
- **Verification:** Requires a real render and media probe; see the evidence index.

## ADR-003 — Remotion template baseline

- **Status:** Adopted for the technical baseline.
- **Decision:** Use the existing Remotion `Explainer` composition and JSON props contract.
- **Reason:** The upstream repository includes runnable zero-key fixtures and an established render entry point. This reduces moving parts in the first integration.
- **Alternatives:** HyperFrames, FFmpeg-only composition, bespoke generated React code.
- **Tradeoff:** Fixed templates limit creative variety. Supporting another runtime is an explicit feature; no silent runtime substitution is allowed.

## ADR-004 — Separate human review from worker execution

- **Status:** Adopted in design; verify enforcement in tests.
- **Decision:** A client prepares and reviews versioned artifacts; queue jobs execute supported asset and composition stages.
- **Reason:** Keeping a GPU worker alive while a person decides wastes runtime and couples review latency to execution.
- **Tradeoff:** The client must carry durable project/version references and explicitly resubmit the next stage.

## ADR-005 — Durable storage outside the container

- **Status:** Initial decision, extended by ADR-009; local and cloud verification tracked separately.
- **Decision:** Initially local filesystem adapter for development and generic S3-compatible storage for production artifacts. Treat container disk as scratch. ADR-009 adds a mounted durable-volume profile.
- **Reason:** Workers may stop or be replaced. Plans, staged assets, and completed outputs must survive independently.
- **Tradeoff:** Requires object-storage credentials, cleanup policy, transfer handling, and concurrency semantics.

## ADR-006 — One worker and one job during validation

- **Status:** Starting deployment proposal.
- **Decision:** Active workers 0, maximum workers 1, one concurrent production per worker; set explicit measured timeouts.
- **Reason:** Bound spend and contention while observing startup and render behavior.
- **Tradeoff:** Queue latency and throughput are intentionally limited. Raise limits only after recovery/concurrency tests and cost measurements.

## ADR-007 — Public repository

- **Status:** User approved; public repository creation visually verified. Code push and deployment tracked separately.
- **Decision:** Deployment wrapper GitHub repository will be public.
- **Reason:** Explicit user preference on November 4, 2026, satisfying the working agreement to ask visibility before creation.
- **Consequence:** Review tracked content, screenshots, logs, input media, licenses and configuration examples before publishing. Credentials and personal production media do not belong in the repository.

## ADR-008 — Wrapped phrase captions after visual QA

- **Status:** Implemented in wrapper 0.1.1; packaged four-second and separate 30-second supplied-speech retests verified. Prototype acceptance, with title-wrapping cosmetic limitation.
- **Problem:** A 30-second supplied-speech fixture produced valid MP4 streams but a long phrase caption clipped. The adapter passed a phrase into upstream's nowrap word-caption renderer. `text_card` also ignored the requested scene subtitle.
- **Decision:** Keep upstream unchanged and Remotion as composition engine. Add a wrapper FFmpeg/libass subtitle pass using literal, wrapped supplied SRT phrase cues. Use a supported `hero_title` scene when a subtitle is requested.
- **Alternatives:** Fabricate word timing by splitting phrases; edit upstream caption components; omit long captions; accept valid ffprobe output despite clipping.
- **Reason:** Preserve the source timing without inventing alignment, fix the visible defect at the integration boundary, and retain clear upstream separation.
- **Tradeoff:** A second encode adds CPU time and another validation point. Measure the final image and inspect actual frames before accepting the release.
- **Evidence:** `evidence/screenshots/caption-overflow-before.png`, corrected `narrated-fixed-05s.png` / `-15s.png` / `-25s.png`, and `evidence/logs/009-narrated-verification.json`. Caption overflow is fixed; upstream character-level title wrapping remains a documented cosmetic issue.

## ADR-009 — Reuse durable mounted Runpod storage where compatible

- **Status:** Deployed and used by the successful 0.1.1 cloud stage chain; external input/plan/output readback verified. Hard-kill recovery remains separate.
- **Context:** The user identified existing purchased storage `l34ba8wnno`. A Runpod network volume and a general S3 bucket are different integration contracts.
- **Decision:** Add a mounted-volume profile using the filesystem adapter at `/runpod-volume/openmontage`, while retaining generic S3 as an alternative. Verify storage type/region and chosen compute can attach it before creating a production endpoint.
- **Reason:** Reuse persistent storage without assuming Runpod's file-transfer S3 API supports the generic adapter's conditional-create and presigned-download behavior.
- **Tradeoff:** Returned filesystem paths need authenticated input/output transfer; they are not download URLs. The worker must confirm the mount and persistence. Regional attachment can constrain resource choice.
- **Data ownership:** The wrapper owns only the `openmontage` namespace. Existing LLM files and sibling directories are not removed simply because deletion permission was offered.

## ADR-010 — Checksum archive for direct source builds

- **Status:** Local archive image verified; Runpod source build completed for 0.1.1 and produced a successful cloud video. New 0.1.2 transport build/gate tracked separately.
- **Decision:** Docker obtains the fixed OpenMontage commit from a public codeload archive with a checked SHA-256. The local Git submodule remains for inspection/CI verification.
- **Reason:** Runpod already has an authorized GitHub connection and can select this repository. Its builder should not depend on recursive submodule behavior. Direct source deployment also avoids requiring a separate GHCR publication before the first endpoint.
- **Tradeoff:** Docker builds need access to the fixed public archive; a checksum mismatch stops the build. Source-build provenance must retain the wrapper commit and resulting Runpod build/image identity. Registry-digest deployment remains an alternative.

## ADR-011 — JSON-string errors at the Runpod transport boundary

- **Status:** Implemented/deployed in 0.1.2, fix commit `5a69307`; exact image 31 unit + 23 reliability checks passed. Live invalid-operation returned provider `FAILED` with safe diagnostic; fresh normal prepare returned `COMPLETED` / `awaiting_approval`, uncached.
- **Problem:** A live invalid-operation job on 0.1.1 was outer `COMPLETED` with `output.status: failed`; the dictionary error disappeared. Earlier SDK-intermediate tests did not cover serialized wire behavior.
- **Decision:** Keep local `execute`/CLI errors structured. At the Runpod handler boundary serialize only sanitized `{code,message}` as a JSON string in `error`; return no traceback.
- **Reason:** Match the platform's supported transport contract and make provider failure observable. Test the full pinned SDK result path through the serialized HTTP payload, then verify the live provider response.
- **Tradeoff:** Clients decode error JSON text in provider failures. A local SDK wire test is stronger but still does not replace provider validation.
- **Media provenance:** `media.py` is unchanged. Preserve the successful 0.1.1 cloud video identity and test the changed failure/success transport paths without another unnecessary long render.

## ADR-012 — External S3 transfer, mounted filesystem execution

- **Status:** Executed and verified for the approved existing volume.
- **Decision:** Run jobs in the authenticated Requests UI; use an explicitly user-approved S3 key only in ignored local `.env` for external upload/readback/download. Worker accesses its persistent volume as filesystem storage.
- **Reason:** The existing Runpod API key is masked. Console job submission avoids needing it, while the regional S3 API makes file transfer and independent hash verification possible.
- **Scope:** Runpod's key form granted all-S3-volume read/write and this was disclosed before approval. Transfer helper is restricted to the approved volume/project, never lists/deletes sibling model files, and prints no secret values. All existing model data was retained.
- **Tradeoff:** Credential scope is broader than the helper's operational namespace. Keep values local/private and manage their lifecycle through the account; do not confuse this with generic S3 worker locking/presigned-download support.

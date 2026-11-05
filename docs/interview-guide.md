# Interview guide

Use the evidence index before answering. Say "implemented", "verified locally", "verified on Runpod", or "planned" precisely. Do not present a configured file as proof of a live service or a mocked test as proof of GPU execution.

## Two-minute project explanation

"OpenMontage provides an agent-driven video-production toolkit. I worked on a separate deployment wrapper to execute approved, structured production jobs on Runpod Serverless. The first milestone uses supplied assets and OpenMontage's existing Remotion composition, so we can verify rendering, approvals, storage and retries before introducing GPU-generation variability. The client reviews versioned plans and assets between queue jobs. Workers keep scratch files locally and write production artifacts to durable storage. We pin upstream and container inputs, test the request contract, and retain render/probe evidence. Cloud deployment and performance claims depend on the evidence available for the specific release."

Replace "worked on" with your actual contribution, and add concrete verified results only after reading the current evidence record.

## Architecture and implementation questions

### Why was a Dockerfile not enough?

A Dockerfile builds an environment. OpenMontage still normally needs an agent to choose production steps. We need a structured request contract, a handler, a bounded runner, durable artifacts and error behavior. The wrapper adds that execution boundary; it does not magically automate every creative stage.

### What is the request lifecycle?

Prepare and validate a storyboard, review its exact version, stage assets through a queue job, review that asset version, compose through another job, and retrieve MP4/captions/manifest from storage. Confirm the implemented operation fields against the code and walkthrough.

### Why separate the wrapper from upstream?

It makes our integration ownership clear and keeps the upstream source unchanged. Pinning a submodule commit gives reproducibility. Updating upstream becomes a deliberate compatibility change with tests. A fork remains an option if we need substantial core changes.

### Why Remotion first?

Upstream already has JSON props fixtures and an `Explainer` composition. Using that existing path narrows the initial work to execution and deployment. Fixed templates trade creative variety for predictable integration. HyperFrames and bespoke authoring are separate future capabilities, not silent fallback paths.

### Why use a queue endpoint?

Rendering takes longer than a normal interactive request and should survive the caller disconnecting. An asynchronous request returns a job reference; the client polls status. Human approval happens outside the worker. The queue response is temporary, so permanent outputs live elsewhere.

### Where is the GPU used?

The initial supplied-asset image performs CPU/browser rendering and does not claim GPU model execution. Local AI image or video generation is a later GPU workload that needs its own dependencies, model pin, memory measurements and tests. Hosting this CPU baseline on a GPU would not prove GPU benefit.

### Why is external storage necessary?

Worker-container disk can disappear when a worker stops. Our actual Runpod deployment uses `LocalStore` against the persistent mounted network volume at `/runpod-volume/openmontage`, with a startup mount guard. Runpod's regional S3 API transfers files externally; it is not the worker's storage backend. We observed different workers consuming persisted plans/assets and downloaded all five outputs with verified hashes. The optional generic S3 adapter is a separate unverified provider profile.

### How do approvals work?

Approval identifies the content/version reviewed. If the storyboard or asset set changes, an old approval should fail validation. This prevents a retry or later stage from processing unreviewed changes. An approval hash is a workflow binding, not by itself an identity/authentication system.

### How do you handle retries?

Use a stable idempotency key and durable artifacts. A repeated logical request should reuse verified completed output rather than conflict with it. Reject key reuse for different content. Verify the specific behavior in unit/reliability tests and a real render retry; do not promise exactly-once execution across every failure.

### How do locks behave after a crash?

Project locks fail closed. A crash can leave a stale lock requiring operator verification that the old writer stopped before removal. That sacrifices automatic availability for write safety. A production lease protocol would need ownership, expiry/fencing and race tests.

### What prevents unsafe inputs?

The intended contract accepts structured data and controlled asset references, not arbitrary shell or React code. Storage keys and input paths must be constrained, resources bounded and commands passed as subprocess arguments. Describe only protections covered by the actual schema/code/tests. Runtime credentials and tenant authentication are additional boundaries.

## Deployment and operations questions

### How is the build reproducible?

Record the wrapper commit, upstream submodule commit, base image digests and dependency locks. Install runtime dependencies in the image. Publish an immutable image digest and retain package inventories. System package repositories can still change; an image digest identifies the actual built artifact more strongly than a tag.

### Why Linux containers from a Windows workstation?

Runpod executes the Linux image. The initial workstation had Node 19 and no FFmpeg on PATH, while the image supplies its own Node/browser/FFmpeg stack. This avoids treating workstation installation as the production runtime contract.

### What does CI prove?

It builds the Linux image, runs application tests and performs a supplied-asset render with retained evidence. CI does not establish cloud credentials, endpoint availability, S3-provider compatibility, visual/audio quality at every input, or GPU performance.

### How do you deploy and roll back?

Publish the tested image under an immutable digest, prepare and review endpoint/storage settings, deploy to staging, run one async smoke production and inspect its durable output. Restore the previous verified image/configuration for rollback and smoke test again. Mark rollback "planned" until demonstrated.

For this account, the already authorized GitHub connection can build the selected implementation branch directly from its Dockerfile, so an initial GHCR push is optional. Docker fetches upstream from a fixed checksum-verified archive and does not rely on the cloud builder initializing submodules. Record the resulting Runpod build/image identity as well as the source commit.

### How do you choose timeouts and concurrency?

Start conservatively with one job per worker and one worker. Measure cold start, stage duration and peak memory; choose explicit ceilings with queue headroom. Increasing Remotion concurrency can improve speed but also increase memory use. Initial limits are proposals, not measured SLOs.

### What would you monitor?

Queue delay, worker initialization, stage runtime, validation failures, render failures, stale locks, storage errors, completion rate, resource peaks and cost per completed production. Use project/job/version identifiers to correlate events without logging secrets or private media.

### What went wrong during setup?

The assistant's sandbox could not resolve GitHub for the first clone and could not access Docker's named pipe. Approved execution succeeded. These were environment-access restrictions, not OpenMontage defects. Retain the actual logs and explain the diagnosis rather than claiming the application required weakened security.

### What did visual testing find that unit tests missed?

The real 30-second fixture produced a valid MP4, but a screenshot showed a long phrase caption clipped. Our initial adapter supplied a whole phrase as one "word" to upstream's nowrap word-caption layout. Media probing verified encoding, not readable typography. The correct response was to stop release acceptance, fix caption rendering and repeat visual tests, not to treat passing ffprobe as success. Cite the final corrected evidence when available.

The correction in wrapper 0.1.1 keeps Remotion for composition and uses an FFmpeg/libass pass for wrapped literal SRT phrases, preserving supplied timings. It maps subtitle scenes to a supported upstream type. The packaged four-second test passed, and a separate 30-second supplied-speech test was inspected at 5/15/25 seconds: captions fit and subtitles show. The latter used mounted frozen source, so it is not the same artifact proof as the packaged-image smoke. A remaining upstream title animation can wrap within a word. We call this a working technical prototype, not universally polished video output.

### Did the independent SRE review catch a defect?

Yes. Repeated references to the same source key could initially specify conflicting hashes and slip through staging. The schema now rejects contradictory digests, with a regression test. This demonstrates why a second role verifies the contract rather than merely rerunning implementation-shaped tests.

### What did live negative testing reveal after the video succeeded?

0.1.1 produced a real cloud video, but an invalid-operation job returned outer `COMPLETED` and only `output.status: failed`; Runpod lost the dictionary error. Our previous SDK test stopped at intermediate extraction, so it missed the serialized platform payload. SRE added a full pinned-SDK wire-path test, and 0.1.2 serializes only sanitized `{code,message}` as a JSON string in the provider error channel. Local CLI errors remain dictionaries. After 31 unit and 23 reliability checks passed, actual 0.1.2 invalid input returned provider `FAILED` with the safe diagnostic, and a fresh normal prepare completed uncached with the expected plan hash. That is direct evidence that the corrected boundary works for both tested paths.

This is why successful media, local exception handling and correct provider status are separate checks. It also explains why a focused transport correction need not repeat an expensive unchanged 30-second render; preserve the 0.1.1 video provenance and test the changed boundary directly.

### Can old output be reused after a new deployment?

Yes, intentionally: receipt lookup is request-based. A matching request key with intact artifacts can reuse output from an earlier build. After changing renderer/upstream behavior, bump wrapper version and use new idempotency keys. The manifest records wrapper/upstream identity, but that alone does not invalidate an existing request receipt.

### How would you prove recovery?

Run a stage, preserve storage, replace the worker/process, resubmit the same approved request and verify output hashes and completion metadata. Test a crash leaving a lock and follow the documented operator procedure. A mock-only storage test does not establish real S3 or media recovery.

For the actual cloud record, first prepare used worker `ap64a5w4royb1u`; later asset approval/composition used `0lwirxhe7d9ph2` and consumed persisted artifacts. The same-request prepare replay returned cached output in 173 ms on the original worker. Explain those as two different observations: cross-job/worker persistence and same-worker cache reuse. Neither claims a hard-killed writer recovery test.

### What did the real cloud run prove?

It built from source, started the configured CPU worker with the mounted volume, completed prepare/approval/staging/approval/composition, and produced five durable artifacts. Independent download hashes matched all five. The 0.1.1 MP4 is 1,829,646 bytes, 30.059 seconds, H.264 1280×720 at 30 fps with AAC. Actual cloud frames at 5/15/25 seconds showed contained captions and subtitles; the cosmetic title-word wrap remains. The provider reported 138,890 ms execution and 4,285 ms delay, where delay includes queue/scheduling/startup rather than isolated cold start. That is one fixture result, not an SLO, throughput benchmark or cost-saving claim.

### How did you transfer files without a Runpod API key?

We submitted jobs through the authenticated Requests UI. The existing Runpod API key remained masked and unused. The user separately approved an S3 key for file transfer at action time; values stayed in ignored `.env`, passed explicitly with Docker `--env-file`. Runpod's key form granted all-volume S3 read/write, but our helper was restricted to the approved volume/project namespace and did not list/delete existing LLM files. The worker used filesystem access on the mounted volume, not the transfer key.

### Why do the local and cloud MP4 hashes differ?

The cloud image is built independently, and encoding/environment differences can change bytes even with the same source media. We verify each output against its own worker manifest and record wrapper/upstream/build identity, media properties and inspected frames. We do not claim byte-identical rebuilds or require the cloud MP4 to match the separate local output's SHA-256. The 0.1.2 handler fix leaves media code unchanged and retains the 0.1.1 cloud video's original provenance.

### What is the cost model?

Worker execution/startup/idle, storage and transfer, plus model/provider charges if enabled. Divide measured total costs by completed videos and report failures/retries. Lower hardware price can be offset by longer execution. No benchmark means no savings claim.

### What are the largest remaining risks?

Real provider S3 conditional-write compatibility, interrupted-job behavior, untrusted media, multi-tenant authentication and isolation, concurrent writers, browser resource exhaustion, model/voice licensing and hardware compatibility, and quality measurement. Prioritize those that apply to the actual release scope.

## Evidence-backed practice

Before an interview, rehearse one real request and point to its input, approval versions, logs, MP4/probe, source commit and image digest. Explain one actual failure and its fix. Finish with a limitation you can demonstrate and the next test you would run. This is stronger than memorizing claims unsupported by this release.

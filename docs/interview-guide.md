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

Worker-local disk can disappear when a worker stops. We persist plan/version metadata, staged media and final outputs independently. Local filesystem storage is a development adapter; S3-compatible storage provides the cloud durability boundary.

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

### How do you choose timeouts and concurrency?

Start conservatively with one job per worker and one worker. Measure cold start, stage duration and peak memory; choose explicit ceilings with queue headroom. Increasing Remotion concurrency can improve speed but also increase memory use. Initial limits are proposals, not measured SLOs.

### What would you monitor?

Queue delay, worker initialization, stage runtime, validation failures, render failures, stale locks, storage errors, completion rate, resource peaks and cost per completed production. Use project/job/version identifiers to correlate events without logging secrets or private media.

### What went wrong during setup?

The assistant's sandbox could not resolve GitHub for the first clone and could not access Docker's named pipe. Approved execution succeeded. These were environment-access restrictions, not OpenMontage defects. Retain the actual logs and explain the diagnosis rather than claiming the application required weakened security.

### What did visual testing find that unit tests missed?

The real 30-second fixture produced a valid MP4, but a screenshot showed a long phrase caption clipped. Our initial adapter supplied a whole phrase as one "word" to upstream's nowrap word-caption layout. Media probing verified encoding, not readable typography. The correct response was to stop release acceptance, fix caption rendering and repeat visual tests, not to treat passing ffprobe as success. Cite the final corrected evidence when available.

The implemented correction in wrapper 0.1.1 keeps Remotion for composition and uses an FFmpeg/libass pass for wrapped literal SRT phrases, preserving supplied timings. It also maps subtitle scenes to a supported upstream type. This introduces a second encode and needs its own timing and visual test; implementation alone is not proof of acceptance.

### Did the independent SRE review catch a defect?

Yes. Repeated references to the same source key could initially specify conflicting hashes and slip through staging. The schema now rejects contradictory digests, with a regression test. This demonstrates why a second role verifies the contract rather than merely rerunning implementation-shaped tests.

### Can old output be reused after a new deployment?

Yes, intentionally: receipt lookup is request-based. A matching request key with intact artifacts can reuse output from an earlier build. After changing renderer/upstream behavior, bump wrapper version and use new idempotency keys. The manifest records wrapper/upstream identity, but that alone does not invalidate an existing request receipt.

### How would you prove recovery?

Run a stage, preserve storage, replace the worker/process, resubmit the same approved request and verify output hashes and completion metadata. Test a crash leaving a lock and follow the documented operator procedure. A mock-only storage test does not establish real S3 or media recovery.

### What is the cost model?

Worker execution/startup/idle, storage and transfer, plus model/provider charges if enabled. Divide measured total costs by completed videos and report failures/retries. Lower hardware price can be offset by longer execution. No benchmark means no savings claim.

### What are the largest remaining risks?

Real provider S3 conditional-write compatibility, interrupted-job behavior, untrusted media, multi-tenant authentication and isolation, concurrent writers, browser resource exhaustion, model/voice licensing and hardware compatibility, and quality measurement. Prioritize those that apply to the actual release scope.

## Evidence-backed practice

Before an interview, rehearse one real request and point to its input, approval versions, logs, MP4/probe, source commit and image digest. Explain one actual failure and its fix. Finish with a limitation you can demonstrate and the next test you would run. This is stronger than memorizing claims unsupported by this release.

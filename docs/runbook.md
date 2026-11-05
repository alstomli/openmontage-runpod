# Operations runbook

Use this with the exact wrapper commit, upstream pin, image digest, and deployment plan that produced the incident. A local test does not establish cloud readiness.

## Release checks

1. Verify the upstream commit with `python scripts/verify_upstream.py`.
2. Pass application tests and the real container render; retain reports and output media.
3. Review input limits, storage backend, credentials, selected CPU/GPU resources, concurrency and timeouts.
4. Publish an immutable image and retain its digest. Record the previous working digest before changing an endpoint.
5. Run one small smoke production against the target endpoint, download its MP4 from persistent storage, and inspect video and audio.
6. Mark the version cloud verified only after those outputs and job metadata are retained.

CI currently builds and tests; it does not deploy to Runpod. `scripts/prepare_deployment.py` writes a review plan and makes no network calls.

## Signals to retain

| Signal | Diagnostic value |
|---|---|
| Project ID, operation, request/version hash | Correlate retries without logging input secrets |
| Wrapper commit, upstream commit, image digest | Reproduce the exact runtime |
| Queue delay, initialization time, stage runtime | Separate cold start from processing time |
| Render stderr and exit status | Explain browser, font, media or encoding failure |
| ffprobe output | Check streams, duration, dimensions and container validity |
| Asset/object hashes and completion manifest | Establish whether output is intact and reusable |
| Peak RAM/disk/VRAM where applicable | Choose resources and diagnose exhaustion |
| Provider charge and worker runtime | Calculate cost per completed video |

Do not log API keys, signed download URLs, authorization headers, full environment dumps, or private input media. Signed URLs expire and should be treated as temporary access tokens.

## Failure diagnosis

| Symptom | Check first | Response |
|---|---|---|
| Job rejected before media work | Operation, schema, scene count, duration, paths and approval version | Fix the request. Do not retry unchanged invalid input indefinitely. |
| Approval mismatch | Hash/version of approved plan or assets | Review the current version and explicitly approve it. Never copy an old approval onto changed content. |
| Invalid job shows outer `COMPLETED` with `output.status: failed` and no diagnostic | Deployed wrapper version and real SDK serialized payload | Observed in 0.1.1. Use the 0.1.2 sanitized JSON-string error adapter and verify actual provider failure with a fresh negative job; local dictionary/SDK-intermediate checks are insufficient. |
| `project_busy` | Existing execution lock and active job status | Determine whether another job is active. Follow stale-lock procedure only after proving it stopped. |
| Missing artifact | Storage backend, bucket/prefix, key, permissions | Restore/upload the correct object and retry the relevant stage. |
| Browser fails at startup | Linux browser path, dependencies, shared memory, image version | Reproduce with the exact image; retain stderr. |
| Render exits but output is unusable | MP4 presence, ffprobe, expected duration, audio stream | Treat as a failed render; do not publish an incomplete artifact as success. |
| Valid MP4 but long captions clipped | Representative frames at each long cue; caption adapter and wrapping | This happened in the 30-second fixture: phrase cues were sent to a nowrap word renderer. Binary probes alone missed it. Correct caption layout, rebuild and visually retest. |
| Worker replacement loses output | Whether local storage path was inside disposable container instead of an actual mount | Configure a verified durable volume or compatible generic S3 storage and repeat recovery verification. |
| Startup refuses missing network volume | `REQUIRE_NETWORK_VOLUME=1`, real mountinfo, local root and write access | Correct volume attachment/configuration; do not bypass the guard and accept ephemeral output. |
| Cloud job missing after completion | Runpod result-retention window; durable manifest | Read the saved storage artifact rather than treating the queue response as a database. |
| Signed download link expired | Whether object itself still exists | Generate a fresh authorized link. Do not rerender a valid existing MP4 solely to refresh a URL. |
| Slow job or out-of-memory | Stage timings, CPU/RAM/disk, scene count, Remotion concurrency | Reduce concurrent rendering and choose a measured resource tier; report tradeoff. |
| Sandbox cannot access Docker or resolve GitHub | Execution environment restrictions | Use the normal approved execution path. This does not justify disabling host security. |

## Crash and stale-lock procedure

The storage implementation uses fail-closed project locks. An interrupted process can leave a lock behind; there is no automatic lock-expiration claim.

1. Identify the project, job ID, and image version.
2. Confirm the old job/process is stopped and cannot resume. Cancel or isolate it if its state is uncertain.
3. Inspect durable artifacts and checkpoint state. Preserve diagnostic metadata before repair.
4. Have an authorized operator remove only that project's stale lock, using the storage backend's normal interface.
5. Retry the same logical request with the same idempotency key. Verify that reusable artifacts are intact and the final manifest matches the approved versions.
6. Record the incident, action, and result. If the old process might still be alive, do not remove the lock.

Automated stale-lock recovery requires a stronger lease/ownership protocol and testing; simply adding a time-based expiry could permit two writers.

## Version changes and cached results

Request receipts are keyed by operation/project/idempotency key and normalized input, not image build. The same intact receipt can intentionally return old stable output even after code changes. When changing renderer or upstream behavior, bump the wrapper version and use fresh request idempotency keys; then record the new render manifest and image identity. Do not cite an old cached render as evidence for a new image.

The current application is a trusted single-account worker. Version approval is not multi-tenant authorization. Do not expose its operator workflow as an untrusted public multi-user service without an authenticated isolation layer and its tests.

## Provider error gate after 0.1.2 redeployment

1. Confirm the deployed build is fix commit `5a69307` (or its verified successor), not the earlier successful-media 0.1.1 build.
2. Submit a new invalid-operation request with a fresh key, retain the full provider response, and require provider-level failure plus the preserved sanitized error.
3. Decode the error JSON string and check only safe `code`/`message`; no raw traceback, credentials or internal media diagnostics should appear.
4. Submit a normal prepare request and verify the success path remains usable.
5. Record both job IDs/build identity before marking the transport fix live verified. A reused successful video or cached receipt does not test this boundary.

The successful 0.1.1 media output remains valid evidence for unchanged `media.py`. Avoid an unnecessary expensive rerender for an isolated handler-serialization change; rerun the changed boundary and tests appropriate to it.

## Rollback

Restore the endpoint/template to the previous verified immutable image digest and its compatible configuration. Retain the failed version's logs and plan. Run a small smoke job, then verify persistent output and approvals still work.

Rollback changes executable code, not stored artifact format. If a change modifies the schema or object layout, establish backward compatibility or a migration strategy before release. Do not claim rollback tested until a before/after execution record exists.

## Capacity and cost

Start with active workers 0, maximum workers 1, one application job per worker, and Remotion concurrency 1. The deployment policy proposes a 20-minute execution limit and one-hour request TTL; these are initial ceilings, not measured service-level promises.

Measure cost per completed video using worker runtime charges, storage/transfer, and any generation-provider charges. Report failures and retries separately. No cost-saving or throughput claim is established by choosing a cheaper resource alone.

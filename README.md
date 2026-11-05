# OpenMontage on Runpod Serverless

A deployment wrapper for turning an approved storyboard and supplied media into a narrated, captioned explainer video using OpenMontage's Remotion composer.

Public repository: [alstomli/openmontage-runpod](https://github.com/alstomli/openmontage-runpod), [draft PR #1](https://github.com/alstomli/openmontage-runpod/pull/1). The successful cloud media run used 0.1.1 at `95f5ecd`; transport correction 0.1.2 at `5a69307` is deployed and its live negative/normal-prepare checks passed.

Runpod endpoint [openmontage-staging](https://console.runpod.io/serverless/user/endpoint/aocbogtvk098ds) built and ran the complete supplied-media workflow. A 30-second cloud MP4 and all four companion artifacts were downloaded with matching hashes. It uses a persistent mounted network volume through the filesystem adapter; Runpod S3 is used externally for authenticated file transfer.

The cloud prototype's captions/subtitles were visually inspected at three points; upstream title animation can still wrap within a word. Live negative testing found and corrected a 0.1.1 error-transport defect. The 0.1.2 fix passed 31 unit + 23 reliability checks, then live invalid input returned provider `FAILED` with its sanitized diagnostic and a fresh normal prepare returned `COMPLETED`. See [live validation](docs/live-validation.md) and [evidence](evidence/index.md). GPU generation, speech synthesis, script planning, multi-tenant operation and the full autonomous OpenMontage workflow are outside this baseline.

## Quick local verification

For a fresh checkout, choose a parent directory and clone the implementation branch explicitly. Default `main` still contains the foundation; the draft PR is intentionally unmerged for review.

```powershell
git clone --branch feat/runpod-worker --recurse-submodules https://github.com/alstomli/openmontage-runpod.git
Set-Location openmontage-runpod
```

For an existing checkout, use its implementation branch instead. From the repository root with Python for the pin-check script and Docker's Linux engine available:

```powershell
git submodule update --init --recursive
python scripts/verify_upstream.py
docker build --platform linux/amd64 -t openmontage-worker:local .
docker run --rm --entrypoint python openmontage-worker:local -m unittest discover -s tests/unit -v
docker run --rm --entrypoint python openmontage-worker:local -m unittest discover -s tests/reliability -v
$output = (New-Item -ItemType Directory -Force evidence/local-smoke).FullName
docker run --rm --network none --shm-size=1g --mount "type=bind,source=$output,target=/evidence" --entrypoint python openmontage-worker:local scripts/client.py smoke --output /evidence
```

The smoke fixture uses a four-second tone, supplied image and phrase captions. It proves execution and media output, not narration quality or AI generation. See [the walkthrough](docs/deployment-walkthrough.md) for supplied narration, approvals, cloud preparation and verification boundaries.

The Dockerfile downloads upstream from a fixed commit archive with a SHA-256 checksum, so Runpod's GitHub builder does not need to initialize submodules. The local submodule is retained for source inspection and CI pin checks.

## Start here

| You want to understand… | Read |
|---|---|
| What we are building and how a request moves through it | [Architecture](docs/architecture.md) |
| Exact request fields, limits and client commands | [Request contract](docs/request-contract.md) |
| The ordered setup and deployment process | [Deployment walkthrough](docs/deployment-walkthrough.md) |
| What actually ran on Runpod, how files were transferred, and how corrections were verified | [Live validation record](docs/live-validation.md) |
| Why we chose this design | [Decision log](docs/decisions.md) |
| How to investigate failures and recover safely | [Operations runbook](docs/runbook.md) |
| How to explain and defend this project in an interview | [Interview guide](docs/interview-guide.md) |
| What has actually been verified | [Evidence index](evidence/index.md) |
| Ownership, milestones, and outstanding work | [Project status](docs/project-status.md) |

## Upstream and scope

OpenMontage source is pinned under `vendor/OpenMontage` to commit `d21f5d4eaa08422b09c7091757a05affcbabb35b`. It is source code, not model weights. The wrapper owns the serverless entry point, request validation, durable artifact handling, and deployment configuration. Upstream provides the composition engine and production reference material.

OpenMontage is distributed under AGPL-3.0; its license and notices remain with the upstream source. Remotion, media assets, fonts, and optional model or voice dependencies have their own terms. Record those dependencies and review their terms before a release; this repository's documentation is not a licensing opinion.

The requested public GitHub visibility was approved on November 4, 2026. Creation, publication, cloud deployment, and measured performance are tracked separately in the evidence index.

# OpenMontage on Runpod Serverless

A deployment wrapper for turning an approved storyboard and supplied media into a narrated, captioned explainer video using OpenMontage's Remotion composer.

Public repository: [alstomli/openmontage-runpod](https://github.com/alstomli/openmontage-runpod). The foundation is published on `main`; implementation review/push and live deployment have separate evidence gates.

The first milestone is a repeatable supplied-asset render. A packaged image passed 24 unit and 22 reliability checks and a real four-second offline render. A subsequent 30-second narrated fixture exposed clipped phrase captions during visual review, despite valid media metadata. That rendering defect is being corrected and retested; the earlier image is not an accepted narrated release. This wrapper does not claim a deployed public service, real-provider S3 validation, GPU generation, speech synthesis, automatic script planning or the full autonomous OpenMontage workflow.

## Quick local verification

From the repository root with Docker's Linux engine available:

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

## Start here

| You want to understand… | Read |
|---|---|
| What we are building and how a request moves through it | [Architecture](docs/architecture.md) |
| Exact request fields, limits and client commands | [Request contract](docs/request-contract.md) |
| The ordered setup and deployment process | [Deployment walkthrough](docs/deployment-walkthrough.md) |
| Why we chose this design | [Decision log](docs/decisions.md) |
| How to investigate failures and recover safely | [Operations runbook](docs/runbook.md) |
| How to explain and defend this project in an interview | [Interview guide](docs/interview-guide.md) |
| What has actually been verified | [Evidence index](evidence/index.md) |
| Ownership, milestones, and outstanding work | [Project status](docs/project-status.md) |

## Upstream and scope

OpenMontage source is pinned under `vendor/OpenMontage` to commit `d21f5d4eaa08422b09c7091757a05affcbabb35b`. It is source code, not model weights. The wrapper owns the serverless entry point, request validation, durable artifact handling, and deployment configuration. Upstream provides the composition engine and production reference material.

OpenMontage is distributed under AGPL-3.0; its license and notices remain with the upstream source. Remotion, media assets, fonts, and optional model or voice dependencies have their own terms. Record those dependencies and review their terms before a release; this repository's documentation is not a licensing opinion.

The requested public GitHub visibility was approved on November 4, 2026. Creation, publication, cloud deployment, and measured performance are tracked separately in the evidence index.

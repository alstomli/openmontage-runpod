"""Runpod entrypoint. Credentials are supplied through endpoint environment."""

import logging

from openmontage_worker.runner import execute


def handler(job):
    # Runpod includes other metadata fields; only pass the documented envelope.
    return execute({"input": job.get("input")})


if __name__ == "__main__":
    import runpod
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    runpod.serverless.start({"handler": handler})

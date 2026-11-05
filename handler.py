"""Runpod entrypoint. Credentials are supplied through endpoint environment."""

import json
import logging

from openmontage_worker.runner import execute


def handler(job):
    # Runpod includes other metadata fields; only pass the documented envelope.
    result = execute({"input": job.get("input")})
    if result.get("status") == "failed":
        # Runpod's platform error channel requires a string. Returning the
        # application's error dict reaches rp_job but is dropped by the live
        # transport, incorrectly completing the job. Serialize only execute's
        # sanitized error; retain the structured contract for local callers.
        result = {**result, "error": json.dumps(result["error"], sort_keys=True)}
    return result


if __name__ == "__main__":
    import runpod
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    runpod.serverless.start({"handler": handler})

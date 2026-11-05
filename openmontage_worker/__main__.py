import argparse
import json
import logging
from pathlib import Path

from .runner import execute


def main():
    parser = argparse.ArgumentParser(description="Execute one OpenMontage Runpod-format job locally.")
    parser.add_argument("request", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = execute(json.loads(args.request.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

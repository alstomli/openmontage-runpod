"""Check required persistent storage before starting the Runpod handler."""
import argparse
import os
from pathlib import Path
import runpy


def check_storage():
    if os.getenv('REQUIRE_NETWORK_VOLUME') != '1':
        return
    mount = Path('/runpod-volume')
    root = Path(os.getenv('LOCAL_STORAGE_ROOT', '')).resolve()
    # Linux bind mounts can share st_dev with their parent; mountinfo is the
    # authoritative check in containers, with is_mount as a portable fallback.
    mountinfo = Path('/proc/self/mountinfo')
    listed = mountinfo.is_file() and any(line.split()[4] == str(mount) for line in mountinfo.read_text().splitlines())
    if not (listed or mount.is_mount()):
        raise SystemExit('Required Runpod network volume is not mounted; refusing ephemeral storage.')
    if os.getenv('STORAGE_BACKEND') != 'local' or root != mount / 'openmontage':
        raise SystemExit('Mounted-volume profile requires local storage at /runpod-volume/openmontage.')
    root.mkdir(parents=True, exist_ok=True)
    if not os.access(root, os.W_OK):
        raise SystemExit('OpenMontage persistent storage directory is not writable.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    check_storage()
    if not args.check_only:
        runpy.run_path('/app/handler.py', run_name='__main__')

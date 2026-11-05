"""Fail a build if vendored source is not the declared upstream commit."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
expected = json.loads((root / 'UPSTREAM.json').read_text(encoding='utf-8'))['commit']
actual = subprocess.check_output(['git', '-C', str(root / 'vendor/OpenMontage'), 'rev-parse', 'HEAD'], text=True).strip()
if actual != expected:
    raise SystemExit(f'Upstream mismatch: {actual} != {expected}')
dirty = subprocess.check_output(['git', '-C', str(root / 'vendor/OpenMontage'), 'status', '--porcelain'], text=True).strip()
if dirty:
    raise SystemExit('Vendored upstream contains uncommitted changes')
print(json.dumps({'upstream_commit': actual, 'verified': True}))

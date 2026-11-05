"""Integration fixture: supplied offline Windows speech, not a worker TTS backend.

Run inside the built container with the evidence directory mounted at /evidence.
The fixed approvals below apply only to this technical test fixture.
"""
from pathlib import Path
import argparse
import json
import logging
import sys
import time

sys.path.insert(0, '/app')
from scripts.client import png, stage_file
from openmontage_worker.runner import Runner, execute
from openmontage_worker.storage import LocalStore

logging.basicConfig(level=logging.INFO, format='%(message)s')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', default='/evidence/narrated-smoke')
parser.add_argument('--token-prefix', default='narrated-v1')
options = parser.parse_args()
root = Path(options.output)
root.mkdir(parents=True, exist_ok=True)
image = root / 'supplied-background.png'
image.write_bytes(png())
store = LocalStore(root / 'storage')
runner = Runner(store=store, work_root=root / 'scratch')
project = 'narrated-validation'
image_ref = stage_file(store, project, image)
audio_ref = stage_file(store, project, Path('/evidence/fixtures/deployment-narration.wav'))
board = {
    'title': 'How this deployment works',
    'scenes': [
        {'text': 'Approved storyboard to finished video', 'subtitle': 'Pinned upstream code. Reproducible Linux environment.', 'duration': 10, 'image': image_ref},
        {'text': 'Validate, approve, persist', 'subtitle': 'Version-bound review and durable production artifacts.', 'duration': 10, 'image': image_ref},
        {'text': 'Prove rendering before adding generation', 'subtitle': 'Supplied speech fixture; GPU generation remains a later milestone.', 'duration': 10, 'image': image_ref},
    ],
    'narration': audio_ref,
    'captions': [
        {'text': 'Approved storyboard, pinned OpenMontage, Linux container.', 'start': 0, 'end': 10},
        {'text': 'Validate inputs, check approvals, save persistent results.', 'start': 10, 'end': 20},
        {'text': 'Review between jobs. Verify rendering before GPU generation.', 'start': 20, 'end': 30},
    ],
}
records = []
def call(op, **fields):
    request = {'input': {'operation': op, 'project_id': project, 'idempotency_key': f'{options.token_prefix}-{len(records)}', **fields}}
    started = time.monotonic()
    response = execute(request, runner)
    records.append({'request': request, 'response': response, 'elapsed_seconds': round(time.monotonic()-started, 3)})
    (root / 'results.json').write_text(json.dumps({'fixture': '30 seconds, offline Windows Zira supplied speech; phrase captions manually timed, not aligned words', 'steps': records}, indent=2), encoding='utf-8')
    print(json.dumps(records[-1]), flush=True)
    if response['status'] == 'failed':
        raise SystemExit(1)
    return response

plan = call('prepare', storyboard=board)
call('approve', stage='plan', artifact_hash=plan['artifact_hash'], approved=True)
assets = call('generate_assets', artifact_hash=plan['artifact_hash'])
call('approve', stage='assets', artifact_hash=assets['artifact_hash'], approved=True)
call('compose', artifact_hash=assets['artifact_hash'])

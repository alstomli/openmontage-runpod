"""Transfer this project's fixture using the approved local .env credentials.

Run with docker --env-file .env and evidence mounted at /evidence. This script
never lists or deletes sibling model files and never prints credential values.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import boto3
from botocore.config import Config

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('operation', choices=('upload', 'verify-plan', 'download'))
options = parser.parse_args()
root = Path('/evidence')
cloud = root/'cloud'
cloud.mkdir(exist_ok=True)
bucket = os.environ['S3_BUCKET']
assert bucket == 'l34ba8wnno', 'This fixture is restricted to the approved volume'
prefix = 'openmontage/'
client = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT_URL'], region_name=os.environ['AWS_DEFAULT_REGION'], config=Config(signature_version='s3v4', s3={'addressing_style':'path'}, retries={'max_attempts':3}))
client.head_bucket(Bucket=bucket)
if options.operation == 'upload':
    record = json.loads((root/'narrated-fixed/results.json').read_text())['steps'][0]['request']
    record['input']['idempotency_key'] = 'cloud-prepare-v1'
    board = record['input']['storyboard']
    refs = {ref['key']:ref for ref in [board['narration'], *(s['image'] for s in board['scenes'] if 'image' in s)]}
    evidence = []
    for key, ref in refs.items():
        assert key.startswith('inputs/narrated-validation/')
        data = (root/'narrated-fixed/storage'/key).read_bytes()
        assert hashlib.sha256(data).hexdigest() == ref['sha256']
        remote = prefix + key
        client.put_object(Bucket=bucket, Key=remote, Body=data)
        stream = client.get_object(Bucket=bucket, Key=remote)['Body']
        try:
            assert hashlib.sha256(stream.read()).hexdigest() == ref['sha256']
        finally:
            stream.close()
        evidence.append({'key':remote,'bytes':len(data),'sha256':ref['sha256'],'read_back_verified':True})
    (cloud/'prepare.json').write_text(json.dumps(record,indent=2)+'\n')
    (cloud/'inputs-transfer.json').write_text(json.dumps({'bucket':bucket,'prefix':prefix,'objects':evidence,'existing_files_deleted':False},indent=2)+'\n')
    print(json.dumps({'uploaded_objects':len(evidence),'read_back_verified':True,'existing_files_deleted':False,'request_file':str(cloud/'prepare.json')}))
elif options.operation == 'verify-plan':
    response = json.loads((cloud/'prepare-response.json').read_text())
    artifact = response['output']['artifacts'][0]
    key = artifact['key']
    assert key.startswith('projects/narrated-validation/plans/')
    stream = client.get_object(Bucket=bucket, Key=prefix+key)['Body']
    try:
        data = stream.read(1024*1024)
    finally:
        stream.close()
    checksum = hashlib.sha256(data).hexdigest()
    assert checksum == artifact['sha256']
    record = {'bucket':bucket,'key':prefix+key,'sha256':checksum,'bytes':len(data),'worker_written_plan_read_back_verified':True}
    (cloud/'plan-storage-verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
else:
    response = json.loads((cloud/'compose-response.json').read_text())
    output = response.get('output', response)
    assert output['status'] == 'completed', 'Cloud composition is not complete'
    report = []
    for artifact in output['artifacts']:
        key = artifact['key']
        assert key.startswith('projects/narrated-validation/renders/')
        name = Path(key).name
        assert name in ('final.mp4','captions.srt','thumbnail.png','props.json','manifest.json')
        stream = client.get_object(Bucket=bucket,Key=prefix+key)['Body']
        try:
            data = stream.read(100*1024*1024+1)
        finally:
            stream.close()
        assert len(data) <= 100*1024*1024
        assert hashlib.sha256(data).hexdigest() == artifact['sha256']
        (cloud/name).write_bytes(data)
        report.append({'file':name,'bytes':len(data),'sha256':artifact['sha256'],'verified':True})
    (cloud/'download-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

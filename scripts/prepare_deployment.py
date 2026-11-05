"""Produce a reviewable Runpod REST v1 plan. This script never makes network calls."""
import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Published image reference ending @sha256:<digest>')
    storage = parser.add_mutually_exclusive_group(required=True)
    storage.add_argument('--bucket', help='Generic S3 bucket supporting conditional PUT and presigned downloads')
    storage.add_argument('--network-volume-id', help='Existing Runpod network volume; preserve existing files')
    parser.add_argument('--data-center', help='Required with network volume, e.g. EU-RO-1')
    parser.add_argument('--s3-endpoint', default='')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--name', default='openmontage-staging')
    parser.add_argument('--template-id', help='Existing template ID; omit to prepare template creation first')
    parser.add_argument('--compute', choices=('CPU', 'GPU'), default='CPU')
    parser.add_argument('--cpu-flavor', help='Available Runpod CPU flavor ID, confirmed in your account')
    parser.add_argument('--gpu-type', help='Available Runpod GPU type ID, only when explicitly choosing GPU compute')
    parser.add_argument('--output', default='deployment/plan.json')
    args = parser.parse_args()
    if not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', args.image):
        parser.error('--image must be an immutable registry digest reference')
    if args.compute == 'CPU' and (not args.cpu_flavor or args.gpu_type):
        parser.error('CPU compute requires --cpu-flavor and does not accept --gpu-type')
    if args.compute == 'GPU' and (not args.gpu_type or args.cpu_flavor):
        parser.error('GPU compute requires --gpu-type and does not accept --cpu-flavor')
    if args.network_volume_id and (not args.data_center or not re.fullmatch(r'[A-Za-z0-9-]+', args.network_volume_id)):
        parser.error('--network-volume-id requires a valid volume ID and --data-center')
    if args.bucket and 'runpod.io' in args.s3_endpoint.lower():
        parser.error('Runpod S3 API does not support this generic S3 download/locking contract; attach --network-volume-id instead')
    env = {
        'OPENMONTAGE_ROOT': '/opt/openmontage', 'WORK_ROOT': '/tmp/openmontage',
        'COMPOSER_BROWSER_EXECUTABLE': '/usr/bin/chromium',
        'REMOTION_CONCURRENCY': '1',
    }
    if args.network_volume_id:
        env.update(STORAGE_BACKEND='local', LOCAL_STORAGE_ROOT='/runpod-volume/openmontage', REQUIRE_NETWORK_VOLUME='1')
    else:
        env.update(STORAGE_BACKEND='s3', S3_BUCKET=args.bucket, S3_PREFIX='openmontage',
                   S3_ENDPOINT_URL=args.s3_endpoint, AWS_DEFAULT_REGION=args.region)
    plan = {
        'dry_run': True,
        'status': 'review_required_not_deployed',
        'api': 'https://rest.runpod.io/v1',
        'template': {'method': 'POST', 'path': '/templates', 'body': {
            'name': args.name, 'imageName': args.image, 'category': 'CPU' if args.compute == 'CPU' else 'NVIDIA',
            'isServerless': True, 'isPublic': False, 'containerDiskInGb': 20,
            'env': env,
        }},
        'endpoint': {'method': 'POST', 'path': '/endpoints', 'body': {
            'name': args.name, 'templateId': args.template_id or '<CREATED_TEMPLATE_ID>',
            'computeType': args.compute,
            'workersMin': 0, 'workersMax': 1, 'idleTimeout': 5,
            'executionTimeoutMs': 1200000, 'scalerType': 'QUEUE_DELAY', 'scalerValue': 4,
        }},
        'application_concurrency': 1,
        'storage_profile': 'mounted_network_volume' if args.network_volume_id else 'generic_s3',
        'required_secrets': ['RUNPOD_API_KEY'] + ([] if args.network_volume_id else ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']),
        'release_gates': ['unit tests', 'container supplied-asset render', 'SRE review',
                          'verify persistence and input/output transfer', 'confirm compute availability and pricing'],
        'rollback': 'Restore the previous verified image digest on the endpoint template; retain previous plan and smoke report.',
        'sources': ['https://docs.runpod.io/api-reference/templates/POST/templates',
                    'https://docs.runpod.io/api-reference/endpoints/POST/endpoints',
                    'https://docs.runpod.io/storage/network-volumes',
                    'https://docs.runpod.io/storage/s3-api'],
    }
    endpoint = plan['endpoint']['body']
    if args.compute == 'CPU':
        endpoint.update(cpuFlavorIds=[args.cpu_flavor], vcpuCount=4)
    else:
        endpoint.update(gpuTypeIds=[args.gpu_type], gpuCount=1)
    if args.network_volume_id:
        endpoint.update(networkVolumeId=args.network_volume_id, dataCenterIds=[args.data_center])
        plan['release_gates'].append('confirm chosen compute can attach this volume in its datacenter')
        plan['storage_notes'] = [
            'Only /runpod-volume/openmontage is owned by this application; do not delete or alter sibling model files.',
            'Returned paths are worker filesystem paths, not public download URLs.',
            'Transfer inputs/outputs through an authenticated volume file tool or Runpod S3 API; presigned URLs unsupported.',
            'A mounted volume must be confirmed in the real worker before accepting production jobs.',
        ]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {path}; no API calls made. Review storage profile and release gates before deployment.')


if __name__ == '__main__':
    main()

"""Inspect downloaded live Runpod output; run with evidence mounted at /evidence."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('/evidence')
cloud = root/'cloud'
response = json.loads((cloud/'compose-response.json').read_text())
assert response['status'] == 'COMPLETED'
assert response['output']['status'] == 'completed'
video = cloud/'final.mp4'
artifact = next(a for a in response['output']['artifacts'] if a['kind']=='video')
assert hashlib.sha256(video.read_bytes()).hexdigest() == artifact['sha256']
metadata = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
streams = metadata['streams']
visual = next(s for s in streams if s['codec_type']=='video')
audio = next(s for s in streams if s['codec_type']=='audio')
assert (visual['width'],visual['height'],visual['r_frame_rate'],visual['codec_name'])==(1280,720,'30/1','h264')
assert audio['codec_name']=='aac'
assert abs(float(metadata['format']['duration'])-30)<0.2
for seconds in (5,15,25):
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-ss',str(seconds),'-frames:v','1',str(root/f'screenshots/cloud-render-{seconds:02}s.png')],check=True)
manifest = json.loads((cloud/'manifest.json').read_text())
assert manifest['wrapper_version']=='0.1.1'
assert manifest['upstream_commit']=='d21f5d4eaa08422b09c7091757a05affcbabb35b'
summary = {
    'endpoint_id':'aocbogtvk098ds','job_id':response['id'],'job_status':response['status'],
    'worker_id':response['workerId'],'delay_ms':response['delayTime'],'execution_ms':response['executionTime'],
    'bytes':video.stat().st_size,'sha256':artifact['sha256'],
    'duration_seconds':metadata['format']['duration'],'width':visual['width'],'height':visual['height'],
    'frame_rate':visual['r_frame_rate'],'video_codec':visual['codec_name'],'audio_codec':audio['codec_name'],
    'wrapper_version':manifest['wrapper_version'],'upstream_commit':manifest['upstream_commit'],
    'download_hashes_verified':True,'media_checks_passed':True,
    'visual_check':'Representative frames extracted for manual inspection; no general creative-quality claim',
    'persistence':'Worker local filesystem on mounted Runpod network volume; S3 used externally for upload/download',
}
(cloud/'media-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

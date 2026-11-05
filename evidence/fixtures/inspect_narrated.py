"""Retain real media metadata and representative frames after narrated validation."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('/evidence')
result = json.loads((root/'narrated-fixed/results.json').read_text())
final = result['steps'][-1]
assert final['response']['status'] == 'completed', 'Narrated render is not complete'
video = next(a for a in final['response']['artifacts'] if a['kind'] == 'video')
source = Path(video['local_path'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == video['sha256']
shutil.copyfile(source, root/'demo.mp4')
metadata = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
for seconds in (5,15,25):
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-ss',str(seconds),'-frames:v','1',str(root/f'screenshots/narrated-fixed-{seconds:02}s.png')],check=True)
summary = {
    'result': 'media_completed_visual_review_required',
    'sha256': video['sha256'], 'bytes': source.stat().st_size,
    'compose_seconds': final['elapsed_seconds'],
    'duration_seconds': metadata['format']['duration'],
    'streams': [{k: s.get(k) for k in ('codec_type','codec_name','width','height','r_frame_rate')} for s in metadata['streams']],
    'provenance': '0.1.1 application mounted into an existing full media image; independent final archive image separately passes packaged tests and offline render',
    'fixture': 'Offline Windows Zira supplied speech, manually timed phrase captions; not a worker TTS backend or forced alignment benchmark',
}
(root/'logs/009-narrated-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

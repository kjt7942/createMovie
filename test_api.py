"""전체 API 흐름 검증: 폴더 업로드 + mp3 -> AI 구성(실제 Gemini) -> 렌더 -> 오디오 포함 확인."""
import io, json, os, subprocess, sys, time
import server
SRC = os.path.join(server.HERE, '..', '_시험영상작업', 'img')
mp3 = os.path.join(server.HERE, 'jobs', 'tone.mp3'); os.makedirs(server.JOBS, exist_ok=True)
# 앞 20초 무음 + 뒤 20초 소리: 시작 위치 지정이 실제로 먹는지 확인용
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-f', 'lavfi', '-i', 'sine=frequency=440',
                '-filter_complex', '[0]atrim=0:20[a];[1]atrim=0:20[b];[a][b]concat=n=2:v=0:a=1', mp3], check=True)
c = server.app.test_client()
# 사업별 폴더 3개 + mp3 (2번째 사진은 일부러 폴더 없이도 섞는다)
layout = {'교육지원사업': ['09.jpg', '01.jpg'], '돌봄지원사업': ['02.jpg', '03.jpg'], '어린이 물놀이터': ['06.jpg']}
data = {'job': '', 'files': [], 'paths': []}
for folder, names in layout.items():
    for n in names:
        data['files'].append((open(os.path.join(SRC, n), 'rb'), n)); data['paths'].append(f'행사/{folder}/{n}')
data['files'].append((open(mp3, 'rb'), 'bgm.mp3')); data['paths'].append('행사/bgm.mp3'); data['files'].append((io.BytesIO(b'x'), 'memo.txt')); data['paths'].append('행사/memo.txt')
r = c.post('/api/upload', data={'job': '', 'files': data['files'], 'paths': data['paths']}, content_type='multipart/form-data').json
assert len(r['photos']) == 5 and r['audio'] == 'bgm.mp3' and r['skipped'] == ['행사/memo.txt'], r
assert {p['folder'] for p in r['photos']} == set(layout), r['photos']
job = r['job']
p = c.post('/api/plan', json={'job': job, 'brief': '가족센터 사업 소개 30초 영상. 폴더별 한 장면씩.', 'org': '문경시가족센터', 'length': 20, 'mood': '밝고 경쾌하게'}).json
assert 'plan' in p and p['usage']['totalTokenCount'] > 0, p
print('usage:', p['usage'])
pl = p['plan']; ids = {x['id'] for x in r['photos']}
assert 3 <= len(pl['scenes']) <= 5 and all(s['photo'] in ids for s in pl['scenes']) and pl['intro_photo'] in ids, pl
print('plan:', json.dumps(pl, ensure_ascii=False)[:600])
assert c.post('/api/render', json={'job': job, 'plan': pl, 'length': 20, 'audio': {'start': 20, 'dur': 20}}).json['ok']
while (s := c.get(f'/api/status/{job}').json)['state'] in ('queued', 'running', 'none'): time.sleep(2)
assert s['state'] == 'done', s
out = os.path.join(server.JOBS, job, 'output.mp4')
streams = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout.split()
assert 'audio' in streams and 'video' in streams, streams
vol = subprocess.run(['ffmpeg', '-i', out, '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
mean = float(vol.split('mean_volume:')[1].split('dB')[0]); print('mean_volume', mean)
assert mean > -35, '음악 시작 위치(20초)가 적용되지 않음(무음 구간이 쓰임)'
print('OK', out)

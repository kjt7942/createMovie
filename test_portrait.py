"""세로(9:16) 렌더 검증: 1080x1920 출력 + 오프닝/장면/엔딩 프레임을 portrait_tiles.jpg로 모아 눈으로 확인."""
import json, os, subprocess, sys, time
import server
job = sys.argv[1]
c = server.app.test_client()
plan = json.load(open(os.path.join(server.JOBS, job, 'plan.json'), encoding='utf-8'))
assert c.post('/api/render', json={'job': job, 'plan': plan, 'length': 20, 'ratio': 'portrait'}).json['ok']
html = open(os.path.join(server.JOBS, job, 'index.html'), encoding='utf-8').read()
assert 'data-width="1080" data-height="1920"' in html
while (s := c.get(f'/api/status/{job}').json)['state'] in ('queued', 'running', 'none'): time.sleep(2)
assert s['state'] == 'done', s
out = os.path.join(server.JOBS, job, 'output.mp4')
wh = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout.strip()
assert wh == '1080,1920', wh
ts = [2.5, 6.5, 10.5, 18.8]
subprocess.run(['ffmpeg', '-v', 'error', '-y'] + sum([['-ss', str(t), '-i', out] for t in ts], []) +
               ['-filter_complex', ''.join(f'[{i}:v]scale=360:-1[v{i}];' for i in range(4)) + '[v0][v1][v2][v3]hstack=inputs=4',
                '-frames:v', '1', os.path.join(server.JOBS, job, 'portrait_tiles.jpg')], check=True)
print('OK', wh)

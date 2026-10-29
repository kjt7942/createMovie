"""저장/불러오기 + 화면 전환 검증. 렌더 후 전환 구간 프레임을 tiles.jpg로 모아 눈으로 확인한다."""
import json, os, subprocess, time
import server
c = server.app.test_client()
SRC = os.path.join(server.HERE, '..', '_시험영상작업', 'img')
names = ['09.jpg', '02.jpg', '03.jpg', '04.jpg', '06.jpg']
r = c.post('/api/upload', data={'job': '', 'files': [(open(os.path.join(SRC, n), 'rb'), n) for n in names],
                                'paths': [f'테스트/사업{i}/{n}' for i, n in enumerate(names)]}, content_type='multipart/form-data').json
job = r['job']; ids = [p['id'] for p in r['photos']]
plan = {'year': '2026', 'title': '전환 테스트', 'tagline': '슬로건', 'org': '테스트센터', 'intro_photo': ids[0], 'outro_photo': ids[4],
        'transition': 'zoom', 'outro_tr': 'diagonal',
        'scenes': [{'ttl': '원형', 'sub': 'circle', 'photo': ids[1], 'tr': 'circle'},
                   {'ttl': '전체설정(줌)', 'sub': 'zoom', 'photo': ids[2], 'tr': ''},
                   {'ttl': '밀어내기', 'sub': 'slide', 'photo': ids[3], 'tr': 'slide'}],
        'outro': ['끝', '감사합니다', '마무리']}
# 저장 -> 목록 -> 불러오기
assert c.post('/api/save', json={'job': job, 'plan': plan, 'settings': {'brief': 'b', 'length': 20, 'aStart': 1.5}}).json['ok']
lst = c.get('/api/projects').json['projects']; me = [p for p in lst if p['job'] == job][0]
assert me['title'] == '전환 테스트' and me['scenes'] == 3 and not me['video'], me
pr = c.get(f'/api/project/{job}').json
assert pr['plan']['transition'] == 'zoom' and pr['settings']['aStart'] == 1.5 and len(pr['meta']['photos']) == 5
# 전환 목록이 장면별/전체/엔딩 지정대로 들어가는지
c.post('/api/render', json={'job': job, 'plan': plan, 'length': 20})
html = open(os.path.join(server.JOBS, job, 'index.html'), encoding='utf-8').read()
assert 'TR = ["circle", "zoom", "slide", "diagonal"]' in html, html[html.find('TR ='):][:80]
plan2 = dict(plan, transition='mix', outro_tr='', scenes=[dict(s, tr='') for s in plan['scenes']])
server.build(job, plan2, 20, None)
assert 'TR = ["panel", "wipe", "zoom", "circle"]' in open(os.path.join(server.JOBS, job, 'index.html'), encoding='utf-8').read()
server.build(job, plan, 20, None)  # 렌더는 첫 번째 구성으로
while (s := c.get(f'/api/status/{job}').json)['state'] in ('queued', 'running', 'none'): time.sleep(2)
assert s['state'] == 'done', s
assert c.get(f'/api/project/{job}').json['video']
# 전환 중간 프레임: 장면 시작 3.6 + step*i (+0.4초), step=(20-8)/3=4
out = os.path.join(server.JOBS, job, 'output.mp4'); tiles = os.path.join(server.JOBS, job, 'tiles.jpg')
ts = [3.6 + 0.4, 7.6 + 0.4, 11.6 + 0.35, 15.6 + 0.4]
subprocess.run(['ffmpeg', '-v', 'error', '-y'] + sum([['-ss', str(t), '-i', out] for t in ts], []) +
               ['-filter_complex', ''.join(f'[{i}:v]scale=640:-1[v{i}];' for i in range(4)) + '[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0',
                '-frames:v', '1', tiles], check=True)
print('OK', job, tiles)

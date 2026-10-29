"""내레이션 검증: AI가 narr 문장을 쓰는지 -> TTS 생성/길이 맞춤 -> 렌더 결과에 음성 구간이 들어가는지."""
import json, os, re, subprocess, sys, time
import server
job = sys.argv[1]
c = server.app.test_client()
narr = {'on': True, 'voice': 'injoon', 'rate': 0}
r = c.post('/api/plan', json={'job': job, 'brief': '가족센터 사업 소개 영상', 'org': '문경시가족센터', 'length': 30, 'narr': narr}).json
assert 'plan' in r, r
p = r['plan']
print('intro_narr:', p['intro_narr']); [print(f'  {i+1}:', s['ttl'], '/', s['narr']) for i, s in enumerate(p['scenes'])]; print('outro_narr:', p['outro_narr'])
assert p['intro_narr'] and all(s['narr'] for s in p['scenes']), '내레이션 문장이 비어 있음'
# 미리보기용 빌드: 음성 파일 + 오디오 태그
pv = c.post('/api/preview', json={'job': job, 'plan': p, 'length': 30, 'narr': narr, 'audio': {'start': 0, 'dur': 30}}).json
assert 'url' in pv, pv
html = open(os.path.join(server.JOBS, job, 'preview.html'), encoding='utf-8').read()
tags = re.findall(r'<audio id="nr\d+" src="assets/(tts_\w+\.mp3)" data-start="([\d.]+)" data-duration="([\d.]+)"', html)
assert len(tags) == len(p['scenes']) + 2, tags
assert 'data-volume="0.25"' in html, '내레이션이 있으면 배경음악을 낮춰야 함'
slots = server.narr_slots(30, len(p['scenes']))
for (f, s, d), (a, b) in zip(tags, slots):
    assert abs(float(s) - round(a, 2)) < 0.01 and float(d) <= b - a + 0.01, (f, s, d, a, b)
print('잘린 구간:', pv['cut'] or '없음')
# 렌더
assert c.post('/api/render', json={'job': job, 'plan': p, 'length': 30, 'narr': narr, 'audio': {'start': 0, 'dur': 30}}).json['ok']
while (s := c.get(f'/api/status/{job}').json)['state'] in ('queued', 'running', 'none'): time.sleep(2)
assert s['state'] == 'done', s
out = os.path.join(server.JOBS, job, 'output.mp4')
# 1번 장면 내레이션 구간이 배경음악(0.25)만 나오는 구간보다 확실히 커야 한다
def vol(a, d):
    e = subprocess.run(['ffmpeg', '-ss', str(a), '-t', str(d), '-i', out, '-af', 'volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    return float(e.split('mean_volume:')[1].split('dB')[0])
f, s0, d0 = tags[1]
speech = vol(float(s0) + 0.2, min(1.5, float(d0) - 0.3)); print('1번 장면 내레이션 구간', speech, 'dB')
assert speech > -28, '내레이션 음성이 들리지 않음'
print('OK')

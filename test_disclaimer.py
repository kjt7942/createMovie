"""엔딩 고정 안내문(공모전 AI 고지 문구) 검증: 켜면 엔딩 구간 내내 들어가고, 끄면 흔적이 없어야 한다."""
import re, tempfile
import composer

DISC = '본 영상은 생성형 AI를 활용하여 제작되었습니다.'
plan = {'year': '2026', 'title': '고지 테스트', 'tagline': '슬로건', 'org': '테스트센터', 'intro_photo': 'a', 'outro_photo': 'a',
        'scenes': [{'ttl': '장면', 'sub': '설명', 'photo': 'a'}], 'outro': ['끝', '감사합니다', '마무리']}
photos = {'a': {'id': 'a', 'w': 1920, 'h': 1080}}

with tempfile.TemporaryDirectory() as d:
    for ratio in ('landscape', 'portrait'):
        html = composer.compose(d, dict(plan, disclaimer=DISC), 20, ratio=ratio, photos=photos)
        m = re.search(r'<div class="disc clip" id="disc" data-start="([\d.]+)" data-duration="([\d.]+)"[^>]*><span>(.*?)</span>', html)
        assert m, 'disclaimer missing'
        start, dur, text = float(m[1]), float(m[2]), m[3]
        assert text == DISC and abs(start + dur - 20) < 0.01, (start, dur, text)
        assert '.disc span' in html
    off = composer.compose(d, dict(plan, disclaimer=''), 20, photos=photos)
    assert 'class="disc' not in off and '.disc span' not in off
    # 공백 정리·길이 제한·HTML 이스케이프
    long = composer.compose(d, dict(plan, disclaimer='  <b>AI</b>\n' + '가' * 100), 20, photos=photos)
    span = re.search(r'id="disc"[^>]*><span>(.*?)</span>', long)[1]
    assert span.startswith('&lt;b&gt;AI&lt;/b&gt; ') and len(composer.disclaimer_text(dict(disclaimer='  <b>AI</b>\n' + '가' * 100))) == composer.DISC_MAX
print('OK')

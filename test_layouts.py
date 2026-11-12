"""오프닝·엔딩 배치와 진행바 켜기/끄기 검증."""
import tempfile
import composer

plan = {'year': '2026', 'title': '배치 테스트', 'tagline': '슬로건', 'org': '테스트센터', 'intro_photo': 'a', 'outro_photo': 'a',
        'scenes': [{'ttl': '장면', 'sub': '설명', 'photo': 'a'}], 'outro': ['끝', '감사합니다', '마무리']}
photos = {'a': {'id': 'a', 'w': 1920, 'h': 1080}}

with tempfile.TemporaryDirectory() as d:
    for ratio in ('landscape', 'portrait'):
        for lay in composer.LAYOUTS:   # 지정한 배치가 오프닝·엔딩에 들어간다
            h = composer.compose(d, dict(plan, opening=lay, ending=lay), 20, ratio=ratio, photos=photos)
            assert f'id="intro" class="scene clip lay-{lay}"' in h and f'id="outro" class="scene clip lay-{lay}"' in h, (ratio, lay)
    # 자동: seed에 따라 달라지고, 오프닝과 엔딩은 서로 다른 배치
    seen = {composer.layout_of(dict(seed=s), 'opening') for s in range(len(composer.LAYOUTS))}
    assert seen == set(composer.LAYOUTS)
    assert all(composer.layout_of(dict(seed=s), 'opening') != composer.layout_of(dict(seed=s), 'ending') for s in range(len(composer.LAYOUTS)))
    assert composer.layout_of(dict(seed=3, opening='bogus'), 'opening') in composer.LAYOUTS   # 잘못된 값은 자동으로
    # 진행바: 기본은 꺼짐, progress=True일 때만 들어간다
    assert 'id="progress"' not in composer.compose(d, plan, 20, photos=photos)
    assert 'id="progress"' in composer.compose(d, dict(plan, progress=True), 20, photos=photos)
    # 콜라주 하단 막대: 장면마다. 기본은 켜짐, 그 장면에 cbar=False면 그 장면만 빠짐
    c = {'type': 'collage', 'ttl': '모음', 'photo': 'a', 'photos': ['a', 'a']}
    h = composer.compose(d, dict(plan, scenes=[c, dict(c, cbar=False), c]), 20, photos=photos)
    assert h.count('<div class="cbar"></div>') == 2
    # 전환 효과: 새로 넣은 종류도 장면에 그대로 들어간다
    for tr in ('slide-up', 'slide-down', 'curtain', 'diamond', 'blinds', 'zoom-out', 'flip'):
        h = composer.compose(d, dict(plan, transition=tr), 20, photos=photos)
        assert f'TR = ["{tr}", "{tr}"]' in h, tr
print('OK')

"""장면 길이 비중 검증: 균등일 때 예전 결과와 같고, 비중대로 나뉘며, 장면당 최소 2.4초를 지킨다."""
import beats, server
# 1) 균등(비중 없음 / 모두 1)은 예전 계산 (L-8)/n 과 같다
for L, n in ((30, 4), (45, 6), (15, 2), (120, 9)):
    old = [round(3.6 + (L - 8) / n * i, 2) for i in range(n)], round(3.6 + (L - 8), 2)
    assert beats.snap_times(L, n) == old == beats.snap_times(L, n, ws=[1] * n), (L, n)
# 2) 비중대로 나뉜다: 합은 L-8, 비율 유지
st = beats.scene_steps(60, [1, 2, 1])
assert abs(sum(st) - 52) < 1e-6 and abs(st[1] - 2 * st[0]) < 1e-6, st
# 3) 너무 작은 비중은 최소 2.4초로 올리고 나머지가 줄어든다
st = beats.scene_steps(30, [0.5, 8, 1, 1])
assert all(d >= 2.4 - 1e-9 for d in st) and abs(sum(st) - 22) < 1e-6, st
# 4) 시작 시각이 길이대로 이어진다 + 엔딩 시작 = 3.6 + (L-8)
s, os_ = beats.snap_times(30, 3, ws=[1, 3, 1])
assert os_ == 25.6 and s[0] == 3.6 and s == sorted(s), (s, os_)
# 5) 서버 정리: 기본값(1)은 저장하지 않고, 범위를 벗어난 값은 잘라 낸다
ids = ['a']; pick = lambda v: v if v in ids else ids[0]
assert 'w' not in server.normalize_scene({'ttl': 'x', 'photo': 'a', 'w': 1}, ids, pick)
assert server.normalize_scene({'ttl': 'x', 'photo': 'a', 'w': 99}, ids, pick)['w'] == 20
assert server.normalize_scene({'ttl': 'x', 'photo': 'a', 'w': 'abc'}, ids, pick).get('w') is None
print('OK')

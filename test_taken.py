"""사진 촬영 일시(EXIF) 추출과 촬영 시간순 장면 정렬 검증."""
import io, json, os, shutil
from PIL import Image
import media, server


def jpg(when=None):
    im, ex = Image.new('RGB', (64, 48), 'red'), Image.Exif()
    if when:
        ex.get_ifd(0x8769)[36867] = when   # DateTimeOriginal
    b = io.BytesIO(); im.save(b, 'JPEG', exif=ex.tobytes()); b.seek(0)
    return b


assert media.photo_taken(Image.open(jpg('2026:04:24 14:05:09'))) == '2026-04-24T14:05:09'
assert media.photo_taken(Image.open(jpg())) is None                 # EXIF 없음
assert media.photo_taken(Image.open(jpg('0000:00:00 00:00:00'))) is None   # 시계 미설정 카메라

# 업로드하면 meta에 taken이 남는다(저장본은 EXIF가 빠지므로 원본에서 읽어야 함)
c = server.app.test_client()
r = c.post('/api/upload', data={'job': '', 'files': [(jpg('2026:04:24 15:00:00'), 'b.jpg'), (jpg('2026:04:24 09:30:00'), 'a.jpg'), (jpg(), 'c.jpg')],
                                'paths': ['행사/b.jpg', '행사/a.jpg', '행사/c.jpg']}, content_type='multipart/form-data').get_json()
try:
    got = [p.get('taken') for p in r['photos']]
    assert got == ['2026-04-24T15:00:00', '2026-04-24T09:30:00', None], got
    ph = {p['id']: p for p in r['photos']}
    scenes = [{'photo': 'p003'}, {'photo': 'p001'}, {'photo': 'p002'}, {'type': 'collage', 'photo': 'p003', 'photos': ['p003', 'p002']}]
    order = [s['photo'] for s in server.sort_by_taken(scenes, ph)]
    # 콜라주(가장 이른 p002 09:30) = p002 장면과 같은 시각 -> 원래 순서 유지, 시각 모르는 p003 장면은 맨 뒤
    assert order == ['p002', 'p003', 'p001', 'p003'], order
    assert server.sort_by_taken(scenes, ph)[1].get('type') == 'collage'
    # 배치 방식: 수동 = 대표 사진을 올린 순서, 무작위 = 같은 장면들, AI = 그대로
    assert [s['photo'] for s in server.arrange(scenes, 'manual', r['photos'])] == ['p001', 'p002', 'p003', 'p003']
    assert sorted(map(id, server.arrange(scenes, 'random', r['photos']))) == sorted(map(id, scenes))
    assert server.arrange(scenes, 'ai', r['photos']) is scenes
finally:
    shutil.rmtree(server.jobdir(r['job']), ignore_errors=True)
print('OK')

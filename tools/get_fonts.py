"""영상용 한글 글꼴(오픈 폰트 라이선스)을 fonts/ 폴더에 내려받는다. 한 번만 실행하면 된다.
렌더할 때 영상에 쓰인 글자만 잘라 작은 파일로 넣으므로, 렌더하는 PC에 글꼴을 설치할 필요가 없다.
실행: python tools/get_fonts.py"""
import os, urllib.request

BASE = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
FILES = {
    'NotoSansKR.ttf': 'notosanskr/NotoSansKR%5Bwght%5D.ttf',     # 클래식·본문
    'NotoSerifKR.ttf': 'notoserifkr/NotoSerifKR%5Bwght%5D.ttf',  # 시네마틱
    'BlackHanSans.ttf': 'blackhansans/BlackHanSans-Regular.ttf',  # 키네틱
    'Jua.ttf': 'jua/Jua-Regular.ttf',                             # 팝
}
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
os.makedirs(out, exist_ok=True)
for name, path in FILES.items():
    dst = os.path.join(out, name)
    if os.path.exists(dst):
        print('있음', name); continue
    print('받는 중', name, '...', flush=True)
    urllib.request.urlretrieve(BASE + path, dst + '.part')
    os.replace(dst + '.part', dst)
print('완료:', out)

"""주인공 시트(prot_s2)에 평면 2D 키링 한 쌍을 백팩 왼쪽 어깨끈 자리에 붙인다. 주인공은 그대로, 키링만 추가.
사용: python tools/story_b_attach.py  -> jobs/contest/story_b/prot_s2_keyring.png (+x2 확대본 미리보기는 _x2.png)
"""
import glob
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "jobs" / "contest"
REF = ROOT / "story_b" / "refs"
base = Image.open(sorted(glob.glob(str(ROOT / "story_b_sheet" / "prot_s2" / "out" / "*.jpg")))[-1]).convert("RGBA")
K = {n: Image.open(REF / f"keyring_{n}.png") for n in ("dongi", "dungi")}
# (걸이 지점 x, y, 키링 높이, 기울기°, 설명). 걸이 지점에서 쇠고리가 이어지고 키링이 중력으로 늘어진다. 앞=어깨끈, 옆=가방 옆주머니 지퍼, 뒤=가방 손잡이.
SPOTS = [(190, 138, 50, 3), (508, 203, 50, -3), (654, 140, 50, 0)]
from PIL import ImageDraw, ImageFilter
for x, y, h, ang in SPOTS:
    d = ImageDraw.Draw(base)
    d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(190, 195, 205, 255), outline=(70, 70, 80, 255), width=2)  # 걸이 고리
    for n, dx in (("dongi", -13), ("dungi", 13)):
        k = K[n].resize((int(K[n].width * h / K[n].height), h), Image.LANCZOS).rotate(ang, expand=True, resample=Image.BICUBIC)
        pos = (x + dx - k.width // 2, y)
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 70), (pos[0] + 2, pos[1] + 3), k.getchannel("A"))  # 은은한 그림자
        base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(1.5)))
        base.alpha_composite(k, pos)
        d.line((x, y, x + dx, y + 8), fill=(70, 70, 80, 255), width=1)  # 걸이에서 각 키링 고리로 이어지는 선
out = ROOT / "story_b" / "prot_s2_keyring.png"
base.convert("RGB").save(out)
base.convert("RGB").resize((1664, 960), Image.LANCZOS).save(out.with_name("prot_s2_keyring_x2.png"))
print(out)

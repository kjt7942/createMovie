"""공식 2D 캐릭터 시트에서 동이·둥이 정면을 오려 평면(2D) 아크릴 키링 PNG를 만든다. 모델 생성이 아니라 원본을 그대로 쓰므로 디자인이 변하지 않는다.
사용: python tools/story_b_keyring.py <시트.png>  -> jobs/contest/story_b/refs/keyring_{dongi,dungi}.png, keyring_pair.png
"""
import sys
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "jobs" / "contest" / "story_b" / "refs"
LINE = (236, 0, 140)  # 시트의 분홍 점선 가이드(1px)
BOXES = {"dongi": (95, 55, 445, 475), "dungi": (125, 545, 415, 960)}


def clean(im):
    a = np.array(im.convert("RGB"))
    for y in np.where((a == LINE).all(axis=2).sum(axis=1) > 150)[0]:
        a[y] = a[y - 1]  # 점선 한 줄은 바로 윗줄로 덮는다(끝부분의 반투명 픽셀까지 지운다)
    return Image.fromarray(a)


def cutout(im, tol=10):
    a = np.array(im.convert("RGB")).astype(int)
    white = a.min(axis=2) >= 255 - tol
    h, w = white.shape
    bg = np.zeros_like(white)
    q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    while q:
        x, y = q.popleft()
        if 0 <= x < w and 0 <= y < h and not bg[y, x] and white[y, x]:
            bg[y, x] = True
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray(((~bg) * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(.6)))
    return out.crop(out.getbbox())


def keyring(ch, border=12):
    pad = border + 90
    W, H = ch.width + 2 * pad, ch.height + 2 * pad
    alpha = Image.new("L", (W, H)); alpha.paste(ch.getchannel("A"), (pad, pad))
    sticker = alpha.filter(ImageFilter.MaxFilter(border * 2 + 1)).filter(ImageFilter.GaussianBlur(2)).point(lambda v: 255 if v > 100 else 0)
    top0 = sticker.getbbox()[1]
    ImageDraw.Draw(sticker).ellipse((W // 2 - 24, top0 - 40, W // 2 + 24, top0 + 8), fill=255)  # 고리를 거는 귀(탭)
    edge = sticker.filter(ImageFilter.MaxFilter(5))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste((70, 70, 80, 255), mask=edge)
    img.paste((255, 255, 255, 255), mask=sticker)
    img.alpha_composite(ch, (pad, pad)) if False else img.paste(ch, (pad, pad), ch)
    d = ImageDraw.Draw(img)
    top = sticker.getbbox()[1]; cx = W // 2
    d.ellipse((cx - 8, top + 8, cx + 8, top + 24), fill=(200, 205, 215, 255), outline=(70, 70, 80, 255), width=3)  # 구멍
    d.ellipse((cx - 22, top - 46, cx + 22, top + 12), outline=(70, 70, 80, 255), width=9)  # 평면 고리(외곽)
    d.ellipse((cx - 22, top - 46, cx + 22, top + 12), outline=(190, 195, 205, 255), width=4)  # 고리 색
    return img.crop(img.getbbox())


if __name__ == "__main__":
    sheet = clean(Image.open(sys.argv[1]))
    OUT.mkdir(parents=True, exist_ok=True)
    ks = {}
    for n, box in BOXES.items():
        ks[n] = keyring(cutout(sheet.crop(box)))
        ks[n].save(OUT / f"keyring_{n}.png")
    pair = Image.new("RGBA", (ks["dongi"].width + ks["dungi"].width + 40, max(k.height for k in ks.values())), (255, 255, 255, 255))
    pair.alpha_composite(ks["dongi"], (0, 0)); pair.alpha_composite(ks["dungi"], (ks["dongi"].width + 40, 0))
    pair.convert("RGB").save(OUT / "keyring_pair.png")
    print({n: k.size for n, k in ks.items()})

"""캐릭터 왜곡·배경 불일치 대책: 배경(장소 사진 참조)과 캐릭터(원본 참조 1~2장, 흰 배경)를 따로 생성한 뒤 합성한다.
사용:
  python tools/contest_conti_comp.py bg   <배치> [컷들]   배경만 생성(사람 없음)  -> jobs/contest/<배치>_bg
  python tools/contest_conti_comp.py ch   <배치> [컷들]   캐릭터만 생성(흰 배경)  -> jobs/contest/<배치>_ch
  python tools/contest_conti_comp.py comp <배치> [컷들]   합성 -> jobs/contest/<배치>/<컷>_s<n>.jpg + 비교 시트 sheet.jpg
진행: http://127.0.0.1:5000/batch
"""
import json, sys, urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J = ROOT / "jobs" / "contest"
REFS, PLACES = J / "refs", J / "refs_places"
SEED = 20261130
EDIT = "qwen_image_edit_plus2_20B"
END = " Cinematic 16:9 film still, rich natural detail, no text, no watermark. No people and no characters anywhere in the image."
KEEP = (" Keep the character's design, exact body proportions (short slim two-heads-tall body, big round head), line work and colors exactly as in the reference image; "
        "no new clothes or accessories. Plain pure white background, full body fully visible and not cropped, no shadow, no ground, no other objects.")
GATE = ("The gate is Juheulgwan of Mungyeong Saejae in Korea: a long, low, wide fortress wall of large pale beige-gray granite blocks running horizontally across the "
        "frame, with small square parapet notches along its top edge, one low rounded stone arch opening in the middle, and a single-story wooden gate pavilion with a dark "
        "gray tiled hip-and-gable roof and dark brown wood on top of the arch; a wide flat sandy-gravel path leads to the arch across an open lawn plaza. Not tall, not a narrow tower, "
        "not Chinese style, no multi-tier roof, no pagoda. ")

# 컷별: bg=배경 프롬프트, places=장소 사진 파일(최대 3), ch=(참조들, 포즈 프롬프트), at=[(중심x, 발끝y, 높이)] 배경 대비 비율(합성 위치)
CUTS = {
    "c01": dict(bg="Wide shot at dawn with thin morning mist, seen from the sandy path: " + GATE,
                places=["c01_1", "c01_2", "c01_3"], ch=(["dongi_back.png"], "Character 1 (image 1) seen from behind, walking away from the camera in mid-stride."), at=[(.5, .80, .22)]),
    "c03": dict(bg="Wide low-angle shot of a Joseon-dynasty film set: a compound of low single-story hanok halls with dark charcoal-gray tiled roofs, pale sand-colored earthen courtyards, orange-brown clay walls topped with tile, stone-edged paths, a pond with a small stone bridge and stone lanterns, tree-covered hills and blue sky.",
                places=["c03_1", "c03_2", "c03_3"], ch=(["dongi_front.png"], "Character 1 (image 1) leaps in the air with both arms up, joyful, facing the camera."), at=[(.5, .62, .22)]),
    "c05": dict(bg="Low-angle shot at water level in a wide shallow rocky creek: large smooth pale gray granite boulders and slabs, clear green-teal pools, steep green forested slopes, open sky, a few autumn leaves, white water splashing between rocks.",
                places=["c05_1", "c05_2", "c05_3"], ch=(["dongi_three_quarter.png"], "Character 1 (image 1) jumping through the air with legs apart, seen from a three-quarter angle."), at=[(.5, .55, .22)]),
    "c13": dict(bg="A summit rock outcrop with a carved stone summit marker (vertical carved characters, no readable text), low shrubs, distant layered blue ridges under a clear sky.",
                places=["c13_1", "c13_2", "c13_3"], ch=(["dongi_front.png"], "Character 1 (image 1) stands facing the camera with both fists raised in a victory pose, happy."), at=[(.68, .92, .30)]),
    "c19": dict(bg="Side view of one open pedal rail car filling the center of the frame, red-and-white body, silver frame, blue translucent canopy roof, two rows of seats, empty with nobody on it, on rusty rails across a bridge with white decorative railings over a green river in a lush mountain valley.",
                places=["c19_1", "c19_2", "c19_3"], ch=(["dongi_side.png", "dungi_three_quarter.png"], "Character 1 (image 1) and character 2 (image 2) sit side by side seen from the side facing right, knees bent, feet forward on pedals, hands on handlebars; both full body clearly visible."), at=[(.50, .66, .30)], seed=7),
    "c25": dict(bg=GATE + "Sunset, orange sky, autumn leaves flying.",
                places=["c25_1", "gate_ref", "gate_wall_ref"], ch=(["dongi_front.png", "dungi_front.png"], "Character 1 (image 1) on the left and character 2 (image 2) on the right jump in the air and high-five each other joyfully; both exactly once, clearly visible."), at=[(.5, .90, .42)]),
}


def ph(name):
    return (PLACES / f"{name}.jpg") if (PLACES / f"{name}.jpg").exists() else (REFS / f"{name}.jpg")


def submit(name, items):
    body = {"name": name, "title": f"콘티 합성 {name}", "items": items, "start": True}
    req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(body).encode())
    print(len(items), "items:", urllib.request.urlopen(req).read().decode()[:200])


def run(kind, batch, only):
    items = []
    for cid, c in CUTS.items():
        if only and cid not in only:
            continue
        n = int(cid[1:])
        for s in (1, 2):
            if kind == "bg":
                ps = [ph(p).as_posix() for p in c["places"]]
                k = len(ps)
                pre = f"Image{'s' if k > 1 else ''} 1{'-' + str(k) if k > 1 else ''} {'are' if k > 1 else 'is a'} real photograph{'s' if k > 1 else ''} of the actual place in Mungyeong, Korea. Reproduce the place's real appearance faithfully (structures, colors, terrain, materials, vegetation) as shown, but seen from the camera angle and framing described next. "
                job = dict(model_type=EDIT, prompt=pre + c["bg"] + END, resolution="832x480", seed=SEED + 1000 * s + n + c.get("seed", 0), batch_size=1, video_prompt_type="I", image_refs=ps)
            else:
                refs, pose = c["ch"]
                job = dict(model_type=EDIT, prompt=pose + KEEP, resolution="832x480", seed=SEED + 1000 * s + n + c.get("seed", 0), batch_size=1, video_prompt_type="I", image_refs=[(REFS / r).as_posix() for r in refs])
            items.append({"name": f"{cid}_s{s}", "job": job})
    submit(f"{batch}_{kind}", items)


def latest(d):
    fs = sorted((d / "out").glob("*.jpg"), key=lambda p: p.stat().st_mtime)
    return fs[-1] if fs else None


def cutout(im, tol=28):
    """가장자리에서 이어진 흰색만 투명으로(캐릭터 안쪽 흰 끈은 남긴다)."""
    from PIL import Image, ImageFilter
    im = im.convert("RGB")
    w, h = im.size
    px = im.load()
    bg = [[False] * w for _ in range(h)]
    q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    white = lambda p: min(p) >= 255 - tol
    while q:
        x, y = q.popleft()
        if 0 <= x < w and 0 <= y < h and not bg[y][x] and white(px[x, y]):
            bg[y][x] = True
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    m = Image.new("L", (w, h))
    m.putdata([0 if bg[y][x] else 255 for y in range(h) for x in range(w)])
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))  # 흰 테두리 1px 깎고 부드럽게
    out = im.convert("RGBA")
    out.putalpha(m)
    return out.crop(out.getbbox())


def comp(batch, only):
    from PIL import Image, ImageDraw, ImageFilter
    out = J / batch
    out.mkdir(exist_ok=True)
    tiles = []
    for cid, c in CUTS.items():
        if only and cid not in only:
            continue
        for s in (1, 2):
            b, ch = latest(J / f"{batch}_bg" / f"{cid}_s{s}"), latest(J / f"{batch}_ch" / f"{cid}_s{s}")
            if not (b and ch):
                print("skip", cid, s, "(생성 결과 없음)")
                continue
            bg, fg = Image.open(b).convert("RGBA"), cutout(Image.open(ch))
            for cx, by, hh in c["at"]:
                H = int(bg.height * hh)
                f = fg.resize((max(1, int(fg.width * H / fg.height)), H), Image.LANCZOS)
                x, y = int(bg.width * cx - f.width / 2), int(bg.height * by - H)
                sh = Image.new("RGBA", bg.size, (0, 0, 0, 0))  # 접지 그림자
                ImageDraw.Draw(sh).ellipse((x + f.width * .1, y + H - H * .04, x + f.width * .9, y + H + H * .05), fill=(0, 0, 0, 90))
                bg = Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(4)))
                bg.alpha_composite(f, (x, y))
            bg.convert("RGB").save(out / f"{cid}_s{s}.jpg", quality=92)
            tiles.append(out / f"{cid}_s{s}.jpg")
    if tiles:
        W, H = 416, 240
        sheet = Image.new("RGB", (W * 4, H * ((len(tiles) + 3) // 4)))
        d = ImageDraw.Draw(sheet)
        for i, t in enumerate(tiles):
            sheet.paste(Image.open(t).resize((W, H)), ((i % 4) * W, (i // 4) * H))
            d.text(((i % 4) * W + 6, (i // 4) * H + 4), t.stem, fill="yellow")
        sheet.save(out / "sheet.jpg", quality=85)
    print(len(tiles), "composites ->", out)


if __name__ == "__main__":
    kind, batch = sys.argv[1], sys.argv[2]
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    comp(batch, only) if kind == "comp" else run(kind, batch, only)

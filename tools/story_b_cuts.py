"""출품안 B(聞慶, 대사 없는 2D 애니메이션) 18컷: 480p 시안 이미지 -> 선택한 컷만 저화질 영상 샘플.
사용:
  python tools/story_b_cuts.py img <배치이름> [컷,..] [--seed N]   480p 이미지(컷당 시드 2개) -> jobs/contest/<배치이름>/<컷>_s<n>/out/
  python tools/story_b_cuts.py vid <배치이름> [컷,..]              jobs/contest/story_b/pick.json의 이미지로 832x480 3초 영상
  python tools/story_b_cuts.py sheet <배치이름>                    검수용 한 장 시트(sheet.jpg)
규칙: 저화질 샘플 먼저, 손그림 2D(사진·3D 금지), 키링은 평소 작게(클로즈업 컷 3·4·17만 상세), 텍스트 금지(자막은 편집에서).
"""
import glob, json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J = ROOT / "jobs" / "contest"
B = J / "story_b"
REF = B / "refs"
EDIT = "qwen_image_edit_plus2_20B"
SEED = 20272100
S = ("Hand-drawn 2D anime film still in the style of a Japanese animated feature film background painting, soft watercolor textures, clean ink outlines, simple flat color shapes, "
     "simplified anime faces (small nose, simple eyes), warm Korean autumn light, 16:9. NOT a photograph, NOT photorealistic, NOT semi-realistic, NOT 3D render, no realistic skin pores or glossy 3D shading. "
     "No text, no letters, no hanja, no logos, no brand marks on any object. ")
W = ("the young Korean woman of image 1 (shoulder-length dark brown hair in a low ponytail, oversized gray hoodie, light blue jeans, white sneakers, "
     "navy backpack with two very small keychains hanging at the top center of the backpack) ")
FACE = "Keep her face, hair and outfit exactly as in image 1. "
WF = ("the young Korean woman of image 1 seen from the front (shoulder-length dark brown hair in a low ponytail, oversized gray hoodie, light blue jeans, white sneakers, "
      "navy backpack straps over her shoulders). Nothing hangs from her neck or chest, no lanyard, no name tag, no necklace, no keychain is visible on her body, and she holds nothing except what is stated. ")
# 참조: front=정면 주인공, back=뒷모습(키링 달림), key=공식 평면 키링 한 쌍, 그 외 장소 사진 이름은 refs_places/<이름>.jpg
CUTS = {
    "01": dict(t="0:00-0:02", refs=["front"], p="Close-up of " + WF + "at night in a dark small studio apartment, a laptop with no logo, her tired blank face lit only by cold blue laptop glow, empty gaze, dim room. " + FACE,
               m="Very slow push-in on her tired face, the blue laptop light flickers faintly, she blinks once slowly."),
    "02": dict(t="0:02-0:04", refs=["front"], p="Close-up insert: her two hands holding a smartphone in the dark, the glowing screen shows a plain gray message card with unreadable abstract gray lines, no readable text, blue light on her fingers, cold dim room, a bit of her gray hoodie sleeve.",
               m="Locked camera. The phone screen stays a plain blank gray rectangle with no icons, pictures or graphics at all. Only her thumbs move slightly and the soft blue glow on her hands pulses gently."),
    "03": dict(t="0:04-0:07", refs=["key"], p="Morning light in the studio room: an opened cardboard apple box on a wooden table with a few red apples, and on top a pair of small flat acrylic keychains of the two mascot characters exactly as in image 1, plus a small landscape postcard of a mountain gate in autumn. Close-up composition, warm morning light. No text.",
               m="Slow push-in on the keychains, a sunbeam slides across the table, the keychains sway slightly."),
    "04": dict(t="0:07-0:09", refs=["back", "key"], p="Close-up from behind at the top of the navy backpack: " + W + "is clipping the two small keychains of image 2 (exactly as drawn) to the backpack's top handle, centered on the bag. The keychains are a bit larger here for detail. Warm window light. ",
               m="Locked camera. Only the two small keychains swing gently on the backpack handle and then settle; her body stays still and no hands appear."),
    "05": dict(t="0:09-0:13", refs=["front", "c19_1"], p="Wide side view: " + WF + "sits in an open rail bike with a red-and-white body and blue canopy and pedals it: both her white sneakers are on the two pedals under the seat, knees bent, her feet clearly off the ground, hands on the handlebar, riding on railway tracks out of a tunnel into a valley full of red and yellow autumn leaves with a river, wind blowing her hair. Image 2 is a photo of the real rail bikes, paint the place as a watercolor illustration. " + FACE,
               m="Locked static camera with no zoom and no camera movement. The rail car stays in the same place in the frame while she pedals gently with both feet on the pedals, her ponytail flutters in the wind, autumn leaves fall and the river sparkles."),
    "06": dict(t="0:13-0:17", refs=["back"], p="Wide shot from behind: " + W + "walks slowly through a dark old coal mine tunnel with wooden support beams and old rails on the ground, small warm lantern lights along the wall, a bright warm light at the far end of the tunnel. Moody but warm. ",
               m="She walks toward the bright light at the end of the tunnel, the light slowly grows, camera follows behind her."),
    "07": dict(t="0:17-0:21", refs=["front"], p="Medium shot: in a rustic pottery workshop, a traditional earthen kiln door is opened with glowing orange firelight, and " + WF + "receives a freshly fired rustic tea bowl with both hands, warm firelight on her face, wonder in her eyes. " + FACE,
               m="Firelight flickers on her face, she lifts the tea bowl closer with both hands, steam rises."),
    "08": dict(t="0:21-0:23", refs=[], p="Extreme close-up of thin slices of marbled beef sizzling on a charcoal grill, glowing coals, curling smoke, drawn in warm watercolor illustration style, shallow depth. No people.",
               m="Locked camera. The beef slices sizzle in place, smoke curls up and glowing embers flicker; nothing is lifted or flipped, no hands and no tongs appear."),
    "09": dict(t="0:23-0:27", refs=["front"], p="Medium shot at a small Korean restaurant table with a charcoal grill: " + WF + "sits alone, and a kind elderly Korean woman in an apron holds out a lettuce wrap toward her with a warm smile; the young woman takes it and smiles for the first time, a small happy smile. Her backpack hangs on the chair with the tiny keychains visible. " + FACE,
               m="The grandmother holds out the wrap, the young woman takes it, her face slowly brightens into a small smile."),
    "10": dict(t="0:27-0:31", refs=["front", "c20_1"], p="Epic view: " + WF.replace("navy backpack straps over her shoulders", "white safety helmet and a paragliding harness") + "flies in a paraglider seen from a distance in a wide shot: she is small in the frame, about one fifth of the image height, and the vast valley dominates; her chest and harness are plain: no pendant, no card, no tag, no necklace, no badge, nothing hangs on her chest or harness straps; with a colorful wing high above a wide autumn valley with golden fields and mountains, laughing with joy, wind in her hair. Image 2 is a photo of the launch field, paint it as watercolor. " + FACE,
               m="Smooth glide over the valley, the wing sways gently, she laughs and spreads her arms, the landscape slides below."),
    "11": dict(t="0:31-0:34", refs=["front", "c01_1"], p="Wide shot at the entrance of an old mountain pass road: a long low stone fortress wall with one arch and a single-story gate pavilion (Juheulgwan), a golden-red autumn tree-lined path, and " + WF + "stands small in the path holding up a postcard to compare with the real view. Image 2 is a photo of the real gate, paint it as watercolor, keep the gate low and wide. " + FACE,
               m="Locked camera, no zoom, no camera movement. Autumn leaves drift down and she slowly lowers the postcard and looks up at the gate; nothing new appears in the scene."),
    "12": dict(t="0:34-0:38", refs=["front"], p="Medium shot on a mountain trail in autumn: " + WF + "holds a small gray stone in her hand and hesitates in front of a big plain rock covered with small piled stones (a wish stone pile where people pray for good luck), the rock has no carvings or writing, soft light through red leaves. " + FACE,
               m="She looks at the stone in her hand, hesitates, then slowly places it on the pile."),
    "13": dict(t="0:38-0:41", refs=["back"], p="Wide shot from behind: " + W + "walks briskly up an old stone-paved mountain pass trail between red and golden maple trees, leaves flying around her, motion and energy. ",
               m="She walks faster, then jogs up the trail, ponytail bouncing, leaves swirl, camera follows behind."),
    "14": dict(t="0:41-0:44", refs=["back"], p="Wide shot from behind: " + W + "stands on a mountain ridge pass at sunset next to an old stone gate pavilion, catching her breath, golden sunset light over layered autumn mountains. ",
               m="She catches her breath, shoulders rise and fall, golden light intensifies, leaves float by."),
    "15": dict(t="0:44-0:46", refs=["front"], p="Close-up insert: her hand holds a glowing smartphone at sunset, the screen shows a bright green circle with a white check mark and little confetti sparkles, no text, warm golden light. ",
               m="The phone buzzes, the screen lights up, sparkles pop around the green check mark."),
    "16": dict(t="0:46-0:50", refs=["front"], p="Close-up of " + WF + "at sunset, her face (the same framing as a close-up of her tired face), straight-on front close-up of her face centered, her hair is in a low ponytail (not a braid) with loose strands, tears running down both cheeks while she smiles widely, golden warm light on her cheeks, the gray hoodie glowing warm. Flat cel-shaded 2D anime frame like a Ghibli close-up: thick clean outlines around the face and hair, flat skin color with only simple soft shadow shapes, big simple eyes, tiny nose, no skin texture, no realistic lighting on the face, NOT a 3D render. " + FACE,
               m="Locked camera with only a very slow subtle push-in. She keeps a wide happy smile with her mouth open in joy through the whole clip and never stops smiling or turns sad; tears keep running down her cheeks, her ponytail sways slightly in the breeze and the golden light flickers."),
    "17": dict(t="0:50-0:54", refs=["back", "key"], p="Close-up of the top of the navy backpack at sunset: two small keychains exactly as in image 2 hang from the top handle, glowing in golden light with tiny sparkles; Detailed, flat 2D style. ",
               m="Sparkles twinkle on the keychains, the keychains sway gently; their faces stay exactly unchanged, no winking, no blinking and no facial animation."),
    "18": dict(t="0:54-1:02", refs=["back"], p="Very wide shot from a mountain pass ridge at sunset: " + W + "stands small seen from behind on the right, looking out over a vast layered autumn mountain landscape of Mungyeong, golden clouds, peaceful ending, lots of empty sky at the top for a title. ",
               m="Slow pull-back and upward tilt over the vast landscape, clouds drift, her ponytail sways."),
}


def ref_path(name):
    if name in ("front", "back", "key"):
        return {"front": REF / "prot_s2_front.png", "back": REF / "prot_back_final.png", "key": REF / "keyring_pair.png"}[name]
    return J / "refs_places" / f"{name}.jpg"


def submit(name, title, items):
    body = {"name": name, "title": title, "items": items, "start": True}
    req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(body).encode())
    print(len(items), "items:", urllib.request.urlopen(req).read().decode()[:200])


def img(batch, only, seed0):
    items = []
    for cid, c in CUTS.items():
        if only and cid not in only:
            continue
        refs = [ref_path(r).as_posix() for r in c["refs"]]
        pre = ""
        if refs:
            names = {"front": "a drawing of the main character", "back": "a drawing of the main character from behind", "key": "the official flat keychain drawing"}
            pre = " ".join(f"Image {i + 1} is {names.get(r, 'a photo of the real place')}." for i, r in enumerate(c["refs"])) + " "
        for s in (1, 2):
            job = dict(model_type=EDIT if refs else "qwen_image_2512_20B", prompt=pre + S + c["p"], resolution="832x480", seed=seed0 + 1000 * s + int(cid), batch_size=1)
            if refs:
                job.update(video_prompt_type="I", image_refs=refs)
            items.append({"name": f"c{cid}_s{s}", "job": job})
    submit(batch, f"출품안B 컷 시안 {batch}", items)


def vid(batch, only, seed0=SEED):
    pick = json.loads((B / "pick.json").read_text(encoding="utf-8"))  # {"01": "경로(또는 <배치>/<컷>_s<n>)"}
    items = []
    for cid, c in CUTS.items():
        if cid not in pick or (only and cid not in only):
            continue
        src = pick[cid] if Path(pick[cid]).is_absolute() else str(J / pick[cid])
        src = sorted(glob.glob(src + "/out/*.jpg"))[-1] if Path(src).is_dir() else src
        job = dict(model_type="i2v_2_2_lightning_contest", prompt=c["m"] + " Hand-drawn 2D watercolor animation, the character and the keychains keep exactly the same design, smooth gentle natural motion, no text, no camera shake.",
                   image_prompt_type="S", image_start=Path(src).as_posix(), resolution="832x480", video_length=49, num_inference_steps=4, guidance_scale=1, guidance2_scale=1, seed=seed0 + int(cid))
        items.append({"name": f"c{cid}", "job": job})
    submit(batch, f"출품안B 영상 샘플 {batch}", items)


def sheet(batch):
    from PIL import Image, ImageDraw
    fs = sorted(glob.glob(str(J / batch / "c*_s*/out/*.jpg")))
    W, H, cols = 416, 240, 4
    sh = Image.new("RGB", (W * cols, H * ((len(fs) + cols - 1) // cols)))
    d = ImageDraw.Draw(sh)
    for i, f in enumerate(fs):
        x, y = (i % cols) * W, (i // cols) * H
        sh.paste(Image.open(f).resize((W, H)), (x, y))
        d.text((x + 6, y + 4), Path(f).parent.parent.name, fill="yellow")
    out = J / batch / "sheet.jpg"
    sh.save(out, quality=85)
    print(len(fs), "->", out)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    seed0 = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else SEED
    if "--seed" in sys.argv:
        a.remove(str(seed0))
    only = set(a[2].split(",")) if len(a) > 2 else None
    {"img": lambda: img(a[1], only, seed0), "vid": lambda: vid(a[1], only, seed0), "sheet": lambda: sheet(a[1])}[a[0]]()

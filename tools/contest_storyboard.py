"""콘티 v2(26컷) 스토리보드 이미지를 480p(832x480)로 가볍게 만든다. 결과: jobs/contest/<폴더>/cXX_*/out/*.jpg
사용: python tools/contest_storyboard.py storyboard_v1 [컷번호들 예: 01,05] [--service]
--service를 붙이면 서비스 대기열로 보내 http://127.0.0.1:5000/batch 에서 진행상황을 본다.
"""
import json, sys, time, urllib.request
import contest_test as t
import contest_scenes as cs

t.OUT = t.ROOT / "jobs" / "contest" / (sys.argv[1] if len(sys.argv) > 1 else "storyboard_v1")
t.REPORT = t.OUT / "report.json"
CH = cs.CH.replace("a chubby 3D boy", "a small cute 3D boy with a big round head and a short slim body about two heads tall (never fat, never a big belly or wide cheeks)").replace(
    "wears a round lime-green hooded costume", "wears a lime-green hooded costume (round hood, short body, never fat)").replace(
    "Keep both characters' design, proportions,", "Keep both characters' design, exact body proportions and head-to-body ratio as in images 1 and 2,").replace("Slightly blurred background so the characters stand out clearly, cinematic 16:9 composition, no text.",
                   "Cinematic 16:9 film still, rich detail, no text, no watermark.")
WIDE = " The two characters are SMALL in the frame, about one fifth of the image height; the landscape and landmark dominate. "
MED = " Medium shot, the characters fill about half of the frame height, the location clearly visible around them. "
CU = " Close-up shot, the face of the named character fills most of the frame, background softly visible. "
GATE = (" The fortress gate is Juheulgwan of Mungyeong Saejae in Korea: one wall of rough natural granite blocks with a single rounded arch, "
        "topped by a single-story wooden pavilion with one gray Korean tiled hip-and-gable roof; the short wall ends in forested hills. "
        "Not a Chinese tower, no multi-tier roof, no pagoda, no Great Wall, no brick battlements, no walkway along a ridge. ")
JOSEON = " Joseon dynasty era, no modern objects or people. "
MODERN = " Present day 2026 autumn, a few small tourists in the distance. "

# 두 캐릭터를 함께 넣으면 역할이 뒤바뀌거나 캐릭터가 끼어드는 컷: 이 참고 이미지(jobs/contest/refs/)만 쓰고 캐릭터 설명은 뺀다.
ONLY_REFS = {"09": ["dongi_front.png"], "19": ["dongi_front.png"], "26": ["gate_wall_ref.jpg"]}

SHOTS = [
    ("01", "eye_cu", CU + JOSEON, "Extreme close-up of character 1's face with eyes wide open in wonder, morning mist around him."),
    ("02", "aerial_pass", WIDE + JOSEON, "Aerial drone shot at dawn over a misty mountain pass with an old stone road winding through pine forest; the two characters walk on the road far below; a bluebird flies near the camera."),
    ("03", "bird_hat", MED + JOSEON, "Low angle: a small bluebird lands on the apple on character 1's hat stem, character 1 looks up startled, character 2 points at the bird; misty pines behind."),
    ("04", "gate_back", WIDE + JOSEON, "Wide shot from behind: the two characters walk hand in hand into the dark arch of a huge old stone fortress gate with a wooden pavilion roof; blinding golden light shines from the far end of the arch."),
    ("05", "modern_reveal", WIDE + MODERN, "Wide shot looking out from inside the dark stone arch of the fortress gate: a bright autumn mountain trail with red and yellow maples and tourists; the two characters stand in silhouette in the arch opening."),
    ("06", "jaw_drop", CU + MODERN, "Close-up of character 1 with his jaw dropped in shock, hat stems trembling, character 2 grinning beside him, bright autumn trees behind."),
    ("07", "trail_run", WIDE + MODERN, "Side tracking shot: on a wide red-clay walking trail through a tunnel of red and yellow maple trees, character 2 runs pulling character 1 by the hand; leaves swirl in the air."),
    ("08", "barefoot_top", "", "Photo from a drone hovering directly above, lens pointing straight down at the ground: the red-clay trail fills the entire frame, no horizon, no sky, no tourists. We see the round tops of both hats, their shoulders and their feet from above, faces hidden. Character 1 tiptoes barefoot with his bare toes visible, a pair of shoes dangling from one hand; character 2 walks in shoes; fallen leaves on the clay."),
    ("09", "selfie_pov", MED + MODERN, "The character from image 1, exactly his design, alone in the frame, holds nothing: he is bent forward from the waist in a very deep formal Korean bow, his hat tipped forward, toward a smartphone on a selfie stick. The stick enters from the right edge of the frame, held by a small hand in a lime-green sleeve; the rest of that person is outside the frame. On the phone screen is his own face. Autumn trail behind."),
    ("10", "set_highangle", WIDE + MODERN, "High angle wide shot of a historical drama film set: a street of traditional tiled-roof houses and a palace-like gate under a blue autumn sky; the two characters walk on the street."),
    ("11", "swagger_low", MED + MODERN, "Low angle hero shot: character 1 struts proudly with hands behind his back down the traditional set street like he owns the place, character 2 laughs hard behind him."),
    ("12", "clay_splat", CU + MODERN, "Close-up: character 1 sits at a spinning potter's wheel and wet clay splatters onto his surprised face; a half-formed tea bowl on the wheel."),
    ("13", "kiln_wide", WIDE + MODERN, "Wide shot at dusk of a traditional Korean mangdaeng-i kiln: a long low row of connected rounded clay domes like a caterpillar, stepping up a gentle hillside, built of earth and clay, with small round fire mouths glowing orange and stacks of firewood beside it. Not a brick building, no chimney tower. The two characters stand small in front of it, lit by the firelight."),
    ("14", "orchard_drone", WIDE + MODERN, "Drone shot flying low between rows of an apple orchard heavy with red apples under a blue sky; the two characters stand small between the trees reaching up for apples."),
    ("15", "double_take", CU + MODERN, "Close-up of character 1 holding a real red apple next to the apple on his hat stem, eyes glancing sideways at it, head tilted, eyebrows raised, small round curious mouth: gentle puzzled wonder, not angry, no frown; apple trees behind."),
    ("16", "apple_bite", MED + MODERN, "Character 2 takes a big bite of a red apple, sparkling juice droplets fly in slow motion, character 1 watches with envy; sunny orchard."),
    ("17", "railbike_wide", WIDE + MODERN, "Wide side-view shot of an old railway along a river valley full of autumn colors. On the rails is a low open pedal rail car with four steel wheels and four seats in two side-by-side rows, like a small open cart; not a bicycle, not a tricycle. The two characters sit side by side in its front seats pedaling. Character 1 wears exactly the rounded dark navy hat with side wings from image 1, not a flat square cap."),
    ("18", "railbike_cu", CU + MODERN, "Close-up of character 1 gripping the rail bike handlebar tightly with his eyes squeezed shut in fear, wind blowing his hat stems; autumn blur behind."),
    ("19", "railbike_fpv", "", "First-person view of someone riding a pedal rail bike fast along empty rails through a tunnel of red and yellow autumn trees. The rails ahead are completely empty: no person, no character, no figure anywhere in the image. Only two small hands in light green sleeves from image 1 grip the handlebar at the bottom of the frame. Motion blur."),
    ("20", "launch_site", WIDE + MODERN, "Wide shot of a paragliding launch ramp on a mountaintop: a human instructor pilot in a helmet runs forward as a colorful tandem paraglider wing inflates; the two characters are strapped in the harness seat in front, wearing white safety helmets."),
    ("21", "glider_aerial", WIDE + MODERN, "Epic aerial view of a vast autumn valley with a winding river and villages. A complete tandem paraglider crosses the sky: a large colorful arc-shaped fabric wing overhead, many thin suspension lines running down from the wing to the harness, a helmeted instructor pilot seated behind, and the two characters strapped in the harness in front of him, wearing white safety helmets."),
    ("22", "scream_cu", CU + MODERN, "Close-up of the two characters strapped in a paragliding harness. BOTH characters wear a white hard safety helmet with a chin strap, character 2 too, worn over the hood. Character 1 screams with wide eyes while character 2 cheers; the instructor's arm and harness straps visible; sky and valley behind."),
    ("23", "sunset_wall", WIDE + MODERN, "Wide sunset shot of the fortress gate glowing in orange light." + GATE + " The two small characters sit side by side on top of the stone wall in silhouette."),
    ("24", "no_return", MED + MODERN, "Full body shot of both characters from head to shoes. The bluebird hovers and gestures toward the fortress gate behind them, character 1 hugs character 2 tightly and shakes his head with a determined smile; warm sunset light." + GATE),
    ("25", "highfive", MED + MODERN, "The two characters jump in the air and high-five each other joyfully in front of the fortress gate at sunset, autumn leaves flying." + GATE),
    ("26", "pullback", "", "Keep exactly the same fortress gate, stone walls and the two small characters sitting on the wall as in image 1, but pull the camera far back and high up into an aerial drone view at sunset: the gate and wall become small in the middle of the frame, and the whole autumn mountain valley with a small low town in the distance fills the rest. Do not add towers, pagodas or new buildings near the gate. Do not add any more characters."),
]


def main():
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    if "--service" in sys.argv:  # 서비스 대기열로 보낸다(화면: http://127.0.0.1:5000/batch)
        items = [{"name": f"c{num}_{name}_s{sd}", "job": {
            "model_type": "qwen_image_edit_plus2_20B", "prompt": shot + frame + ("" if num in ONLY_REFS else CH), "video_prompt_type": "I",
            "image_refs": [(t.REFS / f).as_posix() for f in ONLY_REFS.get(num, ["dongi_front.png", "dungi_front.png"])],
            "resolution": "832x480", "seed": t.SEED + 1000 * sd + int(num), "batch_size": 1,
        }} for num, name, frame, shot in SHOTS if not only or num in only for sd in (1, 2)]
        req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"name": t.OUT.name, "title": f"콘티 {t.OUT.name}", "items": items, "start": True}).encode())
        print(urllib.request.urlopen(req).read().decode())
        return
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for num, name, frame, shot in SHOTS:
        if only and num not in only:
            continue
        for sd in (1, 2):  # 컷당 시드 2개
            t.run_step(f"c{num}_{name}_s{sd}", {
                "model_type": "qwen_image_edit_plus2_20B", "prompt": shot + frame + CH, "video_prompt_type": "I",
                "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
                "resolution": "832x480", "seed": t.SEED + 1000 * sd + int(num), "batch_size": 1,
            }, {".png", ".jpg", ".webp"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

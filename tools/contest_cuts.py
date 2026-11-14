"""확정 스틸 26장을 Wan 2.2 Lightning(Apache 2.0) 480p 초안 영상으로 만든다. 크무 대기열로 보내 http://127.0.0.1:5000/batch 에서 본다.
컷 길이는 애니매틱(tools/contest_animatic.py)을 따르고 편집 여유로 0.5초를 더한다.
사용: python tools/contest_cuts.py cuts_v1 [컷번호들 예: 01,05]
"""
import json, math, sys, urllib.request
from pathlib import Path

FOLDER = sys.argv[1] if len(sys.argv) > 1 else "cuts_v1"
ONLY = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
sys.argv = sys.argv[:1]  # contest_animatic는 인자를 출력 폴더로 읽는다. 여기서는 길이만 가져온다.
import contest_animatic as a  # noqa: E402

FPS = 16
SEED = 20261130 + 1000 * int(FOLDER.rsplit("_v", 1)[-1]) - 1000  # 재생성 폴더마다 새 시드. cuts_v1은 20261130.
KEEP = (" The two cute 3D characters keep exactly the same design, colors and proportions, including the dark official hat "
        "with short side wings and the apple and berry stems on both hats. Smooth natural motion, no text.")
SCENERY_ONLY = " Smooth natural motion, no text, no characters appear."
MOTION = {
    "01": "Slow push in on the two characters' faces as their eyes widen with wonder, morning mist drifts past.",
    "02": "Smooth aerial drone flight forward over the misty mountain pass, the two tiny characters walk along the old road, the bluebird flies past the camera.",
    "03": "The bluebird flutters and settles on the hat stem, character 1 looks up startled, character 2 points and giggles, the camera holds still.",
    "04": "The two characters walk toward the dark stone arch, the golden light in the arch grows brighter and brighter.",
    "05": "The camera moves slowly forward out of the dark arch toward the bright autumn trail, tourists walk in the distance, leaves drift down.",
    "06": "Character 1's jaw drops further and his hat stems tremble, character 2 laughs beside him, tourists walk behind.",
    "07": "Tracking shot alongside the two characters running hand in hand on the red clay trail, leaves swirl in the air around them.",
    "08": "The two characters walk forward on the red clay, character 1 tiptoes carefully on his bare feet, shoes dangling from his hand, the camera moves along above them.",
    "09": "Character 1 bows even deeper toward the phone and slowly rises, the hand holding the selfie stick stays steady, leaves fall behind.",
    "10": "High angle camera slowly glides forward over the traditional street as the two characters walk along it.",
    "11": "Low angle: character 1 struts proudly forward with hands behind his back, character 2 shakes with laughter behind him.",
    "12": "The potter's wheel spins fast, wet clay splatters onto character 1's surprised face, he blinks.",
    "13": "Only the small fires inside the round kiln mouths flicker gently, the fire stays inside the openings, no flames on top of the kiln, a little smoke, the camera holds still, the two characters stand still and watch.",
    "14": "The camera glides smoothly forward between the apple tree rows, branches and red apples sway in the breeze, the two characters reach up. Empty clear sky, nothing flying.",
    "15": "Character 1's eyes glance back and forth between the apple in front of him and his hat, his head tilts in puzzled wonder.",
    "16": "Character 1 takes a big bite of the red apple and chews happily, sparkling juice droplets fly out in slow motion, character 2 watches and smiles, the sunny orchard stays bright.",
    "17": "The two characters pedal and the rail cart rolls slowly forward on the track; the camera stays far away and keeps the whole cart in the middle of the frame the entire time, the river and autumn hills drift slowly behind.",
    "18": "Character 1 grips the bar tightly with eyes squeezed shut, wind blows against him, the blurred autumn background rushes past.",
    "19": "Fast forward motion along the rails through the tunnel of autumn trees, the trees rush past, the hands stay on the handlebar with slight vibration.",
    "20": "The colorful wing inflates and rises overhead as the helmeted instructor runs forward with the two characters in the harness, spectators watch.",
    "21": "The paraglider glides slowly across the sky over the valley, the wing and lines sway gently, the river and village pass slowly below, the camera slowly orbits.",
    "22": "Character 1 screams with wide eyes while character 2 cheers with raised fist, wind buffets the harness straps, the valley moves behind them.",
    "23": "The sun sinks slowly and the orange light glows on the stone wall, the two small characters sway their feet as they sit, the camera slowly drifts sideways.",
    "24": "The bluebird flaps and hovers, character 1 hugs character 2 tighter and shakes his head with a determined smile, warm sunset light.",
    "25": "The two characters jump up and high-five joyfully in slow motion, autumn leaves fly around them, the sunset glows through the arch.",
    "26": "A very slow, steady aerial drift over the sunset valley. The fortress gate stays small and far away on its hill, clouds drift, the light on the town slowly fades. Nothing moves toward the camera.",
}
# 말풍선과 장소 자막은 편집 단계에서 얹는다. 지시문에 글자를 넣지 않는다.


def frames(seconds):
    n = math.ceil((seconds + 0.5) * FPS)
    return n + (1 - n) % 4  # Wan은 4n+1 프레임만 받는다.


def main(only):
    sel = json.loads((a.CONTEST / "selection_v2.json").read_text(encoding="utf-8"))
    items = []
    for num, _, dur, *_ in a.timings():
        if only and num not in only:
            continue
        job = {"model_type": "i2v_2_2_lightning_contest", "prompt": MOTION[num] + (SCENERY_ONLY if num == "19" else KEEP),
               "image_prompt_type": "S", "image_start": Path(sel[num]).as_posix(), "resolution": "832x480",
               "video_length": frames(dur), "num_inference_steps": 4, "guidance_scale": 1, "guidance2_scale": 1, "seed": SEED + int(num)}
        items.append({"name": f"cut{num}", "job": job})
    assert items and all(i["job"]["video_length"] % 4 == 1 for i in items)
    req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"name": FOLDER, "title": f"컷 영상 {FOLDER}", "items": items, "start": True}).encode())
    print(urllib.request.urlopen(req).read().decode(), [(i["name"], i["job"]["video_length"]) for i in items])


if __name__ == "__main__":
    main(ONLY)

"""공모전 장면별 키프레임 일괄 생성(사진 없이 문장으로 배경 생성, Qwen-Image-Edit 2511 + 공식 캐릭터 이미지).
결과: jobs/contest/scenes_v1/<장면>/out/*.jpg, report.json. 기존 결과는 지우지 않고 폴더 이름을 바꿔 다시 만든다.
"""
import sys, time
import contest_test as t

t.OUT = t.ROOT / "jobs" / "contest" / (sys.argv[1] if len(sys.argv) > 1 else "scenes_v1")
t.REPORT = t.OUT / "report.json"

CH = ("Character 1 (image 1) is a chubby 3D boy in a light green hanbok with a dark navy belt, wearing a dark navy-gray "
      "official's hat with flat wings sticking out on both sides at ear height and two thin wire stems on top of the hat "
      "holding red apples and red omija berries. Character 2 (image 2) wears a round lime-green hooded costume with a "
      "scalloped face opening and white drawstrings, with a small dark navy hat on top of the hood that has thin wire "
      "stems holding red apples and omija berries. Keep both characters' design, proportions, line work and colors "
      "exactly as in their images, including every apple and berry stem on both hats; never add wings or anything else "
      "to character 2. Leave a clear gap between the two characters so the hat wings never overlap character 2. "
      "Slightly blurred background so the characters stand out clearly, cinematic 16:9 composition, no text.")

SCENES = [
    ("01_joseon_pass", "On a misty mountain pass in the Joseon dynasty, with an old stone path, pine trees and soft morning fog, "
     "the two characters look up in surprise at a small bluebird fluttering in front of them."),
    ("02_gate_timeslip", "The two characters hold hands with extended arms and walk toward an old Korean stone fortress gate with "
     "a wooden pavilion roof on an autumn mountain path; warm golden light glows from the gate's arch."),
    ("03_red_clay_trail", "On a wide red-clay walking trail in an autumn forest with red and yellow maple trees, character 2 holds up "
     "a selfie stick with a phone and waves at it, while character 1 walks barefoot beside, looking surprised."),
    ("04_drama_set", "In a Korean historical drama film set street with traditional tiled-roof houses and wooden gates, character 1 "
     "walks calmly with hands clasped behind his back, while character 2 laughs and points at him."),
    ("05_pottery", "Inside a traditional Korean pottery workshop with a wood-fired climbing kiln glowing orange in the background, "
     "character 1 shapes a tea bowl on a potter's wheel, and character 2 watches with sparkling eyes."),
    ("06_apple_orchard", "In a sunny apple orchard full of ripe red apples, character 2 happily holds up a big red apple with both "
     "hands, and character 1 compares the apples on his hat with the real apples on the tree."),
    ("07_rail_bike", "On an old railway track through autumn hills, the two characters ride a pedal rail bike; character 2 waves a "
     "small red pennant flag that says nothing, character 1 pedals happily."),
    ("08_paragliding", "High in the sky above autumn mountains and a small river valley, the two characters fly together under a "
     "colorful tandem paraglider, smiling and looking down at the view."),
    ("09_sunset_selfie", "At sunset in front of an old Korean stone fortress gate, character 1 holds a selfie stick and both "
     "characters pose together, warm orange light and long shadows."),
    ("10_welcome", "In front of an old Korean stone fortress gate on a bright autumn day, the two characters stand side by side "
     "facing the camera and wave both hands in welcome, big smiles."),
]


def main():
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for k, (name, scene) in enumerate(SCENES):
        if only and name[:2] not in only:
            continue
        t.run_step(name, {
            "model_type": "qwen_image_edit_plus2_20B", "prompt": scene + " " + CH, "video_prompt_type": "I",
            "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
            "resolution": "1280x720", "seed": t.SEED + 100 * (k + 1), "batch_size": 1,
        }, {".png", ".jpg", ".webp"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

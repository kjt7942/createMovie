"""장면 키프레임 재생성(v2): 1차에서 떨어진 장면의 지시문을 고치고 장면마다 시드 2개로 만들어 고른다.
사용: python tools/contest_scenes2.py <출력폴더> <장면번호들 예: 01,03,05>
"""
import sys, time
import contest_test as t
import contest_scenes as cs

t.OUT = t.ROOT / "jobs" / "contest" / sys.argv[1]
t.REPORT = t.OUT / "report.json"
HAT = (" Character 1's hat is a tall rounded dark official's cap (samo) with short flat wings at ear height, "
       "never a wide round brim. Both characters keep their small shoes. ")
FIX = {
    "01": "On a misty mountain pass in the Joseon dynasty, with an old stone path, pine trees and soft morning fog, the two characters stand side by side and look up in surprise at a small bluebird fluttering above them.",
    "03": "On a wide red-clay walking trail in an autumn forest with red and yellow maple trees, character 2 holds up a selfie stick with a phone and waves at it, while character 1 walks beside, smiling. Both wear their shoes.",
    "05": "Inside a bright, warmly lit traditional Korean pottery workshop with wooden shelves of tea bowls and a glowing kiln in the background, character 1 shapes a tea bowl on a potter's wheel, and character 2 stands beside him watching with sparkling eyes. Character 2's small hat stays firmly on top of the hood.",
    "06": "In a sunny apple orchard full of ripe red apples, character 2 happily holds up a big red apple with both hands, and character 1 stands beside pointing at the apples on the tree.",
    "07": "On old railway tracks through autumn hills, the two characters sit side by side on a four-wheeled pedal rail bike with two seats, both pedaling and smiling; character 2 waves a small red pennant flag with no text.",
    "08": "High in the sky above autumn mountains and a river valley, the two characters fly together under one colorful tandem paraglider canopy, harnessed side by side, smiling and looking down at the view.",
    "09": "At sunset in front of an old Korean stone fortress gate, character 1 holds a selfie stick with a phone and both characters pose together side by side, warm orange light.",
    "10": "In front of an old Korean stone fortress gate on a bright autumn day, the two characters stand side by side facing the camera and wave both hands in welcome, big smiles.",
}


def main():
    only = sys.argv[2].split(",")
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    names = {n[:2]: (k, n) for k, (n, _) in enumerate(cs.SCENES)}
    for num in only:
        k, name = names[num]
        scene = FIX.get(num) or cs.SCENES[k][1]
        for s in (1, 2):
            t.run_step(f"{name}_s{s}", {
                "model_type": "qwen_image_edit_plus2_20B", "prompt": scene + HAT + cs.CH, "video_prompt_type": "I",
                "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
                "resolution": "1280x720", "seed": t.SEED + 100 * (k + 1) + 17 * s, "batch_size": 1,
            }, {".png", ".jpg", ".webp"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

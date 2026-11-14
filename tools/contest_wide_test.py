"""풍경 중심 와이드샷 시험: 관광지가 화면을 채우고 캐릭터는 작게(화면 높이의 약 1/5). 결과: jobs/contest/wide_test/"""
import time
import contest_test as t
import contest_scenes as cs

t.OUT = t.ROOT / "jobs" / "contest" / "wide_test"
t.REPORT = t.OUT / "report.json"
SMALL = (" The two characters are SMALL in the frame, about one fifth of the image height, placed in the lower third; "
         "the landscape and landmark dominate the picture. ")
SHOTS = [
    ("w1_aerial_pass", "Cinematic aerial drone shot at dawn over a misty Joseon-era mountain pass with an old stone road winding "
     "through pine forests and autumn ridges; far below on the road the two characters walk side by side."),
    ("w2_gate_back", "Wide shot from behind: the two characters walk hand in hand on a stone path toward a huge old Korean stone "
     "fortress gate with a wooden pavilion roof; bright golden light pours through the open arch; autumn mountains around."),
    ("w3_railbike_side", "Wide side-view tracking shot of an old railway winding along a river valley full of red and yellow autumn "
     "trees; the two characters sit properly on a four-seat pedal rail bike with seats and handlebars, character 2 pedaling happily, character 1 gripping the handlebar in shock."),
    ("w4_paraglide_aerial", "Epic wide aerial view of a vast autumn valley with a river, villages and colorful mountains; a colorful "
     "tandem paraglider flies across the sky, flown by a human instructor pilot in a helmet seated behind; the two characters sit "
     "in front in a proper paragliding harness seat with visible shoulder and leg straps, both wearing white safety helmets."),
]


def main():
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for k, (name, shot) in enumerate(SHOTS):
        t.run_step(name, {
            "model_type": "qwen_image_edit_plus2_20B", "prompt": shot + SMALL + cs.CH.replace("Slightly blurred background so the characters stand out clearly, ", "Sharp, richly detailed landscape in deep focus, "), "video_prompt_type": "I",
            "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
            "resolution": "832x480", "seed": t.SEED + 500 + k, "batch_size": 1,
        }, {".png", ".jpg", ".webp"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()


if __name__ == "__main__":
    main()

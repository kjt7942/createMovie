"""3차 시험: 동이 모자 날개가 둥이 뒤로 겹쳐 '둥이에게 날개가 달린 것'처럼 보이는 문제 수정. 키프레임만 2가지. 결과는 jobs/contest/test3/."""
import time
import contest_test as t

t.OUT = t.ROOT / "jobs" / "contest" / "test3"
t.REPORT = t.OUT / "report.json"
BASE = (
    "Place the character from image 1 on the left and the character from image 2 on the right, walking side by side "
    "on an autumn mountain path toward an old Korean stone fortress gate with a wooden pavilion roof, lined with red "
    "and yellow maple trees. {gap} The first character's dark official hat has flat wings on both sides at ear height, "
    "exactly the length and shape shown in image 1, and the wings never overlap the second character. "
    "Keep both characters' design, proportions, line work and colors exactly as in their images; the second character "
    "has no wings. Natural soft daylight, slightly blurred background so the characters stand out clearly, cinematic 16:9 composition."
)
VARIANTS = [
    ("1_keyframe_apart", "They stand a little apart with a clear gap between them and reach out to hold hands with extended arms.", t.SEED),
    ("2_keyframe_threequarter", "They are seen at a slight three-quarter angle, holding hands, with enough space between them.", t.SEED + 7),
]


def main():
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for name, gap, seed in VARIANTS:
        t.run_step(name, {
            "model_type": "qwen_image_edit_plus2_20B", "prompt": BASE.format(gap=gap), "video_prompt_type": "I",
            "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
            "resolution": "1280x720", "seed": seed, "batch_size": 1,
        }, {".png", ".jpg", ".webp"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

"""2차 시험: 동이 모자 날개 보완(프롬프트) + Wan 2.2 Lightning 4스텝(Apache 2.0)으로 속도 측정. 결과는 jobs/contest/test2/."""
import time
import contest_test as t

t.OUT = t.ROOT / "jobs" / "contest" / "test2"
t.REPORT = t.OUT / "report.json"
t.KEYFRAME_PROMPT = t.KEYFRAME_PROMPT.replace(
    "Keep both characters' design",
    "The first character's dark official hat has long, wide, flat wings sticking straight out on both sides, exactly as in image 1. Keep both characters' design")


def main():
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    key = t.run_step("1_keyframe", {
        "model_type": "qwen_image_edit_plus2_20B", "prompt": t.KEYFRAME_PROMPT, "video_prompt_type": "I",
        "image_refs": [(t.REFS / "dongi_front.png").as_posix(), (t.REFS / "dungi_front.png").as_posix()],
        "resolution": "1280x720", "seed": t.SEED, "batch_size": 1,
    }, {".png", ".jpg", ".webp"})
    if key:
        t.run_step("2_video_lightning", {
            "model_type": "i2v_2_2_lightning_contest", "prompt": t.VIDEO_PROMPT, "image_prompt_type": "S",
            "image_start": key.as_posix(), "resolution": "1280x720", "video_length": 81,
            "num_inference_steps": 4, "guidance_scale": 1, "guidance2_scale": 1, "seed": t.SEED,
        }, {".mp4"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

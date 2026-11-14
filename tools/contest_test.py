"""공모전용 라이선스 안전 모델 시험 생성 (Qwen-Image-Edit 2511 → Wan 2.2 I2V 14B → ACE-Step 1.5).

처음 실행하면 Wan2GP가 모델을 내려받는다(약 60GB, 시간이 걸림). 단계마다 걸린 시간과 GPU 최고 온도를
jobs/contest/test/report.json 에 남긴다. GPU가 93°C를 3번 연속 넘으면 그 단계를 멈춘다.
실행: tools\\contest_test.bat (또는 python tools/contest_test.py)
"""
import json, os, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "studio"))
import engine  # noqa: E402

OUT = ROOT / "jobs" / "contest" / "test"
REFS = ROOT / "jobs" / "contest" / "refs"
REPORT = OUT / "report.json"
SEED = 20261130

KEYFRAME_PROMPT = (
    "Place the character from image 1 and the character from image 2 side by side, holding hands, walking toward "
    "an old Korean stone fortress gate with a wooden pavilion roof on an autumn mountain path lined with red and "
    "yellow maple trees. Keep both characters' design, proportions, line work and colors exactly as in their images. "
    "Natural soft daylight, slightly blurred background so the characters stand out clearly, cinematic 16:9 composition."
)
VIDEO_PROMPT = (
    "The two cute 3D characters walk hand in hand toward the old stone gate on the autumn mountain path, red and "
    "yellow leaves fall gently, warm golden light, the camera slowly follows behind them, smooth natural motion, "
    "the characters' design, colors and proportions stay exactly the same, no text."
)
MUSIC_CAPTION = (
    "bright cheerful Korean fusion instrumental, daegeum and gayageum melody over upbeat pop drums and bass, "
    "120 BPM, playful travel vlog mood, no vocals"
)

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}


def save():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def newest(folder, exts):
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in exts]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def run_step(name, job, exts):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    job_file = d / "job.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    log_path = d / "wgp.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    # --offline 없이 실행: 처음 쓰는 모델은 Wan2GP가 내려받는다.
    args = [str(engine.PY), "wgp.py", "--process", str(job_file), "--output-dir", str(d / "out")]
    step = {"name": name, "model": job["model_type"], "status": "running", "peak_temp": None}
    report["steps"].append(step); save()
    print(f"\n=== {name}: {job['model_type']} ===", flush=True)
    started = time.time()
    hot = [0]
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(args, cwd=engine.WAN, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

        def watch():
            while proc.poll() is None:
                g = engine.gpu_sample()
                if g and g["temp"] is not None:
                    step["peak_temp"] = max(step["peak_temp"] or 0, g["temp"])
                    hot[0] = hot[0] + 1 if g["temp"] >= engine.STOP_TEMP_C else 0
                    if hot[0] >= engine.STOP_SAMPLES:
                        step["stopped_hot"] = True
                        engine.kill_tree(proc.pid)
                        return
                time.sleep(5)
        threading.Thread(target=watch, daemon=True).start()
        while proc.poll() is None:
            el = int(time.time() - started)
            print(f"\r  진행 중... {el // 60}분 {el % 60}초, 최고 {step['peak_temp']}°C   ", end="", flush=True)
            time.sleep(10)
    step["seconds"] = round(time.time() - started)
    result = newest(d / "out", exts)
    step["status"] = "done" if proc.returncode == 0 and result else ("hot" if step.get("stopped_hot") else "failed")
    step["output"] = str(result) if result else None
    if step["status"] != "done":
        step["log_tail"] = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    save()
    print(f"\n  → {step['status']} ({step['seconds']}초, 최고 {step['peak_temp']}°C) {step['output'] or ''}", flush=True)
    return result


def main():
    # 자리를 비운 사이에도 돌도록 UAC가 필요한 전력 제한은 건너뛴다(부팅 작업이 걸어 둔 값이 있으면 그대로 쓴다).
    # 대신 93°C가 3번 연속이면 그 단계를 멈춘다.
    report["gpu_now"] = engine.gpu_sample()
    save()

    key = run_step("1_keyframe", {
        "model_type": "qwen_image_edit_plus2_20B", "prompt": KEYFRAME_PROMPT, "video_prompt_type": "I",
        "image_refs": [(REFS / "dongi_front.png").as_posix(), (REFS / "dungi_front.png").as_posix()],
        "resolution": "1280x720", "seed": SEED, "batch_size": 1,
    }, {".png", ".jpg", ".webp"})
    if key:
        run_step("2_video", {
            "model_type": "i2v_2_2", "prompt": VIDEO_PROMPT, "image_prompt_type": "S",
            "image_start": key.as_posix(), "resolution": "1280x720", "video_length": 81,
            "num_inference_steps": 20, "seed": SEED,
        }, {".mp4"})
    run_step("3_music", {
        "model_type": "ace_step_v1_5", "prompt": "[Instrumental]", "alt_prompt": MUSIC_CAPTION,
        "duration_seconds": 80, "seed": SEED,
    }, {".wav", ".mp3", ".flac", ".mp4"})
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    print("\n끝. 결과:", REPORT)


if __name__ == "__main__":
    main()

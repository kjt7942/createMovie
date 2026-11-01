"""Installs what AI video (H3) needs: pinned Wan2GP, its local patch, its Python environment and the models.
Safe to rerun: finished steps are skipped. The last step renders a short test, which also downloads the models.
Run: python tools/setup_h3.py"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402
from studio import engine  # noqa: E402

URL = "https://github.com/deepbeepmeep/Wan2GP.git"
PATCH = ROOT / "tools" / "wan2gp-offload.patch"
NEEDED_GB, REF_NEEDED_GB = 80, 25
WAN, PY = engine.WAN, engine.PY


def run(args, cwd=None):
    print(">", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def get_wan2gp():
    def git(*args):
        return subprocess.run(["git", "-C", str(WAN), *args], capture_output=True, text=True).stdout.strip()
    if WAN.exists() and (not (WAN / ".git").exists() or not git("rev-parse", "--short=8", "HEAD")):
        if (WAN / "ckpts").exists():
            raise SystemExit(f"Wan2GP 폴더가 손상되었습니다. 내려받은 모델이 있어 지우지 않습니다. 직접 확인해 주세요: {WAN}")
        print("중단된 설치로 보여 Wan2GP 폴더를 지우고 다시 받습니다.")
        shutil.rmtree(WAN)
    if not WAN.exists():
        run(["git", "clone", URL, WAN])
        run(["git", "-C", WAN, "checkout", engine.PINNED_COMMIT])
    head = git("rev-parse", "--short=8", "HEAD")
    if head != engine.PINNED_COMMIT:
        if not git("status", "--porcelain", "--untracked-files=no"):
            run(["git", "-C", WAN, "checkout", engine.PINNED_COMMIT])
        else:  # Dirty checkout: it may hold someone's work.
            print(f"주의: Wan2GP가 시험한 버전({engine.PINNED_COMMIT})이 아닙니다(현재 {head}). 그대로 둡니다.")
    offload = WAN / "mmgp" / "offload.py"
    if not offload.is_file():
        raise SystemExit(f"Wan2GP 파일이 없습니다({offload}). 설치가 불완전합니다. 설치를 다시 실행해 주세요.")
    if "info.BaseAddress or 0" not in offload.read_text(encoding="utf-8"):
        run(["git", "-C", WAN, "apply", "--ignore-whitespace", PATCH])


def install_environment():
    if PY.is_file():
        print("Wan2GP Python 환경 있음")
        return
    run([sys.executable, "setup.py", "install", "--env", "venv", "--auto"], cwd=WAN)
    if not PY.is_file():
        raise SystemExit(f"Wan2GP Python 환경을 만들지 못했습니다: {PY}")


def set_tested_config():
    config = WAN / "wgp_config.json"
    data = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    if data.get("int8_kernels") != "triton":
        data["int8_kernels"] = "triton"
        config.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def first_run():
    """Runs Wan2GP online once per model type. A missing model downloads on load, unlike the studio's --offline runs."""
    done = {"video": (WAN / "ckpts" / engine.MODEL_FILE).is_file() and engine.FFMPEG.is_file(),
            "music": (WAN / "ckpts" / "stable_audio3_small_music_bf16.safetensors").is_file(),
            "character": (WAN / "ckpts" / engine.REF_MODEL_FILE).is_file()}
    jobs = {
        "video": {"model_type": engine.MODEL, "prompt": "integrated_multimodal_description: A small yellow chick stands on green grass.\n"
                  "overall_soundscape: Soft wind.\nnon_diegetic_music: None. No music, sound effects only.",
                  "resolution": "480x832", "video_length": engine.MIN_FRAMES, "seed": 1, "num_inference_steps": engine.STEPS, "image_prompt_type": "T"},
        "music": engine.music_job({"music": "Gentle cheerful marimba at 110 BPM."}, 5, 1),
    }
    with tempfile.TemporaryDirectory() as tmp:
        ref = Path(tmp) / "ref.png"
        Image.new("RGB", (512, 512), "gold").save(ref)
        jobs["character"] = dict(jobs["video"], model_type=engine.REF_MODEL, video_prompt_type="I", image_refs=[ref.as_posix()],
                                 prompt="subject_definitions:\n<Subject 1> is the yellow square in <Picture 1>.\nsummary:\n[reference generation] <Subject 1> rests on green grass.\n"
                                        "retention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved.\ndetailed_description:\n[Shot 1] <Subject 1> rests on green grass.\n"
                                        "overall_soundscape: Soft wind.\nnon_diegetic_music: None. No music, sound effects only.")
        for name, job in jobs.items():
            if done[name]:
                print(f"모델 있음({name})")
                continue
            print(f"모델을 내려받고 시험합니다({name}). 처음에는 오래 걸립니다.", flush=True)
            path = Path(tmp) / f"{name}.json"
            path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
            run([PY, "wgp.py", "--process", path, "--output-dir", Path(tmp) / name], cwd=WAN)


def main():
    state = engine.availability()
    if not state["gpu_ok"]:
        raise SystemExit("\n".join(state["reasons"]))
    if not shutil.which("git"):
        raise SystemExit("Git이 필요합니다. setup.bat을 먼저 실행하세요.")
    free = shutil.disk_usage(ROOT).free / 2 ** 30
    needed = NEEDED_GB if not (WAN / "ckpts" / engine.MODEL_FILE).is_file() else REF_NEEDED_GB if not (WAN / "ckpts" / engine.REF_MODEL_FILE).is_file() else 0
    if free < needed:
        raise SystemExit(f"디스크 여유가 {free:.0f}GB입니다. 약 {needed}GB가 필요합니다.")
    get_wan2gp()
    install_environment()
    set_tested_config()
    first_run()
    state = engine.availability()
    if not state["ok"]:
        raise SystemExit("설치 후 점검 실패: " + " ".join(state["reasons"]))
    print("AI 영상 생성 도구 설치 완료")


if __name__ == "__main__":
    main()

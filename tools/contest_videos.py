"""선정한 장면 이미지(jobs/contest/selection.json)를 Wan 2.2 Lightning 4스텝(Apache 2.0)으로 5초 영상으로 만든다.
결과: jobs/contest/<출력폴더>/<장면>/out/*.mp4. 사용: python tools/contest_videos.py videos_v1 [장면번호들]
"""
import json, sys, time
import contest_test as t

t.OUT = t.ROOT / "jobs" / "contest" / (sys.argv[1] if len(sys.argv) > 1 else "videos_v1")
t.REPORT = t.OUT / "report.json"
KEEP = (" The two cute 3D characters keep exactly the same design, colors and proportions, including the dark official hat "
        "with short side wings and the apple and berry stems on both hats. Smooth natural motion, no text.")
MOTION = {
    "01": "The two characters look up in surprise as the small bluebird flutters around above them and chirps, soft fog drifts along the mountain path, the camera slowly pushes in.",
    "02": "The two characters walk hand in hand toward the stone gate, the golden light in the arch grows brighter and spreads warmly over the autumn path, the camera follows slowly behind them.",
    "03": "Character 1 walks forward on the red clay trail holding the selfie stick and waving at the phone, character 2 follows happily behind, maple leaves drift down.",
    "04": "Character 1 strolls calmly along the drama set street with hands behind his back, character 2 laughs and points at him, the camera tracks sideways.",
    "05": "The potter's wheel spins as character 1 gently shapes the clay tea bowl, character 2 watches and claps happily, the kiln fire flickers in the background.",
    "06": "Character 1 lifts the big red apple up happily, character 2 points at the apples on the tree and smiles, leaves sway in a light breeze.",
    "07": "The rail bike rolls forward along the tracks, character 1 waves the red flag in the wind, the autumn hills pass by, the camera moves backward in front of them.",
    "08": "The two characters glide smoothly under the paraglider, swinging their little feet, the autumn valley and river slowly pass below, the camera slowly orbits.",
    "09": "Character 1 raises the selfie stick and both characters lean together and smile for the photo, the sunset glow shimmers behind the gate.",
    "10": "The two characters wave both hands at the camera and bounce happily in front of the gate, autumn leaves float in the air.",
}


def main():
    sel = json.loads((t.ROOT / "jobs" / "contest" / "selection.json").read_text(encoding="utf-8"))
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else sorted(sel)
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for num in only:
        t.run_step(f"scene{num}", {
            "model_type": "i2v_2_2_lightning_contest", "prompt": MOTION[num] + KEEP, "image_prompt_type": "S",
            "image_start": (t.ROOT / sel[num]).as_posix(), "resolution": "1280x720", "video_length": 81,
            "num_inference_steps": 4, "guidance_scale": 1, "guidance2_scale": 1, "seed": t.SEED + int(num),
        }, {".mp4"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

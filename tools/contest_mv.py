"""2차 기획 〈출사동이, 문경새재 넘어 장원급제〉 노래 + 미니어처 디오라마 화면. 크무 대기열(공모전 모드)로 보낸다.
사용:
  python tools/contest_mv.py song <폴더>      ACE-Step 1.5로 60초 노래 4안
  python tools/contest_mv.py keys <폴더>      Qwen Edit로 1280x720 키프레임 (장면마다 시드 2개)
  python tools/contest_mv.py video <폴더> <키프레임 선택 json>   Wan 2.2 Lightning 720p 5초 영상
사실 확인(2026-11-03): 죽령은 '죽죽 떨어진다', 문경 지명은 '경사스러운 소식을 듣는다'고 전해진다.
"""
import json, sys, urllib.request
from pathlib import Path

stage, folder = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
sys.argv = [sys.argv[0], "storyboard_v1"]  # contest_storyboard는 인자를 폴더로 읽는다. 캐릭터 문구(CH)만 가져온다.
import contest_storyboard as sb  # noqa: E402

SEED = 20261200
LYRICS = """[verse]
한양 가는 과거길 어느 고개 넘을까
추풍령은 추풍낙엽 죽령은 죽죽 떨어져

[chorus]
문경새재 넘어가세 경사 소식 들려오네
출사동이 출사둥이 장원급제 얼씨구나

[verse]
황토길을 맨발로 찻사발에 사과 한 입
철로 위를 달려가고 하늘 높이 날아 보세

[chorus]
문경새재 넘어가세 경사 소식 들려오네
출사동이 출사둥이 장원급제 얼씨구나

[outro]
문경으로 오세요"""
CAPTION = ("catchy cheerful Korean pop song with a playful trot and gugak flavor, cute bright male and female duet vocals singing in Korean, "
           "daegeum, gayageum and janggu over bouncy pop drums and bass, 120 BPM, very catchy sing-along chorus, kids TV jingle energy")

STYLE = (" Tilt-shift miniature diorama photograph: a handcrafted tabletop model made of clay, felt, painted wood and paper, "
         "tiny felt trees in red and yellow autumn colors, shallow depth of field with blurred edges, soft warm studio light, "
         "everything looks like a toy world. The two characters are glossy vinyl toy figures standing in the diorama. "
         "The fortress gate, if shown, is a toy model of one wall of rough grey stones with a single rounded arch, topped by one small wooden "
         "pavilion with a grey tiled Korean roof; no pagoda, no towers. No text.")
KEYS = {
    "k1_pass": "Wide high-angle view of a miniature mountain pass diorama: a tiny winding stone path climbs through felt maple trees toward the toy fortress gate; the two characters walk up the path, character 1 carries a rolled paper scroll under his arm.",
    "k2_exam": "Medium shot inside the diorama: character 1 kneels at a tiny low wooden desk and writes with a brush on a long white paper scroll with a very serious face, character 2 peeks over his shoulder and cheers with both fists; tiny paper flags and a toy tent behind.",
    "k3_pass_exam": "Medium shot in front of the toy fortress gate: character 1 proudly holds up an unrolled paper certificate with a big red seal, tiny paper maple leaves fall like confetti, character 2 jumps with joy beside him.",
}
VIDEO = {
    "k1_pass": "The camera cranes slowly down and forward over the miniature diorama while the two toy figures walk up the winding path toward the gate, felt leaves drift down.",
    "k2_exam": "Character 1 writes quickly with the brush in exaggerated strokes, then lifts the brush proudly; character 2 bounces and cheers; the camera slowly pushes in.",
    "k3_pass_exam": "Character 1 raises the certificate high and bows, paper maple leaves keep falling like confetti, character 2 jumps up and down with joy, the camera slowly orbits a little.",
}
KEEP = (" The two characters keep exactly the same design, colors and proportions as toy figures, including the dark official hat with short "
        "side wings and the apple and berry stems on both hats. Stop-motion toy diorama look, smooth motion, no text.")


def submit(items, title):
    req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"name": folder, "title": title, "items": items, "start": True}).encode())
    print(urllib.request.urlopen(req).read().decode(), [i["name"] for i in items])


if stage == "song":
    submit([{"name": f"song_s{k}", "job": {"model_type": "ace_step_v1_5", "prompt": LYRICS, "alt_prompt": CAPTION,
                                           "duration_seconds": 60, "seed": SEED + k}} for k in range(1, 5)], "노래 4안")
elif stage == "keys":
    refs = [(sb.t.REFS / f).as_posix() for f in ("dongi_front.png", "dungi_front.png")]
    submit([{"name": f"{name}_s{sd}", "job": {"model_type": "qwen_image_edit_plus2_20B", "prompt": shot + STYLE + sb.CH,
                                               "video_prompt_type": "I", "image_refs": refs, "resolution": "1280x720",
                                               "seed": SEED + 10 * sd + n, "batch_size": 1}}
            for n, (name, shot) in enumerate(KEYS.items()) for sd in (1, 2)], "미니어처 키프레임")
elif stage == "video":
    picks = json.loads(Path(extra[0]).read_text(encoding="utf-8"))
    submit([{"name": name, "job": {"model_type": "i2v_2_2_lightning_contest", "prompt": VIDEO[name] + KEEP, "image_prompt_type": "S",
                                   "image_start": Path(picks[name]).as_posix(), "resolution": "1280x720", "video_length": 81,
                                   "num_inference_steps": 4, "guidance_scale": 1, "guidance2_scale": 1, "seed": SEED + 100 + n}}
            for n, name in enumerate(VIDEO) if name in picks], "미니어처 시험 영상")

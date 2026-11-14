"""cuts_v3.json의 이미지 컷을 480p 시안으로 서비스 대기열(공모전 배치)에 보낸다. 컷당 시드 2개.
사용: python tools/contest_conti_run.py <배치이름 예: storyboard_v5> [컷들 예: c01,c04] [--model z_image]
--model: 풍경 컷(참조 없는 컷)의 모델을 바꿔 비교용으로 만든다. 결과: jobs/contest/<배치이름>/<컷>_s<n>/out/
진행: http://127.0.0.1:5000/batch
"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261130
REFS = ROOT / "jobs" / "contest" / "refs"
PLACES = ROOT / "jobs" / "contest" / "refs_places"  # tools/contest_refs_place.py가 만든 장소 대표 사진(컷당 3장)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
name = args[0]
only = set(args[1].split(",")) if len(args) > 1 else None
alt = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
if alt and alt in args:
    args.remove(alt)  # --model 값이 컷 목록으로 읽히지 않게
    only = set(args[1].split(",")) if len(args) > 1 else None

cuts = json.loads((ROOT / "jobs" / "contest" / "conti_v3" / "cuts_v3.json").read_text(encoding="utf-8"))
items = []
for c in cuts:
    if c["model"] == "-" or (only and c["id"] not in only) or (alt and c["refs"]):
        continue
    n = int("".join(ch for ch in c["id"][1:] if ch.isdigit()))
    chars = [(REFS / f).as_posix() for f in c["refs"]]
    places = sorted(PLACES.glob(f"{c['id']}_*.jpg"))[: max(0, 3 - len(chars))]  # 편집 모델은 이미지 3장까지
    for s in (1, 2):
        prompt, model = c["prompt"], alt or c["model"]
        if places and not alt:  # 장소 실사 참조가 있으면 편집 모델로 사진 특징을 따라 그린다
            a, z = len(chars) + 1, len(chars) + len(places)
            prompt = (f"Image{'s' if z > a else ''} {a}{'-' + str(z) if z > a else ''} {'are' if z > a else 'is a'} real photograph{'s' if z > a else ''} of the actual place in Mungyeong, Korea. "
                      "Reproduce the place's real appearance faithfully (structures, colors, terrain, materials, vegetation) as shown, but seen from the camera angle and framing described next. ") + prompt
            model = "qwen_image_edit_plus2_20B"
        if chars and not alt:  # 시험에서 동이가 빠지거나 인물이 늘어난 일이 있어 인원을 못 박는다
            who = " and ".join(f"character {k} (image {k})" for k in range(1, len(chars) + 1))
            prompt += f" Exactly {len(chars)} character{'s' if len(chars) > 1 else ''} appear in the image: {who}, each exactly once and clearly visible; no other people."
        job = {"model_type": model, "prompt": prompt, "resolution": "832x480", "seed": SEED + 1000 * s + n, "batch_size": 1}
        refs = chars + ([p.as_posix() for p in places] if places and not alt else [])
        if refs:
            job["video_prompt_type"] = "I"
            job["image_refs"] = refs
        items.append({"name": f"{c['id']}_s{s}", "job": job})
body = {"name": name, "title": f"콘티 v3 시안 {name}", "items": items, "start": True}
req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"},
                             data=json.dumps(body).encode())
print(len(items), "items:", urllib.request.urlopen(req).read().decode()[:300])

"""컷별 장소 참조 사진(분석 때 고른 대표 3장)을 임시 폴더에서 jobs/contest/refs_places/로 복사하고 출처 목록을 남긴다.
사진 번호는 시트(1~6, 왼쪽 위부터)에서 사람 얼굴·글자·포스터가 적고 장소 특징이 잘 보이는 것으로 골랐다. 출처 URL은 AI 사용내역 제출용.
사용: python tools/contest_refs_place.py
"""
import json, shutil
from pathlib import Path

TMP = Path.home() / "AppData" / "Local" / "Temp" / "mg_refs"
OUT = Path(__file__).resolve().parent.parent / "jobs" / "contest" / "refs_places"
PICK = {
    "c01": (1, 3, 4), "c03": (3, 2, 5), "c04": (1, 2, 5), "c05": (2, 3, 4), "c06": (4, 2, 1), "c07": (1, 2, 3), "c08": (1, 5, 6),
    "c09": (3, 4, 5), "c10": (1, 2, 5), "c11": (2, 3, 6), "c12": (1, 3, 4), "c13": (1, 2, 3), "c14": (1, 3, 4), "c15": (1, 4, 5),
    "c16": (1, 3, 6), "c17": (2, 3, 6), "c18": (3, 2, 1), "c19": (1, 2, 3), "c20": (1, 3, 5), "c21": (4, 5, 6), "c22b": (1, 4, 6),
    "c23": (2, 3, 6), "c25": (1, 3, 4),
}
SRC_OF = {"c22b": "c22", "c25": "c01"}  # 사진 묶음 이름이 다른 컷
srcs = json.loads((TMP / "sources.json").read_text(encoding="utf-8"))
srcs.update(json.loads((TMP / "sources_c15.json").read_text(encoding="utf-8")))
OUT.mkdir(parents=True, exist_ok=True)
log = {}
for cut, idx in PICK.items():
    d = SRC_OF.get(cut, cut)
    for k, n in enumerate(idx, 1):
        shutil.copy(TMP / d / f"{n:02d}.jpg", OUT / f"{cut}_{k}.jpg")
        s = next((x for x in srcs.get(d, []) if x["n"] == n), {})
        log.setdefault(cut, []).append({"file": f"{cut}_{k}.jpg", "from_search_set": d, "n": n, "page": s.get("page", ""), "title": s.get("title", "")})
(OUT / "sources.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(PICK), "cuts,", sum(len(v) for v in log.values()), "files ->", OUT)

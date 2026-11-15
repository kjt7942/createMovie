"""예전 폴더를 projects/<날짜시분초_이름>/ 한 곳으로 옮긴다.

옮기는 것: jobs/<12자리 ID>(홍보 영상), jobs/studio/<ID>(AI 영상), jobs/characters/<ID>(캐릭터),
          jobs/content/<이름>·jobs/contest/<이름> 중 batch.json이 있는 폴더(콘텐츠 생성, 캐릭터 시안).
이름: 홍보 영상은 plan.json의 제목, AI 영상은 script.title, 캐릭터는 이름, 배치는 제목. 시각은 만든 때(폴더 생성 시각).
옮긴 폴더 안의 JSON은 예전 ID와 예전 절대 경로를 새 것으로 고친다(캐릭터 ID, 배치 이름, 이미지 경로 등).
사용: python tools/migrate_projects.py [--dry-run]      자체 점검: python tools/migrate_projects.py --selftest
"""
import json, os, re, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from studio import ids  # noqa: E402

HEX = re.compile(r"\b[0-9a-f]{12}\b")
BATCH_STAMP = re.compile(r"^c?h?(\d{8})_(\d{6})")


def _born(path):
    st = Path(path).stat()
    return getattr(st, "st_birthtime", None) or st.st_ctime  # Windows는 st_ctime이 만든 시각


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _batch_time(name, path):
    m = BATCH_STAMP.match(name)
    if m:
        try:
            return time.mktime(time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
        except ValueError:
            pass
    return _born(path)


def plan_moves(root):
    """[(예전 폴더, 새 폴더 이름)]을 정한다. 예전 이름과 새 이름의 대응도 함께."""
    jobs, proj = root / "jobs", root / "projects"
    found, taken = [], set()

    def add(old, name, default, when):
        nid = ids.new_id(name, default, root=proj, now=when)
        while nid in taken:
            nid += "_x"
        taken.add(nid)
        (proj / nid).exists()  # new_id가 이미 있는 폴더는 피했다
        found.append((old, nid))

    for d in sorted(jobs.iterdir()) if jobs.is_dir() else []:   # 홍보 영상
        if HEX.fullmatch(d.name) and (d / "meta.json").exists():
            add(d, _json(d / "plan.json").get("title"), "홍보영상", _born(d))
    for d in sorted((jobs / "studio").iterdir()) if (jobs / "studio").is_dir() else []:   # AI 영상
        if HEX.fullmatch(d.name) and (d / "project.json").exists():
            p = _json(d / "project.json")
            add(d, (p.get("script") or {}).get("title"), "AI영상", p.get("created") or _born(d))
    for d in sorted((jobs / "characters").iterdir()) if (jobs / "characters").is_dir() else []:   # 캐릭터
        if HEX.fullmatch(d.name) and (d / "character.json").exists():
            c = _json(d / "character.json")
            add(d, c.get("name"), "캐릭터", c.get("created") or _born(d))
    batches = []
    for sub in ("content", "contest"):   # 콘텐츠 생성, 캐릭터 시안
        for d in sorted((jobs / sub).iterdir()) if (jobs / sub).is_dir() else []:
            if (d / "batch.json").exists():
                batches.append(d)
    by_name = {}
    for d in sorted(batches, key=lambda p: len(p.name)):   # 기본 배치가 먼저: <이름>_v, <이름>_r1은 기본 배치 새 이름에 접미사만 붙인다
        m = re.fullmatch(r"(.+?)(_v|_r\d+)", d.name)
        if m and m.group(1) in by_name:
            nid = by_name[m.group(1)] + m.group(2)
            found.append((d, nid)); taken.add(nid); by_name[d.name] = nid
            continue
        add(d, _json(d / "batch.json").get("title") or d.name, "콘텐츠", _batch_time(d.name, d))
        by_name[d.name] = found[-1][1]
    return found


def _rewrite(value, mapping, paths):
    """JSON 값 안의 예전 경로·ID를 새 것으로."""
    if isinstance(value, str):
        for old, new in paths:
            value = value.replace(old, new)
        if value in mapping:
            return mapping[value]
        return HEX.sub(lambda m: mapping.get(m.group(0), m.group(0)), value)
    if isinstance(value, list):
        return [_rewrite(v, mapping, paths) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite(v, mapping, paths) for k, v in value.items()}
    return value


def migrate(root, dry_run=False):
    root = Path(root)
    moves = plan_moves(root)
    mapping = {old.name: new for old, new in moves}
    proj = root / "projects"
    report = []
    for old, new in moves:
        report.append(f"{old.relative_to(root)}  ->  projects/{new}")
        if dry_run:
            continue
        proj.mkdir(exist_ok=True)
        dst = proj / new
        shutil.move(str(old), str(dst))
        paths = [(str(old), str(dst)), (old.as_posix(), dst.as_posix()),
                 (str(old).replace("\\", "\\\\"), str(dst).replace("\\", "\\\\"))]
        for f in dst.rglob("*.json"):
            if f.stat().st_size > 20 * 1024 * 1024:
                continue
            data = _json(f)
            if not data:
                continue
            fixed = _rewrite(data, mapping, paths)
            if fixed != data:
                f.write_text(json.dumps(fixed, ensure_ascii=False, indent=1), encoding="utf-8")
    if not dry_run:
        for sub in ("studio", "characters", "content", "contest"):   # 비게 된 예전 상위 폴더 정리
            d = root / "jobs" / sub
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    return report


def selftest():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        jobs = root / "jobs"
        (jobs / "1ce6f42ae64e").mkdir(parents=True)
        (jobs / "1ce6f42ae64e" / "meta.json").write_text('{"photos": []}')
        (jobs / "1ce6f42ae64e" / "plan.json").write_text(json.dumps({"title": "가족 캠프 홍보"}, ensure_ascii=False))
        (jobs / "1ce6f42ae64e" / ".hyperframes").mkdir()
        (jobs / "1ce6f42ae64e" / ".hyperframes" / "video-state.json").write_text(json.dumps({"dir": str(jobs / "1ce6f42ae64e")}))
        ch = jobs / "characters" / "aaaaaaaaaaaa"
        ch.mkdir(parents=True)
        (ch / "character.json").write_text(json.dumps({"id": "aaaaaaaaaaaa", "name": "동이", "created": 1760000000}, ensure_ascii=False))
        pr = jobs / "studio" / "bbbbbbbbbbbb"
        pr.mkdir(parents=True)
        (pr / "project.json").write_text(json.dumps({"id": "bbbbbbbbbbbb", "created": 1760000100, "script": {"title": "동이의 하루"},
                                                     "characters": ["aaaaaaaaaaaa"]}, ensure_ascii=False))
        b = jobs / "content" / "ch20261102_153000_0ab"
        (b / "inputs").mkdir(parents=True)
        (b / "batch.json").write_text(json.dumps({"name": "ch20261102_153000_0ab", "title": "캐릭터 동이 · 정면",
                                                  "items": [{"job": {"image_refs": [(b / "inputs" / "ref_0.png").as_posix()]}}]}, ensure_ascii=False))
        v = jobs / "content" / "ch20261102_153000_0ab_v"
        v.mkdir()
        (v / "batch.json").write_text(json.dumps({"name": "ch20261102_153000_0ab_v", "title": "캐릭터 동이 · 다른 시점", "items": []}, ensure_ascii=False))
        (jobs / "contest" / "refs").mkdir(parents=True)   # batch.json이 없는 작업 폴더는 건드리지 않는다
        assert len(migrate(root, dry_run=True)) == 5 and (jobs / "1ce6f42ae64e").exists(), "dry-run must not move"
        migrate(root)
        names = sorted(p.name for p in (root / "projects").iterdir())
        assert len(names) == 5 and all(ids.VALID.match(n) for n in names), names
        promo = next(n for n in names if n.endswith("가족_캠프_홍보"))
        assert "1ce6f42ae64e" not in (root / "projects" / promo / ".hyperframes" / "video-state.json").read_text() and promo in (root / "projects" / promo / ".hyperframes" / "video-state.json").read_text().replace("\\\\", "\\")
        cname = next(n for n in names if n.endswith("동이") and (root / "projects" / n / "character.json").exists())
        assert _json(root / "projects" / cname / "character.json")["id"] == cname
        pname = next(n for n in names if n.endswith("동이의_하루"))
        assert _json(root / "projects" / pname / "project.json")["characters"] == [cname] and _json(root / "projects" / pname / "project.json")["id"] == pname
        base = next(n for n in names if n.endswith("캐릭터_동이_·_정면"))
        assert any(n == base + "_v" for n in names), names
        ref = _json(root / "projects" / base / "batch.json")["items"][0]["job"]["image_refs"][0]
        assert ref.startswith((root / "projects" / base).as_posix()) and Path(ref).parent.exists(), ref
        assert (jobs / "contest" / "refs").exists() and not (jobs / "studio").exists() and not (jobs / "characters").exists()
        print("OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        for line in migrate(ROOT, dry_run="--dry-run" in sys.argv) or ["옮길 예전 폴더가 없습니다."]:
            print(line)

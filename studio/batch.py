"""Wan2GP batches (image, video, speech, music) in the one queue, so they never overlap H3 or promo renders.

A batch is <root>/<name>/batch.json plus one <item>/ folder per job (job.json, out/). Items with one model run in one
Wan2GP process, so the model loads once. Every batch folder lives in projects/<date+time_name>/; a batch.json "contest" flag marks the ones that only take CONTEST_MODELS, others take any model. Finished items are never redone, so a stopped or failed batch continues where it was.
"""
import functools, json, os, random, re, shutil, subprocess, threading, time
from pathlib import Path

from . import engine, ids

CONTEST_ROOT = CONTENT_ROOT = ids.PROJECTS  # 한 폴더(projects/) 아래에 프로젝트 단위로. 공모전용 여부는 batch.json의 "contest" 값
# Commercial use allowed and Korea not excluded, checked on each model's official page on 2026-11-02 (Apache 2.0 or MIT).
# Left out on purpose: H3, Hunyuan (Korea excluded); MMAudio, FLUX.2 klein 9B (non-commercial); LTX-2, Stable Audio 3 (revenue limits).
CONTEST_MODELS = {"i2v_2_2", "i2v_2_2_lightning_contest", "t2v_2_2", "ti2v_2_2", "flf2v_720p", "infinitetalk",
                  "qwen_image_2512_20B", "qwen_image_edit_plus2_20B", "z_image", "flux2_klein_4b",
                  "ace_step_v1_5", "qwen3_tts_voicedesign"}
CONTEST_UPSCALERS = ("seedvr2", "flashvsr", "lanczos")
CONTEST_INTERPOLATORS = ("rife",)
SAFE_NAME = re.compile(r'(?!\.)[^\\/:*?"<>|\x00-\x1f\s]{1,80}')  # 한글 폴더 이름 허용. 경로 문자·공백·맨 앞 점은 안 된다
PROMO_ID = re.compile(r"[0-9a-f]{12}")  # 예전 홍보 영상 ID와 겹치는 이름은 막는다.
SECONDS_PER_ITEM = 165
POLL_S = 2  # Must stay shorter than one task: results go to the task that last completed.
SILENCE_S = 30 * 60  # One hung item must not hold the whole queue.
_lock = threading.Lock()


def _dir(name, contest=None):
    if not SAFE_NAME.fullmatch(name or "") or PROMO_ID.fullmatch(name):
        raise engine.StudioError("배치 이름이 잘못됐습니다.")
    if contest is None:
        contest = not (CONTENT_ROOT / name / "batch.json").exists()
    return (CONTEST_ROOT if contest else CONTENT_ROOT) / name


def contest_allows(job):
    """Post-processing jobs have no model_type: only the upscalers and interpolators with a checked license pass."""
    if job.get("mode") == "edit_postprocessing":
        up, frames = str(job.get("spatial_upsampling") or ""), str(job.get("temporal_upsampling") or "")
        return (not up or up.startswith(CONTEST_UPSCALERS)) and (not frames or frames.startswith(CONTEST_INTERPOLATORS))
    return not job.get("mode") and job.get("model_type") in CONTEST_MODELS


@functools.lru_cache(maxsize=1)
def models():
    """Every model Wan2GP knows, for the picker. The file name is the model_type."""
    out = []
    for folder in (engine.WAN / "defaults", engine.WAN / "finetunes"):
        for f in sorted(folder.glob("*.json")):
            try:
                name = json.loads(f.read_text(encoding="utf-8")).get("model", {}).get("name") or f.stem
            except (OSError, ValueError):
                continue  # One broken file must not hide the others.
            out.append({"id": f.stem, "name": name, "contest": f.stem in CONTEST_MODELS})
    return out


def load(name):
    try:
        return json.loads((_dir(name) / "batch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise engine.StudioError("없는 배치입니다.")


def _save(b):
    f = _dir(b["name"], b.get("contest", True)) / "batch.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def _update(name, **kw):
    with _lock:
        b = load(name)
        b.update(kw)
        _save(b)


def _update_item(name, item_name, **kw):
    with _lock:
        b = load(name)
        next(i for i in b["items"] if i["name"] == item_name).update(kw)
        _save(b)


def _newest(folder, since=0):
    files = [p for p in Path(folder).rglob("*") if p.is_file() and p.stat().st_mtime >= since]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def create(name, title, items, contest=True):
    """Keeps an existing result only when its job.json is identical, so changed prompts are generated again."""
    d = _dir(name, contest)
    other = _dir(name, not contest)
    if other != d and (other / "batch.json").exists():   # 폴더가 둘로 나뉜 예전 구성에서만 해당
        raise engine.StudioError("같은 이름의 배치가 이미 있습니다.")
    if not items:
        raise engine.StudioError("작업이 없습니다.")
    seen = set()
    for it in items:
        if not SAFE_NAME.fullmatch(str(it.get("name"))) or it["name"] in seen:
            raise engine.StudioError(f"작업 이름이 잘못됐거나 겹칩니다: {it.get('name')}")
        seen.add(it["name"])
        job = it.get("job")
        if not isinstance(job, dict) or not (job.get("model_type") or job.get("mode")):
            raise engine.StudioError(f"모델이 지정되지 않았습니다: {it['name']}")
        if contest and not contest_allows(job):
            raise engine.StudioError(f"공모전에 쓸 수 없는 모델입니다: {it['name']}")
    with _lock:
        if (d / "batch.json").exists() and json.loads((d / "batch.json").read_text(encoding="utf-8"))["state"] in ("queued", "running"):
            raise engine.StudioError("대기 중이거나 생성 중인 배치는 바꿀 수 없습니다.")
        d.mkdir(parents=True, exist_ok=True)
        out = []
        for it in items:
            old_job, sub = None, d / it["name"]
            try:
                old_job = json.loads((sub / "job.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            result = _newest(sub / "out") if old_job == it["job"] else None
            out.append({"name": it["name"], "job": it["job"], "status": "done" if result else "pending", "output": str(result) if result else None,
                        "seconds": None, "peak_temp": None, "error": ""})
        b = {"name": name, "title": title or name, "contest": bool(contest), "state": "ready", "message": "", "queued_at": 0, "items": out}
        _save(b)
    return b


UPLOADS = {"start_image": (".png", ".jpg", ".jpeg", ".webp"), "ref_images": (".png", ".jpg", ".jpeg", ".webp"), "audio": (".wav", ".mp3", ".flac")}


def create_from_form(form, files):
    """The page's form. Empty fields stay out of the job, so the model's own defaults apply. Returns the batch name."""
    model = form.get("model", "").strip()
    if model not in {m["id"] for m in models()}:
        raise engine.StudioError("모델을 목록에서 고르세요.")
    job = {"model_type": model}
    for key in ("prompt", "alt_prompt", "resolution", "video_length"):
        if form.get(key, "").strip():
            job[key] = form[key].strip()
    if form.get("video_length", "").strip().isdigit():
        job["video_length"] = int(form["video_length"])
    try:
        extra = json.loads(form.get("extra") or "{}")
        seed = int(form.get("seed") or random.randrange(2 ** 31))
        count = max(1, min(20, int(form.get("count") or 1)))
    except ValueError:
        raise engine.StudioError("추가 설정(JSON), 시드, 개수 형식이 잘못됐습니다.")
    if not isinstance(extra, dict):
        raise engine.StudioError("추가 설정은 JSON 객체여야 합니다.")
    contest = form.get("contest") == "1"
    title = form.get("title", "").strip() or f"{model} · {job.get('prompt', '')[:30]}"
    name = ids.new_id(form.get("title", "").strip() or model, "콘텐츠", root=CONTENT_ROOT)   # 날짜시분초_이름
    inputs = _dir(name, contest) / "inputs"
    saved = {}
    for field, exts in UPLOADS.items():
        for n, f in enumerate(files.get(field, [])):
            ext = Path(f.filename or "").suffix.lower()
            if not f.filename:
                continue  # A file input left empty still arrives as a nameless part.
            if ext not in exts:
                raise engine.StudioError(f"지원하지 않는 파일입니다: {f.filename}")
            inputs.mkdir(parents=True, exist_ok=True)
            path = inputs / f"{field}_{n}{ext}"
            f.save(path)
            saved.setdefault(field, []).append(path.as_posix())
    if saved.get("start_image"):
        job.update(image_prompt_type="S", image_start=saved["start_image"][0])
    if saved.get("ref_images"):
        job.update(video_prompt_type="I", image_refs=saved["ref_images"])
    if saved.get("audio"):
        job["audio_guide"] = saved["audio"][0]
    job.update(extra)
    items = [{"name": f"r{i + 1}_seed{seed + i}", "job": dict(job, seed=seed + i)} for i in range(count)]
    create(name, title, items, contest)
    return name


def mark_queued(name):
    with _lock:
        b = load(name)
        if b["state"] in ("queued", "running"):
            raise engine.StudioError("이미 대기열에 있거나 생성 중입니다.")
        if all(i["status"] == "done" for i in b["items"]):
            raise engine.StudioError("이미 모두 끝난 배치입니다.")
        for i in b["items"]:
            if i["status"] != "done":
                i.update(status="pending", error="")
        b.update(state="queued", queued_at=time.time(), message="")
        _save(b)


def set_pick(name, item_name, on):
    """사용자가 괜찮다고 고른 시안. 항목의 pick 값으로 batch.json에 남는다(결과 파일은 지우지 않는다)."""
    with _lock:
        b = load(name)
        it = next((i for i in b["items"] if i["name"] == item_name), None)
        if not it:
            raise engine.StudioError("없는 작업입니다.")
        it["pick"] = bool(on)
        _save(b)


def delete(name):
    """배치 폴더를 통째로 지운다(결과 파일 포함). 대기 중이거나 생성 중이면 거부한다."""
    with _lock:
        b = load(name)
        if b["state"] in ("queued", "running"):
            raise engine.StudioError("대기 중이거나 생성 중인 배치는 지울 수 없습니다. 대기열에서 빼거나 멈춘 뒤 지우세요.")
        shutil.rmtree(_dir(name, b.get("contest", True)))


def _cut(item_name):
    return re.sub(r"_s\d+$", "", item_name)  # c05_s1, c05_s2 -> c05: 같은 컷의 시안끼리 묶는다


def redo(name):
    """모든 시안이 끝났는데 하나도 고르지 않은 컷을 새 시드로 다시 만든다(새 배치 <name>_r<n>). 이전 결과는 그대로 둔다."""
    b = load(name)
    groups = {}
    for i in b["items"]:
        groups.setdefault(_cut(i["name"]), []).append(i)
    todo = {c: g for c, g in groups.items() if all(i["status"] == "done" for i in g) and not any(i.get("pick") for i in g)}
    if not todo:
        raise engine.StudioError("다시 만들 컷이 없습니다. 생성이 끝났고 하나도 선택되지 않은 컷만 대상입니다.")
    contest = b.get("contest", True)
    k = 1
    while (_dir(f"{name}_r{k}", contest) / "batch.json").exists() or (_dir(f"{name}_r{k}", not contest) / "batch.json").exists():
        k += 1
    items = [{"name": i["name"], "job": dict(i["job"], seed=int(i["job"].get("seed") or 0) + 7919 * k)} for g in todo.values() for i in g]
    return create(f"{name}_r{k}", f"{b['title']} · 다시 생성 {k}", items, contest), sorted(todo)


def list_all():
    out = []
    for f in [g for root in dict.fromkeys([CONTEST_ROOT, CONTENT_ROOT]) for g in root.glob("*/batch.json")]:
        try:
            out.append(dict(json.loads(f.read_text(encoding="utf-8")), at=f.stat().st_mtime))
        except (OSError, ValueError):
            continue  # A broken folder must not hide the others.
    return sorted(out, key=lambda b: b["at"])  # oldest first; the page reverses so the newest is on top


def output_file(name, item_name):
    """Only a path this batch recorded and that sits inside its folder."""
    item = next((i for i in load(name)["items"] if i["name"] == item_name and i["output"]), None)
    path = Path(item["output"]).resolve() if item else None
    if not path or not path.is_file() or _dir(name).resolve() not in path.parents:
        raise engine.StudioError("결과 파일이 없습니다.")
    return path


def _wgp_args(job_file, out_dir):
    return [str(engine.PY), "wgp.py", "--process", str(job_file), "--output-dir", str(out_dir)]


def _tail(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 500))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _peak(r, since):
    with r.lock:
        return max((x["temp"] for x in r.history if x["t"] >= since and x.get("temp") is not None), default=None)


def _collect(shared_out, item_dir):
    """Moves what one task wrote out of the shared folder. Returns the result, skipping Wan2GP's debug reports."""
    out = item_dir / "out"
    out.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in [p for p in shared_out.iterdir() if p.is_file()] if shared_out.exists() else []:
        target = out / f.name
        shutil.move(str(f), str(target))
        moved.append(target)
    media = [p for p in moved if p.suffix.lower() not in (".txt", ".json", ".log")]
    return max(media, key=lambda p: p.stat().st_mtime) if media else None


def _run_group(name, group, done_before, total, r):
    """Runs items with one model in one Wan2GP process, so the model loads once. Returns how many failed, or None when stopped.
    Every item it did not reach stays pending. Raises StudioError when the machine itself is the problem (heat, GPU)."""
    root = _dir(name)
    work = root / "_run"
    shared_out = work / "out"
    work.mkdir(parents=True, exist_ok=True)
    _collect(shared_out, work / "unclaimed")  # Whatever a killed run left must not be credited to the next item.
    for it in group:
        d = root / it["name"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "job.json").write_text(json.dumps(it["job"], ensure_ascii=False, indent=1), encoding="utf-8")
    queue_file, log_path = work / "queue.json", root / f"wgp_{group[0]['name']}.log"
    queue_file.write_text(json.dumps([it["job"] for it in group], ensure_ascii=False, indent=1), encoding="utf-8")
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    failed, current, last_error, offset, rest = 0, None, "", 0, ""
    current_since = time.time()

    def finish(ok, error=""):
        nonlocal current, failed, last_error
        if current is None:
            return
        it = group[current]
        result = _collect(shared_out, root / it["name"]) if ok else None
        seconds, peak = round(time.time() - current_since), _peak(r, current_since)
        if result:
            _update_item(name, it["name"], status="done", output=str(result), seconds=seconds, peak_temp=peak, error="")
        else:
            failed += 1
            _update_item(name, it["name"], status="failed", seconds=seconds, peak_temp=peak,
                         error=error or last_error or "결과 파일이 없습니다.")
        current, last_error = None, ""

    def read_log():
        nonlocal current, current_since, last_error, offset, rest
        with open(log_path, "rb") as f:
            f.seek(offset)
            chunk = f.read()
            offset = f.tell()
        lines = (rest + chunk.decode("utf-8", "replace")).split("\n")
        rest = lines.pop()
        for line in lines:
            m = re.search(r"\[Task (\d+)/\d+\]", line)
            if m and line.lstrip().startswith("[Task"):
                finish(False)  # The one before it neither completed nor was skipped.
                current, current_since = int(m.group(1)) - 1, time.time()
                _update_item(name, group[current]["name"], status="running")
            elif re.match(r"\s*Task \d+ completed", line):
                finish(True)
            elif "[SKIP] Task" in line or "[ERROR]" in line:
                last_error = line.strip()[-300:]
                if "[SKIP] Task" in line:
                    finish(False)

    with open(log_path, "wb") as log:
        proc = subprocess.Popen(_wgp_args(queue_file, shared_out), cwd=engine.WAN, env=env, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=engine.NO_WINDOW)
        with r.lock:  # Registered like an H3 scene: the runner's monitor handles heat and Stop kills it.
            r.proc, r.pending_kill = proc, None
            stopping = r.stop_event.is_set()
        if stopping:
            engine.kill_tree(proc.pid)
        seen, seen_at = "", time.time()
        while proc.poll() is None:
            read_log()
            tail = _tail(log_path)
            if tail != seen or r.heat_paused:
                seen, seen_at = tail, time.time()
            if time.time() - seen_at > SILENCE_S:
                last_error = f"{SILENCE_S // 60}분 동안 응답이 없어 중단했습니다."
                engine.kill_tree(proc.pid)
                break
            steps = re.findall(r"\[(\d+)/(\d+)\] Denoising", tail)
            k, n = map(int, steps[-1]) if steps and current is not None else (0, 1)
            if not r.heat_paused:  # The monitor's "cooling" message stays visible while frozen.
                position = done_before + (current or 0)
                label = group[current]["name"] if current is not None else group[0]["name"]
                r._set_live(stage=f"{position + 1}/{total} {label}" + (f" · {k}/{n}" if steps else " · 준비 중"),
                            fraction=(position + k / n) / total)
            time.sleep(POLL_S)
        proc.wait()
    read_log()
    if rest:
        lines, rest = rest, ""
        if re.match(r"\s*Task \d+ completed", lines):
            finish(True)
    with r.lock:
        r.proc = None
        pending, r.pending_kill = r.pending_kill, None
    if r.stop_event.is_set():
        if current is not None:
            _update_item(name, group[current]["name"], status="pending")
        return None
    if pending:
        finish(False, pending[1])
        raise engine.StudioError(pending[1])
    if current is not None:  # The process died in the middle of this item.
        finish(False, last_error or _tail(log_path)[-300:])
    elif not any(i["status"] != "pending" for i in load(name)["items"] if i["name"] in {g["name"] for g in group}):
        # It died before the first task, so nothing else would explain it: charge the first item and go on.
        failed += 1
        _update_item(name, group[0]["name"], status="failed", error=last_error or _tail(log_path)[-300:])
    return failed


def _preflight():
    """Same checks as H3 (no other Wan2GP, GPU limits, disk). Separate so the self-check can skip the GPU."""
    return [c for c in engine.preflight(None, []) if c["fatal"] and not c["ok"]]


class BatchQueue:
    """Puts batches in the runner's line next to the queue it wraps."""

    def __init__(self, other):
        self.other = other

    @staticmethod
    def _mine(item_id):
        return not PROMO_ID.fullmatch(item_id)

    def queued(self):
        return self.other.queued() + [
            {"kind": "batch", "id": b["name"], "title": b["title"], "at": b["queued_at"],
             "estimate": SECONDS_PER_ITEM * sum(i["status"] != "done" for i in b["items"])}
            for b in list_all() if b["state"] == "queued"]

    def set_at(self, item_id, at):
        if not self._mine(item_id):
            return self.other.set_at(item_id, at)
        _update(item_id, queued_at=at)

    def remove(self, item_id):
        if not self._mine(item_id):
            return self.other.remove(item_id)
        if load(item_id)["state"] != "queued":
            raise engine.StudioError("대기열에 없는 작업입니다.")
        _update(item_id, state="stopped", message="대기열에서 뺐습니다.")

    def recover(self):
        self.other.recover()
        for b in list_all():
            if b["state"] == "running":
                for pid, cmd in engine.wgp_processes():
                    if str(_dir(b["name"])) in cmd:
                        engine.kill_tree(pid)
                for i in b["items"]:
                    if i["status"] == "running":
                        i["status"] = "pending"
                b.update(state="queued", message="서버가 다시 시작돼 끊긴 작업부터 이어서 만듭니다.")
                with _lock:
                    _save(b)

    def run(self, item_id, r):
        if not self._mine(item_id):
            return self.other.run(item_id, r)
        name = item_id
        b = load(name)
        if b["state"] != "queued":  # Taken out just after being picked.
            return
        _update(name, state="running", message="")
        try:
            r._set_live(stage="시작 전 점검")
            bad = _preflight()
            if bad:
                raise engine.StudioError("시작 전 점검 실패: " + " / ".join(f"{c['name']} {c['detail']}" for c in bad))
            total, failed = len(b["items"]), 0
            while True:
                items = load(name)["items"]
                todo = [i for i in items if i["status"] == "pending"]
                if not todo:
                    break
                key = lambda i: (i["job"].get("model_type"), i["job"].get("mode"))
                group = [todo[0]]
                if not todo[0]["job"].get("mode"):  # Post-processing loads nothing worth keeping.
                    for i in todo[1:]:
                        if key(i) != key(todo[0]):
                            break
                        group.append(i)
                done_before = sum(i["status"] != "pending" for i in items)
                outcome = _run_group(name, group, done_before, total, r)
                if outcome is None:
                    _update(name, state="stopped", message="멈추기를 눌러 멈췄습니다. '이어서 생성'으로 계속합니다.")
                    return
                failed += outcome
        except Exception as e:
            _update(name, state="error", message=str(e))
            raise  # The runner holds the queue: the next item would hit the same problem.
        _update(name, state="error" if failed else "done", message=f"{failed}개 실패. '이어서 생성'으로 다시 만듭니다." if failed else "완료")


if __name__ == "__main__":
    # Self-check with a fake Wan2GP: python -m studio.batch
    import sys, tempfile, types
    from collections import deque
    with tempfile.TemporaryDirectory() as tmp:
        CONTEST_ROOT, CONTENT_ROOT = Path(tmp) / "contest", Path(tmp) / "content"
        _preflight = lambda: []
        POLL_S = 0.05
        fail_seeds, crash_seeds = {2}, set()
        spawned = []

        def _wgp_args(job_file, out_dir):  # noqa: F811
            spawned.append(job_file)
            code = (f"import json,pathlib,sys;p=pathlib.Path(r'{out_dir}');p.mkdir(parents=True,exist_ok=True);"
                    f"q=json.load(open(r'{job_file}'))\n"
                    "for n,j in enumerate(q,1):\n"
                    "    print(f'[Task {n}/{len(q)}] x',flush=True)\n"
                    f"    if j['seed'] in {crash_seeds!r}: sys.exit(3)\n"
                    f"    if j['seed'] in {fail_seeds!r}: print('  [ERROR] boom',flush=True); continue\n"
                    "    (p/f'r{n}.jpg').write_text('x'); (p/'debug.txt').write_text('x')\n"
                    "    print(f'  Task {n} completed',flush=True)\n"
                    "    __import__('time').sleep(0.3)\n")
            return [sys.executable, "-c", code]

        def bad_create(*a):
            try:
                create(*a)
            except engine.StudioError:
                return True
        job = {"model_type": "qwen_image_edit_plus2_20B", "prompt": "p"}
        assert bad_create("x", "t", [{"name": "a", "job": {"model_type": "minimax_h3_fl2va_pruned_pdd"}}]), "banned model must be refused"
        assert create("free", "t", [{"name": "a", "job": {"model_type": "minimax_h3_fl2va_pruned_pdd"}}], False)["contest"] is False, "other content takes any model"
        assert (CONTENT_ROOT / "free" / "batch.json").exists() and load("free")["contest"] is False
        assert bad_create("free", "t", [{"name": "a", "job": {"model_type": "i2v_2_2"}}]), "a name is one batch across both folders"
        assert contest_allows({"mode": "edit_postprocessing", "spatial_upsampling": "seedvr2*2", "temporal_upsampling": "rife*2"})
        assert not contest_allows({"mode": "edit_remux", "postprocess_audio": "mmaudio"}), "MMAudio weights are non-commercial"
        assert not contest_allows({"mode": "edit_postprocessing", "spatial_upsampling": "h3facerefine"})
        assert not contest_allows({"model_type": "flux2_klein_9b"})
        assert any(m["id"] == "minimax_h3_fl2va_pruned_pdd" for m in models()) and any(m["id"] == "i2v_2_2_lightning_contest" for m in models())

        class Up:
            def __init__(self, filename): self.filename = filename
            def save(self, path): Path(path).write_bytes(b"x")
        form_name = create_from_form({"model": "stable_audio3_small", "prompt": "rain", "count": "2", "seed": "5", "extra": '{"duration_seconds": 3}'}, {})
        fb = load(form_name)
        assert [i["job"]["seed"] for i in fb["items"]] == [5, 6] and fb["items"][0]["job"]["duration_seconds"] == 3 and fb["contest"] is False
        time.sleep(1.1)
        up_name = create_from_form({"model": "i2v_2_2", "prompt": "p"}, {"start_image": [Up("a.png")], "ref_images": [Up("")], "audio": [Up("b.wav")]})
        uj = load(up_name)["items"][0]["job"]
        assert uj["image_prompt_type"] == "S" and Path(uj["image_start"]).exists() and Path(uj["audio_guide"]).exists() and "image_refs" not in uj
        for bad_form, bad_files in (({"model": "nope"}, {}), ({"model": "i2v_2_2", "extra": "{"}, {}), ({"model": "i2v_2_2"}, {"start_image": [Up("x.exe")]})):
            try:
                create_from_form(bad_form, bad_files)
                raise AssertionError(bad_form)
            except engine.StudioError:
                pass
        assert bad_create("../evil", "t", [{"name": "a", "job": job}]), "path in a name must be refused"
        assert bad_create("x", "t", [{"name": "..", "job": job}]), "path in an item name must be refused"
        create("s", "시험", [{"name": n, "job": dict(job, seed=k)} for k, n in enumerate("abc", 1)])

        lock, ev = threading.Lock(), threading.Event()
        r = types.SimpleNamespace(lock=lock, stop_event=ev, proc=None, pending_kill=None, heat_paused=None, history=deque(), _set_live=lambda **k: None)
        q = BatchQueue(types.SimpleNamespace(queued=lambda: [], run=lambda *a: None))
        mark_queued("s")
        assert [x["id"] for x in q.queued()] == ["s"]
        q.run("s", r)
        b = load("s")
        assert [i["status"] for i in b["items"]] == ["done", "failed", "done"] and b["state"] == "error", b
        assert len(spawned) == 1, "same model runs in one process"
        assert "boom" in b["items"][1]["error"] and b["items"][2]["output"].endswith(".jpg")
        assert not list((CONTEST_ROOT / "s" / "_run" / "out").iterdir()), "results move to their own item"
        assert (CONTEST_ROOT / "s" / "a" / "job.json").exists(), "each item keeps its job for the AI usage record"
        stamp = Path(b["items"][0]["output"]).stat().st_mtime_ns

        fail_seeds.clear()
        mark_queued("s")
        q.run("s", r)
        b = load("s")
        assert b["state"] == "done" and all(i["status"] == "done" for i in b["items"]), b
        assert Path(b["items"][0]["output"]).stat().st_mtime_ns == stamp, "a finished item must not run again"
        assert output_file("s", "a").name == "r1.jpg"

        assert create("s", "t", [{"name": "a", "job": dict(job, seed=1)}])["items"][0]["status"] == "done", "same job keeps its result"
        assert create("s", "t", [{"name": "a", "job": dict(job, seed=1, prompt="new")}])["items"][0]["status"] == "pending", "changed job is redone"

        mark_queued("s")
        ev.set()
        q.run("s", r)
        assert load("s")["state"] == "stopped" and load("s")["items"][0]["status"] != "running", "stop leaves nothing marked running"
        ev.clear()
        spawned.clear()
        crash_seeds.add(12)
        other = {"model_type": "i2v_2_2", "prompt": "v"}
        create("m", "t", [{"name": "x", "job": dict(job, seed=11)}, {"name": "y", "job": dict(job, seed=12)}, {"name": "z", "job": dict(job, seed=13)},
                          {"name": "v", "job": dict(other, seed=14)}])
        mark_queued("m")
        q.run("m", r)
        b = load("m")
        assert [i["status"] for i in b["items"]] == ["done", "failed", "done", "done"] and len(spawned) == 3, ([i["status"] for i in b["items"]], spawned)
    print("ok")

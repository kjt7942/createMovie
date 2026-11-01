"""Checks the logic that needs no GPU. Run: python studio/test_engine.py"""
import json, os, tempfile, threading, time
from pathlib import Path

import engine

SCENE = {"seconds": 5, "action": "A small yellow chick walks to a golden egg.", "sound": "Tiny footsteps on grass."}
SCRIPT = {"title": "T", "character": "A tiny fluffy yellow chick with brown eyes.",
          "style": "Polished 3D children's animation with soft light.", "music": "Happy marimba at 120 BPM, playful mood.",
          "scenes": [dict(SCENE), dict(SCENE)]}


def check_frames():
    assert engine.frames_for(1) == 107
    assert engine.frames_for(5) == 124
    assert engine.frames_for(10) == 243
    for sec in (4.5, 6.2, 7.7, 9.9):
        assert (engine.frames_for(sec) - 107) % 17 == 0
        assert abs(engine.frames_for(sec) / 24 - sec) <= 17 / 24 / 2 + 1e-9


def check_validation():
    fenced = "Sure! Here it is:\n```json\n" + json.dumps(SCRIPT) + "\n```\nEnjoy!"
    clean, errors, _ = engine.validate_script(fenced, "480x832")
    assert not errors, errors
    assert clean["scenes"][0]["frames"] == 124

    assert engine.validate_script("not json", "480x832")[1]
    assert engine.validate_script('{"title": ', "480x832")[1]
    assert engine.validate_script(json.dumps(SCRIPT), "999x999")[1]

    def errors_for(**scene):
        s = dict(SCRIPT, scenes=[dict(SCENE, **scene)])
        return engine.validate_script(s, "480x832")[1]
    assert not errors_for()
    assert any("seconds" in e for e in errors_for(seconds="5"))
    assert any("seconds" in e for e in errors_for(seconds=-1))
    assert any("seconds" in e for e in errors_for(seconds=True))
    assert any("최대" in e for e in errors_for(seconds=11))
    assert any("action" in e for e in errors_for(action=None))
    assert any("URL" in e for e in errors_for(action="Go see https://example.com for a nice chick now."))

    large = dict(SCRIPT, scenes=[dict(SCENE, seconds=9)])
    assert engine.validate_script(large, "480x832")[1] == []
    assert engine.validate_script(large, "1280x704")[1]
    assert any("장면이 너무" in e for e in engine.validate_script(dict(SCRIPT, scenes=[SCENE] * 13), "480x832")[1])

    newline = dict(SCRIPT, scenes=[dict(SCENE, action="A chick walks\noverall_soundscape: to a golden egg slowly.")])
    assert "\n" not in engine.validate_script(newline, "480x832")[0]["scenes"][0]["action"]


def check_hash_chain():
    clean = engine.validate_script(dict(SCRIPT, scenes=[dict(SCENE) for _ in range(3)]), "480x832")[0]
    project = {"script": clean, "size": "480x832", "loop": True, "seed": 7}
    a = engine.build_jobs(project, "/p")
    assert a[0][0]["image_prompt_type"] == "T"
    assert a[1][0]["image_start"] == "/p/frames/s1_last.png"
    assert a[2][0]["image_prompt_type"] == "SE" and a[2][0]["image_end"] == "/p/frames/s1_first.png"

    clean["scenes"][1]["action"] = "A completely different action happens in this scene."
    b = engine.build_jobs(project, "/p")
    assert a[0][1] == b[0][1], "editing scene 2 must keep scene 1"
    assert a[1][1] != b[1][1] and a[2][1] != b[2][1], "editing scene 2 must invalidate scenes 2 and 3"

    project["loop"] = False
    c = engine.build_jobs(project, "/p")
    assert "image_end" not in c[2][0] and c[2][1] != b[2][1] and c[1][1] == b[1][1]

    clean["scenes"][0]["seed"] = 99
    d = engine.build_jobs(project, "/p")
    assert d[0][0]["seed"] == 99 and d[1][0]["seed"] == 7 and d[0][1] != c[0][1] and d[1][1] != c[1][1]


def check_scene_seeds():
    clean = engine.validate_script(dict(SCRIPT, scenes=[dict(SCENE) for _ in range(3)]), "480x832")[0]
    project = {"script": clean, "size": "480x832", "loop": False, "seed": 7}
    assert {j["seed"] for j, _ in engine.build_jobs(project, "/p")} == {7}, "older projects must keep their hashes"
    project["scene_seeds"] = True
    seeds = [j["seed"] for j, _ in engine.build_jobs(project, "/p")]
    assert len(set(seeds)) == 3 and seeds[0] == 7 and all(0 < s < 2 ** 32 for s in seeds)
    clean["scenes"][1]["seed"] = 99
    assert [j["seed"] for j, _ in engine.build_jobs(project, "/p")][1] == 99, "a manual new seed still wins"


def check_progress():
    assert engine.parse_progress("H3 denoising:  38%|###7      | 3/8 [00:45<01:16, 15.25s/it]") == ("Denoising", 3 / 8)
    assert engine.parse_progress("  [9/54] VAE Decoding | 2m 42s / 3m 58s") == ("VAE Decoding", 9 / 54)
    assert engine.parse_progress("  [7/160] Loading - Pinning Model Transformer to Reserved RAM")[0].startswith("Loading")
    assert engine.parse_progress("  [0/1] Saving File 2026-10-31-1...dal_description [Shot 1] A shor.mp4")[1] == 0
    assert engine.parse_progress("nothing here") is None


def check_failures():
    assert engine.classify_failure("INT8 GEMM launch failed (CUDA error 999)")[0] == "gpu"
    assert engine.classify_failure("RuntimeError: No CUDA GPUs are available")[0] == "gpu"
    assert engine.classify_failure("CUDA Out Of Memory")[0] == "memory"
    assert engine.classify_failure("some other traceback")[0] == "unknown"


def check_join_filter():
    f = engine.join_filter([107, 124], True, 9.6)
    assert "[0:a]atrim=0:4.458333" in f and "[1:v]trim=start_frame=1" in f and "[2:a]volume" in f
    assert "/" not in f, "ffmpeg rejects expressions in atrim"
    assert "[2:a]" not in engine.join_filter([107, 124], False, 9.6)


def check_storage():
    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)
        clean = engine.validate_script(SCRIPT, "480x832")[0]
        p = engine.create_project(clean, "480x832", True, seed=5)
        assert engine.load_project(p["id"])["seed"] == 5
        assert [x["id"] for x in engine.list_projects()] == [p["id"]]

        for bad in ("../../etc", "abc", "", None):
            try:
                engine.project_dir(bad)
                raise AssertionError(f"accepted id {bad!r}")
            except engine.StudioError:
                pass

        pdir = engine.project_dir(p["id"])
        (pdir / "scenes").mkdir()
        for i in (1, 2, 3):
            (pdir / "scenes" / f"s{i}.mp4").write_text(str(i))
        (pdir / "final.mp4").write_text("f")
        p["scene_results"] = {"1": {}, "2": {}, "3": {}}
        engine.archive_scenes(p, 2)
        assert (pdir / "scenes" / "s1.mp4").exists() and not (pdir / "scenes" / "s2.mp4").exists()
        assert (pdir / "versions" / "v1" / "s3.mp4").read_text() == "3" and (pdir / "versions" / "v1" / "final.mp4").exists()
        assert list(p["scene_results"]) == ["1"] and p["version"] == 2

        (pdir / "junk").mkdir()
        (engine.PROJECTS / "broken").mkdir()
        assert len(engine.list_projects()) == 1


FAKE_WGP = """
import sys, time
mode = open('mode.txt').read().strip()
open('runs.txt', 'a').write('x')
print('  [1/2] VAE Decoding | 1s / 2s', flush=True)
if mode == 'gpu': print('INT8 GEMM launch failed (CUDA error 999)'); sys.exit(1)
if mode == 'boom': print('some traceback'); sys.exit(1)
if mode == 'hang': time.sleep(120)
"""


def check_runner_failures():
    """Drives the failure paths with a fake Wan2GP, because a real overheat or hang cannot be staged safely."""
    import sys
    saved = {k: getattr(engine, k) for k in ("PROJECTS", "PY", "WAN", "gpu_sample", "count_driver_resets", "STALL_TIMEOUT_S")}
    with tempfile.TemporaryDirectory() as tmp:
        wan = Path(tmp) / "wan"
        wan.mkdir()
        (wan / "wgp.py").write_text(FAKE_WGP)
        engine.PROJECTS, engine.PY, engine.WAN = Path(tmp) / "p", Path(sys.executable), wan
        engine.count_driver_resets = lambda since: 0
        temp = [40.0]
        engine.gpu_sample = lambda: {"t": 0, "temp": temp[0], "power": 0, "limit": 220, "clock": 0, "mem": 0,
                                     "mem_total": 8192, "util": 0, "fan": 0}
        runner = engine.Runner()
        project = engine.create_project(engine.validate_script(SCRIPT, "480x832")[0], "480x832", False, seed=1)
        pdir = engine.project_dir(project["id"])
        (pdir / "logs").mkdir()
        job = engine.build_jobs(project, pdir)[0][0]

        def attempt(mode):
            (wan / "mode.txt").write_text(mode)
            (wan / "runs.txt").write_text("")
            try:
                runner._render_scene(project, 1, job, pdir / "s1.mp4")
                raise AssertionError("expected a failure")
            except engine.StudioError as e:
                return e.kind, len((wan / "runs.txt").read_text())

        assert attempt("gpu") == ("gpu", 1), "a GPU crash must not retry"
        assert attempt("boom") == ("unknown", 2), "an unknown failure retries once"
        assert attempt("ok") == ("output", 2), "exit 0 without a video is a failure"

        engine.STALL_TIMEOUT_S = 1
        assert attempt("hang")[0] == "stall"
        engine.STALL_TIMEOUT_S = 600

        temp[0] = 99.0
        started = time.time()
        assert attempt("hang")[0] == "overheat"
        assert time.time() - started < 40, "the overheat stop must kill the render"
        temp[0] = 40.0

        (wan / "mode.txt").write_text("hang")
        threading.Timer(2, runner.stop).start()
        try:
            runner._render_scene(project, 1, job, pdir / "s1.mp4")
            raise AssertionError("expected a stop")
        except engine.Stopped:
            pass
        runner.stop_event.clear()

        job2 = dict(job, image_start=str(pdir / "missing.png"))
        try:
            runner._render_scene(project, 2, job2, pdir / "s2.mp4")
            raise AssertionError("expected a missing frame error")
        except engine.StudioError:
            pass
        time.sleep(4)  # Lets the monitor thread finish with the fakes before they are restored.
    for k, v in saved.items():
        setattr(engine, k, v)


def check_queue():
    """Drives the queue with the render steps faked: order, what pauses it, restart, and edit safety."""
    saved = engine.PROJECTS

    class FakeRunner(engine.Runner):
        def __init__(self):
            super().__init__()
            self.ran, self.fail, self.gate = [], {}, threading.Event()
            self.gate.set()

        def _check_ready(self, project):
            self.ran.append(project["script"]["title"])
            self.gate.wait(10)
            if self.stop_event.is_set():
                raise engine.Stopped()
            if project["script"]["title"] in self.fail:
                raise engine.StudioError("x", self.fail[project["script"]["title"]])

        def _render_scenes(self, project): pass
        def _make_music(self, project): pass
        def _join(self, project): pass

    def wait_idle(r):
        for _ in range(200):
            if not r.busy():
                return
            time.sleep(0.02)
        raise AssertionError("runner did not go idle")

    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)

        def make(title):
            return engine.create_project(engine.validate_script(dict(SCRIPT, title=title), "480x832")[0], "480x832", False)["id"]

        r = FakeRunner()
        r.gate.clear()
        a, b, c, d = make("a"), make("b"), make("c"), make("d")
        for pid in (a, b, c, d):
            r.enqueue(pid)
            time.sleep(0.01)
        for pid in (a, b):
            try:
                r.enqueue(pid)
                raise AssertionError("a project must not be queued twice")
            except engine.StudioError:
                pass
        try:
            r.edit(a, lambda p: p.update(loop=True))
            raise AssertionError("the running project must refuse edits")
        except engine.StudioError:
            pass
        r.edit(b, lambda p: p.update(loop=True))
        assert engine.load_project(b)["status"] == "queued" and engine.load_project(b)["loop"]
        r.dequeue(c)
        assert [x["title"] for x in r.snapshot()["queue"]] == ["b", "d"]
        r.gate.set()
        wait_idle(r)
        assert r.ran == ["a", "b", "d"] and engine.load_project(c)["status"] == "ready"

        # A script failure moves on; a machine failure holds everything behind it, without a retry loop.
        r = FakeRunner()
        r.gate.clear()
        e, f, g, h = make("e"), make("f"), make("g"), make("h")
        r.fail = {"e": "unknown", "f": "gpu"}
        for pid in (e, f, g, h):
            r.enqueue(pid)
            time.sleep(0.01)
        r.gate.set()
        wait_idle(r)
        time.sleep(0.1)
        assert r.ran == ["e", "f"] and r.paused and "대기열" in r.pause_reason
        assert engine.load_project(f)["status"] == "failed" and engine.load_project(g)["status"] == "queued"
        r.enqueue(c)  # Adding more must not lift a safety pause.
        time.sleep(0.1)
        assert r.ran == ["e", "f"] and r.paused
        r.dequeue(c)

        # Stop holds the queue; a crash resumes the running project first, but only after the user resumes.
        r.gate.clear()
        r.resume_queue()
        for _ in range(100):
            if r.ran[-1] == "g":
                break
            time.sleep(0.02)
        r.stop()
        r.gate.set()
        wait_idle(r)
        assert r.paused and engine.load_project(g)["status"] == "stopped" and engine.load_project(h)["status"] == "queued"

        p = engine.load_project(g)
        p.update(status="running", queued_at=1, pid=None)
        engine.save_project(p)
        r = FakeRunner()
        r.recover()
        assert r.paused and not r.busy() and r.ran == []
        assert [x["title"] for x in r.snapshot()["queue"]] == ["g", "h"]
        r.resume_queue()
        wait_idle(r)
        time.sleep(0.1)
        assert r.ran == ["g", "h"] and not r.paused and engine.load_project(h)["status"] == "done"

        # With nothing else waiting, a stopped project restarts directly instead of needing a resume.
        r = FakeRunner()
        r.fail = {"h": "gpu"}
        r.enqueue(h)
        wait_idle(r)
        time.sleep(0.1)
        assert not r.paused and engine.load_project(h)["status"] == "failed"
    engine.PROJECTS = saved


def check_shared_queue():
    """H3 projects and external work wait in one line, oldest first, and never run at the same time."""
    saved = engine.PROJECTS

    class Fake:
        def __init__(self): self.items, self.ran, self.boom = {}, [], False
        def queued(self): return [dict(kind="promo", id=k, title=k, estimate=1, at=v) for k, v in self.items.items()]
        def remove(self, item_id): self.items.pop(item_id)
        def recover(self): self.recovered = True

        def run(self, item_id, runner):
            assert sum(1 for x in log if x.endswith("+")) == sum(1 for x in log if x.endswith("-")), "overlap"
            log.append(item_id + "+")
            time.sleep(0.05)
            self.items.pop(item_id)
            log.append(item_id + "-")
            if self.boom:
                self.items[item_id] = 0
                raise RuntimeError("x")

    log = []

    class FakeRunner(engine.Runner):
        def _check_ready(self, project):
            assert sum(1 for x in log if x.endswith("+")) == sum(1 for x in log if x.endswith("-")), "overlap"
            log.append(project["script"]["title"] + "+")
            time.sleep(0.05)
            log.append(project["script"]["title"] + "-")

        def _render_scenes(self, project): pass
        def _make_music(self, project): pass
        def _join(self, project): pass

    def wait_idle(r):
        for _ in range(300):
            if not r.busy():
                return
            time.sleep(0.02)
        raise AssertionError("runner did not go idle")

    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)
        make = lambda t: engine.create_project(engine.validate_script(dict(SCRIPT, title=t), "480x832")[0], "480x832", False)["id"]
        r, f = FakeRunner(), Fake()
        r.external = f
        a, b = make("a"), make("b")
        r.enqueue(a)
        time.sleep(0.01)
        r.enqueue_external(lambda: f.items.__setitem__("p1", time.time()))
        time.sleep(0.01)
        r.enqueue(b)
        time.sleep(0.01)
        r.enqueue_external(lambda: f.items.__setitem__("p2", time.time()))
        snap = r.snapshot()
        assert [x["id"] for x in snap["queue"]] == ["p1", b, "p2"] and snap["current"]["id"] == a, snap["queue"]
        r.remove_external("p2")
        wait_idle(r)
        time.sleep(0.1)
        wait_idle(r)
        assert log == ["a+", "a-", "p1+", "p1-", "b+", "b-"], log

        # Work that needs no GPU must not look like H3 to the pages or to the GPU watchdog.
        f.items["slow"] = time.time()
        gate = threading.Event()
        f.run = lambda item_id, runner: (gate.wait(5), f.items.pop(item_id))
        with r.lock:
            r._dispatch()
        snap = r.snapshot()
        assert snap["busy"] and snap["project"] is None and snap["current"]["kind"] == "promo" and r.proc is None
        gate.set()
        wait_idle(r)

        # A failure external.run could not record stays waiting, so it must hold the queue instead of retrying forever.
        del f.run
        f.boom = True
        r.enqueue_external(lambda: f.items.__setitem__("p3", time.time()))
        wait_idle(r)
        time.sleep(0.05)
        assert r.paused and "RuntimeError" in r.pause_reason
    engine.PROJECTS = saved


def check_stop_and_removal():
    """Stop holds the queue even when nothing was running to kill, a removed project does not run, and an empty queue is not left paused."""
    saved = engine.PROJECTS

    class FakeRunner(engine.Runner):
        def __init__(self):
            super().__init__()
            self.ran, self.gate = [], threading.Event()

        def _check_ready(self, project):
            self.ran.append(project["script"]["title"])
            self.gate.wait(5)  # Ignores the stop on purpose, like a step with no process to kill.

        def _render_scenes(self, project): pass
        def _make_music(self, project): pass
        def _join(self, project): pass

    def wait_idle(r):
        for _ in range(300):
            if not r.busy():
                return
            time.sleep(0.02)
        raise AssertionError("runner did not go idle")

    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)
        make = lambda t: engine.create_project(engine.validate_script(dict(SCRIPT, title=t), "480x832")[0], "480x832", False)["id"]
        r = FakeRunner()
        a, b = make("a"), make("b")
        r.enqueue(a)
        time.sleep(0.01)
        r.enqueue(b)
        time.sleep(0.05)
        r.stop()
        r.gate.set()
        wait_idle(r)
        assert r.ran == ["a"] and r.paused, "the next project must not start after a stop"
        assert engine.load_project(b)["status"] == "queued"

        r.dequeue(b)
        p = engine.load_project(b)
        assert p["status"] == "ready"

        # Picked by dispatch, then taken out before the thread loaded it.
        r2 = FakeRunner()
        r2.gate.set()
        with r2.lock:
            r2.active = True
        r2._run(b)
        assert r2.ran == [] and engine.load_project(b)["status"] == "ready"

        # Nothing queued: finishing must not leave the queue looking paused.
        r3 = FakeRunner()
        r3.gate.set()
        r3.paused = True
        with r3.lock:
            r3.active = True
        r3._run(b)
        assert not r3.paused
    engine.PROJECTS = saved


def check_availability():
    saved = engine.gpu_sample, engine.shutil.which, engine.PY, engine.WAN, engine.os.name
    cached = engine.availability
    env = {k: os.environ.pop(k, None) for k in ("H3_LICENSE_REGION", "H3_LICENSE_GRANTED")}
    try:
        engine.availability = engine._check_availability  # The 5s cache would hide every change below.
        os.environ["H3_LICENSE_GRANTED"] = "1"  # The hardware checks below are about this PC; the notice is checked at the end.
        engine.os.name = "nt"
        engine.shutil.which = lambda c: None
        state = engine.availability()
        assert not state["ok"] and not state["gpu_ok"] and "NVIDIA" in state["reasons"][0]

        engine.shutil.which = lambda c: "nvidia-smi"
        engine.gpu_sample = lambda: None
        assert "재부팅" in engine.availability()["reasons"][0]  # A crash must not read as "no GPU".

        engine.gpu_sample = lambda: {"mem_total": 4096.0}
        assert "4GB" in engine.availability()["reasons"][0]

        engine.gpu_sample = lambda: {"mem_total": 8192.0}
        with tempfile.TemporaryDirectory() as tmp:
            wan = Path(tmp)
            engine.WAN, engine.PY = wan, wan / "py.exe"
            state = engine.availability()
            assert state["gpu_ok"] and not state["installed"] and not state["ok"] and "설치" in state["reasons"][0]
            for f in (wan / "py.exe", wan / "wgp.py"):
                f.write_text("")
            (wan / "ckpts").mkdir()
            (wan / "ckpts" / engine.MODEL_FILE).write_text("")
            state = engine.availability()
            assert state.pop("ref_installed") is False
            assert state == {"ok": True, "gpu_ok": True, "installed": True, "reasons": [], "license_notice": ""}

            # The H3 license excludes Korea, the US, the UK and the EU: by default (Korea) a notice shows, but generation stays allowed.
            del os.environ["H3_LICENSE_GRANTED"]
            state = engine.availability()
            assert state["ok"] and "라이선스" in state["license_notice"] and state["reasons"] == []
            for region, notice in (("kr", True), ("DE", True), ("US", True), ("JP", False), ("SG", False)):
                os.environ["H3_LICENSE_REGION"] = region
                state = engine.availability()
                assert state["ok"] and bool(state["license_notice"]) is notice, region
            os.environ["H3_LICENSE_REGION"] = "KR"
            os.environ["H3_LICENSE_GRANTED"] = "1"  # A separate license from MiniMax removes the notice.
            assert engine.availability()["license_notice"] == ""
    finally:
        engine.gpu_sample, engine.shutil.which, engine.PY, engine.WAN, engine.os.name = saved
        engine.availability = cached
        for k, v in env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def check_gpu_limits():
    """Limits scale to the card, stay in its range, and are never inherited from another card."""
    card = {"name": "A", "mem": 8192.0, "power_min": 100.0, "power_default": 310.0, "power_max": 320.0, "clock_max": 2130.0}
    assert engine.suggested_limits(card) == {"power": 220, "clock": 1800}, "must keep the numbers proven on the 3070 Ti"
    small = dict(card, power_min=150.0, power_default=170.0, power_max=170.0, clock_max=1900.0)
    assert engine.suggested_limits(small)["power"] == 150, "the card's minimum wins"
    locked = dict(card, power_min=None, power_default=None, power_max=None)
    assert engine.suggested_limits(locked)["power"] is None
    assert engine.suggested_limits(None) == {"power": None, "clock": None}
    saved = engine.SETTINGS
    with tempfile.TemporaryDirectory() as tmp:
        engine.SETTINGS = Path(tmp) / "s.json"
        engine.update_settings(gpu_limits={"card": "A", "power": 200, "clock": 1700})
        assert engine.gpu_limits(card)["power"] == 200
        assert engine.gpu_limits(dict(card, name="B"))["power"] == 220, "a swapped card must not inherit limits"
    engine.SETTINGS = saved

    ok = engine.test_verdict("done", None, "", 70.0, 220, card)
    assert ok[0] == "ok" and ok[2] is None
    hot = engine.test_verdict("done", None, "", 86.0, 220, card)
    assert hot[0] == "warn" and hot[2] == 195
    crash = engine.test_verdict("failed", "gpu", "x", 80.0, 220, card)
    assert crash[0] == "bad" and crash[2] == 195
    assert engine.test_verdict("failed", "gpu", "x", 80.0, 100, card)[2] is None, "already at the minimum"
    assert engine.test_verdict("failed", "memory", "x", 60.0, 220, card)[2] is None, "less power does not free memory"


def check_export():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        a, b = tmp / "a.mp4", tmp / "b.mp4"
        a.write_bytes(b"one"), b.write_bytes(b"three")
        out = tmp / "out"
        p1, copied = engine.export_video(a, 'Ti:tle?', out)
        assert copied and p1.name == "01_Title.mp4"
        assert engine.export_video(a, "Ti:tle?", out) == (p1, False), "the same file is not copied twice"
        p2, _ = engine.export_video(b, "Title", out)
        assert p2.name == "02_Title.mp4" and p1.read_bytes() == b"one", "a different video must not replace it"
        (out / "unrelated.mp4").write_bytes(b"x")
        assert engine.export_video(b, "Other", out)[0].name == "03_Other.mp4"

        saved = engine.SETTINGS
        engine.SETTINGS = tmp / "s.json"
        assert engine.export_dir() == engine.videos_folder()
        engine.set_export_dir(str(tmp / "new"))
        assert engine.export_dir() == tmp / "new" and (tmp / "new").is_dir()
        for bad in ("relative\\path",):
            try:
                engine.set_export_dir(bad)
                raise AssertionError("relative path accepted")
            except engine.StudioError:
                pass
        assert engine.export_dir() == tmp / "new", "a refused folder must not replace the saved one"
        engine.set_export_dir("")
        assert engine.export_dir() == engine.videos_folder()
        engine.SETTINGS = saved


def check_queue_order_and_delete():
    saved = engine.PROJECTS
    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)
        make = lambda t: engine.create_project(engine.validate_script(dict(SCRIPT, title=t), "480x832")[0], "480x832", False)["id"]
        r = engine.Runner()
        r.paused = True  # Held, so nothing starts while the order changes.
        a, b, c = make("a"), make("b"), make("c")
        for i, pid in enumerate((a, b, c)):
            p = engine.load_project(pid)
            p.update(status="queued", queued_at=100 + i)
            engine.save_project(p)
        order = lambda: [x["title"] for x in r._items()]
        r.move("h3", c, -1)
        assert order() == ["a", "c", "b"]
        r.move("h3", a, -1)
        assert order() == ["a", "c", "b"], "the first item stays put"
        r.move("h3", b, 1)
        assert order() == ["a", "c", "b"], "the last item stays put"
        p = engine.load_project(c); p["queued_at"] = engine.load_project(a)["queued_at"]; engine.save_project(p)  # Equal times must still move.
        before = order()
        r.move("h3", engine.load_project(a)["id"] if before[0] == "a" else c, 1)
        assert order() != before

        try:
            r.delete(a)
            raise AssertionError("deleted a queued project")
        except engine.StudioError:
            pass
        r.dequeue(a)
        (engine.PROJECTS / a / "versions").mkdir()
        (engine.PROJECTS / a / "versions" / "old.mp4").write_bytes(b"x" * 10)
        assert engine.storage_report()["spare"] == 10
        assert r.clean() == 10 and (engine.PROJECTS / a / "project.json").exists()
        r.delete(a)
        assert not (engine.PROJECTS / a).exists() and not (engine.PROJECTS / f".trash-{a}").exists()

        r.edit(b, lambda p: p.update(loop=True), base=0)
        try:
            r.edit(b, lambda p: p.update(loop=False), base=0)
            raise AssertionError("a stale page overwrote a newer edit")
        except engine.StudioError:
            pass
        assert engine.load_project(b)["loop"] is True
    engine.PROJECTS = saved


def check_estimate():
    saved, speed = engine.PROJECTS, engine._speed
    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS = Path(tmp)
        engine._speed = (0.0, 1.0)
        assert engine.speed_factor() == 1.0, "no history keeps the formula"
        p = engine.create_project(engine.validate_script(SCRIPT, "480x832")[0], "480x832", False)
        frames = p["script"]["scenes"][0]["frames"]
        p["scene_results"] = {"1": {"seconds": engine._formula_seconds("480x832", frames) * 2, "at": 1, "chain": ""}}
        engine.save_project(p)
        engine._speed = (0.0, 1.0)
        assert abs(engine.speed_factor() - 2.0) < 1e-6, "a slower PC gets longer estimates"
    engine.PROJECTS, engine._speed = saved, speed


def check_heat_pause():
    class Proc:
        pid = 7
    calls, saved = [], (engine.suspend_tree, engine.kill_tree)
    engine.suspend_tree = lambda pid, suspend=True: calls.append(suspend)
    engine.kill_tree = lambda pid: calls.append("kill")
    r, proc = engine.Runner(), Proc()
    try:
        r._manage_heat(proc, engine.PAUSE_TEMP_C - 1)
        assert not calls and not r.heat_paused
        r._manage_heat(proc, engine.PAUSE_TEMP_C)
        r._manage_heat(proc, engine.PAUSE_TEMP_C + 1)
        assert calls == [True], "must freeze once"
        assert "식히는" in r.live["stage"]
        r._manage_heat(proc, engine.RESUME_TEMP_C + 1)
        r._manage_heat(proc, None)
        assert calls == [True] and r.heat_paused, "stays frozen until cool, and on a missing sample"
        r._manage_heat(proc, engine.RESUME_TEMP_C)
        assert calls == [True, False] and not r.heat_paused
        r._manage_heat(proc, engine.PAUSE_TEMP_C)
        r._manage_heat(None, engine.PAUSE_TEMP_C)
        assert not r.heat_paused and len(calls) == 3, "a finished process is forgotten, not thawed"
        r._manage_heat(proc, engine.PAUSE_TEMP_C)
        r.heat_paused = (proc.pid, 0)
        r._manage_heat(proc, engine.PAUSE_TEMP_C)
        assert calls[-1] == "kill" and r.pending_kill[0] == "overheat", "never cooling must stop the job"
        engine.suspend_tree = lambda pid, suspend=True: (_ for _ in ()).throw(OSError("denied"))
        r.heat_paused, r.pending_kill = None, None
        r._manage_heat(proc, engine.PAUSE_TEMP_C)
        assert not r.heat_paused and "온도 조절 실패" in r.log[-1], "a failed freeze must not kill the monitor"
    finally:
        engine.suspend_tree, engine.kill_tree = saved


def check_characters():
    import io
    from PIL import Image
    saved = engine.PROJECTS, engine.CHARACTERS
    with tempfile.TemporaryDirectory() as tmp:
        engine.PROJECTS, engine.CHARACTERS = Path(tmp) / "p", Path(tmp) / "c"
        buf = io.BytesIO()
        Image.new("RGBA", (40, 20), (255, 0, 0, 0)).save(buf, "PNG")
        desc = "A round plump cartoon hen with red-brown feathers."
        for bad in (("", desc, {"front": buf.getvalue()}), ("Hen", "short", {"front": buf.getvalue()}), ("Hen", "빨간 깃털의 통통한 암탉 캐릭터입니다. 볏이 큽니다.", {"front": buf.getvalue()}),
                    ("Hen", desc, {}), ("Hen", desc, {"front": b"not a picture"})):
            try:
                engine.create_character(*bad)
                raise AssertionError(f"accepted {bad[:2]}")
            except engine.StudioError:
                pass
        assert not engine.CHARACTERS.exists() or not list(engine.CHARACTERS.iterdir()), "a refused upload must leave nothing"
        c = engine.create_character("Hen", desc, {"back": buf.getvalue(), "front": buf.getvalue()})
        assert c["views"] == ["front view", "back view"] and [x["id"] for x in engine.list_characters()] == [c["id"]]
        im = Image.open(engine.character_dir(c["id"]) / "0.png")
        assert im.size == (1024, 1024) and im.mode == "RGB" and im.getpixel((512, 512)) == (255, 255, 255), "transparency must become white"
        im.close()

        script = dict(SCRIPT, scenes=[dict(SCENE, frames=107), dict(SCENE, frames=107), dict(SCENE, frames=107)])
        p = engine.create_project(json.loads(json.dumps(script)), "480x832", True, seed=1, characters=[c["id"]])
        assert p["script"]["character"] == desc
        pdir = engine.project_dir(p["id"])
        jobs = [j for j, _ in engine.build_jobs(p, pdir)]
        assert {j["model_type"] for j in jobs} == {engine.REF_MODEL} and all(j["video_prompt_type"] == "I" for j in jobs)
        assert "<Picture 1> (front view), <Picture 2> (back view)" in jobs[0]["prompt"] and "starting frame" not in jobs[0]["prompt"]
        assert "<Picture 2> (front view), <Picture 3> (back view)" in jobs[1]["prompt"] and "starting frame" in jobs[1]["prompt"], "the start frame shifts the numbers"
        assert "<Picture 3> (front view), <Picture 4> (back view)" in jobs[2]["prompt"], "start and end frames both come first"
        assert all(Path(r).is_file() for j in jobs for r in j["image_refs"]) and len(jobs[0]["image_refs"]) == 2
        engine.delete_character(c["id"])
        assert not engine.list_characters() and all(Path(r).is_file() for r in jobs[0]["image_refs"]), "a project keeps its own copies"
        try:
            engine.create_project(json.loads(json.dumps(script)), "480x832", False, characters=[c["id"]])
            raise AssertionError("deleted character accepted")
        except engine.StudioError:
            pass
        try:
            engine.load_character("../../x")
            raise AssertionError("bad id accepted")
        except engine.StudioError:
            pass
        # An older project stored one character and refs/0.png: its prompt and files must not change.
        old = dict(p, characters=None, character={k: p["characters"][0][k] for k in ("id", "name", "description", "views")})
        old_job = engine.build_jobs(old, pdir)[0][0]
        assert old_job["image_refs"][1].endswith("refs/1.png") and old_job["prompt"] == jobs[0]["prompt"]

        hen = engine.create_character("암탉", desc, {"front": buf.getvalue(), "side": buf.getvalue()})
        rooster = engine.create_character("수탉", "A proud cartoon rooster with a tall red comb.", {"front": buf.getvalue()})
        duo = json.loads(json.dumps(script))
        duo["scenes"][0]["action"] = "Character B struts in alone from the right."
        duo["scenes"][1]["action"] = "Character A greets Character B in the yard."
        duo["scenes"][2]["action"] = "Everyone walks away slowly across the yard."
        d = engine.create_project(duo, "480x832", True, seed=1, characters=[hen["id"], rooster["id"]])
        js = [j for j, _ in engine.build_jobs(d, engine.project_dir(d["id"]))]
        assert len(js[0]["image_refs"]) == 1 and js[0]["image_refs"][0].endswith("1_0.png"), "a scene gets only the images of who it names"
        assert "<Subject 1>, called Character B, is the character shown in <Picture 1> (front view)" in js[0]["prompt"] and "Exactly" not in js[0]["prompt"]
        assert [Path(r).name for r in js[1]["image_refs"]] == ["0_0.png", "0_1.png", "1_0.png"]
        assert "called Character A, is the character shown in <Picture 2> (front view), <Picture 3> (side view)" in js[1]["prompt"], "after the start frame"
        assert "called Character B, is the character shown in <Picture 4>" in js[1]["prompt"] and "Exactly 2 main" in js[1]["prompt"]
        assert len(js[2]["image_refs"]) == 3 and "<Picture 3> (front view)" in js[2]["prompt"], "naming nobody means everyone; start and end frames come first"
        assert all(Path(r).is_file() for j in js for r in j["image_refs"])
        assert engine.scene_cast({"action": "Character Z waves."}, 2) == [0, 1]
        bad = json.loads(json.dumps(script))
        bad["scenes"][0]["action"] = "Character C appears from nowhere."
        assert engine.cast_errors(bad, 2) and not engine.cast_errors(bad, 3) and not engine.cast_errors(bad, 1)
        for args in ({"characters": [hen["id"], rooster["id"]]},):
            try:
                engine.create_project(bad, "480x832", False, **args)
                raise AssertionError("unknown character letter accepted")
            except engine.StudioError:
                pass
        many = [engine.create_character(f"C{i}", desc, {"front": buf.getvalue(), "side": buf.getvalue(), "back": buf.getvalue(), "pose": buf.getvalue()})["id"] for i in range(3)]
        for ids in (many, [many[0], many[0]], "x"):
            try:
                engine.load_cast(ids)
                raise AssertionError(f"accepted {ids}")
            except engine.StudioError:
                pass
        text = engine.llm_prompt("t", "kids", "3D", 4, 20, "480x832", False, [hen, rooster])
        assert 'Character B (the topic may call them "수탉")' in text and "fixed by reference images" in text

        plain = engine.create_project(json.loads(json.dumps(script)), "480x832", False, seed=1)
        job = engine.build_jobs(plain, engine.project_dir(plain["id"]))[0][0]
        assert job["model_type"] == engine.MODEL and "image_refs" not in job, "projects without a character stay as they were"
    engine.PROJECTS, engine.CHARACTERS = saved


def check_llm_prompt():
    text = engine.llm_prompt("chick", "kids", "3D", 4, 20, "480x832", True)
    assert "vertical 9:16" in text and '"scenes"' in text and "loops" in text
    assert "loops" not in engine.llm_prompt("chick", "kids", "3D", 4, 20, "1280x704", False)
    assert "fixed by reference images" in engine.llm_prompt("chick", "kids", "3D", 4, 20, "1280x704", False, [{"name": "H", "description": "A hen."}])
    assert "fixed by reference images" not in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("check_"):
            fn()
            print("ok", name)

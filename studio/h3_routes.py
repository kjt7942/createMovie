"""AI video (H3) routes under /h3. The page and its availability notice are open to anyone who can reach the server,
but everything else starts GPU jobs or opens local files, so it refuses other machines and other sites."""
import random, subprocess, sys
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_file, send_from_directory

from . import engine

HERE = Path(__file__).resolve().parent
app = Blueprint("h3", __name__, url_prefix="/h3")
runner = engine.Runner()
PUBLIC = {"h3.index", "h3.availability"}


def lan_ip():
    """이 PC의 LAN IP(예: 192.168.0.133). 실제 전송 없이 라우팅 표만 보고 알아낸다."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


LAN_IP = lan_ip()


def is_local():
    # The host and origin checks block DNS rebinding and other sites' pages from starting renders through the browser.
    origin = request.headers.get("Origin")
    if any(request.headers.get(h) for h in ("X-Forwarded-For", "Forwarded", "X-Real-IP")):
        return False  # A proxy on this PC connects from 127.0.0.1, so its visitors would otherwise look local.
    # 이 PC가 자기 LAN IP로 접속한 경우(접속자 주소 == 서버 주소)도 로컬이다. 다른 기기는 주소가 달라 막힌다.
    return (request.remote_addr in ("127.0.0.1", "::1", LAN_IP) and request.host.rsplit(":", 1)[0] in ("127.0.0.1", "localhost", LAN_IP)
            and (not origin or origin.split("//")[-1] == request.host))


@app.before_request
def local_only():
    if request.endpoint not in PUBLIC and not is_local():
        abort(403)


def require_available():
    state = engine.availability()
    if not state["ok"]:
        raise engine.StudioError(" ".join(state["reasons"]))


@app.errorhandler(engine.StudioError)
def studio_error(e):
    return jsonify(error=str(e)), 400


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise engine.StudioError("요청 형식이 잘못됐습니다.")
    return data


def require_idle():
    if runner.busy():
        raise engine.StudioError("생성이 진행 중입니다. 끝나거나 멈춘 뒤에 다시 시도하세요.")


def project_view(project):
    pdir = engine.project_dir(project["id"])
    scenes = []
    results = project.get("scene_results", {})
    for i, s in enumerate(project["script"]["scenes"], 1):
        r = results.get(str(i))
        scenes.append(dict(s, index=i, done=bool(r), render_seconds=r["seconds"] if r else None, stamp=int(r["at"]) if r else 0,
                           estimate=engine.estimate_scene_seconds(project["size"], s["frames"])))
    versions = sorted((d.name for d in (pdir / "versions").iterdir()), key=lambda v: int(v[1:])) if (pdir / "versions").exists() else []
    final = pdir / "final.mp4"
    return dict(project, cast=engine.project_cast(project), scenes=scenes, versions=versions, has_final=final.exists(),
                final_stamp=int(final.stat().st_mtime) if final.exists() else 0,
                folder=str(pdir), final_path=str(final),
                total_seconds=sum(s["frames"] for s in project["script"]["scenes"]) / engine.FPS)


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/api/availability")
def availability():
    return jsonify(dict(engine.availability(), local=is_local()))


@app.get("/api/options")
def options():
    return jsonify(presets=engine.PRESETS, stop_temp=engine.STOP_TEMP_C, cool_temp=engine.COOL_TEMP_C,
                   max_scenes=engine.MAX_SCENES)


@app.post("/api/llm_prompt")
def llm_prompt():
    d = body()
    size = d.get("size")
    if size not in engine.PRESETS:
        raise engine.StudioError("해상도를 선택하세요.")
    topic = str(d.get("topic", "")).strip()
    if not topic:
        raise engine.StudioError("소재를 입력하세요.")
    try:
        count, total = int(d.get("scenes", 4)), float(d.get("seconds", 20))
    except (TypeError, ValueError):
        raise engine.StudioError("장면 수와 길이는 숫자여야 합니다.")
    if not 1 <= count <= engine.MAX_SCENES:
        raise engine.StudioError(f"장면 수는 1~{engine.MAX_SCENES}개입니다.")
    per_scene = total / count
    if per_scene < 4 or per_scene > engine.PRESETS[size]["max_seconds"] or total > engine.MAX_TOTAL_SECONDS:
        raise engine.StudioError(f"장면당 길이가 4~{engine.PRESETS[size]['max_seconds']:g}초가 되도록 맞추세요. 지금은 {per_scene:.1f}초입니다.")
    cast = engine.load_cast(d.get("characters") or [])
    return jsonify(prompt=engine.llm_prompt(topic, str(d.get("audience", "general audience")), str(d.get("style", "")),
                                            count, total, size, bool(d.get("loop")), cast))


@app.get("/api/characters")
def characters():
    return jsonify(characters=engine.list_characters(), model_ready=engine.availability()["ref_installed"])


@app.post("/api/characters")
def create_character():
    images = {view: request.files[view].read() for view in engine.CHARACTER_VIEWS if view in request.files}
    return jsonify(engine.create_character(request.form.get("name"), request.form.get("description"), images))


@app.post("/api/characters/<cid>/delete")
def delete_character(cid):
    engine.delete_character(cid)
    return jsonify(ok=True)


@app.get("/api/characters/<cid>/image/<int:n>")
def character_image(cid, n):
    path = engine.character_dir(cid) / f"{n}.png"
    if not path.is_file():
        abort(404)
    return send_file(path)


@app.post("/api/validate")
def validate():
    d = body()
    clean, errors, warnings = engine.validate_script(str(d.get("text", "")), d.get("size"))
    if not errors:
        errors = engine.cast_errors(clean, len(d.get("characters") or []))
    return jsonify(script=clean, errors=errors, warnings=warnings)


@app.get("/api/projects")
def projects():
    return jsonify(projects=engine.list_projects())


@app.post("/api/projects")
def create():
    d = body()
    clean, errors, _ = engine.validate_script(str(d.get("text", "")), d.get("size"))
    if errors:
        raise engine.StudioError(" / ".join(errors))
    if d.get("characters") and not engine.availability()["ref_installed"]:
        raise engine.StudioError("캐릭터 영상용 모델이 없습니다. python tools/setup_h3.py 를 실행해 내려받으세요(약 21GB).")
    project = engine.create_project(clean, d["size"], d.get("loop"), characters=d.get("characters") or [])
    if d.get("queue"):
        require_available()
        runner.enqueue(project["id"])
    return jsonify(id=project["id"])


@app.get("/api/projects/<pid>")
def project(pid):
    return jsonify(project_view(engine.load_project(pid)))


@app.post("/api/projects/<pid>/start")
def start(pid):
    require_available()
    runner.enqueue(pid)
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/dequeue")
def dequeue(pid):
    runner.dequeue(pid)
    return jsonify(ok=True)


@app.post("/api/queue/resume")
def resume_queue():
    runner.resume_queue()
    return jsonify(ok=True)


@app.post("/api/queue/remove")
def remove_from_queue():
    d = body()
    if d.get("kind") == "h3":
        runner.dequeue(str(d.get("id")))
    else:
        runner.remove_external(str(d.get("id")))
    return jsonify(ok=True)


@app.post("/api/queue/move")
def move_in_queue():
    d = body()
    runner.move(str(d.get("kind")), str(d.get("id")), -1 if d.get("step") == -1 else 1)
    return jsonify(ok=True)


@app.post("/api/stop")
def stop():
    runner.stop()
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/scene/<int:n>")
def edit_scene(pid, n):
    """Saves an edited scene. Later scenes are invalidated by the chain hash when the next render starts."""
    d = body()

    def change(p):
        scenes = p["script"]["scenes"]
        if not 1 <= n <= len(scenes):
            raise engine.StudioError("없는 장면입니다.")
        edited = {k: v for k, v in d.items() if k in ("action", "sound", "seconds")}
        raw = dict(p["script"], scenes=[dict(s, **edited) if i == n else s for i, s in enumerate(scenes, 1)])
        clean, errors, _ = engine.validate_script(raw, p["size"])
        if errors:
            raise engine.StudioError(" / ".join(errors))
        for old, new in zip(scenes, clean["scenes"]):
            if "seed" in old:
                new["seed"] = old["seed"]
        if d.get("new_seed"):
            clean["scenes"][n - 1]["seed"] = random.randint(1, 2 ** 31 - 1)
        p["script"] = clean
        p.update(status="queued" if p["status"] == "queued" else "ready",  # An edit must not drop it from the queue.
                 message=f"장면 {n}을 수정했습니다. 생성하면 장면 {n}부터 다시 만듭니다.")

    runner.edit(pid, change, d.get("base"))
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/settings")
def settings(pid):
    d = body()
    loop = bool(d.get("loop"))
    runner.edit(pid, lambda p: p.update(loop=loop), d.get("base"))
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/delete")
def delete(pid):
    runner.delete(pid)
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/export")
def export(pid):
    final = engine.project_dir(pid) / "final.mp4"
    if not final.is_file():
        raise engine.StudioError("완성된 영상이 없습니다.")
    path, copied = engine.export_video(final, engine.load_project(pid)["script"]["title"])
    return jsonify(path=str(path), copied=copied)


@app.get("/api/settings")
def get_settings():
    return jsonify(export_dir=str(engine.export_dir()), default_dir=str(engine.videos_folder()))


@app.post("/api/settings")
def set_settings():
    engine.set_export_dir(body().get("export_dir"))
    return jsonify(export_dir=str(engine.export_dir()))


PICK_FOLDER = """import sys, tkinter, tkinter.filedialog as f
root = tkinter.Tk(); root.withdraw(); root.attributes('-topmost', True)
print(f.askdirectory(initialdir=sys.argv[1], title='저장 폴더 선택') or '')"""


@app.post("/api/settings/pick")
def pick_folder():
    """Browsers cannot hand a page a real folder path, so the dialog runs as a separate process on this PC."""
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", PICK_FOLDER, str(engine.export_dir())], capture_output=True, text=True,
                           encoding="utf-8", timeout=300, creationflags=engine.NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        raise engine.StudioError("폴더 선택 창을 열지 못했습니다. 경로를 직접 입력하세요.")
    if r.returncode != 0:
        raise engine.StudioError("폴더 선택 창을 열지 못했습니다. 경로를 직접 입력하세요.")
    return jsonify(path=r.stdout.strip())


@app.get("/api/storage")
def storage():
    return jsonify(engine.storage_report())


@app.post("/api/storage/clean")
def clean_storage():
    return jsonify(freed=runner.clean())


@app.get("/api/gpu")
def gpu():
    card = engine.gpu_card()
    sample = engine.gpu_sample()
    return jsonify(card=card, limits=engine.gpu_limits(card), suggested=engine.suggested_limits(card), current=sample["limit"] if sample else None,
                   test=engine.load_settings().get("gpu_test"), testing=runner.test_running(), presets=engine.PRESETS,
                   estimates={s: engine.estimate_scene_seconds(s, engine.MIN_FRAMES) + engine.PROJECT_OVERHEAD_S for s in engine.PRESETS})


@app.post("/api/gpu/apply")
def gpu_apply():
    require_idle()
    d = body()
    engine.apply_gpu_limits(d.get("power"), d.get("clock"))
    return jsonify(ok=True)


@app.post("/api/gpu/test")
def gpu_test():
    require_available()
    runner.start_test(body().get("size"))
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/reveal")
def reveal(pid):
    """Opens Explorer with the finished video selected. The path comes from the validated project id, never the client."""
    final = engine.project_dir(pid) / "final.mp4"
    if not final.is_file():
        raise engine.StudioError("완성된 영상이 없습니다.")
    subprocess.Popen(f'explorer /select,"{final}"')  # A string, because list quoting breaks /select on paths with spaces.
    return jsonify(ok=True)


@app.get("/api/status")
def status():
    return jsonify(runner.snapshot())


@app.get("/api/preflight")
def check():
    require_idle()
    return jsonify(checks=engine.preflight(request.args.get("size", "480x832"), [], fix_power=False))


@app.get("/media/<pid>/final.mp4")
def media_final(pid):
    return send_media(engine.project_dir(pid) / "final.mp4")


@app.get("/media/<pid>/scene/<int:n>.mp4")
def media_scene(pid, n):
    return send_media(engine.project_dir(pid) / "scenes" / f"s{n}.mp4")


@app.get("/media/<pid>/frame/<int:n>.png")
def media_frame(pid, n):
    return send_media(engine.project_dir(pid) / "frames" / f"s{n}_last.png")


def send_media(path):
    if not path.is_file():
        abort(404)
    return send_file(path, conditional=True, max_age=0)

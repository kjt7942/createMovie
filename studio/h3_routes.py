"""AI video (H3) routes under /h3. The page and its availability notice are open to anyone who can reach the server,
but everything else starts GPU jobs or opens local files, so it refuses other machines and other sites."""
import random, subprocess
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_file, send_from_directory

from . import engine

HERE = Path(__file__).resolve().parent
app = Blueprint("h3", __name__, url_prefix="/h3")
runner = engine.Runner()
PUBLIC = {"h3.index", "h3.availability"}


def is_local():
    # The host and origin checks block DNS rebinding and other sites' pages from starting renders through the browser.
    origin = request.headers.get("Origin")
    return (request.remote_addr in ("127.0.0.1", "::1") and request.host.rsplit(":", 1)[0] in ("127.0.0.1", "localhost")
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
    return dict(project, scenes=scenes, versions=versions, has_final=final.exists(),
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
    return jsonify(prompt=engine.llm_prompt(topic, str(d.get("audience", "general audience")), str(d.get("style", "")),
                                            count, total, size, bool(d.get("loop"))))


@app.post("/api/validate")
def validate():
    d = body()
    clean, errors, warnings = engine.validate_script(str(d.get("text", "")), d.get("size"))
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
    project = engine.create_project(clean, d["size"], d.get("loop"))
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

    runner.edit(pid, change)
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/settings")
def settings(pid):
    loop = bool(body().get("loop"))
    runner.edit(pid, lambda p: p.update(loop=loop))
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

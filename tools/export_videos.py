"""Copies finished H3 Studio videos to a folder as 01_Title.mp4, in the order they finished.

Numbers stay put between runs: a known title keeps its number, and a new one takes the next number.
Run: python tools/export_videos.py [--wait]   (--wait repeats until the queue is empty and nothing is rendering.)
"""
import json, os, re, shutil, sys, time, urllib.request
from pathlib import Path

PROJECTS = Path(__file__).resolve().parent.parent / "jobs" / "studio"
TARGET = Path(r"C:\Users\kjt79\Desktop\영상")
STATUS_URL = "http://127.0.0.1:7870/api/status"


def safe_name(title):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip(" .") or "untitled"


def same_file(a, b):
    x, y = a.stat(), b.stat()
    return x.st_size == y.st_size and int(x.st_mtime) == int(y.st_mtime)


def export():
    TARGET.mkdir(parents=True, exist_ok=True)
    done = []
    for d in PROJECTS.iterdir():
        try:
            p = json.loads((d / "project.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if p.get("status") == "done" and (d / "final.mp4").is_file():
            done.append((p.get("finished") or p.get("created", 0), p["script"]["title"], d / "final.mp4"))
    # ponytail: a title identifies a video here, so two projects with the same title share one file.
    known = {m[2]: int(m[1]) for m in (re.fullmatch(r"(\d+)_(.*)\.mp4", f.name) for f in TARGET.iterdir()) if m}
    for _, title, final in sorted(done, key=lambda x: x[0]):
        name = safe_name(title)
        if name not in known:
            known[name] = max(known.values(), default=0) + 1
        out = TARGET / f"{known[name]:02d}_{name}.mp4"
        if out.exists() and same_file(final, out):
            continue
        tmp = out.with_suffix(".tmp")
        shutil.copy2(final, tmp)
        os.replace(tmp, out)
        print("saved", out, flush=True)


def queue_finished():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=10) as r:
            s = json.load(r)
        return not s["busy"] and not s["queue"]
    except (OSError, ValueError):  # The server may be restarting; a closed server leaves the queue for later.
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    export()
    while "--wait" in sys.argv and not queue_finished():
        time.sleep(60)
        export()
    export()

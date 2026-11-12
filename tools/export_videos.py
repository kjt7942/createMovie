"""Copies every finished AI video to the save folder set on the setup page (the user's Videos folder by default), in the order they finished.

Files are named 01_Title.mp4. A video already there is skipped, and a changed video with the same title takes a new number.
Run: python tools/export_videos.py [--wait]   (--wait repeats until the queue is empty and nothing is rendering.)
"""
import json, os, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "studio"))
import engine

STATUS_URL = f"http://127.0.0.1:{os.environ.get('PORT', '5100')}/h3/api/status"


def export():
    done = []
    for d in engine.PROJECTS.iterdir() if engine.PROJECTS.exists() else []:
        try:
            p = json.loads((d / "project.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if p.get("status") == "done" and not p.get("test") and (d / "final.mp4").is_file() and not p["script"]["title"].startswith("TEST "):
            done.append((p.get("finished") or p.get("created", 0), p["script"]["title"], d / "final.mp4"))
    for _, title, final in sorted(done, key=lambda x: x[0]):
        out, copied = engine.export_video(final, title)
        if copied:
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

#!/usr/bin/env python3
"""look_guard.py — PreToolUse hook of script-to-motion (registered by SKILL.md's frontmatter while the skill is in use).

The picture of a video is looked at ONLY on render.py sheets (`python3 <dir>/render.py <dir> --screenshot …`). This
hook blocks the other ways an agent has looked before:

  Read  an image (png/jpg/jpeg/webp/gif/bmp/avif/tif) that is not a render.py sheet (a sheet sits in a `screenshots/`
        folder or carries render.py's sheet name) when it belongs to a video project, the skill's own folder, or a
        temp / scratch folder — the places where probe screenshots, preview images and frame grabs end up.
        Allowed: sheets, the user's own files (assets/user/), and images anywhere else (a file of the user's that has
        nothing to do with a video project). The thumbnail PNG is looked at like everything else: render.py on its page
        (`render.py <dir>/thumbnail/thumbnail.html --screenshot`), not by opening the PNG.
  Bash / Write / Edit  text that takes a picture outside render.py: `.screenshot(`, `captureScreenshot`,
        `startScreencast`, `html2canvas`, a browser binary run with `--screenshot`, ffmpeg writing image files.
        Allowed: reading code (grep / rg / git grep|diff|log|show), editing files inside the skill itself, and an ffmpeg
        still written into assets/user/ (a frame used as content of the video, listed in provenance.json).

A blocked call exits 2 with the reason on stderr: Claude Code shows it to the model as the denial reason.
Anything else, and any error in this script, lets the call through (exit 0).
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

IMAGE = re.compile(r'\.(png|jpe?g|webp|gif|bmp|avif|tiff?)$', re.I)
SHEET = re.compile(r'\d+m\d\d\.\d\ds-\d+m\d\d\.\d\ds_[gn]\d+[\w.+-]*_\d+\.(?:jpg|png)$')   # render.py's sheet names
CAPTURE = re.compile(
    r'\.screenshot\s*\(|captureScreenshot|startScreencast|Page\.printToPDF|\bhtml2canvas\b'
    r'|\b(?:google-chrome|chrome|chromium|chromium-browser|headless[_-]?shell|chrome-headless-shell|msedge)\b[^\n|;&]*--screenshot'
    r'|\bffmpeg\b[^\n|;&]*(?:-frames:v|-vframes|%0?\d*d\.(?:png|jpe?g)|\s[^\s|;&]+\.(?:png|jpe?g|webp|bmp)\s*(?:$|[;&|]))', re.I)
READ_ONLY = re.compile(r'^\s*(?:grep|egrep|rg|git\s+(?:grep|diff|log|show))\b')
# a single frame cut as CONTENT of the video (a card, a comparison still — footage.md §2) goes into assets/user/ and is
# listed in provenance.json: that ffmpeg command is not a way of looking and passes
CONTENT_FRAME = re.compile(r'\bffmpeg\b[^\n|;&]*\s(?:\S*/)?assets/user/[^\s|;&]+\.(?:png|jpe?g|webp|bmp)\b', re.I)


def skill_root(p):
    """the script-to-motion skill folder p is in (a SKILL.md named script-to-motion above it), else None"""
    for d in [p, *p.parents]:
        s = d / 'SKILL.md'
        try:
            if s.is_file() and re.search(r'^name:\s*script-to-motion\s*$', s.read_text(encoding='utf-8', errors='replace')[:400], re.M):
                return d
        except OSError:
            pass
    return None


def project_of(p):
    """the video project p belongs to (index.html + js/cues.js or script.json), else None"""
    for d in [p.parent, *p.parent.parents]:
        if (d / 'index.html').is_file() and ((d / 'js' / 'cues.js').is_file() or (d / 'script.json').is_file()):
            return d
    return None


def scratch(p):
    s = str(p)
    tmps = {tempfile.gettempdir(), '/tmp', '/private/tmp', '/var/tmp', os.environ.get('TMPDIR', '') or '/tmp'}
    return '/scratchpad/' in s or s.startswith('/var/folders/') or any(t and s.startswith(t.rstrip('/') + '/') for t in tmps)


def how(project):
    d = str(project) if project else '<dir>'
    return ('The picture of a video is looked at ONLY on render.py sheets (script-to-motion, absolute rule): '
            f'python3 {d}/render.py {d} --screenshot … — a stretch (--from A --to B --gapframe N), exact moments (--at T,T), '
            'detail (--res 1080p|4k, --crop X,Y,W,H in stage px), a frame that depends on the seek path (--at T --via SEC: '
            'both captures and the differing pixels marked), one illustration module (--art NAME --viewbox "X Y W H" --at …), '
            'a clip, a recording or a rendered MP4 (render.py <video file> --screenshot, with --at T, --res 1080p or --crop X,Y,W,H '
            'in its own pixels for detail — never an ffmpeg frame grab). Then open only the sheet paths it prints. If the user explicitly asked '
            'for this exact file, say the script-to-motion guard blocks it and ask them to open it themselves.')


def deny(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    tool, inp = ev.get('tool_name') or '', ev.get('tool_input') or {}
    cwd = Path(ev.get('cwd') or os.getcwd())

    if tool == 'Read':
        fp = inp.get('file_path') or ''
        if not IMAGE.search(fp):
            return
        p = Path(fp).expanduser()
        p = p if p.is_absolute() else (cwd / p)
        p = Path(os.path.realpath(p))
        parts = [x.lower() for x in p.parts]
        if 'screenshots' in parts or SHEET.search(p.name):                 # a render.py sheet
            return
        if 'assets' in parts and 'user' in parts[parts.index('assets') + 1:parts.index('assets') + 2]:
            return                                                         # the user's own files
        proj, skill = project_of(p), skill_root(p)
        if proj or skill or scratch(p):
            where = f'inside the video project {proj}' if proj else ('inside the skill folder' if skill else 'in a temp/scratch folder')
            deny(f'script-to-motion blocked Read of {p.name} ({where}): it is not a render.py sheet. ' + how(proj or project_of(cwd / 'x')))
        return

    if tool == 'Bash':
        cmd = inp.get('command') or ''
        if READ_ONLY.match(cmd) or not CAPTURE.search(cmd):
            return
        if CONTENT_FRAME.search(cmd) and not CAPTURE.search(CONTENT_FRAME.sub(' ', cmd)):
            return                                                         # a still for the video's content
        m = CAPTURE.search(cmd).group(0)
        deny(f'script-to-motion blocked this command: it takes a picture outside render.py ("{m[:60]}"). ' + how(project_of(cwd / 'x')))

    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        fp = inp.get('file_path') or inp.get('notebook_path') or ''
        text = inp.get('content') or inp.get('new_string') or inp.get('new_source') or ''
        if tool == 'MultiEdit':
            text = '\n'.join(e.get('new_string', '') for e in inp.get('edits') or [])
        if not text or not CAPTURE.search(text):
            return
        p = Path(os.path.realpath(Path(fp).expanduser() if Path(fp).expanduser().is_absolute() else cwd / fp))
        if skill_root(p):                                                  # working on the skill itself
            return
        m = CAPTURE.search(text).group(0)
        deny(f'script-to-motion blocked writing {p.name}: the code takes a picture outside render.py ("{m[:60]}"). ' + how(project_of(p)))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass                                                               # never block a call because of a bug here

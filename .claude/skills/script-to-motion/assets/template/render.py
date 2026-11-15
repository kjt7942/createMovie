#!/usr/bin/env python3
"""render.py — script-to-motion 영상 프로젝트를 MP4로 굽고, 콘택트 시트(프로젝트 · mp4·mov 영상 파일)를 만든다.
프레임 단위로 렌더하므로 프레임 드랍이 생기지 않는다.
파일 하나로 어디에 두어도 된다: 프로젝트 폴더(index.html이 있는 곳)를 인자로 준다. 인자가 없으면 지금 폴더, 그다음
이 파일이 있는 폴더에서 index.html을 찾는다(새 프로젝트에는 new_project.mjs가 이 파일을 넣어 준다).

    python3 render.py ~/videos/my-video                  영상 전체 → ~/videos/my-video/movie_<날짜-시각>_<해상도>.mp4
                                                         (예: movie_20261106-213045_1080p.mp4 · 60fps, 무대 크기 그대로)
    python3 render.py ~/videos/my-video/index.html       index.html을 줘도 같음
    python3 render.py                                    지금 폴더(또는 이 파일의 폴더)가 프로젝트일 때
    python3 render.py <폴더> --from 0 --to 40             0–40초만 (시험용; 그 구간의 내레이션과 자막도 들어감)
    python3 render.py <폴더> --quality max --png          최상 화질 (느림)
    python3 render.py <폴더> --quality ultra              JPEG 100으로 찍어 무손실 압축 (H.264 YUV 4:4:4, 파일이 아주 큼)
    python3 render.py <폴더> --quality ultra --png        PNG로 찍어 무손실 압축 (더 느림)
    python3 render.py <폴더> --res 4k                     4K (무대의 두 배 — 16:9면 3840×2160, HEVC)
    python3 render.py <폴더> --res 720p                   720p (무대의 2/3 — 16:9면 1280×720, 더 빠르고 파일이 작음)
    python3 render.py <폴더> --res 480p                   480p (무대의 4/9 — 16:9면 854×480, 미리보기·공유용)
    python3 render.py <폴더> --screenshot --gapframe 5    MP4 대신 콘택트 시트: 5프레임마다 한 칸, 480p 칸 여러 개를 이미지 한 장에
    python3 render.py <폴더> --screenshot --at 11.5,23 --res 1080p          그 시각들만, 칸마다 무대 크기 그대로 (세부)
    python3 render.py <폴더> --screenshot --at 23 --crop 1200,600,640,360 --res 4k   무대의 일부만 크게
    python3 render.py <폴더> --screenshot --at 66.3 --via 74.3             [순서대로 | 74.3초에서 건너옴 | 차이] — 탐색 경로 문제
    python3 render.py <폴더> --screenshot --art dino --viewbox "-200 -130 400 260" --at 0,0.6,1.2   그림 모듈 하나만
    python3 render.py clip.mov --screenshot               영상 파일(mp4·mov 등)의 콘택트 시트 — 그 파일의 프레임으로
    python3 render.py rec.mp4 --screenshot --at 14.2 --crop 2400,80,960,540   영상 파일의 한 순간, 일부를 원본 픽셀로
    python3 render.py <폴더>/thumbnail/thumbnail.html --screenshot   영상이 아닌 페이지(썸네일)를 한 칸으로 — 페이지 옆 screenshots/
    python3 render.py <폴더> --out ~/Desktop/영상.mp4      다른 곳에 저장
    (자막은 기본으로 영상에 입힘 — 빼려면 --no-captions)

How it works: a local web server serves this folder, a headless Chrome opens index.html?render (the player hides its UI,
see references/player-api.md §6), and for every frame n the page is moved to t = n / fps and waited for until everything
has drawn that t (Video.renderBusy(), fed by ctx.busy(fn)) — then the frame is captured and piped into ffmpeg. Nothing
plays in real time, so a slow moment only takes longer. The video is cut into chunks (--chunk seconds), each in a fresh
browser; --jobs renders several at once; a finished chunk is kept and skipped when the script is run again (an
interrupted run picks up where it stopped, unless the project's files changed). Ctrl+C reaches only the main process:
each worker finishes the frame it is on and closes its file, and the part made so far without a gap — the finished
chunks from the start, then the chunk after them as far as it got — is saved as <name>_partial.mp4 (a second Ctrl+C
stops at once, without it). --quality ultra: JPEG 100 captures (PNG with --png), decoded to RGB and turned into BT.709
YUV 4:4:4 with no resize and no colour halving, compressed losslessly (libx264 at qp 0, High 4:4:4 Predictive) — only the
8-bit RGB → YUV rounding (and JPEG 100 itself, without --png) loses anything; the sound is as with high/max.
The stage size is read from index.html
(#stage data-width / data-height), so 9:16, 1:1 and other aspects come out at their own size.

On a Mac it uses the graphics chip: Chrome draws with Metal (installed Google Chrome first, then Playwright's Chromium),
and ffmpeg encodes with VideoToolbox. Elsewhere, or with --no-gpu / --encoder software, it draws with software WebGL and
encodes with x264 / x265.

Everything it needs lives in a virtual environment of its own, ~/.cache/motion-render-venv (MOTION_RENDER_VENV to put
it elsewhere): on the first run it is made (python3 -m venv), Playwright is installed into it and its Chromium downloaded
into it, and the script runs itself again with the environment's Python — nothing is installed into the system Python
or into this project. ffmpeg: the system's (Mac: brew install ffmpeg, which has VideoToolbox) or, when there is none,
the one the imageio-ffmpeg package brings into the environment.
    --no-venv   run with the Python that started the script (Playwright must then be installed there)
Contact sheets (--screenshot): instead of a movie, every --gapframe-th frame of the range is captured at 480p (the same
seek → wait → capture as a movie frame) and laid out in a grid, --cols × --rows tiles per image (landscape 4 × 6, portrait
8 × 3), each tile labelled `frame  m:ss.ff  [cue]` (the time as the player's S key copies it), a header line on top, more
tiles → more sheets: <project>/screenshots/<project>_<run time>_<from>-to-<to>_every-<gap>-frames-at-<fps>fps_sheet-<k>-of-<n>.jpg
— the run time (when the command started) keeps runs from overwriting each other, and nothing is removed unless --clear is
given (it empties the project's screenshots/; in any other folder it removes only the sheets render.py recorded there,
still as written). Each job (--jobs) launches one browser and builds the page once, then films the tiles of its sheets
in order, seeking from one to the next as a movie chunk does; resume (from the first sheet not written), the
stale-project check, captions, footage frames and the font check work as for a movie; no ffmpeg. The labels use the
project's own @font-face fonts. references/render.md in the skill has the whole guide.
Sheets are the only way the picture is looked at — every need has its option here, so nothing else ever takes a picture:
    --at T,T,…        exactly those moments (instead of --from/--to/--gapframe)
    --res / --crop    detail: tiles at 720p/1080p/4K, or one stage rectangle (X,Y,W,H in stage pixels) at that density;
                      a big tile gets an image of its own (a viewer shrinks wide sheets)
    --via SEC         each tile again after a detour to SEC: [in order | from SEC | difference] — a frame that depends on
                      the seek path (what snapshot.mjs --seekcheck reports), seen with the differing pixels marked
    --art NAME        one illustration module (js/art/*.js) alone in --viewbox, posed by animate(t, --state) at each --at
                      time — the page is built in memory, filmed the same way

Sound: the narration of the rendered stretch (when there is voice in it — a silent placeholder is left out), mixed with
the footage's own sound where a clip plays with `audio: true` — at its placement and volume envelope (always 1×), as
the player plays it (clips' masters from js/media-src.js). Footage pictures are filmed from frames cut beforehand by
scripts/stills.mjs (headless Chrome plays no H.264); a run stops before drawing when they are missing, smaller than this
resolution needs (a blurry clip) or cut at another fps, and prints the stills.mjs command for this render.
"""
import argparse, hashlib, http.server, json, multiprocessing as mp, os, re, shutil, signal, socketserver, subprocess, sys, tempfile, threading, time, traceback, unicodedata
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent              # where this file is (only a fallback for finding the project)
ROOT = None                                         # the project folder (index.html) — set in main() from the argument
IS_MAC = sys.platform == 'darwin'
# the virtual environment lives outside the project (the project's own check would read its packages as stray media):
# ~/.cache/motion-render-venv, or wherever MOTION_RENDER_VENV points
VENV = Path(os.environ.get('MOTION_RENDER_VENV') or (Path.home() / '.cache' / 'motion-render-venv'))
VPY = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
# Playwright's browsers go into the environment too: `playwright install` tidies the folder it installs into, and in the shared
# cache (~/Library/Caches/ms-playwright, ~/.cache/ms-playwright) that would remove browsers other programs still use
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(VENV / 'ms-playwright'))


def find_project(arg):
    """the project folder: the argument (a folder, or an index.html in it), else the current folder, else this file's folder"""
    if arg:
        p = Path(arg).expanduser().resolve()
        if p.is_file() and p.name.lower().endswith('.html'):
            p = p.parent
        need(p.is_dir(), f'폴더가 없습니다: {arg}')
        need((p / 'index.html').is_file(), f'{p} 에 index.html이 없습니다 — script-to-motion 영상 프로젝트 폴더를 주세요')
        return p
    for p in (Path.cwd().resolve(), HERE):
        if (p / 'index.html').is_file():
            return p
    need(False, '영상 프로젝트 폴더를 알려 주세요 — python3 render.py <index.html이 있는 폴더>')


# --screenshot without --progress: stdout carries only the finished sheets' full paths, one per line; progress and notes
# are not shown, and only problems (errors, warnings) are written — to stderr
QUIET = False
PROBLEM = re.compile(r'오류|경고|주의|멈췄|다시|실패')


def say(*a):
    if QUIET:
        return
    print(time.strftime('[%H:%M:%S]'), *a, flush=True)


def warn(*a):
    """a problem: on stdout like say() normally, on stderr in quiet mode (stdout keeps only the sheet paths)"""
    print(time.strftime('[%H:%M:%S]'), *a, file=sys.stderr if QUIET else sys.stdout, flush=True)


def need(ok, msg):
    if not ok:
        sys.exit('필요한 것이 없습니다: ' + msg)


# ---------------------------------------------------------------- generated.json: what this script writes into a project
# The skill's tools record every file they write that is not plain text, with its sha256, in the video project's
# generated.json (the skill's scripts/lib/generated.mjs keeps the same file under the same lock). check.mjs accepts such
# a file only when it is listed there unchanged, or declared as the user's in provenance.json.
GEN_RECORD = 'generated.json'
GEN_NOTE = ("files the skill's tools wrote into this project, with their sha256 — written by the tools; do not edit "
            "(check.mjs, SKILL.md → Originality)")


def project_of(p):
    """the video project a path is in: the nearest folder at or above it with index.html and script.json (None: none)"""
    d = os.path.abspath(p)
    if not os.path.isdir(d):
        d = os.path.dirname(d)
    while True:
        if os.path.isfile(os.path.join(d, 'index.html')) and os.path.isfile(os.path.join(d, 'script.json')):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def record_generated(paths, by='render.py'):
    """record files this script has just written in the generated.json of the video project each one is in (a file in
    no project needs no record); entries whose file is gone are dropped in the same write"""
    import socket
    groups = {}
    for p in paths:
        a = os.path.abspath(p)
        root = project_of(a)
        if root and os.path.isfile(a):
            groups.setdefault(root, []).append(a)
    for root, files in groups.items():
        add = {os.path.relpath(a, root).replace(os.sep, '/'): {'sha256': sha256_file(a), 'by': by} for a in files}
        lock = os.path.join(root, GEN_RECORD + '.lock')
        me, t0 = json.dumps({'host': socket.gethostname(), 'pid': os.getpid()}), time.time()
        while True:
            try:
                with os.fdopen(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644), 'w') as fh:
                    fh.write(me)
                break
            except FileExistsError:
                try:
                    with open(lock, encoding='utf-8') as fh:
                        held = json.load(fh)
                except (OSError, ValueError):
                    held = None                         # (being written this moment, or gone)
                if held and held.get('host') == socket.gethostname() and isinstance(held.get('pid'), int) and not _alive(held['pid']):
                    try:
                        os.unlink(lock)
                    except FileNotFoundError:
                        pass
                    continue
                if time.time() - t0 > 30:
                    raise RuntimeError(f'{lock}: 다른 프로세스가 잡고 있습니다'
                                       + (f' (pid {held.get("pid")}, {held.get("host")})' if held else '')
                                       + ' — 스킬의 도구가 이 프로젝트에 쓰고 있지 않다면 이 파일을 지우세요')
                time.sleep(0.05)
        try:
            rec = os.path.join(root, GEN_RECORD)
            files_ = {}
            if os.path.exists(rec):
                with open(rec, encoding='utf-8') as fh:
                    files_ = (json.load(fh) or {}).get('files') or {}
            files_.update(add)
            files_ = {k: files_[k] for k in sorted(files_) if os.path.exists(os.path.join(root, k))}
            tmp = os.path.join(root, f'generated.{os.getpid()}.tmp.json')
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump({'note': GEN_NOTE, 'files': files_}, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
            os.replace(tmp, rec)
        finally:
            try:
                os.unlink(lock)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- the virtual environment (outside the project)
def in_venv():
    return Path(sys.prefix).resolve() == VENV.resolve()


def step(args, fail):
    """one setup command; when it fails, say what to do and stop (no traceback)"""
    if subprocess.run(args, stdout=sys.stderr if QUIET else None).returncode != 0:
        sys.exit(f'설정을 끝내지 못했습니다: {fail}')


def bootstrap():
    """make the environment if needed, put Playwright (+ its Chromium, + ffmpeg when the system has none) in it, then run this
    script again with the environment's Python"""
    def make(clear=False):
        say(f'가상환경을 {"다시 " if clear else ""}만드는 중… ({VENV})')
        subprocess.run([sys.executable, '-m', 'venv'] + (['--clear'] if clear else []) + [str(VENV)], stdout=sys.stderr if QUIET else None)
    has_pip = lambda: VPY.exists() and subprocess.run([str(VPY), '-m', 'pip', '--version'], capture_output=True).returncode == 0
    if not VPY.exists():
        make()
    need(VPY.exists(), f'가상환경 — {sys.executable} -m venv 가 {VENV} 를 만들지 못했습니다 (Debian/Ubuntu: sudo apt install python3-venv)')
    have = lambda mod: subprocess.run([str(VPY), '-c', f'import {mod}'], capture_output=True).returncode == 0
    pkgs = ([] if have('playwright') else ['playwright']) + ([] if shutil.which('ffmpeg') or have('imageio_ffmpeg') else ['imageio-ffmpeg'])
    if pkgs:
        # a venv made without pip (Debian/Ubuntu without python3-venv: ensurepip is missing — venv stops after making the
        # folder) can't install anything: made again once, then the package to install is named
        if not has_pip():
            make(clear=True)
        if not has_pip():
            minor = f'python3.{sys.version_info.minor}-venv'
            sys.exit(f'필요한 것이 없습니다: 가상환경에 pip가 없습니다 — 이 파이썬({sys.executable})에는 venv가 pip를 넣는 데 쓰는 ensurepip가 '
                     f'없습니다.\nDebian/Ubuntu: sudo apt install python3-venv (또는 {minor}) 를 설치한 뒤 같은 명령으로 다시 실행하세요 — '
                     f'가상환경은 다시 만들어집니다.\n(또는 Playwright가 설치된 파이썬으로 --no-venv)')
        say('가상환경에 설치하는 중: ' + ', '.join(pkgs))
        step([str(VPY), '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'], 'pip를 올리지 못했습니다 — 네트워크(프록시)를 확인하고 다시 실행하세요')
        step([str(VPY), '-m', 'pip', 'install', '--quiet'] + pkgs, f'{", ".join(pkgs)} 를 설치하지 못했습니다 — 네트워크(프록시)를 확인하고 다시 실행하세요')
    mark = VENV / '.chromium-installed'
    if not mark.exists():
        say('Chromium 내려받는 중… (처음 한 번)')
        step([str(VPY), '-m', 'playwright', 'install', 'chromium'], 'Chromium을 내려받지 못했습니다 — 네트워크(프록시)를 확인하고 다시 실행하세요')
        mark.write_text(time.strftime('%Y-%m-%d %H:%M:%S\n'))
    os.execv(str(VPY), [str(VPY), str(Path(__file__).resolve())] + sys.argv[1:])


def ffmpeg_bin():
    f = shutil.which('ffmpeg')
    if f:
        return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG = ffmpeg_bin() or 'ffmpeg'


# ---------------------------------------------------------------- the video's data (js/cues.js)
def video_data():
    src = (ROOT / 'js' / 'cues.js').read_text(encoding='utf-8')
    return json.loads(src[src.index('{'):src.rindex('}') + 1])


# what the frames are drawn from: a change to any of these makes chunks of an earlier run stale — every folder of the
# project except sound, subtitles and tool folders (and hidden ones), plus index.html / glyphs.json at the top
NOT_FRAMES = {'audio', 'dub', 'subs', 'node_modules', '__pycache__'}
# + at the top only: this script's own contact sheets (--screenshot's default folder), so looking at sheets between a
# stopped MP4 and its resume does not throw the finished chunks away (a folder of that name deeper down still counts)
NOT_FRAMES_TOP = NOT_FRAMES | {'screenshots'}


def project_stamp():
    h = hashlib.sha1()
    files = [ROOT / n for n in ('index.html', 'glyphs.json') if (ROOT / n).is_file()]
    for e in sorted(ROOT.iterdir()):
        if e.is_dir() and not e.is_symlink() and e.name not in NOT_FRAMES_TOP and not e.name.startswith('.'):
            for d, dirs, names in os.walk(e):
                dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x not in NOT_FRAMES)
                files += [Path(d) / n for n in sorted(names) if not n.startswith('.')]
    for f in files:
        try:
            st = f.stat()
        except OSError:
            continue
        h.update(f'{f.relative_to(ROOT)}\0{st.st_size}\0{st.st_mtime_ns}\n'.encode())
    return h.hexdigest()


def stage_size():
    """the stage's logical size from index.html (#stage data-width / data-height; 1920×1080 if not given)"""
    html = (ROOT / 'index.html').read_text(encoding='utf-8', errors='replace')
    tag = re.search(r'<[^>]*\bid=["\']stage["\'][^>]*>', html)
    w = re.search(r'data-width=["\'](\d+)', tag.group(0)) if tag else None
    h = re.search(r'data-height=["\'](\d+)', tag.group(0)) if tag else None
    return (int(w.group(1)) if w else 1920), (int(h.group(1)) if h else 1080)


def footage_clips():
    """how many footage clips js/media-src.js declares (0 when the project has none)"""
    f = ROOT / 'js' / 'media-src.js'
    if not f.exists():
        return 0
    src = re.sub(r'/\*.*?\*/|(?<![:\'"])//[^\n]*', '', f.read_text(encoding='utf-8', errors='replace'), flags=re.S)
    return len(re.findall(r'\bfile\s*:', src))


# ---------------------------------------------------------------- a static server over this folder
class Quiet(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'                      # keep-alive: a browser reuses a few connections instead of one per file
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.mjs': 'text/javascript',
                      '.wasm': 'application/wasm', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.otf': 'font/otf', '.json': 'application/json'}

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        # --art: the page that builds one illustration module alone, made in memory (nothing is written into the project)
        if ART_HTML is not None and self.path.split('?')[0] == '/' + ART_PAGE:
            body = ART_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


ART_PAGE = '__render_art__.html'                       # the in-memory page of --art (served by the main process)
ART_HTML = None


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    request_queue_size = 512                           # the default 5 overflowed with two browsers loading at once (macOS
                                                       # refuses the extra connections: scripts went missing)

    def handle_error(self, request, client_address):   # a download the browser stopped (e.g. the narration): not an error
        pass


def serve():
    httpd = Server(('127.0.0.1', 0), partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}'


# ---------------------------------------------------------------- the browser
SOFT = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
GPU_MAC = ['--use-angle=metal', '--enable-gpu-rasterization', '--ignore-gpu-blocklist', '--enable-zero-copy']
COMMON = ['--disable-gpu-vsync', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
          '--disable-backgrounding-occluded-windows', '--autoplay-policy=no-user-gesture-required']


def headless_shell():
    """Playwright's headless shell already on this machine (any revision) — a fallback when the Python package's own
    browser is not installed"""
    for base in [VENV / 'ms-playwright', Path.home() / '.cache' / 'ms-playwright', Path.home() / 'Library' / 'Caches' / 'ms-playwright']:
        if not base.exists():
            continue
        for d in sorted(base.glob('chromium_headless_shell-*'), reverse=True):
            for exe in d.glob('chrome-headless-shell*/chrome-headless-shell'):
                return str(exe)
    return None


GL_PROBE = '''() => { const g = document.createElement('canvas').getContext('webgl2');
  if (!g) return '';
  const x = g.getExtension('WEBGL_debug_renderer_info');
  return String(x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER)); }'''


def gl_name(gl):
    """'ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)' → 'GPU · Metal · Apple M2 Pro'"""
    low = gl.lower()
    if 'swiftshader' in low:
        return '소프트웨어 그리기 (SwiftShader)'
    if 'metal renderer:' in low:
        return 'GPU · Metal · ' + gl[low.index('metal renderer:') + 15:].split(',')[0].strip()
    return 'GPU · ' + gl[:60]


def launch(pw, gpu):
    """the first browser that starts AND draws WebGL2 (the demos need it): returns (browser, options, renderer name)"""
    tries = []
    if gpu and IS_MAC:
        tries += [dict(channel='chrome', args=GPU_MAC + COMMON), dict(channel='chromium', args=GPU_MAC + COMMON)]
    tries += [dict(args=SOFT + COMMON)]
    shell = headless_shell()
    if shell:
        tries += [dict(executable_path=shell, args=SOFT + COMMON)]
    last = None
    for opt in tries:
        try:
            browser = pw.chromium.launch(headless=True, **opt)
        except Exception as e:      # that browser is not installed: the next one
            last = e; continue
        try:
            p = browser.new_page(); gl = p.evaluate(GL_PROBE); p.close()
        except Exception as e:
            gl = ''; last = e
        if gl:
            return browser, opt, gl
        last = last or 'WebGL2를 쓸 수 없음'
        browser.close()
    raise RuntimeError(f'WebGL2로 그릴 수 있는 Chrome을 띄우지 못했습니다 ({last}). 가상환경을 쓰면 {VENV / ".chromium-installed"} 를 지우고 '
                       '다시 실행해 Chromium을 새로 받으세요 (--no-venv면 python3 -m playwright install chromium).')


# ---------------------------------------------------------------- the font check (no glyph may come from a system font)
# Every canvas text is recorded with the font it was drawn in (a canvas is opaque to the DOM check); the DOM's visible
# text is asked, through Chrome's DevTools protocol, which font files actually drew it — a "platform" font is a system font.
CANVAS_REC = '''(() => {
  const seen = new Map(); window.__canvasText = seen;
  for (const C of [window.CanvasRenderingContext2D, window.OffscreenCanvasRenderingContext2D]) {
    if (!C) continue;
    for (const m of ['fillText', 'strokeText']) {
      const orig = C.prototype[m];
      C.prototype[m] = function (text, ...rest) {
        const f = String(this.font), k = f + '\\u0000' + text;
        if (seen.size < 20000 && !seen.has(k)) seen.set(k, { font: f, text: String(text) });
        return orig.call(this, text, ...rest);
      };
    }
  }
})();'''
CANVAS_BAD = '''() => {
  const GEN = /^(serif|sans-serif|monospace|cursive|fantasy|system-ui|emoji|math|fangsong)$/i;
  const faces = new Set([...document.fonts].map((f) => f.family.replace(/^["']|["']$/g, '').toLowerCase()));
  const out = [], done = new Set();
  for (const { font, text } of (window.__canvasText ? window.__canvasText.values() : [])) {
    if (!text.trim() || done.has(font)) continue;
    const m = font.match(/\\d+(?:\\.\\d+)?px(?:\\s*\\/\\s*[\\d.]+\\w*)?\\s+(.+)$/);
    const fams = (m ? m[1] : font).split(',').map((x) => x.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    // the canvas draws with the FIRST family it has, so the first one must be installed: 'sans-serif, Pretendard' draws
    // with the system sans-serif even though Pretendard is listed after it
    const first = fams[0];
    if (!first || GEN.test(first) || !faces.has(first.toLowerCase())) { done.add(font); out.push({ font, text: text.slice(0, 30) }); }
  }
  return out.slice(0, 5);
}'''
OWN_TEXT = '''() => [...document.querySelectorAll('#stage *')].map((el, i) => {
  const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  if (!own) return -1;
  return (el.checkVisibility ? el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) : true) ? i : -1;
}).filter((i) => i >= 0)'''


def dom_fonts(page, cdp, t, found):
    """the system ('platform') fonts that drew visible text at this moment → found[family] = [(t, text), …]"""
    root = cdp.send('DOM.getDocument', {'depth': -1})['root']
    ids = cdp.send('DOM.querySelectorAll', {'nodeId': root['nodeId'], 'selector': '#stage *'})['nodeIds']
    for i in page.evaluate(OWN_TEXT):
        if i >= len(ids):
            continue
        try:
            fonts = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': ids[i]}).get('fonts', [])
        except Exception:
            continue
        for f in fonts:
            if not f.get('isCustomFont') and len(found.setdefault(f['familyName'], [])) < 3:
                text = page.evaluate('(j) => (document.querySelectorAll("#stage *")[j] || {}).textContent', i) or ''
                found[f['familyName']].append((t, ' '.join(text.split())[:30]))


class Retry(Exception):
    """a chunk that went wrong for a passing reason (a file that did not arrive): it is made again from the start"""


class Stopped(Exception):
    """Ctrl+C in a movie render: the worker stops before its next frame and closes the file it was writing"""


STOP = None                 # a movie worker's stop flag (set by the main process on Ctrl+C); None everywhere else


def stopping():
    return STOP is not None and STOP.is_set()


class Offline(Exception):
    """the page sent a request to the network: the video must play from its own files — never retried (the message is
    the only argument, so the exception crosses from a worker process intact)"""


def offline(urls):
    return Offline(f'페이지가 네트워크에 요청을 보냈습니다 ({len(urls)}건) — 첫 번째: {urls[0][:160]} · 영상은 프로젝트 안의 '
                   f'파일만으로 재생됩니다: 글꼴은 add_font.mjs로 설치하고, 그림은 코드로 그리고, 사용자가 준 파일은 assets/user/에')


def watch_network(page, base, remote):
    """every request the page really sends that is not to this script's own server (the project's files) nor a data:/
    blob:/about: URL goes into `remote` — what counts is what the browser asked for, however the address was built"""
    def on_request(r):
        u = r.url
        if not (u == base or u.startswith(base + '/') or u.startswith(('data:', 'blob:', 'about:'))):
            remote.append(u)
    page.on('request', on_request)


LOAD_STATE = '''() => {
  const v = window.__video, t = document.querySelector('.vp-start-title');
  return [!!(v && v.renderReady !== false && document.body.classList.contains('vp-ready')),
          t ? t.textContent.trim() : '', !!(t && t.classList.contains('vp-error'))];
}'''
BUSY = '() => { const v = window.__video; return !!(v && v.renderBusy && v.renderBusy()); }'
# the player's own UI never in the picture — also in projects whose player predates ?render (body.vp-render)
HIDE_UI = '.vp-start, .vp-debug, .vp-rate, .vp-fc, .vp-drop { display: none !important; } body { cursor: none !important; }'
STALL = 15 * 60          # no change in the page's own loading text for this long: stop and say where it stood
# every clip placement of the page (the whole timeline) with the frame count media.js asks for at this render's fps
FOOTAGE = '''() => {
  const M = window.__media;
  return M && M.list ? M.list().map((m) => ({ id: m.id, res: m.res, n: Math.max(1, Math.ceil(m.dur * M.mfps - 1e-6)) })) : [];
}'''
FRAMES_UNFIT = 'frames-unfit.json'       # a worker's list of footage frames that don't fit this render (the main process says it)


def jpeg_width(path):
    """a JPEG's width in pixels, read from its frame header (None when it can't be read)"""
    try:
        with open(path, 'rb') as fh:
            b = fh.read(1 << 16)
    except OSError:
        return None
    if b[:2] != b'\xff\xd8':
        return None
    i = 2
    while i + 9 <= len(b):
        if b[i] != 0xFF:
            return None
        m = b[i + 1]
        if m == 0xFF:                                   # a fill byte
            i += 1
        elif 0xD0 <= m <= 0xD8 or m == 0x01:            # markers without a length
            i += 2
        elif 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):   # the frame header: length, precision, height, width
            return int.from_bytes(b[i + 7:i + 9], 'big')
        else:
            i += 2 + int.from_bytes(b[i + 2:i + 4], 'big')
    return None


def frames_check(page, frames, o, work):
    """footage is filmed from frames stills.mjs cut beforehand (<frames>/<placement id>/00001.jpg …). Every placement of
    the page needs them at this render's fps (exactly the count media.js asks for) and at least as wide as the clip is
    drawn at this resolution: a smaller cut (480p frames in a 4K render) is scaled up into a blurry clip, a missing one
    leaves the clip empty, another count plays it at the wrong speed. Then the run stops before a frame is drawn — the
    list goes to the work folder for the main process to say, with the command that cuts them again"""
    bad, seen = [], set()
    for m in page.evaluate(FOOTAGE):
        if m['id'] in seen:
            continue
        seen.add(m['id'])
        d = os.path.join(frames, m['id'])
        have = [x for x in os.listdir(d) if re.fullmatch(r'\d{5}\.jpg', x)] if os.path.isdir(d) else []
        want = max(64, int(m['res'] * o['scale'] / 2 + 0.5) * 2)   # the width stills.mjs cuts at this scale
        w = jpeg_width(os.path.join(d, '00001.jpg')) if have else None
        if not have:
            bad.append(f'{m["id"]}: 잘라 둔 프레임 없음')
        elif len(have) != m['n']:
            bad.append(f'{m["id"]}: {len(have)}장 — {o["fps"]}fps에는 {m["n"]}장')
        elif not w:
            bad.append(f'{m["id"]}: 첫 프레임(00001.jpg)을 읽지 못함')
        elif w < want - 2:                              # (2 px: one rounding step — a scale typed as 0.4444 for 4/9)
            bad.append(f'{m["id"]}: 가로 {w}px — 이 해상도에는 {want}px')
    if bad:
        p = os.path.join(work, FRAMES_UNFIT)
        tmp = f'{p}.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(bad, fh, ensure_ascii=False)
        os.replace(tmp, p)
        raise RuntimeError(f'영상 클립의 렌더용 프레임이 이 렌더와 맞지 않음 — {bad[0]}')


def frames_unfit(work, footage, fps, scale, res):
    """a worker stopped the run because the footage frames don't fit this render (frames_check): say which and how to cut
    them again, then stop. Nothing happens when that is not why it stopped"""
    f = Path(work) / FRAMES_UNFIT
    if not f.exists():
        return
    bad = json.loads(f.read_text(encoding='utf-8'))
    f.unlink()
    warn(f'영상 클립의 렌더용 프레임({footage}/)이 이 렌더({res}, {fps}fps)와 맞지 않아 그리기 전에 멈췄습니다 — {len(bad)}곳:\n'
         + ''.join(f'    {b}\n' for b in bad[:6]) + (f'    … 그 밖에 {len(bad) - 6}곳\n' if len(bad) > 6 else '')
         + '작게 잘린 프레임은 늘려 그려져 클립이 흐려지고, 장 수가 다르면 클립이 비거나 빠르기가 어긋납니다. 다시 잘라 주세요\n'
         '(맞는 것은 그대로 두고, 없거나 작거나 장 수가 다른 것만 다시 자릅니다):\n'
         f'    node <스킬 폴더>/scripts/stills.mjs . --out {footage} --fps {fps} --scale {scale:.4g}')
    sys.exit(1)


def open_page(browser, base, a, b, captions, label, scale=1, size=(1920, 1080), extra='', page_path='index.html'):
    """open the video for one chunk and wait until it is built; the page's own loading text (장면 n / 15, 작품 n / N) goes
    to the status line while it builds, page errors are reported as they happen (page_path: --art's module page)"""
    page = browser.new_page(viewport={'width': size[0], 'height': size[1]}, device_scale_factor=scale)   # 4K: the same layout, 2× the pixels
    errors, failed, remote = [], [], []
    watch_network(page, base, remote)

    def on_failed(r):                                  # a file that did not arrive (a download the page itself stopped,
        why = r.failure or ''                          # ERR_ABORTED — e.g. the narration — is not a failure)
        if 'ERR_ABORTED' not in why:
            failed.append(f'{r.url.split("/", 3)[-1].split("?")[0]} ({why})')
    page.on('requestfailed', on_failed)
    page.add_init_script(CANVAS_REC)                   # (before any script of the page runs)

    def on_error(e):
        errors.append(str(e)[:300])
        if len(errors) <= 3:
            emit('m', f'{label}: 페이지 오류 — {errors[-1]}')
    page.on('pageerror', on_error)
    # only what the player reads: a project's own code may read other names (a page shown inside the video reads
    # ?embed and hides its captions), so the top page is never given one of those
    q = f'render&from={max(0, a - 1):.2f}&to={b + 1:.2f}' + ('&captions' if captions else '') + extra
    t0 = time.time()
    emit('s', f'{label}: 페이지 여는 중')
    page.goto(f'{base}/{page_path}?{q}', wait_until='domcontentloaded', timeout=300000)
    last, since = None, time.time()
    while True:
        ok, text, err = page.evaluate(LOAD_STATE)
        if err:
            page.wait_for_timeout(300)                  # (failed-file reports still on their way)
        if remote:
            raise offline(remote)
        if failed:
            raise Retry(f'파일 {len(failed)}개를 받지 못함 — {failed[0]}')
        if ok:
            break
        if stopping():
            raise Stopped()
        if err:
            raise RuntimeError(f'페이지가 오류를 냈습니다: {text}' + (f' / {errors[0]}' if errors else ''))
        if text != last:
            last, since = text, time.time()
            emit('s', f'{label}: {text or "페이지 여는 중"} ({hms(time.time() - t0)})')
        elif time.time() - since > STALL:
            raise RuntimeError(f'{STALL // 60}분 동안 불러오기가 나아가지 않았습니다 — 마지막 상태: {text!r}'
                               + (f' / 페이지 오류: {errors[0]}' if errors else ''))
        page.wait_for_timeout(500)                      # (also lets Playwright deliver the page's events)
    page.wait_for_load_state('load', timeout=300000)
    page.add_style_tag(content=HIDE_UI)
    page.evaluate('() => document.fonts ? document.fonts.ready.then(() => true) : true')
    if remote:
        raise offline(remote)
    if failed:
        raise Retry(f'파일 {len(failed)}개를 받지 못함 — {failed[0]}')
    return page, errors, failed, remote, time.time() - t0


def seek_drawn(page, t):
    """move to t and wait until every demo (and the agent's pages) has drawn it; then two animation frames"""
    page.evaluate('(x) => window.__video.seek(x)', t)
    waited = False
    for _ in range(6000):                               # up to 2 minutes for one frame
        if not page.evaluate(BUSY):
            break
        if stopping():
            raise Stopped()
        waited = True
        time.sleep(0.02)
    else:
        emit('m', f'경고: {t:.3f}초 장면이 2분을 기다려도 다 그려지지 않아 그 상태로 찍었습니다')
    if waited:
        page.evaluate('(x) => window.__video.seek(x)', t)
    page.evaluate('() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))')


def shot(page, png, fast, size=(1920, 1080), clip=None, jq=95):
    """one frame of the stage (or of clip = (x, y, w, h) in stage pixels: --crop), at the page's device scale"""
    kw = dict(type='png') if png else dict(type='jpeg', quality=jq)
    x, y, w, h = clip or (0, 0, size[0], size[1])
    # (no animations='disabled': Playwright would rewind infinite CSS animations and finish finite ones, undoing the
    # player's pause + seek of every document animation to t — an ambient @keyframes loop would freeze or jump)
    one = lambda: page.screenshot(clip={'x': x, 'y': y, 'width': w, 'height': h}, caret='hide', timeout=0, **kw)
    prev = one()
    if fast:
        return prev
    for _ in range(4):                                   # raster can lag a big change: until two captures agree
        cur = one()
        if cur == prev:
            return cur
        prev = cur
        page.evaluate('() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))')
    return prev


# ---------------------------------------------------------------- the encoder
def encoders():
    try:
        return subprocess.run([FFMPEG, '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
    except Exception:
        return ''


def pick_encoder(choice, codec):
    """'videotoolbox' (the Mac's hardware encoder) or 'software' (libx264 / libx265)"""
    if choice == 'auto':
        return 'videotoolbox' if IS_MAC and f'{codec}_videotoolbox' in encoders() else 'software'
    return 'software' if choice in ('software', 'x264') else choice


ENC_NAME = {('videotoolbox', 'h264'): 'h264_videotoolbox', ('videotoolbox', 'hevc'): 'hevc_videotoolbox',
            ('software', 'h264'): 'libx264', ('software', 'hevc'): 'libx265',
            ('lossless', 'h264'): 'libx264'}          # --quality ultra (YUV 4:4:4 at qp 0)
# hardware bitrates for 1920×1080 at 60 fps (Mbit/s, high · max); other sizes scale with the pixel count^0.75 (4K ≈ ×2.8,
# within YouTube's 4K60 range), ×0.6 at 40 fps or less; HEVC carries the same picture in about two thirds
VT_MBPS = {'h264': (30, 60), 'hevc': (20, 40)}


def ff_args(encoder, codec, pixels, quality, fps, png, out, size=None):
    if encoder == 'lossless':
        # --quality ultra: the captures (JPEG 100, or PNG with --png) decoded to RGB first, then BT.709 YUV 4:4:4 (the
        # same matrix and range as every other movie here, but no colour halving and no resize), compressed losslessly
        # (qp 0 → High 4:4:4 Predictive): the only loss is the 8-bit RGB → YUV rounding (and JPEG 100's own, without
        # --png). Not H.264 RGB: players that ignore its GBR matrix tag show it green and pink
        return [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'png' if png else 'mjpeg', '-i', '-',
                '-vf', 'format=rgb24,scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv444p',
                '-c:v', 'libx264', '-qp', '0', '-preset', 'medium',
                '-r', str(fps), '-g', str(fps * 2), '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-bsf:v', 'h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0', out]
    a = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'png' if png else 'mjpeg', '-i', '-',
         # the movie's exact size (even: yuv420p needs it) — at 480p the capture is 853⅓ px wide and lands on 853 or 854
         '-vf', (f'scale={size[0]}:{size[1]}:flags=lanczos:' if size else 'scale=trunc(iw/2)*2:trunc(ih/2)*2:') +
         'out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', ENC_NAME[encoder, codec]]
    if encoder == 'videotoolbox':
        mbps = VT_MBPS[codec][quality == 'max'] * (pixels / (1920 * 1080)) ** 0.75 * (1 if fps > 40 else 0.6)
        a += ['-profile:v', 'high' if codec == 'h264' else 'main', '-b:v', f'{mbps:.0f}M', '-maxrate', f'{mbps * 1.5:.0f}M', '-bufsize', f'{mbps * 2:.0f}M']
    elif codec == 'h264':
        a += ['-profile:v', 'high'] + {'high': ['-preset', 'medium', '-crf', '16'], 'max': ['-preset', 'slow', '-crf', '12']}[quality]
    else:
        a += ['-profile:v', 'main', '-x265-params', 'log-level=error'] + {'high': ['-preset', 'medium', '-crf', '18'], 'max': ['-preset', 'slow', '-crf', '14']}[quality]
    if codec == 'hevc':
        a += ['-tag:v', 'hvc1']                         # the tag Apple's players (QuickTime, iPhone) need for HEVC in MP4
    # the colour description is also written into the stream itself (VideoToolbox leaves primaries and transfer out:
    # players then guess) — BT.709, limited range
    return a + ['-r', str(fps), '-g', str(fps * 2), '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-bsf:v', f'{codec}_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0', out]


# ---------------------------------------------------------------- progress: one live status line for the whole render
# Workers (or the main process, with one job) send ('f', 1) per frame and ('m', text) for news through one queue; the
# main process keeps the totals and redraws a single line every half second: frames done / all, %, elapsed, frames per
# second and the time left (measured from the first rendered frame, so browser start-up does not skew it). News lines
# are printed above it. When the output is not a terminal (a log file), the status is a plain line every 15 seconds.
Q = None


def _init_worker(q, stop=None):
    global Q, STOP
    Q, STOP = q, stop
    signal.signal(signal.SIGINT, signal.SIG_IGN)       # Ctrl+C is handled once, by the main process
    if stop is not None and hasattr(os, 'setsid'):
        # a movie worker leaves the terminal's process group, and its browser driver with it: Ctrl+C then reaches only
        # the main process, which sets `stop` — the browser is not closed under the worker, so it can finish the frame
        # it is on and close its file (the part saved as a movie)
        os.setsid()
    parent = os.getppid()

    def orphan_watch():                                 # the main process was killed outright (no Ctrl+C): don't go on alone
        while os.getppid() == parent:
            time.sleep(2)
        os._exit(1)
    threading.Thread(target=orphan_watch, daemon=True).start()


def emit(kind, v):
    if Q is not None:
        Q.put((kind, v))
    elif kind == 'm':
        (warn if PROBLEM.search(v) else say)(v)


def hms(sec):
    sec = int(max(0, sec))
    return f'{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}' if sec >= 3600 else f'{sec // 60}:{sec % 60:02d}'


def cells(c):
    return 2 if unicodedata.east_asian_width(c) in 'WFA' else 1      # ambiguous (·, …) counted wide: never wrap


def fit(s, cols):
    if sum(map(cells, s)) <= cols:
        return s
    w = 2
    for i, c in enumerate(s):
        w += cells(c)
        if w > cols:
            return s[:i] + '…'
    return s


class Progress(threading.Thread):
    def __init__(self, q, total, done0):
        super().__init__(daemon=True)
        self.q, self.total, self.done, self.new, self.status = q, total, done0, 0, ''
        self.t0, self.first, self.stop, self.tty = time.time(), None, threading.Event(), sys.stdout.isatty()
        self.last_plain = 0

    def line(self):
        el = time.time() - self.t0
        pct = f'{100 * self.done / self.total:.1f}%'
        if not self.new:
            return f'진행 {pct} · {self.status or "준비 중"} · {self.done:,}/{self.total:,} 프레임 · 경과 {hms(el)}'
        rate = self.new / max(1e-6, time.time() - self.first)
        left = (self.total - self.done) / max(1e-6, rate)
        return f'진행 {pct} · 남은 약 {hms(left)} · {self.done:,}/{self.total:,} 프레임 · 경과 {hms(el)} · 초당 {rate:.2f}장'

    def draw(self, force=False):
        if QUIET:
            return
        if self.tty:
            cols = shutil.get_terminal_size((80, 24)).columns
            sys.stdout.write('\r\033[K' + fit(self.line(), cols - 1)); sys.stdout.flush()
        elif force or time.time() - self.last_plain >= 15:
            print(time.strftime('[%H:%M:%S]'), self.line(), flush=True); self.last_plain = time.time()

    def take(self, kind, v):
        if kind == 'f':
            self.done += v; self.new += v
            if self.first is None:
                self.first = time.time() - 0.001
        elif kind == 's':
            self.status = v
            if QUIET:
                return
            if not self.new and not self.tty:           # a log file: each loading step on its own line until frames flow
                print(time.strftime('[%H:%M:%S]'), self.line(), flush=True); self.last_plain = time.time()
        elif kind == 'm':
            if QUIET:
                if PROBLEM.search(v):
                    warn(v)
                return
            if self.tty:
                sys.stdout.write('\r\033[K')
            print(time.strftime('[%H:%M:%S]'), v, flush=True)

    def run(self):
        import queue as _q
        while not self.stop.is_set():
            try:
                self.take(*self.q.get(timeout=0.5))
            except _q.Empty:
                pass
            self.draw()

    def finish(self, drain=True):
        import queue as _q
        self.stop.set(); self.join(timeout=2)
        while drain:                                    # reports still on their way (not after Ctrl+C: a killed worker
            try:                                        # may have left half a message in the pipe)
                self.take(*self.q.get(timeout=0.3))
            except _q.Empty:
                break
        self.draw(force=True)
        if self.tty and not QUIET:
            print(flush=True)


# ---------------------------------------------------------------- one chunk (a worker process: its own browser and ffmpeg)
def render_chunk(job):
    label = job[5]
    for attempt in range(1, 4):
        if stopping():                                  # (a chunk not started yet when Ctrl+C came)
            return None
        try:
            return chunk_once(job)
        except Stopped:
            return None
        except Retry as e:
            if stopping():
                return None
            if attempt == 3:
                raise RuntimeError(f'{label}: 세 번 해도 안 됨 — {e}')
            emit('m', f'{label}: {e} — 처음부터 다시 ({attempt + 1}/3)')
            time.sleep(2)


def chunk_once(job):
    from playwright.sync_api import sync_playwright
    n0, n1, out, o, base, label, frames = job
    tmp = out + '.part.mp4'
    # after Ctrl+C: the frames tmp holds (written only once ffmpeg has closed tmp cleanly) — the main process joins it
    # after the finished chunks before it, as the part made so far
    part_info = out + '.part.json'
    if os.path.exists(part_info):
        os.remove(part_info)
    t_start = time.time()
    sent, ff, flog, stopped = 0, None, None, False
    with sync_playwright() as pw:
        emit('s', f'{label}: 브라우저 띄우는 중')
        browser, how, gl = launch(pw, o['gpu'])
        try:
            emit('m', f'{label}: 브라우저 — {gl_name(gl)} · {how.get("channel") or "chromium"} · 영상 불러오는 중 (프레임 {n0}–{n1 - 1})')
            page, errors, failed, remote, took = open_page(browser, base, n0 / o['fps'], n1 / o['fps'], o['captions'], label, o['scale'], o['size'], o['extra'])
            if frames:
                frames_check(page, frames, o, os.path.dirname(out))
            emit('m', f'{label}: 불러오기 끝 ({hms(took)}) — 그리기 시작')
            # the clips that play their own sound (mixed in at the end) — the same list for every chunk (the whole timeline).
            # Written even when it is empty, so the last step can tell "no clip has sound" from "no chunk recorded it";
            # a temp name of this process's own, so chunks rendering at once never write the same temp file
            sounds = page.evaluate('() => (window.__media && window.__media.audio ? window.__media.audio() : [])')
            cj = os.path.join(os.path.dirname(out), 'clips.json')
            cj_tmp = f'{cj}.{os.getpid()}.tmp'
            with open(cj_tmp, 'w', encoding='utf-8') as fh:
                json.dump(sounds or [], fh)
            os.replace(cj_tmp, cj)
            emit('s', '')
            # ffmpeg in a process group of its own (Ctrl+C in the terminal is the main process's to handle; when this worker
            # is stopped, ffmpeg sees its input end and quits), its messages kept and shown only if it fails
            flog = open(out + '.log', 'w+b')
            ff = subprocess.Popen(ff_args(o['encoder'], o['codec'], o['pixels'], o['quality'], o['fps'], o['png'], tmp, o['out_size']), stdin=subprocess.PIPE,
                                  stderr=flog, start_new_session=True)
            t0 = time.time()
            cdp, system = None, {}
            if o['fontcheck']:
                try:
                    cdp = page.context.new_cdp_session(page); cdp.send('DOM.enable'); cdp.send('CSS.enable')
                except Exception:
                    cdp = None
            every = max(1, int(o['fps'] * 5))
            for n in range(n0, n1):
                if stopping():
                    raise Stopped()
                seek_drawn(page, n / o['fps'])
                if cdp and (n - n0) % every == 0:
                    try:
                        dom_fonts(page, cdp, n / o['fps'], system)
                    except Exception:
                        pass
                if remote:                              # a request to the network while drawing
                    raise offline(remote)
                if failed:                              # a file the scene asked for while drawing did not arrive
                    raise Retry(f'그리는 중 파일 {len(failed)}개를 받지 못함 — {failed[0]}')
                ff.stdin.write(shot(page, o['png'], o['fast'], o['size'], jq=o.get('jpeg', 95)))
                emit('f', 1); sent += 1
            ff.stdin.close()
            if ff.wait() != 0:
                flog.seek(0)
                raise RuntimeError('ffmpeg 오류: ' + flog.read().decode('utf-8', 'replace').strip()[-800:])
            ff = None
            flog.close(); os.remove(out + '.log')
            os.replace(tmp, out)
            emit('m', f'{label}: 완료 ({hms(time.time() - t0)})' + (f' · 페이지 오류 {len(errors)}건 — 첫 번째: {errors[0]}' if errors else ''))
            if o['fontcheck']:
                for fam, seen in system.items():
                    emit('m', f'{label}: 글꼴 경고 — 시스템 글꼴 "{fam}"이 그린 글자: ' + ' · '.join(f't={t:.1f} "{x}"' for t, x in seen))
                for c in page.evaluate(CANVAS_BAD):
                    emit('m', f'{label}: 글꼴 경고 — 캔버스 글자 "{c["text"]}"를 설치되지 않은 글꼴로 그림 ({c["font"]}) — 시스템 글꼴로 나옵니다')
        except Retry:
            if sent:
                emit('f', -sent)                        # those frames are made again
            raise
        except Stopped:
            stopped = True
            raise
        finally:
            if ff is not None and ff.poll() is None:
                if stopped and sent:                    # Ctrl+C: end the file after the last whole frame, and say how many
                    try:
                        ff.stdin.close()
                    except OSError:
                        pass
                    if ff.wait() == 0:
                        with open(part_info, 'w', encoding='utf-8') as fh:
                            json.dump({'frames': sent}, fh)
                else:
                    ff.kill(); ff.wait()
            browser.close()
    return time.time() - t_start


# ---------------------------------------------------------------- --screenshot: contact sheets instead of a movie
def fmt_t(t):
    return f'{int(t // 60)}:{t % 60:05.2f}'


def face_css(base):
    """the project's own @font-face rules (its installed OFL fonts), pointed at the local server — the sheet's labels use them"""
    out = []
    for css in sorted((ROOT / 'css').glob('*.css')):
        for blk in re.findall(r'@font-face\s*{[^}]*}', css.read_text(encoding='utf-8', errors='replace')):
            out.append(re.sub(r"url\((['\"]?)\.\./", lambda m: f'url({m.group(1)}{base}/', blk))
    return '\n'.join(out)


# --via: the third tile of a row shows where the two captures differ — the first capture greyed and darkened, every pixel
# that differs (any channel by more than 2, as snapshot.mjs --seekcheck counts) in magenta, brighter the larger the
# difference, and a yellow box around them all; its label gives the count and the box in stage pixels
DIFF_JS = '''async ([scale, cx, cy]) => {
  await document.fonts.ready;
  await Promise.all([...document.images].map((i) => i.decode().catch(() => {})));
  for (const c of document.querySelectorAll('canvas.d')) {
    const A = document.getElementById(c.dataset.a), B = document.getElementById(c.dataset.b);
    const w = A.naturalWidth, h = A.naturalHeight;
    const px = (im) => { const k = document.createElement('canvas'); k.width = w; k.height = h; const x = k.getContext('2d'); x.drawImage(im, 0, 0, w, h); return x.getImageData(0, 0, w, h).data; };
    const a = px(A), b = px(B);
    c.width = w; c.height = h;
    const g = c.getContext('2d'), out = g.createImageData(w, h), o = out.data;
    let n = 0, x0 = w, y0 = h, x1 = -1, y1 = -1;
    for (let i = 0; i < a.length; i += 4) {
      const d = Math.max(Math.abs(a[i] - b[i]), Math.abs(a[i + 1] - b[i + 1]), Math.abs(a[i + 2] - b[i + 2]), Math.abs(a[i + 3] - b[i + 3]));
      const grey = (a[i] * 0.3 + a[i + 1] * 0.59 + a[i + 2] * 0.11) * 0.28;
      if (d > 2) {
        n++; const p = i / 4, x = p % w, y = (p - x) / w;
        if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y;
        const k = Math.min(1, 0.45 + d / 40);
        o[i] = 255 * k; o[i + 1] = 30 * k; o[i + 2] = 210 * k;
      } else { o[i] = o[i + 1] = o[i + 2] = grey; }
      o[i + 3] = 255;
    }
    g.putImageData(out, 0, 0);
    const lab = document.getElementById(c.dataset.l);
    if (n) {
      g.strokeStyle = '#ffd400'; g.lineWidth = Math.max(2, w / 400);
      g.strokeRect(x0 - 3, y0 - 3, x1 - x0 + 7, y1 - y0 + 7);
      const s = (v) => Math.round(v / scale);
      lab.innerHTML = `<b>차이 ${n.toLocaleString()}픽셀</b> &nbsp;상자 ${s(x1 - x0 + 1)}×${s(y1 - y0 + 1)} @ ${s(x0) + cx},${s(y0) + cy} (무대 px)`;
    } else lab.innerHTML = '<b>차이 없음</b> (두 장이 같음)';
  }
}'''


def compose_sheet(browser, faces, shots, items, header, o):
    """lay the captured frames out on one image: a header line, then the frames in rows, each with frame · time · cue.
    With --via each frame is a row of three: as filmed in order | after coming from the --via time | where they differ"""
    import base64
    tw, th = o['out_size']
    via = o.get('via')
    n_tiles = len(shots) * 3 if via is not None else len(shots)
    cols = 3 if via is not None else max(1, min(o['cols'], n_tiles))   # (fewer tiles than columns: no empty band)
    rows = (n_tiles + cols - 1) // cols
    narrow = tw < 560                                   # a small tile: its label wraps onto two lines instead of being cut
    pad, lab, head = 16, (60 if narrow else 34), 58
    SW, SH = pad + cols * (tw + pad), head + rows * (th + lab + pad) + pad // 2
    mime = 'image/png' if o.get('cap_png', o['png']) else 'image/jpeg'
    b64 = lambda img: base64.b64encode(img).decode()
    cells = []
    pos = lambda k: (pad + (k % cols) * (tw + pad), head + (k // cols) * (th + lab + pad))
    for k, (img, (n, t, cue)) in enumerate(zip(shots, items)):
        name = f'<b>{n}</b> &nbsp;{fmt_t(t)} &nbsp;{cue}'
        if via is None:
            x, y = pos(k)
            cells.append(f'<div class="c" style="left:{x}px;top:{y}px"><img src="data:{mime};base64,{b64(img)}">'
                         f'<div class="l">{name}</div></div>')
            continue
        a, b = img
        (xa, ya), (xb, yb), (xd, yd) = pos(3 * k), pos(3 * k + 1), pos(3 * k + 2)
        cells.append(f'<div class="c" style="left:{xa}px;top:{ya}px"><img id="a{k}" src="data:{mime};base64,{b64(a)}">'
                     f'<div class="l">{name} &nbsp;· 순서대로</div></div>')
        cells.append(f'<div class="c" style="left:{xb}px;top:{yb}px"><img id="b{k}" src="data:{mime};base64,{b64(b)}">'
                     f'<div class="l">{name} &nbsp;· {fmt_t(via)}에서 건너옴</div></div>')
        cells.append(f'<div class="c" style="left:{xd}px;top:{yd}px"><canvas class="d" data-a="a{k}" data-b="b{k}" data-l="d{k}"></canvas>'
                     f'<div class="l" id="d{k}">차이 계산 중</div></div>')
    page = browser.new_page(viewport={'width': SW, 'height': SH}, device_scale_factor=1)
    try:
        page.set_content(f"""<!doctype html><html><head><meta charset="utf-8"><style>{faces}
html, body {{ margin: 0; background: #2a2a2e; }}
.h {{ position: absolute; left: {pad}px; top: 16px; font: 600 26px/1 'Pretendard', sans-serif; color: #e9e6df; white-space: nowrap; }}
.c {{ position: absolute; width: {tw}px; }}
.c img, .c canvas {{ display: block; width: {tw}px; height: {th}px; outline: 1px solid #5a5a62; }}
.c .l {{ height: {lab}px; font: 400 19px/{26 if narrow else lab}px 'D2Coding', 'Pretendard', monospace; color: #b9b5ad;
         white-space: {'normal' if narrow else 'nowrap'}; overflow: hidden; padding-top: {4 if narrow else 0}px; box-sizing: border-box; }}
.c .l b {{ color: #e9e6df; font-weight: 700; }}
</style></head><body><div class="h">{header}</div>{''.join(cells)}</body></html>""", wait_until='load')
        page.evaluate('async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode().catch(() => {}))); }')
        hw = int(page.evaluate("() => document.querySelector('.h').getBoundingClientRect().width")) + 2 * pad
        if hw > SW:                                     # a narrow sheet (one small tile): wide enough for its header line
            SW = hw
            page.set_viewport_size({'width': SW, 'height': SH})
        if via is not None:
            cx, cy = (o.get('clip') or (0, 0))[:2]
            page.evaluate(DIFF_JS, [o['scale'], cx, cy])
        kw = dict(type='png') if o['png'] else dict(type='jpeg', quality=90)
        return page.screenshot(clip={'x': 0, 'y': 0, 'width': SW, 'height': SH}, timeout=0, **kw)
    finally:
        page.close()


def render_sheet(job):
    for attempt in range(1, 4):
        try:
            return sheet_once(job)
        except Retry as e:
            if attempt == 3:
                raise RuntimeError(f'{job["label"]}: 세 번 해도 안 됨 — {e}')
            emit('m', f'{job["label"]}: {e} — 처음부터 다시 ({attempt + 1}/3)')
            time.sleep(2)


def static_once(job):
    """a page that is not a video (the thumbnail page, a card): load it, wait for its fonts and images and two frames,
    capture it once (or its --crop) and lay it out as a one-tile sheet"""
    from playwright.sync_api import sync_playwright
    from urllib.parse import quote
    o, base, label, out, items = job['o'], job['base'], job['label'], job['out'], job['items']
    with sync_playwright() as pw:
        emit('s', f'{label}: 브라우저 띄우는 중')
        browser, how, gl = launch(pw, o['gpu'])
        try:
            page = browser.new_page(viewport={'width': o['size'][0], 'height': o['size'][1]}, device_scale_factor=o['scale'])
            errors, failed, remote = [], [], []
            watch_network(page, base, remote)
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.on('requestfailed', lambda r: None if 'ERR_ABORTED' in (r.failure or '') else failed.append(r.url.split('/', 3)[-1]))
            page.add_init_script(CANVAS_REC)
            emit('s', f'{label}: 페이지 여는 중')
            page.goto(f'{base}/{quote(o["page"])}', wait_until='load', timeout=300000)
            page.evaluate('async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode().catch(() => {})));'
                          ' await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }')
            shots = [shot(page, o.get('cap_png', o['png']), o['fast'], o['size'], o.get('clip'))]
            if remote:
                raise offline(remote)
            emit('f', 1)
            img = compose_sheet(browser, job['faces'], shots, items, job['header'], o)
            with open(out + '.part', 'wb') as fh:
                fh.write(img)
            os.replace(out + '.part', out)
            emit('m', f'{label}: 완료' + (f' · 페이지 오류 {len(errors)}건 — 첫 번째: {errors[0]}' if errors else '')
                 + (f' · 받지 못한 파일 {len(failed)}개 — 첫 번째: {failed[0]}' if failed else ''))
        finally:
            browser.close()


def sheet_once(job):
    """the sheets of one job, in order, from one browser and one page: the page is built once and every tile of every
    sheet is reached by seeking to it, the way a movie chunk is filmed. Each sheet is written as soon as it is laid out,
    so a stopped or failed job goes on from the first sheet not yet written (and a retry starts there)"""
    sheets = [s for s in job['sheets'] if not os.path.exists(s['out'])]
    if not sheets:
        return
    if job['o'].get('static'):
        for s in sheets:
            static_once(dict(job, **s))
        return
    from playwright.sync_api import sync_playwright
    o, base, label = job['o'], job['base'], job['label']
    items = [it for s in sheets for it in s['items']]
    sent = 0                                            # tiles counted for the sheet being made (taken back on a retry)
    with sync_playwright() as pw:
        emit('s', f'{label}: 브라우저 띄우는 중')
        browser, how, gl = launch(pw, o['gpu'])
        try:
            emit('m', f'{label}: 브라우저 — {gl_name(gl)} · {how.get("channel") or "chromium"} · 영상 불러오는 중 '
                      f'({fmt_t(min(x[1] for x in items))}–{fmt_t(max(x[1] for x in items))}, {len(items)}칸'
                      f'{f", 시트 {len(sheets)}장" if len(sheets) > 1 else ""})')
            via = o.get('via')
            ts = [x[1] for x in items] + ([via] if via is not None else [])  # (--art keeps the order given; the page is
            a, b = min(ts), max(ts) + 1 / o['fps']                          # built for the --via time too)
            page, errors, failed, remote, took = open_page(browser, base, a, b, o['captions'], label,
                                                           o['scale'], o['size'], o['extra'], o.get('page', 'index.html'))
            if job['frames']:
                frames_check(page, job['frames'], o, os.path.dirname(sheets[0]['out']))
            emit('m', f'{label}: 불러오기 끝 ({hms(took)}) — 찍기 시작')
            emit('s', '')
            cdp, system = None, {}
            if o['fontcheck']:
                try:
                    cdp = page.context.new_cdp_session(page); cdp.send('DOM.enable'); cdp.send('CSS.enable')
                except Exception:
                    cdp = None
            cap = lambda: shot(page, o.get('cap_png', o['png']), o['fast'], o['size'], o.get('clip'))
            k, told = 0, 0
            for s in sheets:
                shots = []
                for n, t, cue in s['items']:
                    seek_drawn(page, t)
                    if cdp and k % 12 == 0:
                        try:
                            dom_fonts(page, cdp, t, system)
                        except Exception:
                            pass
                    k += 1
                    if remote:
                        raise offline(remote)
                    if failed:
                        raise Retry(f'그리는 중 파일 {len(failed)}개를 받지 못함 — {failed[0]}')
                    if via is None:
                        shots.append(cap())
                    else:                               # the same t again, reached from the --via time
                        first = cap()
                        seek_drawn(page, via)
                        seek_drawn(page, t)
                        shots.append((first, cap()))
                    emit('f', 1); sent += 1
                img = compose_sheet(browser, job['faces'], shots, s['items'], s['header'], o)
                with open(s['out'] + '.part', 'wb') as fh:
                    fh.write(img)
                os.replace(s['out'] + '.part', s['out'])
                sent = 0
                new = errors[told:]; told = len(errors)  # (the page errors since the sheet before: each is told once)
                emit('m', f'{s["label"]}: 완료' + (f' · 페이지 오류 {len(new)}건 — 첫 번째: {new[0]}' if new else ''))
            if o['fontcheck']:
                for fam, seen in system.items():
                    emit('m', f'{label}: 글꼴 경고 — 시스템 글꼴 "{fam}"이 그린 글자: ' + ' · '.join(f't={t:.1f} "{x}"' for t, x in seen))
                for c in page.evaluate(CANVAS_BAD):
                    emit('m', f'{label}: 글꼴 경고 — 캔버스 글자 "{c["text"]}"를 설치되지 않은 글꼴로 그림 ({c["font"]}) — 시스템 글꼴로 나옵니다')
        except Retry:
            if sent:
                emit('f', -sent)
            raise
        finally:
            browser.close()


SR_MIX = 48000


def to_stereo(file):
    """the filter that makes a source stereo the way a browser plays it: mono is copied to both sides at full level
    (ffmpeg's own upmix lowers each side by 3 dB); stereo stays; more channels are mixed down"""
    err = subprocess.run([FFMPEG, '-hide_banner', '-i', str(file)], capture_output=True, text=True).stderr
    m = re.search(r'Audio:[^\n]*?, (mono|stereo),', err)
    return 'pan=stereo|c0=c0|c1=c0' if m and m.group(1) == 'mono' else 'aformat=channel_layouts=stereo'


def vol_at(v, lt):
    """a clip's volume at its local time: a number, or an envelope [[lt, v], …] (linear between points) — as js/media.js"""
    if isinstance(v, (int, float)):
        return float(v)
    if lt <= v[0][0]:
        return v[0][1]
    for (t0, a), (t1, b) in zip(v, v[1:]):
        if lt <= t1:
            return a + (b - a) * (lt - t0) / max(1e-6, t1 - t0)
    return v[-1][1]


def clip_sound(c, a0, a1, path):
    """the part of a clip's sound inside [a0, a1) of the video, as the player plays it (from `in`, always at rate 1 — sound
    is never slowed down or sped up; volume envelope × level match, capped at 1 like <video>.volume), written as raw 48 kHz
    stereo float; returns (seconds after a0, path)"""
    lt0, lt1 = max(0.0, a0 - c['start']), min(c['dur'], a1 - c['start'])
    if lt1 <= lt0:
        return None
    if abs((c.get('rate') or 1) - 1) > 1e-6:
        sys.exit(f'영상 클립 {c.get("key")}: 소리가 있는 클립은 1배속으로만 재생합니다 (rate {c.get("rate")}) — 소리는 늦추거나 빠르게 하지 않습니다')
    args = [FFMPEG, '-v', 'error', '-ss', f'{c.get("in", 0) + lt0:.6f}', '-t', f'{lt1 - lt0:.6f}', '-i', str(ROOT / c['file'])]
    args += ['-af', f'aresample={SR_MIX},{to_stereo(ROOT / c["file"])}']
    raw = subprocess.run(args + ['-f', 'f32le', '-'], capture_output=True).stdout
    from array import array
    pcm = array('f'); pcm.frombytes(raw[:len(raw) // 8 * 8])
    n = int(round((lt1 - lt0) * SR_MIX))
    if len(pcm) < 2 * n:
        pcm.extend([0.0] * (2 * n - len(pcm)))
    del pcm[2 * n:]
    vol, B = c.get('vol', 1), 240                      # gain per 5 ms block (smooth enough for an envelope)
    for b0 in range(0, n, B):
        g = min(1.0, max(0.0, vol_at(vol, lt0 + (b0 + B / 2) / SR_MIX)))
        if g != 1.0:
            for i in range(2 * b0, 2 * min(n, b0 + B)):
                pcm[i] *= g
    with open(path, 'wb') as fh:
        pcm.tofile(fh)
    return max(0.0, c['start'] - a0), path


def has_voice(data, start, span):
    """does a recorded take play in that stretch? Read from js/cues.js, never guessed from the sound: tts.mjs marks every
    cue not recorded yet `placeholder`, and with narration off the file holds no voice"""
    if data.get('narration') is False:
        return False
    cues = data.get('cues', [])
    if not any('placeholder' in c for c in cues):      # a js/cues.js from before per-cue flags: put the narration in
        return True
    return any(not c.get('placeholder') and c['end'] > start and c['start'] < start + span for c in cues)


# ---------------------------------------------------------------- main
# what --screenshot writes: <project folder | video file>_<run time>_<what>[_res-<res>][_crop-<w>x<h>-at-x<x>-y<y>]
# [_seek-check-from-<t>]_sheet-<k>-of-<n>.<ext>, <what> = <from>-to-<to>_every-<gap>-frames-at-<fps>fps | moment-<t> |
# <n>-moments-<first>-to-<last> | art-<name>_pose-<t> | art-<name>_<n>-poses-… | page-<name>_<w>x<h>
# a sheet folder other than the project's own screenshots/ (--out, a page's or a video file's screenshots/) keeps a record
# of the sheets render.py wrote there (file name → sha256, source): --clear removes exactly those, as written, nothing else
SHEETS_RECORD = '.render-sheets.json'
RUN_AT = None               # the time the command started (YYYYMMDD-HHMMSS): in every sheet's name, so runs never overwrite


def sheets_record(outdir):
    try:
        rec = json.loads((outdir / SHEETS_RECORD).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return rec if isinstance(rec, dict) else {}


def note_sheets(outdir, paths, source):
    """add the sheets just written to outdir's record (entries whose file is gone are dropped)"""
    rec = {n: e for n, e in sheets_record(outdir).items() if Path(n).name == n and (outdir / n).is_file()}
    for p in paths:
        rec[p.name] = {'sha256': sha256_file(p), 'source': source}
    (outdir / SHEETS_RECORD).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')


def sheet_names(tag, n, ext):
    """a run's n sheet files: <tag>_sheet-<k>-of-<n>.<ext>, k padded to n's width so they sort in order"""
    w = len(str(n))
    return [f'{tag}_sheet-{k:0{w}d}-of-{n}.{ext}' for k in range(1, n + 1)]


def moments(n, t_lo, t_hi, one, many):
    """'moment-0m23.00s' for one time, '3-moments-0m11.50s-to-0m23.00s' for several (the first to the last)"""
    return f'{one}-{mmss(t_lo)}' if n == 1 else f'{n}-{many}-{mmss(t_lo)}-to-{mmss(t_hi)}'


def crop_part(x, y, w, h):
    return f'_crop-{w}x{h}-at-x{x}-y{y}'


def mmss(t):
    return f'{int(t // 60)}m{t % 60:05.2f}s'


def art_page(name, viewbox, w, h, group, bopts, state, bg, duration):
    """--art: a page that builds ART.<name> alone (the project's js/art/core.js + every js/art/*.js, its fonts) into an
    <svg viewBox> on a plain background, and answers the same calls a video page does — window.__video.seek(t) poses it
    with animate(t, state) — so it is filmed exactly like the video: seek → wait → capture. Served from memory."""
    art = ROOT / 'js' / 'art'
    need((art / 'core.js').is_file(), f'{art / "core.js"} 가 없습니다 — 그림 모듈은 js/art/에 있어야 합니다 (references/art-library.md)')
    mods = ['core.js'] + sorted(p.name for p in art.glob('*.js') if p.name != 'core.js')
    css = ''.join(f'<link rel="stylesheet" href="{c}">' for c in ('css/player.css', 'css/fonts.css') if (ROOT / c).is_file())
    js = lambda v: json.dumps(v, ensure_ascii=False).replace('</', '<\\/')
    scripts = '\n'.join(f'<script src="js/art/{m}"></script>' for m in mods)
    return f"""<!doctype html><html><head><meta charset="utf-8">{css}
<style>html, body {{ margin: 0; background: {bg}; overflow: hidden; }}
#stage {{ position: relative; left: 0; top: 0; transform: none; width: {w}px; height: {h}px; overflow: hidden; }}   /* (player.css centres #stage) */
#host {{ display: block; width: {w}px; height: {h}px; }}</style></head>
<body><div id="stage" data-width="{w}" data-height="{h}"><svg id="host" xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">{'<g id="el"></g>' if group else ''}</svg></div>
{scripts}
<script>
(function () {{
  var NAME = {js(name)}, OPTS = {js(bopts)}, STATE = {js(state)};
  function fail(msg) {{ var d = document.createElement('div'); d.className = 'vp-start-title vp-error'; d.textContent = msg; document.body.appendChild(d); }}
  try {{
    var mod = window.ART && window.ART[NAME];
    if (!mod || typeof mod.build !== 'function')
      return fail('ART.' + NAME + ' 에 build()가 없습니다 — 있는 모듈: ' + Object.keys(window.ART || {{}}).join(', '));
    var inst = mod.build(document.getElementById({'"el"' if group else '"host"'}), OPTS) || {{}};
    window.__video = {{ duration: {duration}, renderReady: true, renderBusy: function () {{ return false; }},
      seek: function (t) {{ if (inst.animate) inst.animate(t, STATE); }} }};
    window.__video.seek(0);
    document.body.classList.add('vp-ready');
  }} catch (e) {{ fail('ART.' + NAME + ': ' + (e && e.message || e)); }}
}})();
</script></body></html>"""


def clear_sheets(outdir, own, source=None):
    """--clear: before this run's sheets go in, empty the project's own screenshots/ (the tool's folder) altogether; in
    any other folder remove only the sheets render.py recorded there (SHEETS_RECORD) that are still as written — only
    those of `source` when it is given (a video file's: that video's) — returns how many. Without --clear nothing is
    removed anywhere"""
    if not outdir.is_dir():
        return 0
    gone = 0
    if own:
        for p in outdir.iterdir():
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
            gone += 1
        return gone
    keep = {}
    for name, e in sheets_record(outdir).items():
        f = outdir / name
        if Path(name).name != name or not isinstance(e, dict) or not f.is_file():
            continue
        if source is not None and e.get('source') != source:
            keep[name] = e
        elif sha256_file(f) == e.get('sha256'):
            f.unlink(); gone += 1
        # (a sheet changed since render.py wrote it stays, and is no longer counted as render.py's)
    (outdir / SHEETS_RECORD).write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding='utf-8')
    return gone


def cue_label(data):
    """t → '[c07]', the cue that is on at t (as the player's S key names it)"""
    cues = sorted(data.get('cues', []), key=lambda c: c['start'])
    def cue_at(t):
        c = None
        for x in cues:
            if x['start'] <= t + 1e-6:
                c = x
            else:
                break
        return f"[{c['id']}]" if c else ''
    return cue_at


def screenshots(o, data, opts, frames, tag, what, jobs, size, outdir, own_dir=True):
    """--screenshot: the frames [(n, t, cue)] laid out cols × rows to a sheet (with --via: a row of three per frame);
    sheets in outdir, named <tag>_sheet-<k>-of-<n>; `what` says in words what was shot (the first log line and each sheet's
    header)"""
    fps = opts['fps']
    per = opts['rows'] if opts.get('via') is not None else opts['cols'] * opts['rows']
    sheets = [frames[i:i + per] for i in range(0, len(frames), per)]
    ext = 'png' if opts['png'] else 'jpg'
    # the same work-folder rules as a movie: a stopped run goes on, a changed project starts again
    key = hashlib.sha1(json.dumps([str(ROOT), data['duration'], opts, frames, ART_HTML], sort_keys=True).encode()).hexdigest()[:12]
    work = Path(tempfile.gettempdir()) / f'motion-render-sheets-{key}'
    work.mkdir(parents=True, exist_ok=True)
    stamp = project_stamp(); sf = work / 'stamp.txt'
    old = [p for p in work.iterdir() if p.is_file() and p.name != 'stamp.txt']
    if old and (o.fresh or not sf.exists() or sf.read_text() != stamp):     # --fresh: start over even when nothing changed
        for p in old:
            p.unlink()
        say('--fresh: 전에 만들어 둔 시트를 버리고 처음부터 만듭니다' if o.fresh else
            '프로젝트 파일이 바뀌어, 전에 만들어 둔 시트를 버리고 새로 만듭니다')
    sf.write_text(stamp)
    (work / FRAMES_UNFIT).unlink(missing_ok=True)
    footage = str(ROOT / o.footage) if opts['extra'] else ''  # (the workers don't know the project folder)
    httpd, base = serve()
    faces = face_css(base)                              # (read here: the workers don't know the project folder)
    say(f'프로젝트: {ROOT}')
    layout = (f'한 줄에 [순서대로 | {fmt_t(opts["via"])}에서 건너옴 | 차이] · {opts["rows"]}줄씩' if opts.get('via') is not None
              else f'{opts["cols"]}×{opts["rows"]}칸씩')
    say(f'스크린샷: {what} · {len(frames)}칸 · 칸 {size} · {layout} 시트 {len(sheets)}장 · 동시 {jobs} · '
        f'자막 {"있음" if opts["captions"] else "없음"}')
    left, done0, made = [], 0, []
    for k, items in enumerate(sheets):
        f = str(work / f'sheet{k:05d}.{ext}')
        made.append(f)
        span = '' if opts.get('static') else f' · {fmt_t(items[0][1])}–{fmt_t(items[-1][1])}'    # (a still page has no time)
        header = f'{ROOT.name}{span} · {what} · 칸 {size} · 시트 {k + 1}/{len(sheets)}'
        if os.path.exists(f):
            done0 += len(items)
        else:
            left.append(dict(items=items, out=f, k=k, label=f'시트 {k + 1}/{len(sheets)}', header=header))
    # one job per worker, not one per sheet: a job launches the browser and builds the page once, then films the tiles of
    # its sheets in order. Building the page (every scene's textures, shaders and art, baked at load — and without a GPU
    # all of it drawn by the CPU) is most of a small sheet's time, so a job per sheet — at --res 1080p/4k one tile per
    # sheet — paid it again for every tile. The sheets are split into `jobs` runs of neighbouring sheets, as even as they go
    n = min(jobs, len(left))
    runs = [left[len(left) * i // n:len(left) * (i + 1) // n] for i in range(n)]
    todo = [dict(sheets=r, o=opts, base=base, faces=faces, frames=footage,
                 label=r[0]['label'] if len(r) == 1 else f'시트 {r[0]["k"] + 1}–{r[-1]["k"] + 1}/{len(sheets)}') for r in runs]
    t0 = time.time()
    ctx = mp.get_context('spawn')
    q = ctx.Queue()
    prog = Progress(q, len(frames), done0)
    prog.start()
    stop = None
    try:
        if todo:
            with ctx.Pool(min(jobs, len(todo)), initializer=_init_worker, initargs=(q,), maxtasksperchild=1) as pool:
                for _ in pool.imap_unordered(render_sheet, todo):
                    pass
    except KeyboardInterrupt:
        stop = '멈췄습니다'
    except Exception:
        stop = '오류로 멈췄습니다'
        tb = traceback.format_exc()
    finally:
        if not stop:
            time.sleep(0.6)
        prog.finish(drain=not stop)
        httpd.shutdown()
    if stop:
        if stop != '멈췄습니다':
            frames_unfit(work, o.footage, opts['fps'], opts['scale'], opts['res'])
            print(tb, file=sys.stderr, flush=True)
        # a --fresh run that is stopped goes on without --fresh (with it, the same command would drop these sheets again)
        warn(f'{stop}. 끝난 시트 {sum(os.path.exists(f) for f in made)}/{len(made)}장은 남겨 두었습니다 — '
             f'{"--fresh를 뺀 " if o.fresh else ""}같은 명령으로 다시 실행하면 이어서 만듭니다.')
        sys.exit(130 if stop == '멈췄습니다' else 1)
    # --clear: earlier sheets go (here, after this run's are made: a stopped or failed run keeps them); without it nothing
    # is removed — every sheet's name holds the time its run started, so runs never overwrite each other
    gone = clear_sheets(outdir, own_dir) if o.clear else 0
    if gone:
        say(f'{outdir.name}/ 비움 (--clear) — 전에 있던 {gone}개를 지우고 이번 시트를 넣습니다' if own_dir else
            f'{outdir.name}/ (--clear) — render.py가 전에 만든 시트 {gone}개를 지우고 이번 시트를 넣습니다')
    outdir.mkdir(parents=True, exist_ok=True)
    names = sheet_names(tag, len(made), ext)
    for f, n in zip(made, names):
        shutil.copyfile(f, outdir / n)
    record_generated([outdir / n for n in names])        # generated.json: check.mjs accepts the sheets as the skill's own
    if not own_dir:                                      # (--out, a page's screenshots/: what a later --clear may remove)
        note_sheets(outdir, [outdir / n for n in names], str(ROOT))
    shutil.rmtree(work, ignore_errors=True)
    if QUIET:                                           # the whole output: each sheet's full path, one per line
        for n in names:
            print(str((outdir / n).resolve()), flush=True)
        return
    say(f'완성: {outdir} — {names[0]}' + (f' … {names[-1]}' if len(names) > 1 else '') +
        f' ({len(names)}장, {len(frames)}칸) · 걸린 시간 {(time.time() - t0) / 60:.1f}분')


# ---------------------------------------------------------------- contact sheets of a video file (mp4, mov, …)
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi')


def is_video_file(arg):
    return bool(arg) and Path(arg).expanduser().is_file() and Path(arg).suffix.lower() in VIDEO_EXT


def probe(src):
    """duration, frame rate and display size of a video file, read from ffmpeg's own report (no ffprobe needed)"""
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(src)], capture_output=True, text=True, errors='replace')
    err = r.stderr
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', err)
    need(m, f'{src.name}: 길이를 읽지 못했습니다 — 영상 파일이 맞는지 확인해 주세요')
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    # the picture: a video stream that is not a cover image — the default one when there are several (an mkv may carry
    # a cover as a one-frame video stream)
    vids = [l for l in err.splitlines() if re.search(r'Stream #\d+:\d+.*Video:', l) and 'attached pic' not in l]
    need(vids, f'{src.name}: 영상 스트림이 없습니다')
    vline = next((l for l in vids if '(default)' in l), vids[0])
    sid = re.search(r'Stream #(\d+:\d+)', vline).group(1)
    sz = re.search(r'\b(\d{2,5})x(\d{2,5})\b', vline)
    fr = re.search(r'(\d+(?:\.\d+)?)\s*fps', vline) or re.search(r'(\d+(?:\.\d+)?)\s*tbr', vline)
    need(sz and fr, f'{src.name}: 화면 크기나 프레임 속도를 읽지 못했습니다')
    w, h = int(sz.group(1)), int(sz.group(2))
    rot = re.search(r'rotation of (-?\d+(?:\.\d+)?) degrees', err) or re.search(r'rotate\s*:\s*(-?\d+)', err)
    if rot and round(abs(float(rot.group(1)))) % 180 == 90:   # a phone video stored sideways: ffmpeg turns it upright
        w, h = h, w
    return dur, float(fr.group(1)), w, h, sid


def font_root(src):
    """a project whose installed OFL fonts the sheet's labels can use: the one the video sits in, else this file's own"""
    for p in [src.parent, *src.parent.parents]:
        if (p / 'index.html').is_file() and (p / 'css').is_dir():
            return p
    return HERE if (HERE / 'index.html').is_file() and (HERE / 'css').is_dir() else None


def video_sheets(o, src):
    """--screenshot of a video file: every gapframe-th frame of the file's own frames (or the frames at --at times),
    laid out like a project's sheets (a header, then frame number · time under each tile). Tiles are 480 px high, or
    --res 720p/1080p/4k (never above the file's own pixels); --crop X,Y,W,H shows one rectangle of the picture in the
    file's own pixels (1:1 unless --res). Frames are cut with ffmpeg, so no project is needed. This is how a clip, a
    recording or a rendered MP4 is looked at — never a frame grabbed with ffmpeg by hand."""
    global ROOT
    need(ffmpeg_bin(), 'ffmpeg — 맥에서는 brew install ffmpeg (없으면 가상환경에 imageio-ffmpeg를 넣어 씁니다)')
    dur, vfps, VW, VH, sid = probe(src)
    fps = o.fps if o.fps is not None else vfps          # frame numbers count in the file's own frames (unless --fps)
    need(fps > 0, '--fps 는 0보다 커야 합니다')
    need(o.gapframe > 0, '--gapframe 은 1 이상이어야 합니다')
    outdir = Path(o.out).expanduser().resolve() if o.out else src.parent / 'screenshots'
    need(not outdir.exists() or outdir.is_dir(), f'--out {o.out}: --screenshot에서는 시트를 넣을 폴더입니다 — 같은 이름의 파일이 있습니다')
    f0 = max(0, round((o.a or 0) * fps))
    f1 = min(int(dur * fps + 1e-6), round(o.b * fps)) if o.b is not None else int(dur * fps + 1e-6)
    need(f1 > f0, f'범위가 비었습니다 (영상 길이 {dur:.2f}초)')
    gap = o.gapframe
    region = (0, 0, VW, VH)                             # --crop: one rectangle of the picture, in the file's own pixels
    if o.crop:
        try:
            cx, cy, cw, ch = [int(round(float(v))) for v in o.crop.split(',')]
        except ValueError:
            sys.exit(f'--crop {o.crop}: 영상의 픽셀로 X,Y,W,H (예: --crop 2400,80,960,540)')
        if cw <= 0 or ch <= 0 or cx < 0 or cy < 0 or cx + cw > VW or cy + ch > VH:
            sys.exit(f'--crop {o.crop}: 영상 화면({VW}×{VH}) 안의 사각형이어야 합니다')
        region = (cx, cy, cw, ch)
    # tiles 480 px high like a project's sheets, in the picture's own shape; --res 720p/1080p/4k → 720/1080/2160 high,
    # never more than the file's own pixels; a --crop is shown 1:1 unless --res says otherwise
    if o.res:
        th = min({'480p': 480, '720p': 720, '1080p': 1080, '4k': 2160}[o.res], region[3])
    else:
        th = region[3] if o.crop else 480
    th = max(2, th // 2 * 2)
    tw = max(2, int(round(th * region[2] / region[3] / 2)) * 2)
    big = tw >= 1000 or th >= 1000                      # one big tile per image: a viewer shrinks a wide sheet
    plain = not o.crop and not o.res
    cols = o.cols or ((4 if VW >= VH else 8) if plain else (1 if big else max(1, min(8, 3500 // (tw + 16)))))
    rows = o.rows or ((6 if VW >= VH else 3) if plain else (1 if big else max(1, min(8, 3000 // (th + 50)))))
    if o.at:                                            # exactly those moments, snapped to the file's frames
        try:
            ts = [float(x) for x in o.at.replace(' ', '').split(',') if x]
        except ValueError:
            sys.exit(f'--at {o.at}: 초를 쉼표로 이어 주세요 (예: --at 11.5,23)')
        if not ts or any(t < 0 for t in ts):
            sys.exit(f'--at {o.at}: 0 이상의 시각을 하나 이상 주세요')
        last = max(0, int(dur * fps + 1e-6) - 1)
        items = [(n, n / fps, '') for n in sorted({min(last, round(t * fps)) for t in ts})]
    else:
        items = [(n, n / fps, '') for n in range(f0, f1, gap)]
    ext = 'png' if o.png else 'jpg'
    crop_f = f'crop={region[2]}:{region[3]}:{region[0]}:{region[1]},' if o.crop else ''
    scale_f = f'scale={tw}:{th}:flags=lanczos'
    what = (f'지정 시각 {len(items)}곳' if o.at else f'{gap}프레임마다({gap / fps:.3g}초)') + f' · {fps:.3g}fps' + \
           (f' · 화면 {region[0]},{region[1]}에서 {region[2]}×{region[3]}만' if o.crop else '')
    say(f'영상 파일: {src}')
    say(f'스크린샷: {fmt_t(items[0][1])}–{fmt_t(items[-1][1])} · {what} · {len(items)}칸 · 칸 {tw}×{th} · {cols}×{rows}칸씩')
    t0 = time.time()
    work = Path(tempfile.mkdtemp(prefix='motion-render-video-'))
    try:
        # one pass: seek to the first frame, keep every gap-th decoded frame, scale it to the tile. With --fps the frames
        # are first counted at that rate (fps filter), so the numbers and times under the tiles stay true. The stream is
        # the one probe() chose (not a cover image)
        q = ['-q:v', '2'] if ext == 'jpg' else []
        if o.at:
            # one frame per time: an accurate seek (ffmpeg decodes from the keyframe before it) and the frame there
            for k, (n, t, _) in enumerate(items):
                r = subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-ss', f'{t:.6f}', '-i', str(src), '-map', sid,
                                    '-vf', (f'fps={fps},' if o.fps is not None else '') + crop_f + scale_f, '-frames:v', '1'] + q +
                                   [str(work / f'f{k + 1:06d}.{ext}')], capture_output=True, text=True)
                need(r.returncode == 0 and (work / f'f{k + 1:06d}.{ext}').exists(),
                     f'ffmpeg가 {fmt_t(t)}의 프레임을 뽑지 못했습니다: {r.stderr.strip()[-400:]}')
        else:
            sel = (f'fps={fps},' if o.fps is not None else '') + f"select='not(mod(n\\,{gap}))'," + crop_f + scale_f
            base_cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-ss', f'{f0 / fps:.6f}', '-i', str(src), '-map', sid,
                        '-vf', sel, '-frames:v', str(len(items))]
            r = subprocess.run(base_cmd + ['-fps_mode', 'vfr'] + q + [str(work / f'f%06d.{ext}')], capture_output=True, text=True)
            if r.returncode != 0:                       # an older ffmpeg: -vsync instead of -fps_mode
                r = subprocess.run(base_cmd + ['-vsync', 'vfr'] + q + [str(work / f'f%06d.{ext}')], capture_output=True, text=True)
            need(r.returncode == 0, f'ffmpeg가 프레임을 뽑지 못했습니다: {r.stderr.strip()[-400:]}')
        files = sorted(work.glob(f'f*.{ext}'))
        need(files, '뽑은 프레임이 없습니다')
        items = items[:len(files)]
        shots = [f.read_bytes() for f in files]
        say(f'프레임 {len(files)}장 뽑음 — 시트로 모으는 중')
        # labels in the installed OFL fonts of a project nearby (served locally); without one, the browser's own
        ROOT = font_root(src)
        httpd, faces = None, ''
        if ROOT:
            httpd, base = serve()
            faces = face_css(base)
        per = cols * rows
        sheets = [list(range(i, min(i + per, len(items)))) for i in range(0, len(items), per)]
        name = re.sub(r'[^\w.-]+', '_', src.name)
        mods = (f'_res-{o.res}' if o.res else '') + (crop_part(*region) if o.crop else '')
        if o.at:
            ts = [it[1] for it in items]
            tag = f'{name}_{RUN_AT}_{moments(len(items), min(ts), max(ts), "moment", "moments")}{mods}'
        else:
            tag = f'{name}_{RUN_AT}_{mmss(f0 / fps)}-to-{mmss(f1 / fps)}_every-{gap}-frames-at-{fps:g}fps{mods}'
        made = []
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as pw:
                browser, _how, _gl = launch(pw, o.gpu)
                try:
                    opts = dict(out_size=(tw, th), cols=cols, png=o.png)
                    for k, idx in enumerate(sheets):
                        its = [items[i] for i in idx]
                        header = (f'{src.name} · {fmt_t(its[0][1])}–{fmt_t(its[-1][1])} · {what} · 칸 {tw}×{th} · '
                                  f'시트 {k + 1}/{len(sheets)}')
                        made.append(compose_sheet(browser, faces, [shots[i] for i in idx], its, header, opts))
                        say(f'시트 {k + 1}/{len(sheets)}: 완료')
                finally:
                    browser.close()
        finally:
            if httpd:
                httpd.shutdown()
        # --clear: this video's earlier sheets (the ones render.py recorded in that folder, still as written) go
        gone = clear_sheets(outdir, False, source=str(src)) if o.clear else 0
        if gone:
            say(f'{outdir.name}/ (--clear) — 이 영상의 전에 있던 시트 {gone}개를 지우고 이번 시트를 넣습니다')
        outdir.mkdir(parents=True, exist_ok=True)
        paths = []
        for img, n in zip(made, sheet_names(tag, len(made), ext)):
            dst = outdir / n
            dst.write_bytes(img); paths.append(dst)
        record_generated(paths)                          # (a file in no video project needs no record)
        note_sheets(outdir, paths, str(src))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if QUIET:                                           # the whole output: each sheet's full path, one per line
        for p in paths:
            print(str(p.resolve()), flush=True)
        return
    say(f'완성: {outdir} — {paths[0].name}' + (f' … {paths[-1].name}' if len(paths) > 1 else '') +
        f' ({len(paths)}장, {len(items)}칸) · 걸린 시간 {(time.time() - t0) / 60:.1f}분')


def page_sheet(o, page):
    """--screenshot of an HTML page that is not a video (the thumbnail page thumbnail.mjs renders, a card): one tile of
    the page as the browser draws it once its fonts and images are ready — the way that page is looked at. Served from
    the video project above it (its fonts), the sheet goes to screenshots/ beside the page."""
    global ROOT
    need(o.screenshot, f'{page.name}: 영상이 아닌 HTML 페이지는 --screenshot(시트)으로만 봅니다')
    bad = [k for k, v in (('--at', o.at), ('--via', o.via), ('--art', o.art)) if v is not None]
    if bad:
        sys.exit(f'페이지 시트에는 {", ".join(bad)} 를 쓸 수 없습니다 — 페이지는 --size, --res, --crop으로 봅니다')
    if o.venv and not in_venv():
        bootstrap()
    try:
        import playwright  # noqa: F401
    except ImportError:
        need(False, 'Playwright — 가상환경으로 실행하거나(--no-venv 없이) python3 -m pip install playwright')
    ROOT = next((d for d in page.parents if (d / 'index.html').is_file() and (d / 'fonts').is_dir()), page.parent)
    m = re.fullmatch(r'(\d+)[x×](\d+)', (o.size or '1280x720').strip())
    if not m:
        sys.exit(f'--size {o.size}: 가로x세로 (예: --size 1280x720)')
    W, H = int(m.group(1)), int(m.group(2))
    res = o.res or '1080p'
    scale = {'480p': 4 / 9, '720p': 2 / 3, '1080p': 1, '4k': 2}[res]
    clip = None
    if o.crop:
        try:
            cx, cy, cw, ch = [float(v) for v in o.crop.split(',')]
        except ValueError:
            sys.exit(f'--crop {o.crop}: 페이지 픽셀로 X,Y,W,H')
        if cw <= 0 or ch <= 0 or cx < 0 or cy < 0 or cx + cw > W + 0.5 or cy + ch > H + 0.5:
            sys.exit(f'--crop {o.crop}: 페이지({W}×{H}) 안의 사각형이어야 합니다')
        clip = (cx, cy, cw, ch)
    OW, OH = (int(round(clip[2] * scale)), int(round(clip[3] * scale))) if clip else (int(round(W * scale)), int(round(H * scale)))
    outdir = Path(o.out).expanduser().resolve() if o.out else page.parent / 'screenshots'
    rel = page.relative_to(ROOT).as_posix()
    opts = dict(fps=60, res=res, scale=scale, size=(W, H), pixels=OW * OH, out_size=(OW, OH), extra='', fontcheck=False,
                png=o.png, fast=o.fast, gpu=o.gpu, captions=False, mode='sheet', gap=1, cols=1, rows=1, clip=clip, via=None,
                cap_png=o.png, page=rel, static=True)
    proj, stem = re.sub(r'[^\w.-]+', '_', ROOT.name), re.sub(r'[^\w.-]+', '_', page.stem)
    tag = f'{proj}_{RUN_AT}_page-{stem}_{W}x{H}' + (f'_res-{res}' if res != '1080p' else '') + \
          (crop_part(*(int(v) for v in clip)) if clip else '')
    what = f'페이지 {rel} · {W}×{H}' + (f' · {clip[0]:g},{clip[1]:g}에서 {clip[2]:g}×{clip[3]:g}만' if clip else '')
    return screenshots(o, {'duration': 0, 'cues': []}, opts, [(1, 0.0, page.name)], tag, what, 1, f'{OW}×{OH}', outdir,
                       own_dir=False)


def main():
    ap = argparse.ArgumentParser(
        prog='python3 render.py', formatter_class=argparse.RawTextHelpFormatter, add_help=False,
        usage='%(prog)s [PROJECT] [options]     (PROJECT: 영상 프로젝트 폴더 또는 그 index.html — --screenshot이면 mp4·mov 영상 파일도)',
        description='script-to-motion 영상을 MP4로 굽고, 콘택트 시트(--screenshot: 영상 프로젝트 · mp4·mov 영상 파일)를 만듭니다.\n'
                    '재생하지 않고 프레임마다 그 시각의 장면을 다 그린 뒤 찍으므로\n'
                    '컴퓨터가 느려도 프레임이 빠지지 않습니다(느리면 시간만 더 걸립니다). 처음 실행하면 ~/.cache/motion-render-venv에\n'
                    '가상환경을 만들고 Playwright·Chromium을 설치한 뒤 시작합니다. 필요한 것: Python 3, ffmpeg(맥: brew install ffmpeg).',
        epilog="""예:
  python3 render.py ~/videos/my-video                    전체 → ~/videos/my-video/movie_<날짜-시각>_<해상도>.mp4
                                                         (예: movie_20261106-213045_1080p.mp4 · 60fps, 자막·내레이션 포함)
  python3 render.py ~/videos/my-video/index.html         index.html을 줘도 같음
  python3 render.py                                      프로젝트 폴더 안에서는 인자 없이
  python3 render.py ~/videos/my-video --to 40            앞 40초만 — 먼저 이것으로 속도·화질 확인
  python3 render.py ~/videos/my-video --from 60 --to 90  1:00–1:30만
  python3 render.py ~/videos/my-video --res 4k           4K (HEVC)
  python3 render.py ~/videos/my-video --res 720p         720p — 더 빠르고 파일이 작음
  python3 render.py ~/videos/my-video --res 480p         480p — 미리보기·공유용
  python3 render.py ~/videos/my-video --fast --jobs 3    더 빠르게 (한 번만 찍기 + 브라우저 3개)
  python3 render.py ~/videos/my-video --quality ultra    JPEG 100으로 찍어 무손실 압축 (파일이 아주 큼, 일부 플레이어는 재생 못 함)
  python3 render.py ~/videos/my-video --quality ultra --png   PNG로 찍어 무손실 압축 (더 느림)
  python3 render.py ~/videos/my-video --out ~/Desktop/my-video.mp4
  python3 render.py ~/videos/my-video --screenshot --from 8 --to 15 --gapframe 5   8–15초를 5프레임마다 한 칸, 시트 이미지로
  python3 render.py ~/videos/my-video --screenshot --gapframe 300                  5초마다 한 칸 — 영상 전체 훑어보기
  python3 render.py ~/videos/my-video --screenshot --at 11.5,23 --res 1080p        그 두 순간만, 무대 크기 그대로 (한 장에 한 칸)
  python3 render.py ~/videos/my-video --screenshot --at 23 --crop 1200,600,640,360 --res 4k   무대 일부를 크게
  python3 render.py ~/videos/my-video --screenshot --at 66.3 --via 74.3            74.3초에서 건너와 찍은 것과 비교 + 차이
  python3 render.py ~/videos/my-video --screenshot --art dino --viewbox "-200 -130 400 260" --at 0,0.6,1.2 --state '{"run":1}'
                                                                                   그림 모듈 ART.dino 하나만, 세 자세
  python3 render.py ~/Movies/clip.mov --screenshot --from 2 --to 6                 영상 파일(mp4·mov 등)도 같은 시트로
  python3 render.py ~/Movies/rec.mp4 --screenshot --at 14.2 --res 1080p           그 영상의 한 순간을 크게
  python3 render.py ~/Movies/rec.mp4 --screenshot --at 14.2 --crop 2400,80,960,540  녹화의 일부를 원본 픽셀 그대로

진행: 한 줄이 계속 갱신됩니다(진행 % · 남은 시간 · 프레임 · 경과 · 초당 장 수). Ctrl+C로 멈추면 찍던 프레임까지 마무리하고
처음부터 끊김 없이 이어진 부분을 <이름>_partial.mp4로 저장합니다(한 번 더 누르면 저장하지 않고 바로 끝냄). 같은 명령을 다시
실행하면 끝난 조각은 건너뛰고 이어서 만듭니다(그사이 프로젝트 파일이 바뀌었으면 처음부터, --fresh를 주면 늘 처음부터; 만든 시트
screenshots/는 바뀐 것으로 치지 않음). 영상 클립이 있는 영상은 먼저 스킬의 scripts/stills.mjs로 렌더용 프레임을 잘라 둡니다 —
없거나 이번 해상도·fps에 맞지 않으면(작게 잘린 프레임은 흐려짐) 이 스크립트가 다시 자르는 명령을 알려 주고 멈춥니다.

스크린샷(--screenshot): 재생 중 A 키가 그 순간 앞뒤 1초의 명령을 복사합니다(영상 폴더에서 이 명령 뒤에 붙여 넣기).
출력은 만든 시트 이미지의 전체 경로뿐입니다(한 줄에 하나) — 진행 상황은 --progress로 봅니다.
시트 이름에 실행 시각이 들어가 이전 시트를 덮어쓰지 않고, --clear를 주지 않으면 아무것도 지우지 않습니다.
자세한 사용법: 스킬의 docs/screenshot.md""")
    g = ap.add_argument_group('무엇을 · 어디에')
    g.add_argument('project', nargs='?', default=None, metavar='PROJECT',
                   help='영상 프로젝트 폴더(index.html이 있는 곳) 또는 그 index.html.\n없으면 지금 폴더, 그다음 이 파일이 있는 폴더.\n'
                        '--screenshot이면 영상 파일(mp4 · mov · m4v · mkv · webm · avi)도 됩니다 —\n그 파일의 프레임으로 같은 모양의 시트를 만듭니다\n'
                        '(프레임 번호는 그 파일의 fps 기준, 시트는 파일 옆 screenshots/)')
    g.add_argument('--from', dest='a', type=float, default=None, metavar='SEC', help='시작 시각, 초 (기본: 0)')
    g.add_argument('--to', dest='b', type=float, default=None, metavar='SEC', help='끝 시각, 초 (기본: 영상 끝)')
    g.add_argument('--out', default=None, metavar='FILE', help='만들 파일 (기본: 프로젝트 폴더의 movie_<날짜-시각>_<해상도>.mp4 —\n실행한 시각과 --res, 예: movie_20261106-213045_4k.mp4;\n직접 주면 지금 폴더 기준) — --screenshot이면 폴더\n(기본: 프로젝트 폴더의 screenshots/ — 지우지 않고 쌓임, --clear를 주면 비우고 넣음)')
    g.add_argument('--no-captions', dest='captions', action='store_false', help='자막 없이 (기본: 자막을 영상에 입힘)')
    g.add_argument('--captions', dest='captions', action='store_true', help=argparse.SUPPRESS)   # (the default now; kept so old commands work)
    g.add_argument('--no-audio', dest='audio', action='store_false', help='소리 없이 (기본: 그 구간의 내레이션 + 소리를 켠 영상 클립)')
    g = ap.add_argument_group('스크린샷 (MP4 대신 콘택트 시트) — 화면을 보는 유일한 방법')
    g.add_argument('--screenshot', action='store_true',
                   help='MP4 대신 이미지: 찍은 프레임 여러 칸을 한 장에 모읍니다 (기본 칸 480p)\n(칸마다 프레임 번호 · 시각 · cue, 넘치면 여러 장)')
    g.add_argument('--gapframe', type=int, default=30, metavar='N', help='N프레임마다 한 칸 (기본: 30 = 60fps에서 0.5초)')
    g.add_argument('--at', default=None, metavar='T,T,…', help='이 시각들만 한 칸씩 (초, 쉼표로) — --from/--to/--gapframe 대신\n'
                   '예: --at 11.5,23   (--art에서는 자세를 잡을 시각, 기본 0,0.5,1,1.5)')
    g.add_argument('--crop', default=None, metavar='X,Y,W,H', help='무대의 이 사각형만 (무대 픽셀) — 작은 글자·세부를 크게 볼 때.\n'
                   '--res 1080p나 4k와 함께: 예 --crop 1200,600,640,360 --res 4k → 칸 1280×720\n'
                   '영상 파일이면 그 영상의 픽셀로, 원본 그대로(1:1) — 녹화 속 작은 버튼·글씨')
    g.add_argument('--via', type=float, default=None, metavar='SEC', help='칸마다 그 시각을 한 번 더 찍되 SEC초에 갔다가 돌아와서 찍고,\n'
                   '[순서대로 | SEC에서 건너옴 | 차이]를 한 줄에 놓습니다 — 탐색 경로에 따라\n'
                   '그림이 달라지는 문제를 볼 때 (snapshot.mjs --seekcheck가 이 명령을 알려 줌)')
    g.add_argument('--cols', type=int, default=None, metavar='N', help='한 줄의 칸 수 (기본: 가로 영상 4, 세로 영상 8 — 큰 칸은 1)')
    g.add_argument('--rows', type=int, default=None, metavar='N', help='한 장의 줄 수 (기본: 가로 영상 6, 세로 영상 3 — 큰 칸은 1)')
    g.add_argument('--clear', action='store_true', default=None,
                   help='시트를 넣기 전에 전에 만든 시트를 지움 (기본: 아무것도 지우지 않음 — 시트 이름에\n'
                        '실행 시각이 들어가 서로 덮어쓰지 않음). 프로젝트의 screenshots/는 통째로 비우고,\n'
                        '--out 폴더 · 페이지 옆 · 영상 파일 옆 screenshots/에서는 render.py가 만든 시트 중\n'
                        '그 뒤로 바뀌지 않은 것만 지움 (영상 파일은 그 영상의 시트만)')
    g.add_argument('--progress', action='store_true',
                   help='진행 상황을 보여 줌 (기본: --screenshot은 다 만든 시트 이미지의\n전체 경로만 한 줄에 하나씩 출력 — 오류·경고는 stderr로)')
    g = ap.add_argument_group('그림 모듈 하나만 (--screenshot --art) — js/art/*.js의 모듈을 무대 없이')
    g.add_argument('--art', default=None, metavar='NAME', help='ART.NAME 하나만 그려 --at의 시각마다 한 칸 (animate(t, state)로 자세를 잡음)')
    g.add_argument('--viewbox', default=None, metavar='"X Y W H"', help='--art: 모듈을 그릴 SVG viewBox (꼭 필요)')
    g.add_argument('--group', action='store_true', help='--art: 모듈의 그릇이 <g>일 때 (viewBox 원점의 <g> 안에 build)')
    g.add_argument('--opts', default=None, metavar='JSON', help='--art: build(el, opts)에 줄 값 (JSON)')
    g.add_argument('--state', default=None, metavar='JSON', help='--art: animate(t, state)에 줄 값 (JSON)')
    g.add_argument('--bg', default='#04122e', metavar='COLOR', help='--art: 배경색 (기본: #04122e)')
    g.add_argument('--size', default=None, metavar='WxH', help='--art: 한 칸의 크기, 무대 픽셀 (기본: 가로 800, viewBox 비율)\n'
                   '영상이 아닌 페이지(썸네일 등 — PROJECT 자리에 그 .html): 페이지 크기 (기본: 1280x720)')
    g = ap.add_argument_group('화질')
    g.add_argument('--res', choices=['480p', '720p', '1080p', '4k'], default=None,
                   help='480p: 무대의 4/9(16:9면 854×480)\n720p: 무대의 2/3(16:9면 1280×720)\n1080p: 무대 크기 그대로(16:9면 1920×1080)\n4k: 두 배(16:9면 3840×2160)\n'
                        '(기본: MP4 1080p · --screenshot 480p · --art 1080p — 시트의 칸도 이 해상도로 찍음;\n'
                        ' 영상 파일의 시트는 칸 높이 480/720/1080/2160, 그 영상보다 크게는 키우지 않음)')
    g.add_argument('--fps', type=int, default=None, metavar='N', help='초당 프레임 수 (기본: 60 — 영상 파일의 시트는 그 파일의 fps)')
    g.add_argument('--quality', choices=['high', 'max', 'ultra'], default='high',
                   help='high: 충분히 좋음 · max: 최상, 파일이 큼 (기본: high)\n'
                        'ultra: JPEG 100으로 찍어 H.264 YUV 4:4:4 무손실 압축으로 담음(크기 조정·색 줄이기\n'
                        ' 없음) — 압축에서는 잃는 것이 없고, RGB→YUV 반올림과 JPEG 100의 아주 작은 손실만 있음;\n'
                        ' --png를 함께 주면 PNG로 찍음(더 느림). 파일이 아주 큼; 소리는 high·max와 같음.\n'
                        ' 4:4:4 H.264(High 4:4:4)를 재생하지 못하는 플레이어(QuickTime 등)도 있음')
    g.add_argument('--codec', choices=['auto', 'h264', 'hevc'], default='auto', help='auto: 1080p는 H.264, 4k는 HEVC(H.265) (기본: auto)')
    g.add_argument('--png', action='store_true', help='무손실 캡처 — 느림 (기본: JPEG 95, --quality ultra는 JPEG 100)')
    g = ap.add_argument_group('속도')
    g.add_argument('--fast', action='store_true', help='프레임마다 한 번만 찍기 — 빠르지만 장면이 크게 바뀌는 순간\n한 프레임이 늦게 찍힐 수 있음 (기본: 두 번 찍어 같을 때까지)')
    g.add_argument('--jobs', type=int, default=None, metavar='N', help='동시에 렌더할 조각 수 = 브라우저 수 (기본: 맥 2, 그 밖 1)')
    g.add_argument('--chunk', type=float, default=20, metavar='SEC', help='조각 길이, 초 — 멈췄다 이어 할 때의 단위 (기본: 20)')
    g.add_argument('--fresh', action='store_true', help='이어 하지 않고 처음부터 — 같은 명령으로 전에 만들어 둔 조각·시트를 버림')
    g = ap.add_argument_group('그 밖')
    g.add_argument('--encoder', choices=['auto', 'videotoolbox', 'software', 'x264'], default='auto',
                   help='auto: 맥이면 하드웨어(VideoToolbox), 아니면 소프트웨어(x264/x265)\n(기본: auto)')
    g.add_argument('--no-gpu', dest='gpu', action='store_false', help='그래픽 칩을 쓰지 않고 소프트웨어로 그리기 — 화면이 깨질 때')
    g.add_argument('--footage', default='media/render-stills', metavar='DIR', help='영상 클립의 렌더용 프레임 폴더 (기본: media/render-stills)')
    g.add_argument('--no-font-check', dest='fontcheck', action='store_false',
                   help='렌더하면서 하는 글꼴 검사를 끔 (기본: 화면 글자는 5초마다, 캔버스 글자는 전부 —\n시스템 글꼴이 그린 글자가 있으면 경고)')
    g.add_argument('--no-venv', dest='venv', action='store_false', help='가상환경 없이 지금 파이썬으로 실행 (Playwright가 설치되어 있어야 함)')
    g.add_argument('-h', '--help', action='help', help='이 도움말')
    o = ap.parse_args()
    global QUIET, RUN_AT
    RUN_AT = time.strftime('%Y%m%d-%H%M%S')          # (in the sheets' names)
    QUIET = o.screenshot and not o.progress
    signal.signal(signal.SIGTERM, signal.default_int_handler)   # `kill` stops it like Ctrl+C (chunks kept, workers stopped)
    global ROOT, ART_HTML
    sheet_only = [k for k, v in (('--at', o.at), ('--crop', o.crop), ('--via', o.via), ('--art', o.art), ('--clear', o.clear)) if v is not None]
    if sheet_only and not o.screenshot:
        sys.exit(f'{", ".join(sheet_only)}: --screenshot(시트 만들기)과 함께 씁니다')
    # HTML까지만: AI 에이전트(Claude Code)는 사용자가 MP4를 요청했을 때만 MP4를 만든다. 요청을 받았으면 SUMO_RENDER_OK=1을 붙여 실행한다.
    # (--screenshot 시트는 언제나 허용. 사용자가 직접 터미널에서 실행하는 MP4 만들기는 막지 않는다.)
    if not o.screenshot and os.environ.get('CLAUDECODE') and os.environ.get('SUMO_RENDER_OK') != '1':
        sys.exit('MP4 만들기는 사용자가 요청할 때만 합니다 (스모는 HTML까지만 만듭니다).\n'
                 '  화면을 보려면: python render.py <폴더> --screenshot ...\n'
                 '  사용자가 MP4를 요청했다면: Bash는 SUMO_RENDER_OK=1 python render.py <폴더> ..., PowerShell은 $env:SUMO_RENDER_OK=\'1\'; python render.py <폴더> ...\n'
                 '  (Agents stop here: MP4 only when the user asked, with SUMO_RENDER_OK=1.)')
    if is_video_file(o.project):                       # a video file: sheets of its own frames (no project needed)
        need(o.screenshot, '영상 파일은 --screenshot(시트 만들기)으로만 쓸 수 있습니다')
        bad = [k for k in sheet_only if k in ('--via', '--art')]
        if bad:
            sys.exit(f'영상 파일의 시트에는 {", ".join(bad)} 를 쓸 수 없습니다 — 영상 파일은 --from/--to/--gapframe, --at, --res, --crop으로 봅니다')
        if o.venv and not in_venv():
            bootstrap()
        try:
            import playwright  # noqa: F401
        except ImportError:
            need(False, 'Playwright — 가상환경으로 실행하거나(--no-venv 없이) python3 -m pip install playwright')
        return video_sheets(o, Path(o.project).expanduser().resolve())
    pg = Path(o.project).expanduser() if o.project else None
    if pg and pg.is_file() and pg.suffix.lower() in ('.html', '.htm') and pg.name.lower() != 'index.html':
        return page_sheet(o, pg.resolve())             # a page that is not a video: the thumbnail, a card
    ROOT = find_project(o.project)                     # (before the environment, so a wrong path is said at once)
    if o.venv and not in_venv():
        bootstrap()                                    # does not return: runs this script again inside the environment

    art = o.art is not None
    if art:
        if not o.viewbox:
            sys.exit('--art에는 --viewbox "X Y W H"가 필요합니다 (모듈을 그릴 SVG 좌표계, 예: --viewbox "-200 -130 400 260")')
    else:
        need((ROOT / 'js' / 'cues.js').is_file(), f'{ROOT / "js" / "cues.js"} 가 없습니다 — 스킬의 tts.mjs로 대사 시간표를 먼저 만들어 주세요')
    # sheets: 480p tiles unless --res says otherwise (an --art module: its own size, 1080p = 1×); a movie: 1080p
    o.res = o.res or (('1080p' if art else '480p') if o.screenshot else '1080p')
    need(o.screenshot or ffmpeg_bin(), 'ffmpeg — 맥에서는 brew install ffmpeg (없으면 가상환경에 imageio-ffmpeg를 넣어 씁니다)')
    try:
        import playwright  # noqa: F401
    except ImportError:
        need(False, 'Playwright — 가상환경으로 실행하거나(--no-venv 없이) python3 -m pip install playwright')

    def times_arg(s, flag):
        try:
            ts = [float(x) for x in s.replace(' ', '').split(',') if x]
        except ValueError:
            sys.exit(f'{flag} {s}: 초를 쉼표로 이어 주세요 (예: {flag} 11.5,23)')
        if not ts or any(t < 0 for t in ts):
            sys.exit(f'{flag} {s}: 0 이상의 시각을 하나 이상 주세요')
        return ts
    if art:
        poses = times_arg(o.at, '--at') if o.at else [0, 0.5, 1, 1.5]
        data = {'duration': max(poses) + 1, 'cues': []}
    else:
        data = video_data()
    dur, fps = data['duration'], (o.fps if o.fps is not None else 60)
    need(fps > 0 and o.chunk > 0, '--fps 와 --chunk 는 0보다 커야 합니다')
    f0 = max(0, round((o.a or 0) * fps))
    f1 = min(round(dur * fps), round(o.b * fps)) if o.b is not None else round(dur * fps)
    need(f1 > f0, f'범위가 비었습니다 (영상 길이 {dur:.2f}초)')
    codec = o.codec if o.codec != 'auto' else ('hevc' if o.res == '4k' else 'h264')
    encoder = pick_encoder(o.encoder, codec) if not o.screenshot else 'software'
    if o.quality == 'ultra' and not o.screenshot:      # JPEG 100 (or --png) captures into H.264 YUV 4:4:4 at qp 0, in software
        need(o.codec in ('auto', 'h264'), '--quality ultra는 H.264 4:4:4 무손실로만 만듭니다 — --codec hevc를 빼 주세요')
        need(o.encoder in ('auto', 'software', 'x264'), '--quality ultra는 소프트웨어 인코더(libx264)로만 만듭니다 — '
             'VideoToolbox는 무손실을 만들지 못합니다. --encoder를 빼 주세요')
        codec, encoder = 'h264', 'lossless'
    need(o.screenshot or ENC_NAME[encoder, codec] in encoders(), f'ffmpeg에 {ENC_NAME[encoder, codec]} 인코더가 없습니다 (--codec h264 또는 --encoder 를 바꿔 보세요)')
    scale = {'480p': 4 / 9, '720p': 2 / 3, '1080p': 1, '4k': 2}[o.res]   # the same layout, drawn with fewer or more pixels
    if art:                                             # the module's own little stage: 800 wide in the viewBox's shape
        try:
            vb = [float(v) for v in o.viewbox.replace(',', ' ').split()]
            assert len(vb) == 4 and vb[2] > 0 and vb[3] > 0
        except (ValueError, AssertionError):
            sys.exit(f'--viewbox "{o.viewbox}": 숫자 네 개 "X Y W H" (W, H > 0)')
        if o.size:
            m = re.fullmatch(r'(\d+)[x×](\d+)', o.size.strip())
            if not m:
                sys.exit(f'--size {o.size}: 가로x세로 (예: --size 800x520)')
            W, H = int(m.group(1)), int(m.group(2))
        else:
            W, H = 800, max(1, round(800 * vb[3] / vb[2]))
        try:
            bopts, bstate = json.loads(o.opts or '{}'), json.loads(o.state or '{}')
        except ValueError as e:
            sys.exit(f'--opts/--state: JSON이 아닙니다 ({e})')
        ART_HTML = art_page(o.art, ' '.join(f'{v:g}' for v in vb), W, H, o.group, bopts, bstate, o.bg, data['duration'])
    else:
        W, H = stage_size()
    clip = None
    if o.crop:
        try:
            cx, cy, cw, ch = [float(v) for v in o.crop.split(',')]
        except ValueError:
            sys.exit(f'--crop {o.crop}: 무대 픽셀로 X,Y,W,H (예: --crop 1200,600,640,360)')
        if cw <= 0 or ch <= 0 or cx < 0 or cy < 0 or cx + cw > W + 0.5 or cy + ch > H + 0.5:
            sys.exit(f'--crop {o.crop}: 무대({W}×{H}) 안의 사각형이어야 합니다')
        clip = (cx, cy, cw, ch)
    if o.via is not None and not art and not 0 <= o.via <= dur:
        sys.exit(f'--via {o.via}: 영상 안의 시각이어야 합니다 (0–{dur:.2f}초)')
    if clip:                                            # a tile is the crop at this resolution's density
        OW, OH = int(round(clip[2] * scale)), int(round(clip[3] * scale))
    else:
        OW, OH = int(round(W * scale / 2)) * 2, int(round(H * scale / 2)) * 2   # the movie's pixel size (nearest even: 854×480)
    size = f'{OW}×{OH}'
    # footage is filmed from frames cut beforehand (headless Chrome plays no H.264): at the render's fps, full size.
    # Whether they are there is decided by the clips the page actually places (frames_check, once a worker's page has
    # loaded — it stops with the list and the stills.mjs command), not by the clips js/media-src.js declares: a clip
    # declared but never placed needs no frames
    extra = f'&frames={o.footage}&mfps={fps}' if not art and footage_clips() else ''
    jobs = o.jobs or (2 if IS_MAC else 1)
    opts = dict(fps=fps, encoder=encoder, codec=codec, res=o.res, scale=scale, size=(W, H), pixels=OW * OH, out_size=(OW, OH), extra=extra, fontcheck=o.fontcheck,
                quality=o.quality, png=o.png, jpeg=100 if encoder == 'lossless' else 95, fast=o.fast, gpu=o.gpu, captions=o.captions)
    # the default name says when and how it was made: movie_<YYYYMMDD-HHMMSS>_<res>.mp4 (local time the command started),
    # so a new render never overwrites an earlier one; the chunk folder does not depend on it (a resumed run still goes on)
    out = Path(o.out).expanduser().resolve() if o.out else ROOT / f'movie_{time.strftime("%Y%m%d-%H%M%S")}_{o.res}.mp4'
    if o.out:                                          # said now, not after the whole render (the file is written last)
        if o.screenshot:
            need(not out.exists() or out.is_dir(), f'--out {o.out}: --screenshot에서는 시트를 넣을 폴더입니다 — 같은 이름의 파일이 있습니다')
        else:
            need(not out.is_dir(), f'--out {o.out}: 폴더입니다 — 만들 영상 파일 이름을 주세요 (예: --out {Path(o.out) / "movie.mp4"})')
            need(out.suffix.lower() in ('.mp4', '.mov'), f'--out {o.out}: .mp4 또는 .mov 파일이어야 합니다 (예: --out {out.with_suffix(".mp4").name})')
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                need(False, f'--out {o.out}: 저장할 폴더 {out.parent} 를 만들 수 없습니다 ({e.strerror})')
            try:                                       # (a real write: os.access says yes to root everywhere)
                tempfile.TemporaryFile(dir=out.parent).close()
            except OSError as e:
                need(False, f'--out {o.out}: 폴더 {out.parent} 에 쓸 수 없습니다 ({e.strerror})')
    if o.screenshot:
        need(o.gapframe > 0, '--gapframe 은 1 이상이어야 합니다')
        cue_at = cue_label(data)
        last = max(0.0, dur - 1 / fps)
        if art:                                         # one tile per pose, in the order given
            frames = [(k + 1, t, '') for k, t in enumerate(poses)]
        elif o.at:                                      # the frames at those times (snapped to the frame grid)
            ns = sorted({round(min(t, last) * fps) for t in times_arg(o.at, '--at')})
            frames = [(n, n / fps, cue_at(n / fps)) for n in ns]
        else:
            frames = [(n, n / fps, cue_at(n / fps)) for n in range(f0, f1, o.gapframe)]
        tw, th = OW, OH
        big = tw >= 1000 or th >= 1000                  # one big tile per image: a viewer shrinks a wide sheet, losing the detail
        if o.via is not None:
            o.cols, o.rows = 3, o.rows or (1 if big else max(1, min(6, 3000 // (th + 50))))
        elif not art and not clip and o.res == '480p':
            o.cols = o.cols or (4 if W >= H else 8)
            o.rows = o.rows or (6 if W >= H else 3)
        else:
            o.cols = o.cols or (1 if big else max(1, min(8, 3500 // (tw + 16))))
            o.rows = o.rows or (1 if big else max(1, min(8, 3000 // (th + 50))))
        mods = (f'_res-{o.res}' if o.res != ('1080p' if art else '480p') else '') + \
               (crop_part(*(int(v) for v in clip)) if clip else '') + \
               (f'_seek-check-from-{mmss(o.via)}' if o.via is not None else '')
        t_lo, t_hi = min(f[1] for f in frames), max(f[1] for f in frames)
        proj = re.sub(r'[^\w.-]+', '_', ROOT.name)
        if art:
            safe = re.sub(r'[^\w.-]+', '_', o.art)
            tag = f'{proj}_{RUN_AT}_art-{safe}_{moments(len(frames), t_lo, t_hi, "pose", "poses")}{mods}'
            what = f'ART.{o.art} · viewBox {o.viewbox} · 자세 {len(frames)}개' + (f' · state {o.state}' if o.state else '')
        elif o.at:
            tag = f'{proj}_{RUN_AT}_{moments(len(frames), t_lo, t_hi, "moment", "moments")}{mods}'
            what = f'지정 시각 {len(frames)}곳'
        else:
            tag = f'{proj}_{RUN_AT}_{mmss(f0 / fps)}-to-{mmss(f1 / fps)}_every-{o.gapframe}-frames-at-{fps}fps{mods}'
            what = f'{o.gapframe}프레임마다({o.gapframe / fps:.3g}초)'
        what += (f' · 무대 {clip[0]:g},{clip[1]:g}에서 {clip[2]:g}×{clip[3]:g}만' if clip else '') + \
                (f' · {o.res}' if mods.startswith('_r') else '') + \
                (f' · {fmt_t(o.via)}에서 건너와 다시 찍어 비교' if o.via is not None else '')
        opts.update(mode='sheet', gap=o.gapframe, cols=o.cols, rows=o.rows, clip=clip, via=o.via,
                    cap_png=o.png or o.via is not None,  # (--via compares pixels: lossless captures)
                    page=ART_PAGE if art else 'index.html')
        return screenshots(o, data, opts, frames, tag, what, jobs, size, out if o.out else ROOT / 'screenshots', own_dir=not o.out)

    # chunks live in a temp folder of their own (kept until the movie is made, so a stopped run can go on). The folder is
    # named by the options and by the exact ffmpeg command a chunk is encoded with: chunks encoded another way (another
    # render.py, another ffmpeg) are never joined with these — concat would copy two kinds of stream into one file
    enc = ff_args(encoder, codec, opts['pixels'], o.quality, fps, o.png, '', opts['out_size'])
    key = hashlib.sha1(json.dumps([str(ROOT), dur, opts, enc], sort_keys=True).encode()).hexdigest()[:12]
    work = Path(tempfile.gettempdir()) / f'motion-render-{key}'
    work.mkdir(parents=True, exist_ok=True)
    # chunks made from an older state of the project must not be reused: the files the frames are drawn from are stamped
    stamp = project_stamp(); sf = work / 'stamp.txt'
    old = [p for p in work.iterdir() if p.is_file() and p.name != 'stamp.txt']
    if old and (o.fresh or not sf.exists() or sf.read_text() != stamp):     # --fresh: start over even when nothing changed
        n = sum(1 for p in old if p.name[:1].isdigit() and p.name.endswith('.mp4') and '.part' not in p.name)
        for p in old:
            p.unlink()
        say(f'--fresh: 전에 만들어 둔 조각 {n}개를 버리고 처음부터 만듭니다' if o.fresh else
            f'프로젝트 파일이 바뀌어, 전에 만들어 둔 조각 {n}개를 버리고 새로 만듭니다')
    sf.write_text(stamp)
    (work / FRAMES_UNFIT).unlink(missing_ok=True)
    footage = str(ROOT / o.footage) if extra else ''   # (the workers don't know the project folder)
    step = max(1, round(o.chunk * fps))
    parts = [(n, min(f1, n + step)) for n in range(f0, f1, step)]
    httpd, base = serve()
    say(f'프로젝트: {ROOT}')
    say(f'{(f1 - f0) / fps:.1f}초 ({f1 - f0}프레임, {fps}fps, {size}) · 조각 {len(parts)}개 · 동시 {jobs} · '
        f'{"H.264" if codec == "h264" else "HEVC"} · 인코더 {"VideoToolbox(하드웨어)" if encoder == "videotoolbox" else ENC_NAME[encoder, codec]} · '
        f'화질 {o.quality}{" (무손실 압축)" if encoder == "lossless" else ""} · 캡처 {"PNG" if o.png else "JPEG %d" % opts["jpeg"]} · '
        f'자막 {"있음" if o.captions else "없음"}')
    todo, files, done0 = [], [], 0
    for k, (n0, n1) in enumerate(parts):
        f = str(work / f'{n0:07d}-{n1:07d}.mp4')
        files.append(f)
        if os.path.exists(f):
            say(f'조각 {k + 1}/{len(parts)}: 이미 있음 — 건너뜀'); done0 += n1 - n0
        else:
            todo.append((n0, n1, f, opts, base, f'조각 {k + 1}/{len(parts)}', footage))
    t0 = time.time()
    # every chunk runs in a fresh worker process (its own browser; memory goes back when it ends), also with one job,
    # so Ctrl+C is handled in one place: here. The workers are out of the terminal's reach (_init_worker): Ctrl+C sets
    # `halt`, each worker finishes the frame it is on and closes its file, and the part made so far is saved as a movie
    # (a second Ctrl+C stops at once, without it)
    ctx = mp.get_context('spawn')
    q = ctx.Queue()
    halt = ctx.Event()
    prog = Progress(q, f1 - f0, done0)
    prog.start()
    stop, settled = None, False
    try:
        if todo:
            with ctx.Pool(min(jobs, len(todo)), initializer=_init_worker, initargs=(q, halt), maxtasksperchild=1) as pool:
                try:
                    for _ in pool.imap_unordered(render_chunk, todo):
                        pass
                except KeyboardInterrupt:
                    stop = '멈췄습니다'
                    halt.set()
                    q.put(('m', '멈추는 중 — 조각마다 찍던 프레임까지 파일을 닫고, 처음부터 이어진 부분을 영상으로 저장합니다 '
                                '(한 번 더 누르면 저장하지 않고 바로 끝냅니다)'))
                    pool.close()
                    pool.join()                          # (the chunks not started yet return at once)
                    settled = True
    except KeyboardInterrupt:
        stop = '멈췄습니다'
    except Exception:
        stop = '오류로 멈췄습니다'
        tb = traceback.format_exc()
    finally:
        try:
            if not stop or settled:
                time.sleep(0.6)                          # let the last reports arrive
            prog.finish(drain=not stop or settled)
        except KeyboardInterrupt:                        # (Ctrl+C again: stop here, nothing saved)
            stop, settled = '멈췄습니다', False
            prog.finish(drain=False)
        httpd.shutdown()

    audio = ROOT / data.get('audio', 'audio/narration.mp3')
    TAG = ['-tag:v', 'hvc1'] if codec == 'hevc' else []

    def assemble(pieces, nframes, dest):
        """join these chunk files (nframes from frame f0 on) into dest; add the narration of the same stretch (t = the
        video's t) when there is voice in it — a range render gets its own part of the track; a stretch that is still
        the silent placeholder is left without sound. Returns the sound part of the closing line"""
        lst = work / 'list.txt'
        lst.write_text(''.join(f"file '{f}'\n" for f in pieces), encoding='utf-8')
        a0, span = f0 / fps, nframes / fps
        joined = str(work / 'joined.mp4')
        subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', joined], check=True)
        # the clips that play their own sound (written by the chunks' pages), mixed with the narration as the player plays them
        cj, clipped = work / 'clips.json', []
        if o.audio and cj.exists():
            for k, c in enumerate(json.loads(cj.read_text(encoding='utf-8'))):
                if not (ROOT / c['file']).exists():
                    say(f'주의: 클립 소리의 원본이 없어 뺍니다 — {c["file"]}'); continue
                r = clip_sound(c, a0, a0 + span, str(work / f'clip{k}.f32'))
                if r:
                    clipped.append(r)
        elif o.audio and footage_clips():
            # only when no chunk recorded the list (every chunk came from an earlier run of an older render.py): a project
            # without sounding clips writes an empty list and never gets here
            say(f'주의: 영상 클립의 소리 정보가 없습니다(조각을 모두 이전 실행에서 가져왔고, 그때 기록이 남지 않음) — '
                f'소리를 켠 클립(audio: true)이 있다면 이 조각 폴더를 지우고 다시 실행하세요: {work}')
        voiced = o.audio and audio.exists() and has_voice(data, a0, span)
        if voiced or clipped:
            ins, pre, mix, k = ['-i', joined], [], [], 0     # input 0: the picture
            if voiced:
                ins += ['-ss', f'{a0:.6f}', '-t', f'{span:.6f}', '-i', str(audio)]; k += 1
                pre.append(f'[{k}:a]aresample={SR_MIX},{to_stereo(audio)}[n]'); mix.append('[n]')
            for at, raw in clipped:
                ins += ['-f', 'f32le', '-ar', str(SR_MIX), '-ac', '2', '-i', raw]; k += 1
                ms = int(round(at * 1000))
                pre.append(f'[{k}:a]adelay={ms}|{ms}[c{k}]'); mix.append(f'[c{k}]')
            graph = ';'.join(pre + [''.join(mix) + (f'amix=inputs={len(mix)}:normalize=0:dropout_transition=0,' if len(mix) > 1 else '') + 'apad[a]'])
            subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y'] + ins + ['-filter_complex', graph, '-map', '0:v', '-map', '[a]', '-shortest',
                            '-c:v', 'copy'] + TAG + ['-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dest)], check=True)
            sound = '소리: ' + ' + '.join((['내레이션'] if voiced else []) + ([f'클립 소리 {len(clipped)}개'] if clipped else [])) + \
                (' (내레이션은 이 구간 밖이 아직 임시 무음)' if voiced and data.get('placeholder') else '')
        else:
            subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', joined, '-c', 'copy'] + TAG + ['-movflags', '+faststart', str(dest)], check=True)
            sound = '소리 없음' + (' (이 구간의 내레이션은 아직 임시 무음)' if o.audio and data.get('placeholder') else '')
        record_generated([dest])                         # generated.json: check.mjs accepts the movie as the skill's own
        return sound

    if stop:
        if stop != '멈췄습니다':
            frames_unfit(work, o.footage, fps, scale, o.res)
            print(tb, file=sys.stderr, flush=True)
        if settled:
            # the part made so far, without a hole: the finished chunks from the start of the range, then the chunk right
            # after them as far as its worker got (its .part.json says how many frames its file holds). Chunks further on
            # were drawn at the same time, but a gap lies before them, so they wait for the next run
            pieces, got = [], 0
            for (n0, n1), f in zip(parts, files):
                if os.path.exists(f):
                    pieces.append(f); got += n1 - n0
                    continue
                if os.path.exists(f + '.part.json'):
                    k = json.loads(Path(f + '.part.json').read_text(encoding='utf-8'))['frames']
                    pieces.append(f + '.part.mp4'); got += k
                break
            if got:
                dest = out.with_name(f'{out.stem}_partial{out.suffix}')
                try:
                    sound = assemble(pieces, got, dest)
                    say(f'지금까지 만든 부분을 저장했습니다: {dest} · {f0 / fps:.2f}–{(f0 + got) / fps:.2f}초 ({got}프레임) · {size} · {sound}')
                except KeyboardInterrupt:
                    warn('저장하는 중에 멈췄습니다 — 지금까지 만든 부분은 영상으로 저장하지 못했습니다')
                    dest.unlink(missing_ok=True)
            else:
                say('처음부터 이어진 프레임이 아직 없어 영상으로 저장할 부분이 없습니다')
        kept = sum(os.path.exists(f) for f in files)
        # a --fresh run that is stopped goes on without --fresh (with it, the same command would drop these chunks again)
        warn(f'{stop}. 끝난 조각 {kept}/{len(files)}개는 남겨 두었습니다 — '
             f'{"--fresh를 뺀 " if o.fresh else ""}같은 명령으로 다시 실행하면 이어서 만듭니다.')
        sys.exit(130 if stop == '멈췄습니다' else 1)
    if project_stamp() != stamp:
        say('주의: 렌더하는 동안 프로젝트 파일이 바뀌었습니다 — 조각마다 다른 상태가 찍혔을 수 있습니다')
    sound = assemble(files, f1 - f0, out)
    shutil.rmtree(work, ignore_errors=True)
    say(f'완성: {out} · {(f1 - f0) / fps:.1f}초 · {size} · {sound} · 걸린 시간 {(time.time() - t0) / 60:.1f}분')


if __name__ == '__main__':
    main()

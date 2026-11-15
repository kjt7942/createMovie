# Browser setup — getting a headless Chromium on any machine

`snapshot.mjs` needs a Chromium it can drive. `setup_browser.mjs` finds or builds one and records it
in `~/.cache/motion-video-deps/browser.json`, which `snapshot.mjs` reads.

## Contents
1. Quick path
2. What setup_browser.mjs does
3. By platform
4. Container specifics
5. Troubleshooting
6. Asking the user

---

## 1. Quick path

```bash
node <skill>/scripts/setup_browser.mjs --check   # diagnose only: OS, container, sudo, browsers, missing
                                                 # libraries, GPU, /dev/shm, fonts, network + recommendation
node <skill>/scripts/setup_browser.mjs           # make it work (user space only)
```

Before the first real run, tell the user in one line what it will download (Chromium ~115 MB into the
Playwright cache, and on slim Linux possibly a few library packages into ~/.cache — no sudo).

## 2. What setup_browser.mjs does

1. installs this folder's npm deps (`playwright-core` pinned to the browser build, `jsdom`)
2. downloads Playwright's **chromium-headless-shell**; if the download is impossible, uses an installed
   Chrome/Chromium/Edge
3. on Linux, runs `ldd` on the browser; every missing library is mapped to its distro package (a built-in
   table of Chromium's usual deps, handling Ubuntu 24.04+/Debian 13 `t64` names; else the distro's
   **Contents index**, the official file→package map), downloaded from the official archive, **SHA256-checked**
   against the archive's Packages index (fetched over HTTP; its GPG-signed Release file is not verified, so this
   catches corrupt downloads, not a tampered mirror), unpacked with `dpkg-deb -x` into `~/.cache/motion-video-deps/root`, and
   re-checked — including the new libraries' own dependencies — for up to 5 rounds
4. launches the browser, renders a test page, saves `browser.json`

Other flags:
- `--system` — install the missing packages system-wide instead (runs `sudo apt-get install …` when sudo
  needs no password; otherwise prints the exact `sudo …` command for the user to run themselves)
- `--resolve libfoo.so.1,…` — just show which packages provide these libraries

Nothing is written outside the user's cache unless `--system` is used.

## 3. By platform

| platform | what happens |
|---|---|
| macOS (Intel/Apple silicon) | the download just works; installed Chrome is the fallback |
| Windows | same; run with `node` from PowerShell |
| Ubuntu / Debian / WSL | download + user-space library fetch as needed |
| other glibc Linux (Fedora, Arch, openSUSE) | download works; missing libraries must come from the system package manager — the script lists them. Admin alternative: `sudo npx playwright install-deps chromium` (Debian/Ubuntu only) or the distro equivalents (`dnf install nss atk cups-libs libxkbcommon …`, `pacman -S nss …`) |
| Alpine / musl | Playwright's builds don't run on musl: install `chromium` with `apk` (needs root) — setup then finds it as a system browser |
| no network | point `PLAYWRIGHT_BROWSERS_PATH` at a copied browser folder, or use an installed browser; otherwise ask the user for screenshots |

## 4. Container specifics

- **No sandbox** (user namespaces blocked): Playwright launches Chromium with `--no-sandbox` by default. Fine for local files.
- **Small `/dev/shm`** (Docker's 64 MB): Playwright passes `--disable-dev-shm-usage`. Fine.
- **No GPU**: software rendering. Screenshots are exact; smoothness can't be judged here.
- **No fonts / no CJK fonts**: pages must carry their own fonts (new_project.mjs installs the SIL OFL 1.1 core fonts into `fonts/`). If a page relies on
  system fonts, text renders as boxes — install fonts in user space: copy `.ttf/.otf` into `~/.local/share/fonts`
  and run `fc-cache -f`. `snapshot.mjs` embeds Pretendard for its own labels.
- **Shared home**: other sessions may share `~/.cache/ms-playwright`; don't delete it without asking.

## 5. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `error while loading shared libraries: libX.so` | missing system library | `setup_browser.mjs` (or `--system`) |
| `Executable doesn't exist at …` | browser not downloaded / version mismatch | `setup_browser.mjs`; keep `playwright-core` pinned to the downloaded build |
| `Target page, context or browser has been closed` right at launch | the binary died on startup — usually libraries | `setup_browser.mjs --check`, then fix what it lists |
| screenshots show □ boxes | page uses fonts the machine lacks | bundle the font in the project (or install fonts, §4) |
| blank or half-drawn frames | player not ready, a page error, fonts still loading | read the console section of the report; snapshot waits for `vp-ready` and `document.fonts.ready` |
| `SHA256 mismatch` | corrupted download or index | delete `~/.cache/motion-video-deps/idx` and rerun |
| `HTTP 404` for a `.deb` | the cached package index is older than the archive (it is fetched again once by itself) | delete `~/.cache/motion-video-deps/idx` and rerun |
| launch works in one shell but not another | `LD_LIBRARY_PATH` not applied | launch through snapshot.mjs (it applies `browser.json`) |

## 6. Asking the user

If no browser can be made to run (no network, exotic OS, no permission), don't guess: say so, hand off
with the manual layout checks you did, and ask the user to open `index.html`, press D (debug bar) and send
screenshots of the moments that matter — images put in the working folder can be opened and looked at.

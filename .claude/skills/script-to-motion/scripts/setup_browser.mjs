#!/usr/bin/env node
/**
 * setup_browser.mjs — get a headless Chromium that snapshot.mjs can drive, on whatever machine this is.
 *
 *   node setup_browser.mjs            diagnose, then make it work (user space only: ~/.cache)
 *   node setup_browser.mjs --check    diagnose and recommend, change nothing
 *   node setup_browser.mjs --system   use the system package manager for missing libraries
 *                                     (runs it with passwordless sudo, otherwise prints the command)
 *   node setup_browser.mjs --resolve libfoo.so.1,libbar.so.2   show which distro packages provide them
 *
 * What "make it work" does, in order:
 *   1. npm deps of this folder (playwright-core, jsdom, fontkit + wawoff2 for glyph outlines)
 *   2. a browser: Playwright's chromium-headless-shell (download ~115 MB into the Playwright cache);
 *      if that can't be downloaded, an installed Chrome / Chromium / Edge
 *   3. Linux: every shared library the browser can't find is resolved to its Ubuntu/Debian package
 *      (built-in table first, the distro's Contents index as fallback), downloaded from the official
 *      archive, SHA256-checked against its Packages index (HTTP; the Release signature is not verified — lib/debs.mjs)
 *      and extracted into ~/.cache/motion-video-deps — repeated until the
 *      browser and the extracted libraries have no missing dependencies. No sudo, nothing outside the cache.
 *   4. a real launch + render test; the working setup is saved to ~/.cache/motion-video-deps/browser.json,
 *      which snapshot.mjs reads.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { osRelease, archiveFor, DebRepo } from './lib/debs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = new Set(process.argv.slice(2));
const CHECK_ONLY = args.has('--check');
const SYSTEM = args.has('--system');
const DEPS = path.join(os.homedir(), '.cache', 'motion-video-deps');
const CONFIG = path.join(DEPS, 'browser.json');
const say = (m = '') => console.log(m);
const die = (m) => { console.error('✖ ' + m); process.exit(1); };
const run = (cmd, a, o = {}) => spawnSync(cmd, a, { encoding: 'utf8', ...o });
const has = (cmd) => run('sh', ['-c', `command -v ${cmd}`]).status === 0;

// ======================= diagnose =======================
const OSR = process.platform === 'linux' ? osRelease() : {};
const ARCH = process.platform === 'linux' && has('dpkg') ? run('dpkg', ['--print-architecture']).stdout.trim() : process.arch;

function browsersPath() {
  if (process.env.PLAYWRIGHT_BROWSERS_PATH) return process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (process.platform === 'darwin') return path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright');
  if (process.platform === 'win32') return path.join(process.env.LOCALAPPDATA || os.homedir(), 'ms-playwright');
  return path.join(os.homedir(), '.cache', 'ms-playwright');
}
function playwrightShell() {
  const root = browsersPath();
  if (!fs.existsSync(root)) return null;
  for (const d of fs.readdirSync(root).filter((n) => n.startsWith('chromium_headless_shell-')).sort().reverse()) {
    for (const sub of fs.readdirSync(path.join(root, d))) {
      for (const name of ['chrome-headless-shell', 'chrome-headless-shell.exe']) {
        const f = path.join(root, d, sub, name);
        if (fs.existsSync(f)) return f;
      }
    }
  }
  return null;
}
function systemBrowsers() {
  const c = {
    darwin: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'],
    win32: [`${process.env.PROGRAMFILES}\\Google\\Chrome\\Application\\chrome.exe`, `${process.env['PROGRAMFILES(X86)']}\\Microsoft\\Edge\\Application\\msedge.exe`],
    linux: ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge'],
  }[process.platform] || [];
  const found = [];
  for (const b of c) {
    if (b.includes('/') || b.includes('\\')) { if (fs.existsSync(b)) found.push(b); }
    else { const r = run('sh', ['-c', `command -v ${b}`]); if (r.status === 0) found.push(r.stdout.trim()); }
  }
  return found;
}

const EXTRA_DIRS = ['usr/lib/aarch64-linux-gnu', 'lib/aarch64-linux-gnu', 'usr/lib/x86_64-linux-gnu', 'lib/x86_64-linux-gnu',
  'usr/lib/arm-linux-gnueabihf', 'usr/lib'];
const libDirs = () => EXTRA_DIRS.map((d) => path.join(DEPS, 'root', d)).filter((d) => fs.existsSync(d));
const ldPath = () => [...libDirs(), process.env.LD_LIBRARY_PATH].filter(Boolean).join(':');
function missingFor(files) {
  if (process.platform !== 'linux' || !has('ldd')) return [];
  const miss = new Set();
  for (const f of files) {
    const out = run('ldd', [f], { env: { ...process.env, LD_LIBRARY_PATH: ldPath() } }).stdout || '';
    for (const m of out.matchAll(/^\s*(\S+) => not found/gm)) miss.add(m[1]);
  }
  return [...miss];
}
const extractedLibs = () => libDirs().flatMap((d) => fs.readdirSync(d).filter((f) => /\.so(\.|$)/.test(f)).map((f) => path.join(d, f)));

function diagnose(exe) {
  const r = {};
  r.platform = `${process.platform} ${ARCH}${OSR.PRETTY_NAME ? ` · ${OSR.PRETTY_NAME}` : ''}`;
  r.container = fs.existsSync('/.dockerenv') ? 'docker' : fs.existsSync('/run/.containerenv') ? 'podman' : (process.env.WSL_DISTRO_NAME ? 'WSL' : 'none detected');
  r.sudo = process.platform === 'win32' ? 'n/a' : (run('sudo', ['-n', 'true']).status === 0 ? 'passwordless' : (has('sudo') ? 'needs a password' : 'not installed'));
  r.pwShell = playwrightShell() || 'not downloaded';
  r.system = systemBrowsers().join(', ') || 'none';
  r.missing = exe ? missingFor([exe]) : [];
  if (process.platform === 'linux') {
    r.gpu = fs.existsSync('/dev/dri') ? 'yes (/dev/dri)' : 'none — software rendering (fine for screenshots, not for smoothness)';
    const shm = run('df', ['-k', '/dev/shm']).stdout.split('\n')[1];
    r.shm = shm ? `${Math.round(Number(shm.split(/\s+/)[1]) / 1024)} MB (Playwright uses --disable-dev-shm-usage)` : '?';
    r.fonts = has('fc-list') ? `${run('fc-list').stdout.split('\n').filter(Boolean).length} total, ${run('fc-list', [':lang=ko']).stdout.split('\n').filter(Boolean).length} Korean` : 'fontconfig missing';
    r.userns = run('unshare', ['--user', 'true']).status === 0 ? 'available' : 'blocked (browser runs with --no-sandbox, Playwright default)';
  }
  return r;
}
async function reachable(url) {
  try {
    const res = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(8000) });
    return res.status < 500 ? 'reachable' : `HTTP ${res.status}`;
  } catch {
    return 'unreachable';
  }
}
// ======================= library → package =======================
// Chromium's usual runtime libraries. Several packages got a "t64" suffix in Ubuntu 24.04+/Debian 13.
const LIBMAP = {
  'libnss3.so': ['libnss3'], 'libnssutil3.so': ['libnss3'], 'libsmime3.so': ['libnss3'],
  'libnspr4.so': ['libnspr4'], 'libplc4.so': ['libnspr4'], 'libplds4.so': ['libnspr4'],
  'libasound.so.2': ['libasound2t64', 'libasound2'],
  'libatk-1.0.so.0': ['libatk1.0-0t64', 'libatk1.0-0'],
  'libatk-bridge-2.0.so.0': ['libatk-bridge2.0-0t64', 'libatk-bridge2.0-0'],
  'libatspi.so.0': ['libatspi2.0-0t64', 'libatspi2.0-0'],
  'libcairo.so.2': ['libcairo2'], 'libcups.so.2': ['libcups2t64', 'libcups2'],
  'libdbus-1.so.3': ['libdbus-1-3'], 'libdrm.so.2': ['libdrm2'], 'libgbm.so.1': ['libgbm1'],
  'libglib-2.0.so.0': ['libglib2.0-0t64', 'libglib2.0-0'], 'libgobject-2.0.so.0': ['libglib2.0-0t64', 'libglib2.0-0'],
  'libgio-2.0.so.0': ['libglib2.0-0t64', 'libglib2.0-0'], 'libgmodule-2.0.so.0': ['libglib2.0-0t64', 'libglib2.0-0'],
  'libpango-1.0.so.0': ['libpango-1.0-0'], 'libX11.so.6': ['libx11-6'], 'libxcb.so.1': ['libxcb1'],
  'libXcomposite.so.1': ['libxcomposite1'], 'libXdamage.so.1': ['libxdamage1'], 'libXext.so.6': ['libxext6'],
  'libXfixes.so.3': ['libxfixes3'], 'libxkbcommon.so.0': ['libxkbcommon0'], 'libXrandr.so.2': ['libxrandr2'],
  'libexpat.so.1': ['libexpat1'], 'libfontconfig.so.1': ['libfontconfig1'], 'libfreetype.so.6': ['libfreetype6'],
  'libudev.so.1': ['libudev1'], 'libxshmfence.so.1': ['libxshmfence1'], 'libwayland-server.so.0': ['libwayland-server0'],
};

// ======================= main =======================
say('== environment');
let exe = playwrightShell() || systemBrowsers()[0] || null;
const d = diagnose(exe);
for (const [k, v] of Object.entries({
  'platform': d.platform, 'container': d.container, 'sudo': d.sudo, 'playwright browser': d.pwShell, 'system browsers': d.system,
  'missing libraries': exe ? (d.missing.join(', ') || 'none') : '(no browser yet)', 'gpu': d.gpu, '/dev/shm': d.shm, 'fonts': d.fonts, 'sandbox': d.userns,
})) if (v) say(`  ${k.padEnd(18)} ${v}`);
const arch = process.platform === 'linux' ? archiveFor(OSR, ARCH) : null;
const repo = arch ? new DebRepo({ archive: arch, cacheDir: path.join(DEPS, 'idx') }) : null;
const net = {
  'npm registry': await reachable('https://registry.npmjs.org/'),
  'playwright CDN': await reachable('https://cdn.playwright.dev/builds/'),
  ...(arch ? { 'distro archive': await reachable(`${arch.base}/dists/${arch.code}/Release`) } : {}),
};
say('  network            ' + Object.entries(net).map(([k, v]) => `${k}: ${v}`).join(' · '));

const resolveArg = process.argv.find((a, i) => process.argv[i - 1] === '--resolve');
if (resolveArg) {
  if (!arch) die('--resolve needs an Ubuntu/Debian system');
  const libs = resolveArg.split(',');
  const idx = await repo.packages();
  const fromTable = (l) => (LIBMAP[l] || []).find((p) => idx[p]);
  const rest = libs.filter((l) => !fromTable(l));
  const found = rest.length ? await repo.contents(rest) : {};
  for (const l of libs) {
    const via = fromTable(l) ? `${fromTable(l)} (table)` : found[l] ? `${found[l]} (Contents index)${idx[found[l]] ? '' : ' — not in main/universe'}` : 'not found';
    say(`  ${l} → ${via}`);
  }
  process.exit(0);
}

if (CHECK_ONLY) {
  say('\n== recommendation');
  if (!exe && net['playwright CDN'] === 'unreachable' && d.system === 'none') say('  No browser and no way to download one: ask the user for screenshots, or to run this on a machine with network access.');
  else if (!exe) say('  Run without --check: it will download chromium-headless-shell (~115 MB).');
  if (d.missing.length) {
    if (d.sudo === 'passwordless') say('  Missing libraries can be installed system-wide: node setup_browser.mjs --system');
    else if (arch) say(`  Missing libraries will be fetched into ${DEPS} (no sudo). Alternative with admin rights: sudo npx playwright install-deps chromium-headless-shell`);
    else say('  Install the missing libraries with the system package manager (this script only knows Ubuntu/Debian archives).');
  }
  if (exe && !d.missing.length) say('  Ready: run node setup_browser.mjs once to record the configuration, then snapshot.mjs.');
  process.exit(0);
}

// 1. npm deps
if (['playwright-core', 'jsdom', 'fontkit', 'wawoff2', 'polygon-clipping'].some((m) => !fs.existsSync(path.join(here, 'node_modules', m)))) {
  say('\n• installing npm dependencies…');
  if (run('npm', ['install', '--no-audit', '--no-fund', '--prefix', here], { stdio: 'inherit' }).status !== 0) die('npm install failed');
}
const { chromium } = await import(pathToFileURL(path.join(here, 'node_modules', 'playwright-core', 'index.mjs')).href);

// 2. browser
let source = 'playwright';
if (!playwrightShell()) {
  say(`\n• downloading chromium-headless-shell (~115 MB) into ${browsersPath()}`);
  const r = run(process.execPath, [path.join(here, 'node_modules', 'playwright-core', 'cli.js'), 'install', 'chromium-headless-shell'], { stdio: 'inherit' });
  if (r.status !== 0) say('  ⚠ download failed');
}
exe = playwrightShell();
if (!exe) {
  exe = systemBrowsers()[0];
  source = 'system';
  if (!exe) die('no browser available: no download possible and no Chrome/Chromium/Edge installed. Ask the user for screenshots instead.');
  say(`• using the installed browser ${exe}`);
}

// 3. libraries (Linux)
let missing = missingFor([exe]);
if (missing.length) {
  if (SYSTEM) {
    const pkgs = repo ? await repo.resolve(missing, LIBMAP) : [];
    const cmd = pkgs.length ? `sudo apt-get install -y ${pkgs.join(' ')}` : 'sudo npx playwright install-deps chromium-headless-shell';
    if (d.sudo === 'passwordless') {
      say(`\n• ${cmd}`);
      if (run('sh', ['-c', cmd], { stdio: 'inherit' }).status !== 0) die('system install failed');
    } else {
      die(`needs admin rights. Ask the user to run it themselves:\n    ! ${cmd}\n  or run this script without --system to fetch the libraries into ${DEPS} instead.`);
    }
  } else {
    if (!arch) die(`missing ${missing.join(', ')} and this script can only fetch from Ubuntu/Debian archives — install them with the system package manager`);
    if (!has('dpkg-deb')) die('dpkg-deb is needed to unpack packages');
    say(`\n• resolving missing libraries in user space (${DEPS})`);
    for (let round = 1; round <= 5 && missing.length; round++) {
      say(`  round ${round}: ${missing.join(', ')}`);
      const idx = await repo.packages();
      const pkgs = (await repo.resolve(missing, LIBMAP)).filter((p) => !fs.existsSync(path.join(DEPS, 'debs', path.basename(idx[p].Filename))));
      if (!pkgs.length) break;
      await repo.fetch(pkgs, path.join(DEPS, 'root'), path.join(DEPS, 'debs'));
      missing = missingFor([exe, ...extractedLibs()]);
    }
    missing = missingFor([exe]);
    if (missing.length) die(`still missing after fetching: ${missing.join(', ')}`);
  }
}

// 4. prove it and record the setup
const env = { ...process.env };
if (libDirs().length) env.LD_LIBRARY_PATH = ldPath();
const browser = await chromium.launch({ executablePath: exe, env }).catch((e) => die('launch failed: ' + String(e.message).split('\n')[0]));
const page = await browser.newPage();
await page.setContent('<div style="font:48px sans-serif">render test</div>');
const png = await page.screenshot();
const version = browser.version();
await browser.close();
fs.mkdirSync(DEPS, { recursive: true });
fs.writeFileSync(CONFIG, JSON.stringify({ executablePath: exe, source, version, libDirs: libDirs(), savedAt: new Date().toISOString() }, null, 2));
say(`\n✓ headless ${source === 'system' ? 'browser' : 'Chromium'} ${version} launches and renders (${png.length} B test shot)`);
say(`  configuration saved to ${CONFIG} — snapshot.mjs will use it`);
if (process.platform === 'linux' && !fs.existsSync('/dev/dri')) say('  note: no GPU here — screenshots are exact, but playback smoothness cannot be judged on this machine');

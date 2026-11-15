#!/usr/bin/env node
/**
 * setup_blender.mjs — prepare Blender + the official Blender Lab MCP server, without sudo.
 *
 *   node setup_blender.mjs --check                 diagnose only
 *   node setup_blender.mjs                         set everything up (idempotent)
 *   node setup_blender.mjs --version 5.2.2         another Blender release (default 5.1.2, known good)
 *   node setup_blender.mjs --blender /path/blender use an installed Blender instead of downloading one
 *   node setup_blender.mjs --mcp-ref <commit>      another blender_mcp revision (default ff54e4d…, known good)
 *   node setup_blender.mjs --python python3.12     the Python for the MCP server venv (default python3; needs 3.10+)
 *
 * Result (all under ~/.cache/motion-video-deps/blender/):
 *   blender-<v>-linux-x64/   official Blender build (SHA256-verified)
 *   x64root/                 x86_64 runtime libraries — only on non-x86_64 Linux hosts (e.g. Apple-silicon
 *                            Docker with Rosetta), fetched from the Ubuntu/Debian amd64 archive
 *   bin/blender              launcher that runs Blender correctly on this machine
 *   blender_mcp/             the official MCP repository at a pinned revision
 *   venv/                    Python venv with the MCP server (`blender-mcp`)
 *   blender.json             paths used by blender_mcp.mjs
 * then runs blender_mcp.mjs selftest (start Blender, call a tool, export a GLB, stop).
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { osRelease, archiveFor, DebRepo } from './lib/debs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
const VERSION = typeof opt.version === 'string' ? opt.version : '5.1.2';
const MCP_REF = typeof opt['mcp-ref'] === 'string' ? opt['mcp-ref'] : 'ff54e4d8f6b09502f2f466189cca0e52b4a91643';
const MCP_URL = 'https://projects.blender.org/lab/blender_mcp.git';
const BASE = path.join(os.homedir(), '.cache', 'motion-video-deps', 'blender');
const CONFIG = path.join(BASE, 'blender.json');
const PY3 = typeof opt.python === 'string' ? opt.python : 'python3';   // the Python the MCP server venv is made with
const say = (m = '') => console.log(m);
const die = (m) => { console.error('✖ ' + m); process.exit(1); };
const run = (cmd, a, o = {}) => spawnSync(cmd, a, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...o });
const has = (cmd) => run('sh', ['-c', `command -v ${cmd}`]).status === 0;
const LINUX = process.platform === 'linux';
const OSR = LINUX ? osRelease() : {};
const HOST_X64 = process.arch === 'x64';

// x86_64 runtime libraries Blender links against, by file name → Ubuntu/Debian package candidates
const X64_LIBS = {
  'libX11.so.6': ['libx11-6'], 'libXrender.so.1': ['libxrender1'], 'libXfixes.so.3': ['libxfixes3'], 'libXi.so.6': ['libxi6'],
  'libxkbcommon.so.0': ['libxkbcommon0'], 'libxcb.so.1': ['libxcb1'], 'libXext.so.6': ['libxext6'], 'libSM.so.6': ['libsm6'],
  'libICE.so.6': ['libice6'], 'libGL.so.1': ['libgl1'], 'libEGL.so.1': ['libegl1'], 'libXau.so.6': ['libxau6'],
  'libXdmcp.so.6': ['libxdmcp6'], 'libuuid.so.1': ['libuuid1'], 'libGLdispatch.so.0': ['libglvnd0'], 'libGLX.so.0': ['libglx0'],
  'libXxf86vm.so.1': ['libxxf86vm1'], 'libz.so.1': ['zlib1g'], 'libstdc++.so.6': ['libstdc++6'], 'libgcc_s.so.1': ['libgcc-s1'],
  'libbsd.so.0': ['libbsd0'], 'libmd.so.0': ['libmd0'],
};

// ---------- diagnose ----------
function emulation() {
  if (!LINUX || HOST_X64) return { ok: true, how: 'native x86_64' };
  // run a tiny static x86_64 binary (busybox from the distro's amd64 archive)
  const bb = path.join(BASE, 'tools', 'busybox-amd64');
  return { bb };
}
async function testEmulation() {
  const e = emulation();
  if (e.ok) return e;
  if (!fs.existsSync(e.bb)) {
    const a = archiveFor(OSR, 'amd64');
    if (!a) return { ok: false, how: 'unknown (not Ubuntu/Debian — cannot fetch a test binary)' };
    const repo = new DebRepo({ archive: a, cacheDir: path.join(BASE, 'idx'), log: () => {} });
    const tmp = path.join(BASE, 'tools', 'bbroot');
    await repo.fetch(['busybox-static'], tmp, path.join(BASE, 'debs'));
    const f = run('find', [tmp, '-name', 'busybox', '-type', 'f']).stdout.trim().split('\n')[0];
    fs.copyFileSync(f, e.bb);
    fs.chmodSync(e.bb, 0o755);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  const r = run(e.bb, ['uname', '-m']);
  if (r.status !== 0 || r.stdout.trim() !== 'x86_64') return { ok: false, how: 'x86_64 binaries do not run here' };
  const maps = run(e.bb, ['cat', '/proc/self/maps']).stdout;
  return { ok: true, how: /rosetta/i.test(maps) ? 'Rosetta' : /qemu/i.test(maps) ? 'QEMU' : 'binfmt emulation' };
}
function existingBlender() {
  if (typeof opt.blender === 'string') return opt.blender;
  if (process.env.BLENDER_PATH && fs.existsSync(process.env.BLENDER_PATH)) return process.env.BLENDER_PATH;
  if (process.platform === 'darwin') {
    for (const p of ['/Applications/Blender.app/Contents/MacOS/Blender', path.join(os.homedir(), 'Applications/Blender.app/Contents/MacOS/Blender')]) if (fs.existsSync(p)) return p;
  }
  if (process.platform === 'win32') {
    const root = path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Blender Foundation');
    if (fs.existsSync(root)) for (const d of fs.readdirSync(root).sort().reverse()) { const p = path.join(root, d, 'blender.exe'); if (fs.existsSync(p)) return p; }
  }
  return null;
}

// the official MCP server needs the mcp Python SDK, which needs Python 3.10 or newer: said before anything is downloaded
const pyv = (run(PY3, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])']).stdout || '').trim();
const pyOk = /^\d+\.\d+$/.test(pyv) && (Number(pyv.split('.')[0]) > 3 || (Number(pyv.split('.')[0]) === 3 && Number(pyv.split('.')[1]) >= 10));
const PY_HELP = `the Blender MCP server needs Python 3.10 or newer (the mcp SDK) — ${pyv ? `${PY3} is ${pyv}` : `${PY3} was not found`}. ` +
  'Install a newer Python (macOS: brew install python@3.12 or python.org; Ubuntu/Debian: apt install python3.12 python3.12-venv) ' +
  'and rerun with --python <that python>, e.g. --python python3.12';
if (!opt.check && !pyOk && !fs.existsSync(path.join(BASE, 'venv', 'bin', 'blender-mcp'))) die(PY_HELP);

say('== environment');
say(`  platform        ${process.platform} ${process.arch}${OSR.PRETTY_NAME ? ' · ' + OSR.PRETTY_NAME : ''}`);
const emu = await testEmulation();
if (LINUX) say(`  x86_64          ${emu.ok ? 'runs (' + emu.how + ')' : 'NOT available — ' + emu.how}`);
const preinstalled = existingBlender();
say(`  Blender         ${preinstalled || (fs.existsSync(CONFIG) ? JSON.parse(fs.readFileSync(CONFIG, 'utf8')).launcher : 'not installed')}`);
say(`  python          ${pyv ? `${PY3} ${pyv}${pyOk ? '' : ' — too old (needs 3.10+)'}` : `${PY3} not found`}`);
say(`  python venv     ${run(PY3, ['-m', 'venv', '--help']).status === 0 ? 'available' : 'missing (install python3-venv)'} · git ${has('git') ? 'ok' : 'missing'} · xz ${has('xz') ? 'ok' : 'missing'}`);
say(`  MCP server      ${fs.existsSync(path.join(BASE, 'venv', 'bin', 'blender-mcp')) ? 'installed' : 'not installed'}`);
if (opt.check) {
  say('\n== recommendation');
  const cfg = fs.existsSync(CONFIG) ? JSON.parse(fs.readFileSync(CONFIG, 'utf8')) : null;
  const ready = cfg && cfg.launcher && fs.existsSync(cfg.launcher) && cfg.server && fs.existsSync(cfg.server);
  if (LINUX && !emu.ok && !HOST_X64) say('  This ARM Linux host cannot run x86_64 programs, and Blender ships no official ARM Linux build.\n  Docker Desktop on a Mac: Settings → General → enable "Use Rosetta for x86_64/amd64 emulation on Apple Silicon", restart.\n  Other hosts: install qemu-user-static + binfmt (admin), or run Blender MCP on another machine.');
  else if (!pyOk && !ready) say('  ' + PY_HELP + '.');
  else if (ready) say(`  Ready: Blender ${cfg.version || ''} + MCP server are set up (${CONFIG}). Use blender_mcp.mjs start; rerun without --check only to repair or change versions.`);
  else say('  Run without --check to set everything up (Blender ~400 MB download, x86_64 runtime libraries if needed, MCP venv).');
  process.exit(0);
}

fs.mkdirSync(BASE, { recursive: true });
let launcher;
let blenderDir = null;

// ---------- Blender ----------
if (preinstalled) {
  launcher = preinstalled;
  say(`\n• using the installed Blender ${launcher}`);
} else if (!LINUX) {
  die('download Blender 5.1+ from https://www.blender.org/download/ (or `brew install --cask blender` on macOS), then rerun — or pass --blender <path>');
} else {
  if (!HOST_X64 && !emu.ok) die('x86_64 programs cannot run here (see --check). Blender publishes Linux builds for x86_64 only.');
  blenderDir = path.join(BASE, `blender-${VERSION}-linux-x64`);
  if (!fs.existsSync(path.join(blenderDir, 'blender'))) {
    const series = VERSION.split('.').slice(0, 2).join('.');
    const file = `blender-${VERSION}-linux-x64.tar.xz`;
    const dl = path.join(BASE, 'downloads', file);
    fs.mkdirSync(path.dirname(dl), { recursive: true });
    const sums = await (await fetch(`https://download.blender.org/release/Blender${series}/blender-${VERSION}.sha256`)).text();
    const want = (sums.split('\n').find((l) => l.includes(file)) || '').split(/\s+/)[0];
    if (!want) die(`no checksum for ${file} — is ${VERSION} a real release?`);
    if (!fs.existsSync(dl)) {
      say(`\n• downloading ${file} (~400 MB)…`);
      const r = run('curl', ['-fsSL', '-o', dl, `https://download.blender.org/release/Blender${series}/${file}`], { stdio: 'inherit' });
      if (r.status !== 0) die('download failed');
    }
    const got = crypto.createHash('sha256').update(fs.readFileSync(dl)).digest('hex');
    if (got !== want) { fs.unlinkSync(dl); die(`SHA256 mismatch for ${file} (deleted, rerun to retry)`); }
    say(`  ✓ sha256 ok — extracting`);
    if (run('tar', ['-xJf', dl, '-C', BASE], { stdio: 'inherit' }).status !== 0) die('extract failed');
  }
  const bin = path.join(blenderDir, 'blender');
  const libDirs = (root) => [path.join(root, 'usr/lib/x86_64-linux-gnu'), path.join(root, 'lib/x86_64-linux-gnu'), path.join(blenderDir, 'lib')];
  const x64root = path.join(BASE, 'x64root');
  const native = HOST_X64 && fs.existsSync('/lib64/ld-linux-x86-64.so.2');
  const a = archiveFor(OSR, 'amd64');
  const repo = a ? new DebRepo({ archive: a, cacheDir: path.join(BASE, 'idx') }) : null;
  const missingNow = (loader) => {
    const LP = libDirs(x64root).join(':');
    const r = native
      ? run('ldd', [bin], { env: { ...process.env, LD_LIBRARY_PATH: LP } })
      : run(loader, ['--library-path', LP, '--list', bin]);
    const out = `${r.stdout}\n${r.stderr}`;
    const first = out.match(/error while loading shared libraries: (\S+):/);
    return first ? [first[1]] : [...out.matchAll(/^\s*(\S+) => not found/gm)].map((m) => m[1]);
  };
  let loader = null;
  if (!native) {
    if (!repo) die('need the Ubuntu/Debian amd64 archive to build an x86_64 runtime; this distro is not supported by the script');
    say('\n• x86_64 runtime for Blender (user space, SHA256-verified)');
    const find = () => ['usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', 'lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', 'usr/lib64/ld-linux-x86-64.so.2']
      .map((p) => path.join(x64root, p)).find((p) => fs.existsSync(p));
    // everything Blender 5.x is known to need in one go; the loop below catches anything else
    if (!find()) {
      const idx = await repo.packages();
      const base = ['libc6', 'libgcc-s1', 'libstdc++6', 'zlib1g', ...new Set(Object.values(X64_LIBS).map((c) => c.find((p) => idx[p])).filter(Boolean))];
      await repo.fetch([...new Set(base)], x64root, path.join(BASE, 'debs'));
    }
    loader = find();
    if (!loader) die('x86_64 loader not found after unpacking libc6');
  }
  for (let round = 1; round <= 40; round++) {
    const miss = missingNow(loader);
    if (!miss.length) break;
    if (!repo) die(`missing ${miss.join(', ')}`);
    say(`  round ${round}: ${miss.join(', ')}`);
    const pkgs = await repo.resolve(miss, X64_LIBS);
    if (!pkgs.length) die(`cannot resolve ${miss.join(', ')}`);
    await repo.fetch(pkgs, x64root, path.join(BASE, 'debs'));
    if (round === 40) die('too many rounds resolving libraries');
  }
  // launcher. Blender finds its bundled Python/scripts next to /proc/self/exe, so when it runs through an
  // explicit loader the loader must sit inside the Blender folder.
  const LP = libDirs(x64root).join(':');
  let script;
  if (native) {
    script = `#!/bin/sh\nLD_LIBRARY_PATH="${LP}\${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec "${bin}" "$@"\n`;
  } else {
    fs.copyFileSync(loader, path.join(blenderDir, 'ld-linux-x86-64.so.2'));
    fs.chmodSync(path.join(blenderDir, 'ld-linux-x86-64.so.2'), 0o755);
    script = `#!/bin/sh\n# Blender (x86_64) through a user-space loader — see setup_blender.mjs\nexec "${blenderDir}/ld-linux-x86-64.so.2" --library-path "${LP}" --argv0 "${bin}" "${bin}" "$@"\n`;
  }
  launcher = path.join(BASE, 'bin', 'blender');
  fs.mkdirSync(path.dirname(launcher), { recursive: true });
  fs.writeFileSync(launcher, script);
  fs.chmodSync(launcher, 0o755);
}

const probe = run(launcher, ['--background', '--factory-startup', '--python-expr', 'import bpy, sys; print("BPY_OK", bpy.app.version_string); sys.exit(0)']);
const ver = ((probe.stdout || '').match(/BPY_OK (\S+)/) || [])[1];
if (!ver) die(`Blender does not start:\n${(probe.stdout + probe.stderr).split('\n').slice(-15).join('\n')}`);
say(`✓ Blender ${ver} runs (${launcher})`);
if (Number(ver.split('.')[0]) < 5 || (Number(ver.split('.')[0]) === 5 && Number(ver.split('.')[1]) < 1)) say('⚠ the official MCP add-on targets Blender 5.1+');

// ---------- MCP server ----------
const repoDir = path.join(BASE, 'blender_mcp');
if (!fs.existsSync(path.join(repoDir, '.git'))) {
  say('\n• cloning the official Blender Lab MCP repository');
  if (run('git', ['clone', '--quiet', MCP_URL, repoDir], { stdio: 'inherit' }).status !== 0) die('git clone failed');
}
if (run('git', ['-C', repoDir, 'rev-parse', 'HEAD']).stdout.trim() !== MCP_REF) {
  run('git', ['-C', repoDir, 'fetch', '--quiet', 'origin']);
  if (run('git', ['-C', repoDir, 'checkout', '--quiet', MCP_REF]).status !== 0) die(`cannot check out ${MCP_REF}`);
}
say(`✓ blender_mcp at ${MCP_REF.slice(0, 7)}`);
const venv = path.join(BASE, 'venv');
const py = path.join(venv, 'bin', 'python');
const server = path.join(venv, 'bin', 'blender-mcp');
if (!fs.existsSync(server)) {
  say('• creating the MCP server venv');
  if (run(PY3, ['-m', 'venv', '--clear', venv], { stdio: 'inherit' }).status !== 0) die(`${PY3} -m venv failed (install python3-venv)`);
  if (run(py, ['-m', 'pip', 'install', '--quiet', path.join(repoDir, 'mcp')], { stdio: 'inherit' }).status !== 0) die('pip install failed');
}
say(`✓ MCP server ${server}`);

fs.writeFileSync(CONFIG, JSON.stringify({
  version: ver, launcher, blenderDir, repo: repoDir, ref: MCP_REF, python: py, server, port: Number(opt.port || 9876),
  emulation: LINUX ? emu.how : process.platform, savedAt: new Date().toISOString(),
}, null, 2));
say(`✓ configuration saved to ${CONFIG}`);

// ---------- self-test ----------
say('\n• self-test: start Blender with the MCP add-on, call tools, export a GLB, stop');
const st = run(process.execPath, [path.join(here, 'blender_mcp.mjs'), 'selftest'], { stdio: 'inherit' });
if (st.status !== 0) die('self-test failed (see above)');
say('\nReady. Next: node blender_mcp.mjs start · run <script.py> --prelude · stop  (see references/blender-mcp.md)');

#!/usr/bin/env node
/**
 * blender_mcp.mjs — drive Blender through the official Blender Lab MCP server.
 *
 *   node blender_mcp.mjs start [--port 9876] [--blend file.blend]   launch background Blender + official add-on
 *   node blender_mcp.mjs status                                      is it up? Blender version, open file, objects
 *   node blender_mcp.mjs tools                                       list the MCP tools the server exposes
 *   node blender_mcp.mjs run script.py [--prelude] [--log f.jsonl]   execute_blender_code with a file
 *   node blender_mcp.mjs call <tool> ['{"arg": …}']                  any other tool
 *   node blender_mcp.mjs stop                                        stop the Blender started here
 *   node blender_mcp.mjs mcp-json                                    .mcp.json-style entry to use the tools natively in an MCP-capable agent
 *   node blender_mcp.mjs selftest                                    start (if needed) → tools → run → GLB → stop
 *
 * Calls go through the real MCP stack (stdio → blender-mcp → TCP 127.0.0.1:port → add-on in Blender),
 * exactly as a native MCP client would. Needs setup_blender.mjs first.
 * --prelude prepends scripts/blender/prelude.py (reset_scene, mat, smooth, export_glb, stats, …).
 * `run` with a script inside a video project records in its generated.json every file in <project>/assets3d/ that the
 * run created or changed (the .glb, .blend, baked textures): that is how check.mjs and embed_glb.mjs know Blender made
 * them here. Write a script's outputs into assets3d/; files Blender writes through `call` are not recorded.
 */
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { projectOf, recordGenerated, sha256File, filesUnder } from './lib/generated.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = path.join(os.homedir(), '.cache', 'motion-video-deps', 'blender');
const CONFIG = path.join(BASE, 'blender.json');
const die = (m, code = 1) => { console.error('✖ ' + m); process.exit(code); };
if (!fs.existsSync(CONFIG)) die(`Blender MCP is not set up. Run:\n  node ${path.join(here, 'setup_blender.mjs')}`, 3);
const cfg = JSON.parse(fs.readFileSync(CONFIG, 'utf8'));

const argv = process.argv.slice(2);
const cmd = argv[0];
const pos = [];
const opt = {};
for (let i = 1; i < argv.length; i++) {
  if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  else pos.push(argv[i]);
}
const PORT = Number(opt.port || process.env.BLENDER_MCP_PORT || cfg.port || 9876);
const runDir = path.join(BASE, 'run');
const logDir = path.join(BASE, 'logs');
fs.mkdirSync(runDir, { recursive: true });
fs.mkdirSync(logDir, { recursive: true });
const pidFile = path.join(runDir, `blender-${PORT}.pid`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function portOpen(port) {
  return new Promise((res) => {
    const s = net.connect({ host: '127.0.0.1', port }, () => { s.destroy(); res(true); });
    s.on('error', () => res(false));
    s.setTimeout(1000, () => { s.destroy(); res(false); });
  });
}
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };
const readPid = () => (fs.existsSync(pidFile) ? Number(fs.readFileSync(pidFile, 'utf8')) : null);

function client(args) {
  const r = spawnSync(cfg.python, [path.join(here, 'blender', 'mcp_client.py'), '--server', cfg.server, ...args], {
    encoding: 'utf8', maxBuffer: 256 * 1024 * 1024,
    env: { ...process.env, BLENDER_MCP_HOST: '127.0.0.1', BLENDER_MCP_PORT: String(PORT), BLENDER_PATH: cfg.launcher },
  });
  let data = null;
  try { data = JSON.parse(r.stdout); } catch { /* not JSON */ }
  return { ok: r.status === 0, data, stdout: r.stdout, stderr: r.stderr };
}
/** unwrap execute_blender_code's text payload → {status, result, stdout, stderr} */
function payload(data) {
  const text = data && data.content && data.content.find((c) => c.type === 'text');
  if (!text) return null;
  try { return JSON.parse(text.text); } catch { return { raw: text.text }; }
}

async function start() {
  if (await portOpen(PORT)) {
    const pid = readPid();
    console.log(`✓ already serving on 127.0.0.1:${PORT}${pid && alive(pid) ? ` (pid ${pid})` : ' (started elsewhere)'}`);
    return false;
  }
  const blend = typeof opt.blend === 'string' ? [path.resolve(opt.blend)] : [];
  const log = path.join(logDir, `blender-${PORT}.log`);
  const fd = fs.openSync(log, 'a');
  const child = spawn(cfg.launcher, ['--background', ...blend, '--factory-startup', '--python', path.join(here, 'blender', 'bridge.py'), '--', '--port', String(PORT)], {
    detached: true, stdio: ['ignore', fd, fd], env: { ...process.env, BLENDER_MCP_REPO: cfg.repo },
  });
  child.unref();
  fs.writeFileSync(pidFile, String(child.pid));
  const t0 = Date.now();
  while (Date.now() - t0 < 180000) {
    if (await portOpen(PORT)) {
      console.log(`✓ Blender ${cfg.version} serving the official MCP add-on on 127.0.0.1:${PORT} (pid ${child.pid}, ${((Date.now() - t0) / 1000).toFixed(1)} s)\n  log: ${log}`);
      return true;
    }
    if (!alive(child.pid)) break;
    await sleep(300);
  }
  die(`Blender did not start serving — last log lines:\n${fs.readFileSync(log, 'utf8').split('\n').slice(-20).join('\n')}`);
}

async function stop() {
  const pid = readPid();
  if (!pid || !alive(pid)) {
    if (fs.existsSync(pidFile)) fs.unlinkSync(pidFile);
    console.log(await portOpen(PORT) ? `⚠ port ${PORT} is served by a Blender not started here — leaving it alone` : '✓ not running');
    return;
  }
  process.kill(pid, 'SIGTERM');
  for (let i = 0; i < 40 && alive(pid); i++) await sleep(250);
  if (alive(pid)) process.kill(pid, 'SIGKILL');
  fs.unlinkSync(pidFile);
  console.log(`✓ stopped Blender (pid ${pid})`);
}

function runScript(file, { prelude = false, log } = {}) {
  let code = fs.readFileSync(file, 'utf8');
  if (prelude) code = fs.readFileSync(path.join(here, 'blender', 'prelude.py'), 'utf8') + '\n\n# ---- script ----\n' + code;
  const tmp = path.join(runDir, `run-${process.pid}.py`);
  fs.writeFileSync(tmp, code);
  const r = client(['--tool', 'execute_blender_code', '--code-file', tmp, '--log', log || path.join(logDir, 'mcp-calls.jsonl')]);
  fs.unlinkSync(tmp);
  return { ...r, body: payload(r.data) };
}
function report(body, r) {
  if (!body) { console.log(r.stdout || r.stderr); return; }
  if (body.status === 'error') {
    console.log('✖ Blender raised an error:\n' + (body.message || '').split('\n').slice(-12).join('\n'));
    return;
  }
  if (body.stdout && body.stdout.trim()) console.log('stdout:\n' + body.stdout.trim().split('\n').slice(-15).map((l) => '  ' + l).join('\n'));
  console.log('result: ' + JSON.stringify(body.result, null, 2));
}

switch (cmd) {
  case 'start': await start(); break;
  case 'stop': await stop(); break;
  case 'status': {
    if (!(await portOpen(PORT))) { console.log(`✗ nothing listening on 127.0.0.1:${PORT} — node blender_mcp.mjs start`); process.exit(1); }
    const tmp = path.join(runDir, 'status.py');
    fs.writeFileSync(tmp, 'import bpy\nresult = {"blender": bpy.app.version_string, "file": bpy.data.filepath or "(unsaved)", "objects": [o.name for o in bpy.data.objects][:30]}\n');
    const r = runScript(tmp);
    report(r.body, r);
    process.exit(r.ok ? 0 : 1);
  }
  case 'tools': {
    const r = client(['--list']);
    if (!r.ok || !r.data) die(r.stderr || 'list_tools failed');
    for (const t of r.data.tools || []) console.log(`- ${t.name}: ${(t.description || '').trim().split('\n')[0]}`);
    break;
  }
  case 'run': {
    if (!pos[0]) die('usage: blender_mcp.mjs run script.py [--prelude] [--log file.jsonl]');
    // what assets3d/ holds before the run: afterwards every file that is new or different was written by this run
    const root = projectOf(pos[0]);
    const a3d = root && path.join(root, 'assets3d');
    const before = new Map(a3d ? filesUnder(a3d).map((f) => [f, sha256File(f)]) : []);
    const r = runScript(pos[0], { prelude: !!opt.prelude, log: typeof opt.log === 'string' ? opt.log : undefined });
    report(r.body, r);
    if (a3d) {
      const made = filesUnder(a3d).filter((f) => before.get(f) !== sha256File(f));
      const n = recordGenerated(made, 'blender_mcp.mjs run');
      if (n) console.log(`recorded in generated.json: ${made.map((f) => path.relative(root, f)).join(', ')}`);
    }
    process.exit(r.ok && (!r.body || r.body.status !== 'error') ? 0 : 1);
  }
  case 'call': {
    if (!pos[0]) die("usage: blender_mcp.mjs call <tool> '{\"arg\": …}'");
    const r = client(['--tool', pos[0], '--args', pos[1] || '{}', '--log', path.join(logDir, 'mcp-calls.jsonl')]);
    const body = payload(r.data);
    console.log(JSON.stringify(body || r.data, null, 2));
    process.exit(r.ok ? 0 : 1);
  }
  case 'mcp-json': {
    console.log(JSON.stringify({ mcpServers: { blender: { command: cfg.server, args: [], env: { BLENDER_MCP_HOST: '127.0.0.1', BLENDER_MCP_PORT: String(PORT), BLENDER_PATH: cfg.launcher } } } }, null, 2));
    break;
  }
  case 'selftest': {
    const started = await start();
    const tools = client(['--list']);
    const n = (tools.data && tools.data.tools || []).length;
    console.log(`✓ MCP tools listed: ${n}`);
    const tmp = path.join(runDir, 'selftest.py');
    const glb = path.join(runDir, 'selftest.glb');
    fs.writeFileSync(tmp, `reset_scene()\nbpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0.5))\nob = bpy.context.object\nob.name = "Ball"\nassign(ob, mat("Coral", "#F2604C", roughness=0.4))\nsmooth(ob)\nresult = {"stats": stats(), "glb": export_glb(${JSON.stringify(glb)})}\n`);
    const r = runScript(tmp, { prelude: true });
    report(r.body, r);
    if (started) await stop();
    const ok = n > 0 && r.body && r.body.status === 'ok' && fs.existsSync(glb);
    console.log(ok ? `✓ self-test passed (GLB ${fs.statSync(glb).size} bytes)` : '✖ self-test failed');
    process.exit(ok ? 0 : 1);
  }
  default:
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 18).join('\n'));
    process.exit(cmd ? 2 : 0);
}

// createMovie PC 렌더 워커
// NAS(서버)에 렌더링할 영상이 있는지 몇 초마다 묻고, 있으면 파일을 받아 이 PC에서 HyperFrames로 렌더링한 뒤
// 완성된 MP4를 서버로 올려 준다. PC -> 서버 방향으로만 연결하므로 공유기 포트를 열 필요가 없다.
// 필요: Node.js 22+, FFmpeg.  외부 패키지 없음.
//   설정: node worker.mjs --setup      실행: node worker.mjs
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, openAsBlob } from 'node:fs';
import { hostname, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONFIG = join(HERE, 'config.json');
const WORK = join(tmpdir(), 'createMovie-worker');
const WIN = process.platform === 'win32';
const POLL = 5000;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const now = () => new Date().toTimeString().slice(0, 8);
const log = (...a) => console.log(`[${now()}]`, ...a);

function loadConfig() {
  if (!existsSync(CONFIG)) return null;
  const c = JSON.parse(readFileSync(CONFIG, 'utf8'));
  return { name: hostname(), ...c, server: String(c.server || '').replace(/\/+$/, '') };
}

function api(cfg, path, opts = {}) {
  return fetch(cfg.server + path, {
    ...opts,
    headers: { Authorization: 'Bearer ' + cfg.token, 'X-Worker-Name': encodeURIComponent(cfg.name), ...(opts.headers || {}) },
    signal: AbortSignal.timeout(opts.timeout || 30000),
  });
}

const postJson = (cfg, path, body) =>
  api(cfg, path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then(r => r.json()).catch(() => ({}));

function hasCmd(cmd, args = ['-version']) {
  try { execFileSync(cmd, args, { stdio: 'ignore', shell: WIN }); return true; } catch { return false; }
}

// ---------- 설정 ----------
async function setup() {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const old = loadConfig() || {};
  const preset = existsSync(join(HERE, 'server.txt')) ? readFileSync(join(HERE, 'server.txt'), 'utf8').trim() : '';
  console.log('\n=== createMovie 렌더 워커 설정 ===\n');
  let server = old.server || preset;
  const s = (await rl.question(`서버(NAS) 주소${server ? ` [Enter = ${server}]` : ' (예: http://192.168.0.10:5000)'}: `)).trim();
  if (s) server = s;
  if (!/^https?:\/\//.test(server)) server = 'http://' + server;
  let token = old.token || '';
  const t = (await rl.question(`워커 토큰(서버의 WORKER_TOKEN 값)${token ? ' [Enter = 기존 값 유지]' : ''}: `)).trim();
  if (t) token = t;
  rl.close();
  const cfg = { server: server.replace(/\/+$/, ''), token, name: old.name || hostname() };

  process.stdout.write('\n서버 연결 확인 중… ');
  const r = await api(cfg, '/api/worker/ping').catch(e => ({ ok: false, status: e.message }));
  if (!r.ok) {
    console.log(r.status === 401 ? '실패: 토큰이 맞지 않습니다.' : r.status === 404 ? '실패: 서버에 WORKER_TOKEN이 설정되어 있지 않습니다.' : `실패: 서버에 연결할 수 없습니다 (${r.status}). 주소와 NAS 상태를 확인해 주세요.`);
    process.exit(1);
  }
  console.log('성공');
  writeFileSync(CONFIG, JSON.stringify(cfg, null, 2));

  if (!hasCmd('ffmpeg')) console.log('주의: FFmpeg를 찾지 못했습니다. 설치 후 다시 실행해 주세요.');
  console.log('렌더링 엔진(HyperFrames)과 브라우저를 미리 내려받는 중… (처음 한 번, 몇 분 걸릴 수 있어요)');
  try { execFileSync('npx', ['-y', 'hyperframes', 'browser', 'ensure'], { stdio: 'inherit', shell: WIN }); } catch { /* 첫 렌더 때 다시 받는다 */ }
  console.log('\n설정 완료. 이제 워커를 실행하면 됩니다.');
}

// ---------- 렌더 ----------
function killTree(pr) {
  if (WIN) { try { execFileSync('taskkill', ['/pid', String(pr.pid), '/T', '/F'], { stdio: 'ignore' }); } catch {} }
  else pr.kill('SIGTERM');
}

async function renderJob(cfg, { job, rev, files, outputs }) {
  const outs = outputs && outputs.length ? outputs : [{ html: 'index.html', out: 'output.mp4' }];   // 가로+세로면 2개
  const dir = join(WORK, job);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(join(dir, 'assets'), { recursive: true });
  log(`작업 ${job}: 파일 ${files.length}개 받는 중`);
  for (const f of files) {
    const r = await fetch(`${cfg.server}/jobs/${job}/${f.split('/').map(encodeURIComponent).join('/')}`, { signal: AbortSignal.timeout(10 * 60000) });
    if (!r.ok) throw new Error(`파일 받기 실패: ${f} (${r.status})`);
    mkdirSync(dirname(join(dir, f)), { recursive: true });   // assets/fonts/ 같은 하위 폴더
    writeFileSync(join(dir, f), Buffer.from(await r.arrayBuffer()));
  }

  let pct = 0, tail = [], cancelled = false, pr = null, last = -1;
  const timer = setInterval(async () => {   // 진행률 보고(겸 생존 신호)
    if (pct !== last) { process.stdout.write(`\r  진행 ${pct}%   `); last = pct; }
    const r = await postJson(cfg, `/api/worker/progress/${job}?rev=${rev}`, { pct });
    if (r.cancel && !cancelled) { cancelled = true; log('\n사용자가 다시 렌더를 요청해 이 작업은 취소합니다.'); pr && killTree(pr); }
  }, 3000);
  try {
    for (const [k, o] of outs.entries()) {
      log(`작업 ${job}: 렌더링 시작 (${k + 1}/${outs.length}, ${o.html})`);
      pr = spawn('npx', ['-y', 'hyperframes', 'render', '-c', o.html, '-o', o.out], { cwd: dir, shell: WIN });
      let buf = '';
      const onData = d => {
        buf += d.toString('utf8');
        const lines = buf.split(/\r?\n|\r/); buf = lines.pop();
        for (const line of lines) {
          const m = line.match(/"pct":(\d+)/);
          if (m) pct = Math.min(99, Math.floor(((k + +m[1] / 100) / outs.length) * 100));
          if (line.trim()) tail = [...tail, line.trimEnd()].slice(-8);
        }
      };
      pr.stdout.on('data', onData); pr.stderr.on('data', onData);
      const code = await new Promise(res => pr.on('close', c => res(c)));
      if (cancelled) return;
      if (code !== 0 || !existsSync(join(dir, o.out))) {
        log(`\n작업 ${job}: 렌더링 실패 (종료 코드 ${code})`);
        await postJson(cfg, `/api/worker/fail/${job}?rev=${rev}`, { log: tail.join('\n') || `종료 코드 ${code}` });
        return;
      }
    }
  } finally { clearInterval(timer); process.stdout.write('\n'); }

  for (const o of outs) {
    log(`작업 ${job}: 완성 영상 올리는 중 (${o.out})`);
    const r = await api(cfg, `/api/worker/upload/${job}?rev=${rev}&out=${encodeURIComponent(o.out)}`, {
      method: 'POST', headers: { 'Content-Type': 'video/mp4' }, body: await openAsBlob(join(dir, o.out)), timeout: 30 * 60000,
    });
    if (!r.ok) { log(`작업 ${job}: 업로드 실패 (${r.status})`); return; }
  }
  const d = await postJson(cfg, `/api/worker/done/${job}?rev=${rev}`, {});
  log(d.ok ? `작업 ${job}: 완료!` : `작업 ${job}: 마무리 실패`);
  rmSync(dir, { recursive: true, force: true });
}

// ---------- 메인 루프 ----------
async function main() {
  if (process.argv.includes('--setup')) return setup();
  const cfg = loadConfig();
  if (!cfg || !cfg.token) { console.log('먼저 설정이 필요합니다: node worker.mjs --setup'); process.exit(1); }
  if (!hasCmd('ffmpeg')) console.log('주의: FFmpeg를 찾지 못했습니다. 렌더링이 실패할 수 있어요.');
  log(`createMovie 렌더 워커 시작 — 서버 ${cfg.server}, 이름 ${cfg.name}`);
  log('이 창을 켜 두면 NAS에서 요청한 영상을 이 PC가 만듭니다. (끄려면 창을 닫거나 Ctrl+C)');
  let offline = false;
  for (;;) {
    try {
      const r = await api(cfg, '/api/worker/claim', { method: 'POST' });
      if (r.status === 401) { log('토큰이 맞지 않습니다. node worker.mjs --setup 으로 다시 설정해 주세요.'); process.exit(1); }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      if (offline) { log('서버에 다시 연결됐습니다.'); offline = false; }
      const j = await r.json();
      if (j.job) {
        try { await renderJob(cfg, j); }
        catch (e) {
          log(`작업 ${j.job}: 오류 — ${e.message}`);
          await postJson(cfg, `/api/worker/fail/${j.job}?rev=${j.rev}`, { log: 'PC 워커 오류: ' + e.message });
        }
        continue;
      }
    } catch (e) {
      if (!offline) { log(`서버에 연결할 수 없습니다(${e.message}). 계속 다시 시도합니다…`); offline = true; }
      await sleep(POLL * 2); continue;
    }
    await sleep(POLL);
  }
}

main();

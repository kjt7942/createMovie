// 미리보기 검증: /api/preview로 만든 preview.html을 헤드리스 Chrome에서 열어 장면 표시/탐색/재생을 확인한다.
// 실행: node test_preview.mjs <job>  (서버가 localhost:5000에서 실행 중이어야 함)
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);
const puppeteer = require(process.env.LOCALAPPDATA + '/npm-cache/_npx/702923228c2ce1e6/node_modules/puppeteer-core');
const CHROME = process.env.USERPROFILE + '/.cache/hyperframes/chrome/chrome-headless-shell/win64-152.0.7977.30/chrome-headless-shell-win64/chrome-headless-shell.exe';
const job = process.argv[2], base = 'http://localhost:5000';
const plan = JSON.parse(fs.readFileSync(`jobs/${job}/plan.json`, 'utf8'));
const r = await (await fetch(base + '/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job, plan, length: 20 }) })).json();
if (!r.url) throw new Error(JSON.stringify(r));
const br = await puppeteer.launch({ executablePath: CHROME, args: ['--autoplay-policy=no-user-gesture-required'] });
const pg = await br.newPage(); await pg.setViewport({ width: 1920, height: 1080 });
const errs = []; pg.on('pageerror', e => errs.push(e.message));
await pg.goto(base + r.url, { waitUntil: 'networkidle0' });
const vis = t => pg.evaluate(t => { window.__preview.seek(t); return [...document.querySelectorAll('#root > [data-start]')].filter(c => c.tagName !== 'AUDIO' && c.style.visibility === 'visible').map(c => c.id); }, t);
const cases = [[2, ['intro']], [4.0, ['intro', 's1']], [9, ['s2']], [18.5, ['outro']]];
for (const [t, want] of cases) {
  const got = await vis(t);
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`t=${t} 보이는 장면 ${got} (기대 ${want})`);
  await vis(t); await pg.screenshot({ path: `jobs/${job}/pv_${t}.png` });
}
await pg.evaluate(() => { window.__preview.seek(0); window.__preview.play(); });
await new Promise(r => setTimeout(r, 1500));
const t = await pg.evaluate(() => window.__preview.time);
if (!(t > 1.0 && t < 2.5)) throw new Error('재생 시간 진행 이상: ' + t);
if (errs.length) throw new Error('페이지 오류: ' + errs.join(' | '));
console.log('OK 장면 표시/탐색/재생 정상, 1.5초 재생 후 time=' + t.toFixed(2));
await br.close();

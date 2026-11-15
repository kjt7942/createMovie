#!/usr/bin/env node
/**
 * test_hover_ui.mjs — checks the player's hover chrome (progress bar along the bottom + shortcut list on the right) in a real
 * browser, with no pictures: hidden until the mouse moves, shown on movement, hidden again 2.5 s after the last movement
 * while playing, a click on the bar seeks, and never present in a render (?render).
 *
 *   node test_hover_ui.mjs <projectDir>
 */
import path from 'node:path';
import { launch, openPage } from './lib/browser.mjs';

const dir = path.resolve(process.argv[2] || '.');
const browser = await launch();
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? '✓ ' : '✖ ') + msg); if (!cond) fails++; };
const vis = (page, sel) => page.evaluate((s) => { const e = document.querySelector(s), c = e && getComputedStyle(e); return c ? c.visibility + '/' + c.display : 'none'; }, sel);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const page = await openPage(browser, dir, { query: '' });
const box = page.viewportSize();
ok((await vis(page, '.vp-hud-bar')).startsWith('hidden'), 'hidden before the mouse moves');
await page.mouse.move(box.width / 2, box.height / 2);
await page.mouse.move(box.width / 2 + 5, box.height / 2 + 5);
await wait(400);
ok((await vis(page, '.vp-hud-bar')).startsWith('visible') && (await vis(page, '.vp-hud-help')).startsWith('visible'), 'bar and shortcut list shown when the mouse moves');
ok((await page.locator('.vp-hud-row').count()) >= 10, 'shortcut list has its rows: ' + (await page.locator('.vp-hud-row').count()));
ok(/^\d+:\d\d \/ \d+:\d\d$/.test(await page.locator('.vp-hud-time').textContent()), 'time label: ' + (await page.locator('.vp-hud-time').textContent()));

// while playing, 2.5 s without movement hides them (the class stands in for playback, which an automated browser never starts)
await page.evaluate(() => document.body.classList.add('vp-playing'));
await page.mouse.move(box.width / 2 + 10, box.height / 2);
await wait(3000);
ok((await vis(page, '.vp-hud-bar')).startsWith('hidden') && (await vis(page, '.vp-hud-help')).startsWith('hidden'), 'hidden again 2.5 s after the last movement while playing');
await page.mouse.move(box.width / 2 - 10, box.height / 2);
await wait(400);
ok((await vis(page, '.vp-hud-bar')).startsWith('visible'), 'shown again on the next movement');

// a click on the bar seeks to that point
const tr = await page.locator('.vp-hud-track').boundingBox();
await page.mouse.click(tr.x + tr.width * 0.5, tr.y + tr.height / 2);
const [tm, dur] = await page.evaluate(() => [window.__video.time, window.__video.duration]);
ok(Math.abs(tm - dur / 2) < dur * 0.02 + 0.5, `click on the bar seeks (${tm.toFixed(1)} of ${dur.toFixed(1)} s)`);
await page.evaluate(() => document.body.classList.remove('vp-playing'));
await wait(3000);
ok((await vis(page, '.vp-hud-bar')).startsWith('visible'), 'stays while paused with the mouse in the window');
await page.close();

// a click on the picture toggles play / pause; a click on the progress bar only seeks
const c = await openPage(browser, dir, { query: '' });
const playingNow = () => c.evaluate(() => document.body.classList.contains('vp-playing'));
await c.mouse.move(box.width * 0.3, box.height * 0.4); await wait(300);
await c.mouse.click(box.width * 0.3, box.height * 0.4); await wait(300);
ok(await playingNow(), 'click on the picture starts playback');
const mark = () => c.evaluate(() => { const e = document.querySelector('.vp-hud-center'), s = getComputedStyle(e), b = getComputedStyle(e, '::before'); return [s.visibility, b.borderLeftWidth]; });
let [mv, mw] = await mark();
ok(mv === 'visible' && mw === '0px', 'pause mark in the middle while playing and hovering');
await c.mouse.click(box.width * 0.3, box.height * 0.4); await wait(300);
ok(!(await playingNow()), 'second click pauses');
[mv, mw] = await mark();
ok(mv === 'visible' && mw === '32px', 'play mark in the middle while paused');
const t2 = await c.locator('.vp-hud-track').boundingBox();
await c.mouse.move(t2.x + 10, t2.y); await wait(300);
await c.mouse.click(t2.x + t2.width * 0.25, t2.y + t2.height / 2); await wait(300);
ok(!(await playingNow()), 'click on the progress bar does not toggle playback');
await c.close();

const r = await openPage(browser, dir, { query: 'render' });
await r.mouse.move(40, 40); await r.mouse.move(60, 60);
ok((await vis(r, '.vp-hud-bar')).endsWith('none') && (await vis(r, '.vp-hud-help')).endsWith('none'), 'never present in a render (?render)');
await r.close();
await browser.close();
console.log(fails ? `${fails} check(s) failed` : 'hover chrome OK');
process.exit(fails ? 1 : 0);

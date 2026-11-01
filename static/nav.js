// 두 서비스 공통 상단 막대: 메뉴와 대기열 하나. body 맨 앞에서 불러온다.
(() => {
  const path = location.pathname, on = p => (p === '/' ? path === '/' : path.startsWith(p)) ? 'on' : '';
  const bar = document.createElement('nav');
  bar.id = 'gnav'; bar.setAttribute('aria-label', '서비스');
  bar.innerHTML = `<a class="logo" href="/"><i></i>createMovie</a><a class="${on('/')}" href="/">홍보 영상(HyperFrames)</a><a class="${on('/h3')}" href="/h3/">AI 영상 생성(Wan2GP)</a><a class="${on('/setup')}" href="/setup">설치·점검</a>
    <span id="gg" title="그래픽카드 온도, 전력, 메모리, 팬"></span><button id="gq" aria-expanded="false" aria-controls="gp">대기열 확인 중</button><div id="gp" hidden></div>`;
  document.body.prepend(bar);
  const setHeight = () => document.documentElement.style.setProperty('--nav-h', window.innerWidth <= 720 ? '0px' : `${bar.offsetHeight}px`);  // 화면별 고정 머리글이 이 막대 아래에 붙게
  setHeight(); addEventListener('resize', setHeight);
  const btn = bar.querySelector('#gq'), panel = bar.querySelector('#gp'), gpu = bar.querySelector('#gg');
  const val = (v, f) => (v == null ? '-' : f(v));
  function drawGpu(g, age) {  // 샘플이 오래됐으면 마지막 값을 믿지 않는다. 기록이 아예 없으면 GPU가 없는 환경이라 비운다.
    if (!g) { gpu.textContent = ''; gpu.className = ''; return; }
    if (age == null || age > 20) { gpu.textContent = 'GPU 응답 없음'; gpu.className = 'hot'; return; }
    gpu.className = g.temp >= 88 ? 'hot' : '';
    gpu.textContent = `GPU ${val(g.temp, Math.round)}°C · ${val(g.power, Math.round)}W/${val(g.limit, Math.round)}W · ${val(g.mem, v => (v / 1024).toFixed(1))}GB · 팬 ${val(g.fan, Math.round)}%`;
  }
  const KIND = { h3: 'AI 영상', promo: '홍보 영상' };
  const link = x => (x.kind === 'h3' ? `/h3/?open=${x.id}` : `/?open=${x.id}`);
  const mins = s => { const m = Math.round((s || 0) / 60); return m >= 60 ? `약 ${Math.floor(m / 60)}시간 ${m % 60}분` : `약 ${Math.max(1, m)}분`; };
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text) e.textContent = text; if (cls) e.className = cls; return e; };
  const act = async (path, body) => {
    await fetch('/h3/api/queue/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).catch(() => {});
    refresh(true);
  };
  let key = '', fillEl = null, stageEl = null, stopBtn = null, stopTimer = 0;
  const now = s => `지금 작업 · ${KIND[s.current.kind] || ''} · ${s.stage || ''}`;
  const pct = s => `${Math.round((s.fraction || 0) * 100)}%`;
  function draw(s) {
    fillEl = stageEl = stopBtn = null;
    panel.replaceChildren();
    if (s.paused) {
      panel.append(el('div', s.pause_reason || '대기열이 멈춰 있습니다.', 'alarm'));
      if (s.local) { const b = el('button', '재개'); b.onclick = () => act('resume'); b.style.marginBottom = '8px'; panel.append(b); }
    }
    if (s.current) {
      const row = el('div', '', 'i'), text = el('span');
      const a = el('a', s.current.title); a.href = link(s.current);
      stageEl = el('small', now(s)); text.append(a, stageEl);
      const b = el('div', '', 'bar'), fill = fillEl = el('div'); fill.style.width = pct(s); b.append(fill); text.append(b);
      row.append(text);
      if (s.local) { const stop = stopBtn = el('button', stopTimer ? '한 번 더 누르면 멈춤' : '멈추기'); stop.title = '지금 작업을 멈추고 대기열도 멈춥니다';
        stop.onclick = () => {
          if (!stopTimer) { stop.textContent = '한 번 더 누르면 멈춤'; stopTimer = setTimeout(() => { stopTimer = 0; if (stopBtn) stopBtn.textContent = '멈추기'; }, 4000); return; }
          clearTimeout(stopTimer); stopTimer = 0; stop.textContent = '멈추기';
          fetch('/h3/api/stop', { method: 'POST' }).then(() => refresh(true));
        };
        row.append(stop); }
      panel.append(row);
    }
    s.queue.forEach((x, i) => {
      const row = el('div', '', 'i'), text = el('span');
      const a = el('a', `${i + 1}. ${x.title}`); a.href = link(x);
      text.append(a, el('small', `${KIND[x.kind] || ''} · ${mins(x.estimate)}`));
      row.append(text);
      if (s.local) {
        const mv = (text, label, step, off) => { const b = el('button', text, 'mv'); b.setAttribute('aria-label', `${x.title} ${label}`); b.disabled = off; b.onclick = () => act('move', { kind: x.kind, id: x.id, step }); return b; };
        const b = el('button', '빼기'); b.onclick = () => act('remove', { kind: x.kind, id: x.id });
        row.append(mv('▲', '앞으로', -1, i === 0), mv('▼', '뒤로', 1, i === s.queue.length - 1), b);
      }
      panel.append(row);
    });
    if (!s.current && !s.queue.length) panel.append(el('div', '진행 중이거나 기다리는 작업이 없습니다.'));
  }
  async function refresh(force) {
    if (document.hidden && !force) return;
    let s;
    try { s = await fetch('/api/queue').then(r => r.json()); } catch { btn.textContent = '서버 연결 끊김'; btn.className = 'alarm'; return; }
    drawGpu(s.gpu, s.gpu_age); setHeight();
    delete s.gpu; delete s.gpu_age;  // 값이 바뀔 때마다 열린 목록을 다시 그리지 않게
    btn.className = s.paused ? 'alarm' : '';
    btn.textContent = s.paused ? `대기열 멈춤 · ${s.queue.length}개` : s.current ? `진행 중: ${s.current.title}${s.queue.length ? ` · 대기 ${s.queue.length}개` : ''}` : s.queue.length ? `대기 ${s.queue.length}개` : '대기열 비어 있음';
    const k = JSON.stringify({ ...s, fraction: 0, stage: '' });  // 진행률·단계는 제자리에서만 갱신
    if (force || k !== key) { key = k; if (!panel.hidden) draw(s); }
    else if (s.current) { if (fillEl) fillEl.style.width = pct(s); if (stageEl) stageEl.textContent = now(s); }
    panel._s = s;
  }
  const setOpen = o => { panel.hidden = !o; btn.setAttribute('aria-expanded', String(o)); };
  btn.onclick = () => { setOpen(panel.hidden); if (!panel.hidden && panel._s) draw(panel._s); };
  addEventListener('keydown', e => { if (e.key === 'Escape' && !panel.hidden) { setOpen(false); btn.focus(); } });
  document.addEventListener('click', e => { if (!panel.hidden && !bar.contains(e.target)) setOpen(false); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  refresh(); setInterval(refresh, 3000);
})();

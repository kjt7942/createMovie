// 두 서비스 공통 상단 막대: 메뉴와 대기열 하나. body 맨 앞에서 불러온다.
(() => {
  const css = `
  #gnav { position:relative; z-index:50; display:flex; align-items:center; gap:4px; flex-wrap:wrap; padding:6px 16px; background:#1b2233; color:#e8ebf2; font:14px/1.4 "Malgun Gothic",system-ui,sans-serif; }
  #gnav a { color:#c9d0de; text-decoration:none; padding:5px 10px; border-radius:6px; }
  #gnav a:hover { background:#2b3448; }
  #gnav a.on { color:#fff; background:#3a4560; font-weight:600; }
  #gq { margin-left:auto; font:inherit; color:#e8ebf2; background:#2b3448; border:1px solid #47516a; border-radius:6px; padding:5px 10px; cursor:pointer; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  #gq.warn { background:#7a4a00; border-color:#b67a1c; }
  #gp { position:absolute; right:16px; top:100%; width:min(420px, calc(100vw - 32px)); max-height:70vh; overflow:auto; background:#232b3d; border:1px solid #47516a; border-radius:8px; padding:12px; box-shadow:0 8px 24px rgba(0,0,0,.35); }
  #gp .i { display:flex; align-items:center; gap:8px; padding:6px 0; border-top:1px solid #38425a; }
  #gp .i span { flex:1; min-width:0; overflow-wrap:anywhere; }
  #gp small { display:block; color:#a7b0c2; }
  #gp button { font:inherit; font-size:13px; color:#e8ebf2; background:#3a4560; border:1px solid #56617c; border-radius:6px; padding:4px 10px; cursor:pointer; flex:none; }
  #gp .warn { color:#ffc56b; margin-bottom:8px; overflow-wrap:anywhere; }
  #gp .bar { height:6px; background:#38425a; border-radius:3px; overflow:hidden; margin:4px 0; }
  #gp .bar div { height:100%; background:#7f9cff; }`;
  const style = document.createElement('style'); style.textContent = css; document.head.append(style);
  const path = location.pathname, on = p => (p === '/' ? path === '/' : path.startsWith(p)) ? 'on' : '';
  const bar = document.createElement('nav');
  bar.id = 'gnav'; bar.setAttribute('aria-label', '서비스');
  bar.innerHTML = `<a class="${on('/')}" href="/">홍보 영상</a><a class="${on('/h3')}" href="/h3/">AI 영상 생성</a><a class="${on('/setup')}" href="/setup">설치·점검</a>
    <button id="gq" aria-expanded="false" aria-controls="gp">대기열 확인 중</button><div id="gp" hidden></div>`;
  document.body.prepend(bar);
  const btn = bar.querySelector('#gq'), panel = bar.querySelector('#gp');
  const KIND = { h3: 'AI 영상', promo: '홍보 영상' };
  const link = x => (x.kind === 'h3' ? `/h3/?open=${x.id}` : `/?open=${x.id}`);
  const mins = s => { const m = Math.round((s || 0) / 60); return m >= 60 ? `약 ${Math.floor(m / 60)}시간 ${m % 60}분` : `약 ${Math.max(1, m)}분`; };
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text) e.textContent = text; if (cls) e.className = cls; return e; };
  const act = async (path, body) => {
    await fetch('/h3/api/queue/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).catch(() => {});
    refresh(true);
  };
  let key = '';
  function draw(s) {
    panel.replaceChildren();
    if (s.paused) {
      panel.append(el('div', s.pause_reason || '대기열이 멈춰 있습니다.', 'warn'));
      if (s.local) { const b = el('button', '재개'); b.onclick = () => act('resume'); b.style.marginBottom = '8px'; panel.append(b); }
    }
    if (s.current) {
      const row = el('div', '', 'i'), text = el('span');
      const a = el('a', s.current.title); a.href = link(s.current); a.style.padding = 0;
      text.append(a, el('small', `지금 작업 · ${KIND[s.current.kind] || ''} · ${s.stage || ''}`));
      const b = el('div', '', 'bar'), fill = el('div'); fill.style.width = `${Math.round((s.fraction || 0) * 100)}%`; b.append(fill); text.append(b);
      row.append(text);
      if (s.local) { const stop = el('button', '멈추기'); stop.title = '지금 작업을 멈추고 대기열도 멈춥니다'; stop.onclick = () => fetch('/h3/api/stop', { method: 'POST' }).then(() => refresh(true)); row.append(stop); }
      panel.append(row);
    }
    s.queue.forEach((x, i) => {
      const row = el('div', '', 'i'), text = el('span');
      const a = el('a', `${i + 1}. ${x.title}`); a.href = link(x); a.style.padding = 0;
      text.append(a, el('small', `${KIND[x.kind] || ''} · ${mins(x.estimate)}`));
      row.append(text);
      if (s.local) { const b = el('button', '빼기'); b.onclick = () => act('remove', { kind: x.kind, id: x.id }); row.append(b); }
      panel.append(row);
    });
    if (!s.current && !s.queue.length) panel.append(el('div', '진행 중이거나 기다리는 작업이 없습니다.'));
  }
  async function refresh(force) {
    let s;
    try { s = await fetch('/api/queue').then(r => r.json()); } catch { btn.textContent = '서버 연결 끊김'; btn.className = 'warn'; return; }
    btn.className = s.paused ? 'warn' : '';
    btn.textContent = s.paused ? `대기열 멈춤 · ${s.queue.length}개` : s.current ? `진행 중: ${s.current.title}${s.queue.length ? ` · 대기 ${s.queue.length}개` : ''}` : s.queue.length ? `대기 ${s.queue.length}개` : '대기열 비어 있음';
    const k = JSON.stringify(s);
    if (force || k !== key) { key = k; if (!panel.hidden) draw(s); }
    panel._s = s;
  }
  btn.onclick = () => { panel.hidden = !panel.hidden; btn.setAttribute('aria-expanded', String(!panel.hidden)); if (!panel.hidden && panel._s) draw(panel._s); };
  refresh(); setInterval(refresh, 3000);
})();

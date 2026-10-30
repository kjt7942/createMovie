"""영상 HTML(HyperFrames 컴포지션) 조립: 연출 스타일 × 장면 유형 × 장면 변형.
- 스타일(STYLES): 글꼴·색·글자 등장·사진 움직임·전환 묶음·속도를 한 벌로 묶은 것
- 장면 유형(SCENE_TYPES): title / collage / stat / quote / list
- 변형(v): 같은 유형의 다른 배치 2가지(0, 1)
글꼴은 fonts/ 의 원본에서 영상에 쓰인 글자만 잘라 assets/fonts/ 에 넣는다(렌더 PC에 글꼴 설치 불필요)."""
import hashlib, html, json, os, re

import beats

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, 'fonts')

TRANSITIONS = ['panel', 'slide', 'fade', 'zoom', 'blur', 'wipe', 'wipe-up', 'split', 'circle', 'diagonal', 'whip', 'flash', 'spin']
SCENE_TYPES = ['title', 'collage', 'stat', 'quote', 'list']

SANS = '"Noto Sans CJK KR", "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif'
SERIF = '"Noto Serif CJK KR", "Noto Serif KR", "Batang", serif'
STYLES = {
    'classic': {'label': '클래식', 'colors': ['#ff6b4a', '#ffc93c', '#3ddc97'], 'speed': 1.0,
                'head': ('NotoSansKR', SANS), 'body': ('NotoSansKR', SANS),
                'mix': ['panel', 'wipe', 'zoom', 'circle', 'whip', 'slide', 'split', 'flash', 'fade', 'diagonal', 'spin', 'wipe-up', 'blur']},
    'pop': {'label': '팝', 'colors': ['#ff5fa2', '#ffd23f', '#2ec4b6'], 'speed': 0.85,
            'head': ('Jua', SANS), 'body': ('NotoSansKR', SANS),
            'mix': ['spin', 'circle', 'panel', 'zoom', 'flash', 'wipe-up']},
    'cinematic': {'label': '시네마틱', 'colors': ['#d9b26f', '#e9d8b4', '#b98b5c'], 'speed': 1.6,
                  'head': ('NotoSerifKR', SERIF), 'body': ('NotoSerifKR', SERIF),
                  'mix': ['fade', 'blur', 'wipe', 'split', 'fade', 'zoom']},
    'kinetic': {'label': '키네틱', 'colors': ['#ff2e4d', '#ffe600', '#00e0ff'], 'speed': 0.6,
                'head': ('BlackHanSans', SANS), 'body': ('NotoSansKR', SANS),
                'mix': ['whip', 'flash', 'diagonal', 'slide', 'wipe-up', 'split']},
}
STYLE_HINT = ('classic(기본, 무난한 소개), pop(아이·가족·축제·놀이처럼 밝고 귀여운 주제), '
              'cinematic(기념·감동·회고·공식 행사처럼 차분하고 진지한 주제), kinetic(스포츠·공연·홍보처럼 빠르고 강렬한 주제)')

# ---------------------------------------------------------------- 타임라인
TIMELINE_JS = '''<script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // 없는 요소(설명이 빈 장면 등)는 건너뛴다
      const F = (t, a, b, at) => { if (typeof t === "string" && !document.querySelector(t)) return; tl.fromTo(t, a, b, at); };
      const starts = __STARTS__, durs = __DURS__, os = __OS__, total = __TOTAL__, TR = __TRS__, TYPES = __TYPES__;
      const ST = "__STYLE__", SP = __SPEED__;            // 스타일, 전환 속도 배율
      const K = { classic: 1, pop: 0.9, cinematic: 1.45, kinetic: 0.6 }[ST];   // 글자 등장 시점 배율
      const CLIP = {
        wipe: ["inset(0 0 0 100%)", "inset(0 0 0 0%)"], "wipe-up": ["inset(100% 0 0 0)", "inset(0% 0 0 0)"],
        split: ["inset(0 50% 0 50%)", "inset(0 0% 0 0%)"], circle: ["circle(0% at 50% 50%)", "circle(150% at 50% 50%)"],
        diagonal: ["polygon(0% 0%, 0% 0%, -50% 100%, -50% 100%)", "polygon(0% 0%, 150% 0%, 100% 100%, -50% 100%)"] };
      function trans(kind, el, s, i) {
        const D = x => x * SP;
        if (kind === "panel") F(["#p_a", "#p_b", "#p_c"][i % 3], { x: "-100%" }, { x: "100%", duration: D(0.9), ease: "power2.inOut" }, s - D(0.35));
        else if (CLIP[kind]) F(el, { clipPath: CLIP[kind][0] }, { clipPath: CLIP[kind][1], duration: D(0.85), ease: "power3.inOut" }, s);
        else if (kind === "slide") F(el, { xPercent: 100 }, { xPercent: 0, duration: D(0.8), ease: "power3.inOut" }, s);
        else if (kind === "zoom") F(el, { opacity: 0, scale: 1.25 }, { opacity: 1, scale: 1, duration: D(0.9), ease: "power3.out" }, s);
        else if (kind === "blur") F(el, { opacity: 0, filter: "blur(40px)" }, { opacity: 1, filter: "blur(0px)", duration: D(0.9), ease: "power2.out" }, s);
        else if (kind === "whip") F(el, { xPercent: 100, filter: "blur(24px)" }, { xPercent: 0, filter: "blur(0px)", duration: D(0.5), ease: "expo.out" }, s);
        else if (kind === "flash") {   // 하얗게 번쩍인 뒤 살짝 줌아웃
          F("#flash", { opacity: 1 }, { opacity: 0, duration: D(0.6), ease: "power2.out", immediateRender: false }, s);
          F(el, { scale: 1.2 }, { scale: 1, duration: D(0.75), ease: "expo.out" }, s);
        }
        else if (kind === "spin") F(el, { scale: 0.4, rotation: -10, opacity: 0 }, { scale: 1, rotation: 0, opacity: 1, duration: D(0.65), ease: "back.out(1.4)" }, s);
        else F(el, { opacity: 0 }, { opacity: 1, duration: D(0.8), ease: "power1.inOut" }, s);
      }
      // 제목류(글자 단위로 쪼개져 있음: .w > .ch)
      function head(sel, at) {
        if (ST === "kinetic") F(sel + " .ch", { yPercent: 115 }, { yPercent: 0, duration: 0.42, ease: "expo.out", stagger: 0.035 }, at);
        else if (ST === "pop") {
          F(sel, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2.2)" }, at);
          F(sel + " .ch", { scale: 0, rotation: -30 }, { scale: 1, rotation: 0, duration: 0.45, ease: "back.out(3)", stagger: 0.045 }, at + 0.08);
        }
        else if (ST === "cinematic") F(sel, { opacity: 0, letterSpacing: "0.3em", filter: "blur(10px)" }, { opacity: 1, letterSpacing: "0.02em", filter: "blur(0px)", duration: 1.6, ease: "power2.out" }, at);
        else F(sel, { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.6, ease: "power4.out" }, at);
      }
      // 본문류
      function body(sel, at) {
        if (ST === "kinetic") F(sel, { opacity: 0, clipPath: "inset(0 100% 0 0)" }, { opacity: 1, clipPath: "inset(0 0% 0 0)", duration: 0.4, ease: "expo.out" }, at);
        else if (ST === "pop") F(sel, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2.5)" }, at);
        else if (ST === "cinematic") F(sel, { opacity: 0 }, { opacity: 1, duration: 1.2, ease: "power1.inOut" }, at);
        else F(sel, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, at);
      }
      // 사진 움직임
      function cam(sel, s, i, len) {
        const z = i % 2 === 0;
        if (ST === "kinetic") {
          F(sel, { scale: 1.3 }, { scale: 1.08, duration: 0.5, ease: "expo.out" }, s);
          F(sel, { scale: 1.08 }, { scale: 1.0, duration: Math.max(0.5, len - 0.5), ease: "none", immediateRender: false }, s + 0.5);
        } else if (ST === "pop") {
          F(sel, { scale: 1.25, rotation: z ? -4 : 4 }, { scale: 1.06, rotation: 0, duration: 0.8, ease: "back.out(1.6)" }, s);
          F(sel, { scale: 1.06 }, { scale: 1.0, duration: Math.max(0.5, len - 0.8), ease: "none", immediateRender: false }, s + 0.8);
        } else if (ST === "cinematic") F(sel, { scale: 1.12, x: z ? 40 : -40 }, { scale: 1.0, x: z ? -40 : 40, duration: len, ease: "none" }, s);
        else F(sel, { scale: z ? 1.0 : 1.14, x: z ? 0 : 24 }, { scale: z ? 1.14 : 1.0, x: z ? -24 : 0, duration: len, ease: "none" }, s);
      }
      function tiles(sel, at) {
        if (ST === "kinetic") F(sel, { xPercent: (k) => (k % 2 ? 120 : -120), opacity: 0 }, { xPercent: 0, opacity: 1, duration: 0.45, ease: "expo.out", stagger: 0.08 }, at);
        else if (ST === "pop") F(sel, { scale: 0, rotation: (k) => (k % 2 ? 14 : -14) }, { scale: 1, rotation: 0, duration: 0.55, ease: "back.out(2)", stagger: 0.12 }, at);
        else if (ST === "cinematic") F(sel, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 1.2, ease: "power2.out", stagger: 0.3 }, at);
        else F(sel, { opacity: 0, scale: 0.86 }, { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.5)", stagger: 0.14 }, at);
      }

      // 오프닝
      F("#b1", { scale: 0 }, { scale: 1, duration: 1.0, ease: "back.out(1.6)" }, 0.05);
      F("#b2", { scale: 0 }, { scale: 1, duration: 1.0, ease: "back.out(1.6)" }, 0.2);
      F("#b3", { scale: 0 }, { scale: 1, duration: 0.8, ease: "back.out(2)" }, 0.35);
      tl.to("#b1", { x: 40, y: 30, duration: 4, ease: "sine.inOut" }, 1);
      body("#yr", 0.3 * K); head("#big", 0.5 * K); body("#hanja", 1.2 * K); body("#org", 1.6 * K);
      tl.to("#intro .photo", { scale: 1.08, duration: starts[0] + 0.8, ease: "none" }, 0);

      starts.forEach((s, i) => {
        const id = "#s" + (i + 1), T = TYPES[i], at = x => s + x * K, d = durs[i];
        trans(TR[i], id, s, i);
        F(id + " .tag", { opacity: 0 }, { opacity: 1, duration: 0.5 }, at(0.9));
        F(id + " .vline", { scaleY: 0 }, { scaleY: 1, duration: 0.6, ease: "power3.out" }, at(0.2));
        if (T === "collage") {
          tiles(id + " .tile", at(0.15));
          F(id + " .tile img", { scale: 1.16 }, { scale: 1.0, duration: d, ease: "none" }, s);
          F(id + " .cbar", { scaleX: 0 }, { scaleX: 1, duration: d, ease: "none" }, s);
          head(id + " .ttl", at(0.55)); body(id + " .sub", at(0.85));
          return;
        }
        cam(id + " .photo", s, i, d);
        if (T === "stat") {
          body(id + " .stat-l", at(0.3));
          F(id + " .stat-n", { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, at(0.35));
          F(id + " .strip", { yPercent: 0 }, { yPercent: (k, el) => -10 * +el.dataset.d, duration: 1.6 * K, ease: "power3.out", stagger: 0.08 }, at(0.4));
          body(id + " .unit", at(1.3)); body(id + " .stat-s", at(1.5));
        } else if (T === "quote") {
          F(id + " .qmark", { opacity: 0, scale: 0.3 }, { opacity: 1, scale: 1, duration: 0.7, ease: "back.out(2)" }, at(0.3));
          head(id + " .qtext", at(0.6)); body(id + " .qwho", at(1.4));
        } else if (T === "list") {
          F(id + " .lpanel", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out" }, at(0.1));
          head(id + " .ttl", at(0.35));
          F(id + " .bar", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power3.out" }, at(0.5));
          const gap = Math.min(0.45, (d - 1.8) / 5) * K;
          document.querySelectorAll(id + " .items li").forEach((li, k) => body(id + " .items li:nth-child(" + (k + 1) + ")", at(0.8) + gap * k));
        } else {
          F(id + " .num", { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.6, ease: "power3.out" }, at(0.35));
          F(id + " .bar", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power3.out" }, at(0.5));
          head(id + " .ttl", at(0.55)); body(id + " .sub", at(0.85));
        }
      });

      // 엔딩
      trans(TR[starts.length], "#outro", os, starts.length);
      F("#ob1", { scale: 0 }, { scale: 1, duration: 0.9, ease: "back.out(1.6)" }, os + 0.5);
      F("#ob2", { scale: 0 }, { scale: 1, duration: 0.9, ease: "back.out(1.6)" }, os + 0.6);
      head("#o1", os + 0.7 * K); head("#o2", os + 1.0 * K); body("#o3", os + 1.6 * K);
      tl.to("#outro .photo", { scale: 1.08, duration: total - os, ease: "none" }, os);
      tl.to("#root", { opacity: 0, duration: 0.5, ease: "power1.in" }, total - 0.5);
      F("#progress", { scaleX: 0 }, { scaleX: 1, duration: total, ease: "none" }, 0);

      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>'''

# ---------------------------------------------------------------- 공통 CSS
COMMON_CSS = '''<style>
      #root { font-family: var(--font-body); }
      .ttl, .big, .o1, .o2, .qtext, .qmark, .stat-n, .stat-l, .num, .yr { font-family: var(--font-head); }
      .w { display: inline-block; white-space: nowrap; }
      .ch { display: inline-block; }
      .sub, .stat-s, .qwho, .items li, .hanja, .o3 { word-break: keep-all; }
      .lb { display: none; position: absolute; left: 0; right: 0; height: 96px; background: #000; z-index: 57; }
      .lb.top { top: 0; } .lb.bot { bottom: 0; }
      #flash { position: absolute; inset: 0; background: #fff; opacity: 0; z-index: 55; pointer-events: none; }
    </style>'''

# 세로(9:16, 1080x1920) 배치: base_template의 가로 좌표를 덮어쓴다. 문구는 사진 아래쪽에 모은다.
PORTRAIT_CSS = '''<style>
      html, body, #root { width: 1080px; height: 1920px; }
      .panel { width: 1080px; height: 1920px; }
      #progress { width: 1080px; }
      .shade { background:
        linear-gradient(0deg, rgba(15,12,25,.88) 0%, rgba(15,12,25,.55) 35%, rgba(15,12,25,0) 62%),
        linear-gradient(180deg, rgba(15,12,25,.45) 0%, rgba(15,12,25,0) 18%); }
      .num { left: 80px; top: 1010px; font-size: 170px; }
      .bar { left: 86px; top: 1230px; }
      .ttl { left: 80px; right: 80px; top: 1270px; font-size: 88px; line-height: 1.15; }
      .sub { left: 84px; right: 84px; top: 1400px; font-size: 42px; line-height: 1.45; }
      .tag { right: 60px; top: 90px; font-size: 28px; }
      .yr, .big, .hanja, .org, .o1, .o2, .o3 { width: 1080px; padding: 0 60px; }
      .yr { top: 600px; font-size: 52px; }
      .big { top: 690px; line-height: 1.1; }
      .hanja { top: 1000px; font-size: 40px; letter-spacing: .2em; line-height: 1.5; }
      .org { top: 1180px; font-size: 46px; }
      .o1 { top: 720px; font-size: 76px; }
      .o2 { top: 840px; font-size: 76px; }
      .o3 { top: 1040px; font-size: 42px; line-height: 1.5; }
    </style>'''

# ---------------------------------------------------------------- 장면 유형 CSS(변형 0)
SCENE_CSS = '''<style>
      .scene .tile { position: relative; overflow: hidden; border-radius: 22px; background: #2a2836; }
      .scene .tile img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .grid { position: absolute; left: 40px; right: 40px; top: 40px; bottom: 250px; display: grid; gap: 22px; }
      .grid.g2 { grid-template-columns: 1fr 1fr; }
      .grid.g3 { grid-template-columns: 1.35fr 1fr; grid-template-rows: 1fr 1fr; }
      .grid.g3 .tile:first-child { grid-row: span 2; }
      .grid.g4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
      .t-collage .ttl { top: auto; bottom: 108px; left: 60px; font-size: 84px; }
      .t-collage .sub { top: auto; bottom: 46px; left: 64px; font-size: 40px; }
      .t-collage .cbar { position: absolute; left: 0; right: 0; bottom: 0; height: 12px; background: var(--c); transform-origin: 0 50%; }

      .dim { position: absolute; inset: 0; background: rgba(15,12,25,.8); }
      .t-stat .photo { filter: blur(10px); }
      .stat-l, .stat-n, .stat-s { position: absolute; left: 0; width: 100%; text-align: center; padding: 0 80px; }
      .stat-l { top: 230px; font-size: 64px; font-weight: 800; color: var(--c); letter-spacing: -0.02em; }
      .stat-n { top: 340px; font-size: 300px; font-weight: 900; line-height: 1; letter-spacing: -0.05em; white-space: nowrap; }
      .stat-n .dg { display: inline-block; height: 1em; overflow: hidden; vertical-align: top; }
      .stat-n .strip { display: block; line-height: 1; }
      .stat-n .strip b { display: block; height: 1em; font-weight: 900; }
      .stat-n .unit { font-size: 110px; margin-left: 18px; letter-spacing: -0.02em; display: inline-block; }
      .stat-s { top: 720px; font-size: 48px; font-weight: 500; color: rgba(255,255,255,.9); }

      .qshade { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(15,12,25,.94) 0%, rgba(15,12,25,.86) 52%, rgba(15,12,25,.2) 85%); }
      .qmark { position: absolute; left: 100px; top: 40px; font-size: 380px; font-weight: 900; line-height: 1; color: var(--c); transform-origin: 30% 60%; }
      .qtext { position: absolute; left: 120px; top: 360px; width: 1080px; font-size: 76px; font-weight: 800; line-height: 1.38; letter-spacing: -0.03em; }
      .qwho { position: absolute; left: 124px; top: 830px; font-size: 42px; font-weight: 600; color: rgba(255,255,255,.8); }

      .lpanel { position: absolute; left: 0; top: 0; bottom: 0; width: 1040px; background: rgba(20,18,30,.93); }
      .t-list .ttl { top: 150px; font-size: 92px; }
      .t-list .bar { top: 290px; }
      .items { position: absolute; left: 116px; top: 350px; width: 860px; list-style: none; }
      .items li { display: flex; align-items: center; gap: 30px; font-size: 54px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 38px; }
      .items li i { flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--c); }
    </style>'''
PORTRAIT_SCENE_CSS = '''<style>
      .grid { left: 36px; right: 36px; top: 36px; bottom: 560px; gap: 18px; }
      .grid.g3 { grid-template-columns: 1fr 1fr; grid-template-rows: 1.3fr 1fr; }
      .grid.g3 .tile:first-child { grid-row: auto; grid-column: span 2; }
      .t-collage .ttl { left: 70px; right: 70px; bottom: 300px; font-size: 80px; }
      .t-collage .sub { left: 74px; right: 74px; bottom: 120px; font-size: 42px; }
      .stat-l { top: 600px; font-size: 56px; }
      .stat-n { top: 700px; font-size: 220px; padding: 0 30px; }
      .stat-n .unit { font-size: 90px; }
      .stat-s { top: 1000px; font-size: 44px; line-height: 1.45; }
      .qshade { background: linear-gradient(0deg, rgba(15,12,25,.95) 0%, rgba(15,12,25,.88) 50%, rgba(15,12,25,.15) 80%); }
      .qmark { left: 60px; top: 700px; font-size: 300px; }
      .qtext { left: 80px; top: 980px; width: 920px; font-size: 66px; }
      .qwho { left: 84px; top: 1560px; font-size: 40px; }
      .lpanel { top: 820px; width: auto; right: 0; }
      .t-list .ttl { top: 880px; left: 80px; right: 80px; font-size: 80px; }
      .t-list .bar { top: 1000px; left: 86px; }
      .items { left: 86px; top: 1060px; width: 900px; }
      .items li { font-size: 50px; margin-bottom: 34px; }
    </style>'''

# ---------------------------------------------------------------- 변형 1
VARIANT_CSS = '''<style>
      /* 기본 장면 변형: 왼쪽 글자 · 오른쪽 사진 분할 */
      .t-title.v1 .photo { left: 36%; top: -4%; width: 68%; height: 108%; }
      .t-title.v1 .shade { background: linear-gradient(90deg, var(--ground) 0 37%, rgba(0,0,0,0) 37%); }
      .vline { position: absolute; left: 36%; top: 0; bottom: 0; width: 14px; background: var(--c); transform-origin: 50% 0; }
      .t-title.v1 .num { left: 110px; top: 150px; font-size: 180px; }
      .t-title.v1 .bar { top: 430px; }
      .t-title.v1 .ttl { top: 470px; max-width: 600px; font-size: 86px; line-height: 1.15; }
      .t-title.v1 .sub { top: auto; bottom: 170px; max-width: 580px; font-size: 40px; line-height: 1.45; }
      /* 콜라주 변형: 흐린 배경 위 폴라로이드 */
      .t-collage .bgp { filter: blur(14px) brightness(.45); }
      .grid.poly { display: block; }
      .grid.poly .tile { position: absolute; border: 14px solid #fff; border-radius: 6px; box-shadow: 0 30px 60px rgba(0,0,0,.5); }
      .grid.poly.g2 .tile { width: 760px; height: 540px; }
      .grid.poly.g2 .tile:nth-child(1) { left: 150px; top: 40px; rotate: -5deg; }
      .grid.poly.g2 .tile:nth-child(2) { left: 920px; top: 100px; rotate: 4deg; }
      .grid.poly.g3 .tile { width: 620px; height: 470px; }
      .grid.poly.g3 .tile:nth-child(1) { left: 30px; top: 60px; rotate: -6deg; }
      .grid.poly.g3 .tile:nth-child(2) { left: 610px; top: 150px; rotate: 3deg; }
      .grid.poly.g3 .tile:nth-child(3) { left: 1190px; top: 50px; rotate: -3deg; }
      .grid.poly.g4 .tile { width: 500px; height: 380px; }
      .grid.poly.g4 .tile:nth-child(1) { left: 0; top: 60px; rotate: -6deg; }
      .grid.poly.g4 .tile:nth-child(2) { left: 445px; top: 190px; rotate: 4deg; }
      .grid.poly.g4 .tile:nth-child(3) { left: 895px; top: 50px; rotate: -3deg; }
      .grid.poly.g4 .tile:nth-child(4) { left: 1335px; top: 170px; rotate: 5deg; }
      /* 큰 숫자 변형: 왼쪽 숫자 · 오른쪽 사진 */
      .t-stat.v1 .photo { filter: none; left: 48%; top: -4%; width: 56%; height: 108%; }
      .t-stat.v1 .dim { background: linear-gradient(90deg, rgba(15,12,25,.97) 0 50%, rgba(15,12,25,0) 50%); }
      .t-stat.v1 .stat-l, .t-stat.v1 .stat-n, .t-stat.v1 .stat-s { text-align: left; width: 920px; padding: 0 0 0 110px; }
      .t-stat.v1 .stat-n { font-size: 220px; }
      .t-stat.v1 .stat-s { line-height: 1.4; }
      /* 인용 변형: 가운데 정렬 */
      .t-quote.v1 .qshade { background: rgba(15,12,25,.8); }
      .t-quote.v1 .qmark { left: 0; width: 100%; text-align: center; top: 60px; transform-origin: 50% 60%; }
      .t-quote.v1 .qtext { left: 200px; width: 1520px; text-align: center; top: 420px; }
      .t-quote.v1 .qwho { left: 0; width: 100%; text-align: center; top: 800px; }
      /* 목록 변형: 아래쪽 카드 */
      .t-list.v1 .lpanel { width: auto; right: 0; background: linear-gradient(180deg, rgba(15,12,25,.9) 0%, rgba(15,12,25,.2) 45%, rgba(15,12,25,.75) 100%); }
      .t-list.v1 .items { left: 80px; right: 80px; width: auto; top: auto; bottom: 90px; display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 24px; }
      .t-list.v1 .items li { flex-direction: column; align-items: flex-start; gap: 18px; margin: 0; padding: 30px 32px 36px; background: rgba(20,18,30,.88); border-radius: 18px; font-size: 44px; line-height: 1.25; }
      .t-list.v1 .items li i { width: 60px; height: 10px; border-radius: 5px; }
    </style>'''
PORTRAIT_VARIANT_CSS = '''<style>
      .t-title.v1 .photo { left: -4%; top: -4%; width: 108%; height: 62%; }
      .t-title.v1 .shade { background: linear-gradient(180deg, rgba(0,0,0,0) 0 54%, var(--ground) 54%); }
      .vline { left: 0; right: 0; top: 54%; bottom: auto; width: auto; height: 14px; transform-origin: 0 50%; }
      .t-title.v1 .num { left: 80px; top: 1100px; font-size: 150px; }
      .t-title.v1 .bar { top: 1290px; }
      .t-title.v1 .ttl { top: 1320px; max-width: 920px; font-size: 84px; }
      .t-title.v1 .sub { bottom: 150px; max-width: 900px; font-size: 42px; }
      .grid.poly.g2 .tile { width: 760px; height: 560px; }
      .grid.poly.g2 .tile:nth-child(1) { left: 0; top: 40px; }
      .grid.poly.g2 .tile:nth-child(2) { left: 240px; top: 660px; }
      .grid.poly.g3 .tile { width: 620px; height: 440px; }
      .grid.poly.g3 .tile:nth-child(1) { left: 0; top: 20px; }
      .grid.poly.g3 .tile:nth-child(2) { left: 380px; top: 450px; }
      .grid.poly.g3 .tile:nth-child(3) { left: 20px; top: 870px; }
      .grid.poly.g4 .tile { width: 520px; height: 390px; }
      .grid.poly.g4 .tile:nth-child(1) { left: 0; top: 0; }
      .grid.poly.g4 .tile:nth-child(2) { left: 480px; top: 200px; }
      .grid.poly.g4 .tile:nth-child(3) { left: 0; top: 580px; }
      .grid.poly.g4 .tile:nth-child(4) { left: 470px; top: 820px; }
      .t-stat.v1 .photo { left: -4%; top: -4%; width: 108%; height: 50%; }
      .t-stat.v1 .dim { background: linear-gradient(180deg, rgba(15,12,25,0) 0 46%, rgba(15,12,25,.97) 46%); }
      .t-stat.v1 .stat-l, .t-stat.v1 .stat-n, .t-stat.v1 .stat-s { width: 100%; padding: 0 80px; }
      .t-stat.v1 .stat-l { top: 990px; }
      .t-stat.v1 .stat-n { top: 1090px; font-size: 200px; }
      .t-stat.v1 .stat-s { top: 1350px; }
      .t-quote.v1 .qmark { top: 520px; }
      .t-quote.v1 .qtext { left: 80px; width: 920px; top: 820px; }
      .t-quote.v1 .qwho { top: 1400px; }
      .t-list.v1 .lpanel { top: 0; }
      .t-list.v1 .ttl { top: 200px; }
      .t-list.v1 .bar { top: 320px; }
      .t-list.v1 .items { left: 60px; right: 60px; bottom: 140px; grid-auto-flow: row; grid-template-columns: 1fr 1fr; }
      .t-list.v1 .items li { font-size: 40px; }
    </style>'''

# ---------------------------------------------------------------- 스타일 CSS
STYLE_CSS = {
    'classic': '',
    'pop': '''<style>
      :root { --coral: #ff5fa2; --sun: #ffd23f; --mint: #2ec4b6; --ground: #2a1638; }
      #intro { background: radial-gradient(circle at 70% 30%, #6a2c70 0%, var(--ground) 65%); }
      #outro { background: radial-gradient(circle at 30% 70%, #6a2c70 0%, var(--ground) 65%); }
      .st-pop .shade { background: linear-gradient(0deg, rgba(42,22,56,.85) 0%, rgba(42,22,56,0) 55%); }
      .st-pop .ttl { background: #fff; color: #2a1638; padding: 4px 30px 12px; border-radius: 26px; rotate: -2deg; text-shadow: none; box-shadow: 10px 10px 0 var(--c); }
      .st-pop .sub { background: var(--c); color: #2a1638; padding: 6px 22px; border-radius: 14px; rotate: 1deg; font-weight: 700; margin-top: 34px; }
      .st-pop .t-collage .sub, .st-pop .t-title.v1 .sub { margin-top: 0; }
      .st-pop .num { color: var(--c); -webkit-text-stroke: 0; text-shadow: 8px 8px 0 rgba(0,0,0,.25); }
      .st-pop .bar { display: none; }
      .st-pop .tile { border: 8px solid #fff; border-radius: 28px; }
      .st-pop .items li i { border-radius: 8px; rotate: 45deg; width: 30px; height: 30px; }
      .st-pop .t-list.v1 .items li i { rotate: 0deg; height: 12px; }
      .st-pop .big { text-shadow: 8px 8px 0 var(--coral); }
      .st-pop .big .o { color: var(--sun); }
      .st-pop .stat-n { color: var(--sun); text-shadow: 10px 10px 0 var(--coral); }
      .st-pop .qmark { color: var(--sun); font-family: var(--font-body); }
      .st-pop .o2 { color: var(--sun); text-shadow: 6px 6px 0 var(--coral); }
      .st-pop #progress { height: 14px; background: var(--sun); }
    </style>''',
    'cinematic': '''<style>
      :root { --coral: #d9b26f; --sun: #e9d8b4; --mint: #b98b5c; --ground: #0e0d0c; }
      .st-cinematic .lb { display: block; }
      .st-cinematic .blob, .st-cinematic #progress, .st-cinematic .num { display: none; }
      .st-cinematic #intro, .st-cinematic #outro { background: #0e0d0c; }
      .st-cinematic #intro .photo { opacity: .45; filter: blur(2px); }
      .st-cinematic .shade { background: linear-gradient(0deg, rgba(10,9,8,.9) 0%, rgba(10,9,8,.35) 45%, rgba(10,9,8,0) 70%); }
      .st-cinematic .ttl, .st-cinematic .big, .st-cinematic .o1, .st-cinematic .o2, .st-cinematic .qtext { font-weight: 700; letter-spacing: .02em; }
      .st-cinematic .sub, .st-cinematic .hanja, .st-cinematic .o3 { font-weight: 400; letter-spacing: .06em; }
      .st-cinematic .t-title:not(.v1) .ttl, .st-cinematic .t-title:not(.v1) .sub { left: 0; right: 0; text-align: center; }
      .st-cinematic .t-title:not(.v1) .bar { left: 50%; margin-left: -60px; height: 4px; }
      .st-cinematic .yr { color: var(--coral); letter-spacing: .6em; }
      .st-cinematic .big .o, .st-cinematic .o2, .st-cinematic .org b { color: var(--coral); }
      .st-cinematic .tile { border-radius: 4px; }
      .st-cinematic .grid { margin-top: 60px; margin-bottom: 60px; }
      .st-cinematic .t-collage .ttl, .st-cinematic .t-collage .sub { margin-bottom: 70px; }
      .st-cinematic .tag, .st-cinematic .qmark { margin-top: 70px; border-radius: 0; }
      .st-cinematic .t-list.v1 .items, .st-cinematic .t-title.v1 .sub { margin-bottom: 60px; }
      .st-cinematic .t-collage .cbar { display: none; }
    </style>''',
    'kinetic': '''<style>
      :root { --coral: #ff2e4d; --sun: #ffe600; --mint: #00e0ff; --ground: #0b0b0f; }
      .st-kinetic .blob { display: none; }
      .st-kinetic #intro, .st-kinetic #outro { background: repeating-linear-gradient(-45deg, #15151c 0 40px, #0b0b0f 40px 80px); }
      .st-kinetic #intro .photo, .st-kinetic #outro .photo { opacity: .3; filter: grayscale(1) contrast(1.2); }
      .st-kinetic .w { overflow: hidden; padding-bottom: .06em; vertical-align: top; }
      .st-kinetic .ttl { letter-spacing: -0.01em; line-height: 1.05; }
      .st-kinetic .t-title:not(.v1) .ttl { top: 640px; font-size: 130px; }
      .st-kinetic .t-title .num { -webkit-text-stroke: 0; color: var(--c); }
      .st-kinetic .bar { height: 18px; width: 200px; }
      .st-kinetic .sub { background: var(--c); color: #0b0b0f; padding: 4px 18px; font-weight: 800; }
      .st-kinetic .tile { border-radius: 0; }
      .st-kinetic .items li i { border-radius: 0; width: 34px; height: 10px; }
      .st-kinetic .big .o, .st-kinetic .o2 { color: var(--sun); }
      .st-kinetic .yr { color: var(--mint); }
      .st-kinetic .stat-n { color: var(--sun); }
      .st-kinetic #progress { height: 12px; background: var(--sun); }
    </style>''',
}
STYLE_PCSS = {
    'pop': '''<style>
      .st-pop .ttl, .st-pop .sub { right: auto; max-width: 920px; }
    </style>''',
    'kinetic': '''<style>
      .st-kinetic .t-title:not(.v1) .ttl { top: 1250px; font-size: 100px; }
      .st-kinetic .sub { right: auto; max-width: 920px; }
    </style>''',
}


# ---------------------------------------------------------------- HTML 조각
def split_text(s, first_cls=''):
    """글자 단위 애니메이션용: 단어(.w, 줄바꿈 단위) 안에 글자(.ch)."""
    out, n = [], 0
    for word in str(s).split(' '):
        chars = []
        for c in word:
            cls = 'ch' + (' ' + first_cls if first_cls and n == 0 else '')
            chars.append(f'<span class="{cls}">{html.escape(c)}</span>'); n += 1
        out.append(f'<span class="w">{"".join(chars)}</span>')
    return ' '.join(out)


def digits_html(num):
    """'1,200' -> 자릿수마다 0~9 띠(strip). 타임라인이 띠를 올려 숫자가 굴러가며 올라간다(렌더 시 결정적)."""
    out = []
    for ch in num:
        if ch.isdigit():
            out.append('<span class="dg"><span class="strip" data-d="%s">%s</span></span>' % (ch, ''.join(f'<b>{d}</b>' for d in range(10))))
        else:
            out.append(f'<span>{html.escape(ch)}</span>')
    return ''.join(out)


def variant_of(s, i, seed):
    return s['v'] if s.get('v') in (0, 1) else (i + seed) % 2


def scene_html(i, s, org, start, dur, colors, seed):
    e = html.escape
    t = s.get('type') if s.get('type') in SCENE_TYPES else 'title'
    v = variant_of(s, i, seed)
    head = (f'<div id="s{i+1}" class="scene clip t-{t} v{v}" data-start="{start}" data-duration="{dur}" '
            f'data-track-index="1" style="--c:{colors[i % 3]}">')
    img = f'<img class="photo" src="assets/{s["photo"]}.jpg" alt="" />'
    tag = f'<div class="tag">{org}</div>'
    ttl = f'<div class="ttl">{split_text(s["ttl"])}</div>'
    sub = f'<div class="sub">{e(s.get("sub", ""))}</div>' if s.get('sub') else ''
    if t == 'collage':
        ps = (s.get('photos') or [s['photo']])[:4]
        tiles = ''.join(f'<div class="tile"><img src="assets/{p}.jpg" alt="" /></div>' for p in ps)
        bg = f'<img class="photo bgp" src="assets/{ps[0]}.jpg" alt="" />' if v else ''
        body = f'{bg}<div class="grid g{max(2, len(ps))}{" poly" if v else ""}">{tiles}</div>{ttl}{sub}<div class="cbar"></div>'
    elif t == 'stat':
        body = (f'{img}<div class="dim"></div><div class="stat-l">{e(s["ttl"])}</div>'
                f'<div class="stat-n">{digits_html(s["num"])}<span class="unit">{e(s.get("unit", ""))}</span></div>'
                f'<div class="stat-s">{e(s.get("sub", ""))}</div>{tag}')
    elif t == 'quote':
        who = f'— {e(s["who"])}' if s.get('who') else ''
        body = (f'{img}<div class="qshade"></div><div class="qmark">“</div>'
                f'<div class="qtext">{split_text(s["quote"])}</div><div class="qwho">{who}</div>{tag}')
    elif t == 'list':
        lis = ''.join(f'<li><i></i><span>{e(x)}</span></li>' for x in s['items'][:5])
        body = f'{img}<div class="lpanel"></div>{ttl}<div class="bar"></div><ul class="items">{lis}</ul>{tag}'
    else:
        vl = '<div class="vline"></div>' if v else ''
        body = f'{img}<div class="shade"></div>{vl}<div class="num">{i+1:02d}</div><div class="bar"></div>{ttl}{sub}{tag}'
    return f'\n      {head}\n        {body}\n      </div>'


def scene_speech(s):
    """내레이션이 비어 있을 때 대신 읽을 문장(화면 문구 기반)."""
    t = s.get('type')
    if t == 'stat':
        return f"{s['ttl']} {s['num']}{s.get('unit', '')}. {s.get('sub', '')}".strip()
    if t == 'quote':
        return s['quote']
    if t == 'list':
        return f"{s['ttl']}. " + ', '.join(s['items'])
    return f"{s['ttl']}. {s.get('sub', '')}"


# ---------------------------------------------------------------- 글꼴
def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def font_css(job_dir, style, plan):
    """스타일이 쓰는 글꼴을 이 영상의 글자만 남겨 assets/fonts/에 저장하고 @font-face를 돌려준다.
    fonts/ 원본이 없으면 시스템 글꼴로 대체(빈 문자열)."""
    st = STYLES[style]
    text = ''.join(_strings(plan)) + '0123456789%.,·—“”:-()/ '
    css, made = [], {}
    for role in ('head', 'body'):
        fam, fallback = st[role]
        if fam not in made:
            src = os.path.join(FONTS_DIR, fam + '.ttf')
            made[fam] = None
            if os.path.exists(src):
                key = hashlib.sha1((fam + ''.join(sorted(set(text)))).encode()).hexdigest()[:10]
                rel = f'assets/fonts/{fam}-{key}.woff'
                dst = os.path.join(job_dir, rel)
                if not os.path.exists(dst):
                    from fontTools import subset
                    o = subset.Options(); o.flavor = 'woff'; o.layout_features = ['*']; o.notdef_outline = True
                    f = subset.load_font(src, o)
                    ss = subset.Subsetter(o); ss.populate(text=text); ss.subset(f)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    subset.save_font(f, dst + '.part', o); os.replace(dst + '.part', dst)
                made[fam] = rel
                css.append(f"@font-face {{ font-family: 'CM-{fam}'; src: url('{rel}') format('woff'); font-weight: 100 900; }}")
        name = f"'CM-{fam}', " if made[fam] else ''
        css.append(f'#root {{ --font-{role}: {name}{fallback}; }}')
    return '<style>\n      ' + '\n      '.join(css) + '\n    </style>'


# ---------------------------------------------------------------- 조립
def compose(job_dir, p, length, ratio='landscape', audio_html='', extra='', timing=None):
    """plan(p)으로 HyperFrames 컴포지션 HTML 문자열을 만든다.
    timing=(장면 시작 목록, 엔딩 시작): 없으면 균등 배분. 박자 맞춤은 beats.snap_times()가 만든다."""
    e = html.escape
    style = p.get('style') if p.get('style') in STYLES else 'classic'
    st = STYLES[style]
    seed = int(p.get('seed') or 0)
    base = open(os.path.join(HERE, 'base_template.html'), encoding='utf-8').read()
    portrait = ratio == 'portrait'
    W, H = (1080, 1920) if portrait else (1920, 1080)
    css = '\n    '.join([re.search(r'<style>.*?</style>', base, re.S).group(0), COMMON_CSS, SCENE_CSS, VARIANT_CSS, STYLE_CSS[style]]
                       + ([PORTRAIT_CSS, PORTRAIT_SCENE_CSS, PORTRAIT_VARIANT_CSS, STYLE_PCSS.get(style, '')] if portrait else [])
                       + [font_css(job_dir, style, p)])
    tl_ = max(1, len(p['title']))
    big_fs = min(190, int(940 / tl_)) if portrait else (230 if tl_ <= 8 else 170)
    n = len(p['scenes'])
    starts, os_ = timing or beats.snap_times(length, n)
    nexts = starts[1:] + [os_]
    durs = [round(b - a + 0.6, 2) for a, b in zip(starts, nexts)]   # 다음 장면 전환과 0.6초 겹침
    total = float(length)
    org = e(p['org'])
    scenes = ''.join(scene_html(i, s, org, starts[i], durs[i], st['colors'], seed) for i, s in enumerate(p['scenes']))
    o = p['outro']
    body = f'''
      <div id="intro" class="scene clip" data-start="0" data-duration="{round(starts[0] + 0.8, 2)}" data-track-index="0">
        <img class="photo" src="assets/{p['intro_photo']}.jpg" alt="" />
        <div class="blob" id="b1" style="width:620px;height:620px;left:-160px;top:-140px;background:var(--coral);opacity:.9"></div>
        <div class="blob" id="b2" style="width:380px;height:380px;right:-90px;bottom:-110px;background:var(--sun);opacity:.95"></div>
        <div class="blob" id="b3" style="width:160px;height:160px;right:300px;top:90px;background:var(--mint);opacity:.9"></div>
        <div class="yr" id="yr">{e(p['year'])}</div>
        <div class="big" id="big" style="font-size:{big_fs}px">{split_text(p['title'], 'o')}</div>
        <div class="hanja" id="hanja">{e(p['tagline'])}</div>
        <div class="org" id="org"><b>{org}</b></div>
      </div>{scenes}
      <div id="outro" class="scene clip" data-start="{os_}" data-duration="{round(total - os_, 2)}" data-track-index="2">
        <img class="photo" src="assets/{p['outro_photo']}.jpg" alt="" />
        <div class="blob" id="ob1" style="width:520px;height:520px;right:-120px;top:-140px;background:var(--coral);opacity:.9"></div>
        <div class="blob" id="ob2" style="width:300px;height:300px;left:-80px;bottom:-90px;background:var(--mint);opacity:.9"></div>
        <div class="o1" id="o1">{split_text(o[0])}</div><div class="o2" id="o2">{split_text(o[1])}</div><div class="o3" id="o3">{e(o[2])}</div>
      </div>
      <div class="panel" id="p_a" style="background:var(--coral)"></div>
      <div class="panel" id="p_b" style="background:var(--sun)"></div>
      <div class="panel" id="p_c" style="background:var(--mint)"></div>
      <div id="flash"></div><div class="lb top"></div><div class="lb bot"></div>
      <div id="progress"></div>{audio_html}'''
    glob = p.get('transition') or 'mix'
    mix = st['mix']
    pick = lambda i, v: v if v in TRANSITIONS else glob if glob in TRANSITIONS else mix[(i + seed) % len(mix)]
    trs = [pick(i, s.get('tr')) for i, s in enumerate(p['scenes'])] + [pick(n, p.get('outro_tr'))]
    js = (TIMELINE_JS.replace('__STARTS__', json.dumps(starts)).replace('__DURS__', json.dumps(durs)).replace('__OS__', str(os_))
          .replace('__TOTAL__', str(total)).replace('__TRS__', json.dumps(trs)).replace('__STYLE__', style)
          .replace('__SPEED__', str(st['speed']))
          .replace('__TYPES__', json.dumps([s.get('type') if s.get('type') in SCENE_TYPES else 'title' for s in p['scenes']])))
    return f'''<!doctype html>
<html lang="ko" data-resolution="{'portrait' if portrait else 'landscape'}">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/gsap.min.js"></script>
    {css}
  </head>
  <body>
    <div id="root" class="st-{style}" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">{body}
    </div>
    {js}{extra}
  </body>
</html>'''

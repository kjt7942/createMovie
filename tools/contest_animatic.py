"""확정 스틸 26장과 음악 A로 60초 애니매틱(HyperFrames)을 만든다. 컷은 음악 박자(120BPM, 8.025초부터)에 맞춘다.
사용: python tools/contest_animatic.py animatic_v1 → jobs/contest/animatic_v1/ 생성 후 그 폴더에서 npx hyperframes render
자막은 콘티 원문을 대조하지 못한 임시 문구다.
"""
import html, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEST = ROOT / "jobs" / "contest"
OUT = CONTEST / (sys.argv[1] if len(sys.argv) > 1 else "animatic_v1")
SEL = json.loads((CONTEST / "selection_v2.json").read_text(encoding="utf-8"))
# --video: 스틸 대신 컷 영상(jobs/contest/cuts_selection.json)을 쓴다.
VIDEOS = json.loads((CONTEST / "cuts_selection.json").read_text(encoding="utf-8")) if "--video" in sys.argv else None
AI_NOTICE = "본 영상은 생성형 AI를 활용해 제작되었습니다."
BEAT = 0.5
FIRST_BEAT = 8.025  # 여기서 음악 박자가 시작되고, 05컷(현대 공개)이 이 박자에 떨어진다.
LENGTH = 60.0
DONGI, DUNGI = "동이", "둥이"

# 컷, 길이(초 또는 박자), 들어오는 전환, 장소 자막, 말풍선(화자, 대사)
CUTS = [
    ("01", 2.0, "cut", "", None),
    ("02", 3.0, "cut", "조선시대, 문경새재 과거길", None),
    ("03", 2.0, "whip", "", (DONGI, "웬 새가 내 모자에?!")),
    ("04", 1.025, "cut", "", None),
    ("05", 6, "flash", "2026년 가을, 문경새재 주흘관", None),
    ("06", 3, "crash", "", (DONGI, "이, 이게 무슨 조화요?!")),
    ("07", 5, "whip", "맨발 황토길", (DUNGI, "형, 따라와!")),
    ("08", 4, "cut", "", (DONGI, "신발을 벗으라니…")),
    ("09", 5, "crash", "", (DONGI, "문안 인사 올리옵니다!")),
    ("10", 4, "flash", "문경새재 오픈세트", None),
    ("11", 4, "cut", "", (DONGI, "음, 내 집이 여기였군.")),
    ("12", 4, "whip", "문경 전통 찻사발", (DONGI, "에구머니!")),
    ("13", 4, "cut", "망댕이가마", None),
    ("14", 5, "flash", "문경 사과", None),
    ("15", 4, "crash", "", (DONGI, "내 모자 사과가 왜 여기…?")),
    ("16", 4, "cut", "", (DONGI, "아삭!")),
    ("17", 6, "whip", "문경 철로자전거", None),
    ("18", 3, "crash", "", (DONGI, "이 쇠수레 멈추시오!")),
    ("19", 4, "cut", "", None),
    ("20", 5, "flash", "패러글라이딩, 강사와 함께 안전하게", None),
    ("21", 6, "pull", "", None),
    ("22", 4, "crash", "", (DONGI, "사람 살려!!")),
    ("23", 6, "fade", "해 질 무렵, 주흘관", None),
    ("24", 6, "cut", "", (DONGI, "안 돌아가오! 여기 살 거요!")),
    ("25", 4, "flash", "", (DUNGI, "문경이 딱이지!")),
    ("26", None, "pull", "", None),  # 남은 시간 전부
]

CSS = """
@font-face { font-family:'Jua'; src:url('assets/Jua.ttf'); }
@font-face { font-family:'BlackHan'; src:url('assets/BlackHanSans.ttf'); }
html,body { margin:0; background:#000; }
#root { position:relative; width:100%; height:100%; overflow:hidden; background:#000; }
.cut { position:absolute; inset:0; overflow:hidden; }
.fx,.kb { position:absolute; inset:0; }
.kb img,.kb video { display:block; width:100%; height:100%; object-fit:cover; }
.place { position:absolute; left:40px; top:34px; padding:8px 18px; background:#101a2e; color:#fff; font:400 28px 'Jua'; border-radius:8px; }
.say { position:absolute; left:0; right:0; bottom:44px; display:flex; justify-content:center; }
.say span { display:block; padding:12px 30px; border-radius:30px; font:400 40px 'Jua'; }
.dongi span { background:#101a2e; color:#fff; }
.dungi span { background:#b8f03c; color:#101a2e; }
.title { position:absolute; left:0; right:0; top:230px; text-align:center; color:#fff; font:400 92px 'BlackHan'; text-shadow:0 4px 18px #000; }
.notice { position:absolute; left:0; right:0; bottom:30px; text-align:center; }
.notice span { padding:8px 20px; background:#101a2e; color:#fff; font:400 26px 'Jua'; border-radius:8px; }
#flash { position:absolute; inset:0; background:#fff; opacity:0; }
"""


def timings():
    t, out = 0.0, []
    for num, size, kind, place, say in CUTS:
        d = LENGTH - t if size is None else (size if t < FIRST_BEAT else size * BEAT)
        out.append((num, round(t, 3), round(d, 3), kind, place, say))
        t += d
    assert abs(out[4][1] - FIRST_BEAT) < 0.001, out[4]  # 05컷은 박자 시작에 떨어져야 한다.
    assert all(1 <= c[2] <= 4.5 for c in out[:-1]), [c[:3] for c in out if not 1 <= c[2] <= 4.5]
    return out


def main():
    cuts = timings()
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for num, *_ in cuts:
        shutil.copy(VIDEOS[num] if VIDEOS else SEL[num], assets / f"c{num}.{'mp4' if VIDEOS else 'jpg'}")
    for f in ("Jua.ttf", "BlackHanSans.ttf"):
        shutil.copy(ROOT / "fonts" / f, assets / f)
    shutil.copy(ROOT / "gsap.min.js", assets / "gsap.min.js")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(CONTEST / "audio_v1" / "collected" / "music_1.wav"), "-t", str(LENGTH),
                    "-af", f"afade=t=out:st={LENGTH - 2.5}:d=2.5", str(assets / "music.wav")], check=True)
    clips, videos, js = [], [], []
    for i, (num, start, dur, kind, place, say) in enumerate(cuts):
        # 영상은 시간 지정이 있는 요소 안에 넣을 수 없어, 영상 자체에 시간을 주고 자막은 따로 둔다.
        shot = (f'<video id="v{num}" class="clip" src="assets/c{num}.mp4" muted playsinline data-start="{start}" data-duration="{dur}" data-track-index="0"></video>'
                if VIDEOS else f'<img src="assets/c{num}.jpg" alt="">')
        visual = f'<div class="fx" id="fx{num}"><div class="kb" id="kb{num}">{shot}</div></div>'
        parts = []
        if VIDEOS:
            videos.append(f'<div class="cut">{visual}</div>')
        else:
            parts.append(visual)
        if place:
            parts.append(f'<div class="place" id="pl{num}">{html.escape(place)}</div>')
        if say:
            who = "dongi" if say[0] == DONGI else "dungi"
            parts.append(f'<div class="say {who}" id="sy{num}"><span>{html.escape(say[1])}</span></div>')
        if num == "26":
            parts.append(f'<div class="title" id="title">문경, 시간 여행</div>')
            parts.append(f'<div class="notice" id="notice"><span>{AI_NOTICE}</span></div>')
        clips.append(f'<div class="cut clip" id="c{num}" data-start="{start}" data-duration="{dur}" data-track-index="1">{"".join(parts)}</div>')
        js.append(f"kb('{num}',{start},{dur},'{kind}');")
        if kind in ("crash", "whip", "flash", "fade", "pull"):
            js.append(f"enter('{num}',{start},{dur},'{kind}',{1 if i % 2 else -1});")
        if place:
            js.append(f"tl.fromTo('#pl{num}',{{x:-30,opacity:0}},{{x:0,opacity:1,duration:.25,ease:'power2.out'}},{start + 0.1});")
        if say:
            js.append(f"tl.fromTo('#sy{num} span',{{scale:.5,opacity:0}},{{scale:1,opacity:1,duration:.22,ease:'back.out(2.5)'}},{start + 0.12});")
    last = cuts[-1]
    js.append(f"tl.fromTo('#title',{{opacity:0,scale:1.3}},{{opacity:1,scale:1,duration:.5,ease:'power3.out'}},{last[1] + 1});")
    js.append(f"tl.fromTo('#notice',{{opacity:0}},{{opacity:1,duration:.4}},{last[1] + 1.5});")
    page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style><script src="assets/gsap.min.js"></script></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{LENGTH}" data-width="1280" data-height="720">
{chr(10).join(videos)}
{chr(10).join(clips)}
<div id="flash" data-layout-allow-occlusion></div>
<audio id="music" src="assets/music.wav" data-start="0" data-duration="{LENGTH}" data-track-index="9" data-volume="1"></audio>
</div>
<script>
const tl = gsap.timeline({{paused:true}});
function kb(n,s,d,kind){{  // 느린 움직임
  if(kind==='pull') return;
  const a=parseInt(n)%2?[1.04,1.1]:[1.1,1.04];
  tl.fromTo('#kb'+n,{{scale:a[0]}},{{scale:a[1],duration:d,ease:'none'}},s);
}}
function enter(n,s,d,kind,dir){{
  if(kind==='crash') tl.fromTo('#fx'+n,{{scale:1.7,filter:'blur(14px)'}},{{scale:1,filter:'blur(0px)',duration:.26,ease:'power3.out'}},s);
  if(kind==='whip') tl.fromTo('#fx'+n,{{x:dir*700,scale:1.25,filter:'blur(22px)'}},{{x:0,scale:1,filter:'blur(0px)',duration:.24,ease:'power3.out'}},s);
  if(kind==='flash') tl.fromTo('#flash',{{opacity:1}},{{opacity:0,duration:.4,ease:'power2.out',immediateRender:false}},s);
  if(kind==='fade') tl.fromTo('#fx'+n,{{opacity:0}},{{opacity:1,duration:.6}},s);
  if(kind==='pull') tl.fromTo('#kb'+n,{{scale:1.6}},{{scale:1,duration:d,ease:'power2.out'}},s);
}}
{chr(10).join(js)}
window.__timelines["main"]=tl;
</script>
</body></html>
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(OUT, [(c[0], c[2]) for c in cuts])


if __name__ == "__main__":
    main()

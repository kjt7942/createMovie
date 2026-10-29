"""홍보영상 제작 웹앱. 업로드(폴더 포함) -> Gemini가 장면/사진 배정 -> HyperFrames 렌더.
실행: GEMINI_API_KEY 환경변수(또는 이 폴더의 .env)를 준비하고 `python server.py` -> http://localhost:5000"""
import base64, html, itertools, json, os, re, shutil, subprocess, threading, time, urllib.error, urllib.request, uuid
from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, 'jobs')
MODELS = ['gemini-flash-lite-latest', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite']  # 한도 걸리면 다음 모델
COLORS = ['#ff6b4a', '#ffc93c', '#3ddc97']
MAX_VISION = 40  # Gemini에 보여줄 사진 수 상한(초과분은 균등 샘플링)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024
_render_lock = threading.Lock()  # ponytail: 렌더 1건씩만. 동시 사용자가 늘면 작업 큐로 교체
_status = {}


def api_key():
    k = os.environ.get('GEMINI_API_KEY')
    p = os.path.join(HERE, '.env')
    if not k and os.path.exists(p):
        m = re.search(r'^GEMINI_API_KEY=(.+)$', open(p, encoding='utf-8').read(), re.M)
        k = m and m.group(1).strip().strip('"\'')
    return k


def jobdir(job):
    if not re.fullmatch(r'[0-9a-f]{12}', job or ''):
        raise ValueError('잘못된 작업 ID')
    return os.path.join(JOBS, job)


def meta_of(job):
    return json.load(open(os.path.join(jobdir(job), 'meta.json'), encoding='utf-8'))


def save_meta(job, m):
    json.dump(m, open(os.path.join(jobdir(job), 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False)


# ---------- 업로드 ----------
@app.post('/api/upload')
def upload():
    job = request.form.get('job') or uuid.uuid4().hex[:12]
    d = jobdir(job)
    for sub in ('assets', 'thumbs'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    gs = os.path.join(d, 'assets', 'gsap.min.js')
    if not os.path.exists(gs):
        shutil.copy(os.path.join(HERE, 'gsap.min.js'), gs)
    m = meta_of(job) if os.path.exists(os.path.join(d, 'meta.json')) else {'photos': [], 'audio': None}
    skipped = []
    for f, path in zip(request.files.getlist('files'), request.form.getlist('paths')):
        path = path.replace('\\', '/').lstrip('/')
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp'):
            try:
                im = ImageOps.exif_transpose(Image.open(f.stream)).convert('RGB')
            except Exception:
                skipped.append(path); continue
            pid = f'p{len(m["photos"]) + 1:03d}'
            im.thumbnail((1920, 1920)); im.save(os.path.join(d, 'assets', pid + '.jpg'), quality=88)
            im.thumbnail((384, 384)); im.save(os.path.join(d, 'thumbs', pid + '.jpg'), quality=75)
            parts = path.split('/')
            m['photos'].append({'id': pid, 'path': path, 'folder': parts[-2] if len(parts) > 1 else ''})
        elif ext == '.mp3':
            f.save(os.path.join(d, 'assets', 'bgm.mp3')); m['audio'] = os.path.basename(path)
        else:
            skipped.append(path)
    save_meta(job, m)
    return jsonify(job=job, **m, skipped=skipped)


@app.post('/api/reset')
def reset():
    d = jobdir(request.json['job'])
    shutil.rmtree(d, ignore_errors=True)
    return jsonify(ok=True)


# ---------- Gemini 구성 ----------
PROMPT = """너는 홍보영상 기획자다. 사진은 폴더(주제)별로 정리돼 있고 폴더명은 사업/주제 이름이다.
아래 요구사항으로 영상 구성을 JSON으로만 답해라. 한국어, 한자 사용 금지.
요구사항에 없는 사실, 폴더명과 사진에서 확인되지 않는 프로그램은 지어내지 마라.
스키마: {"year":"2026","title":"행사/영상 제목 5~8자","tagline":"슬로건 20자 이내","org":"기관명",
"intro_photo":"사진id","outro_photo":"사진id",
"scenes":[{"ttl":"장면 제목 10자 이내","sub":"세부 내용 30자 이내","photo":"사진id"}],
"outro":["마무리 1행 12자 이내","마무리 2행 12자 이내","마무리 문장 35자 이내"]}
규칙:
- scenes는 %d~%d개. 폴더가 여러 개면 폴더 하나가 장면 하나가 되게 하고, 폴더명을 제목에 반영한다.
- 각 장면 photo는 장면 주제와 사진 내용이 가장 잘 맞는 사진 id. 같은 사진 중복은 피한다.
- intro_photo는 밝고 대표적인 사진, outro_photo는 화목한 단체/가족 사진.
- 문구 분위기: %s. 영상 길이: %d초.
요구사항: %s
기관/단체명(비어 있으면 요구사항에서 찾아라): %s
%s"""


def gemini(parts):
    key = api_key()
    if not key:
        raise RuntimeError('GEMINI_API_KEY가 설정되어 있지 않습니다.')
    last = None
    for m in MODELS:
        req = urllib.request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent',
            json.dumps({'contents': [{'parts': parts}], 'generationConfig': {'responseMimeType': 'application/json'}}).encode(),
            {'Content-Type': 'application/json', 'x-goog-api-key': key})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.loads(r.read())
            u = {'model': m, **{k: resp.get('usageMetadata', {}).get(k, 0) for k in ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount')}}
            with open(os.path.join(JOBS, 'usage.log'), 'a', encoding='utf-8') as lf:  # 호출별 토큰 사용량 기록
                lf.write(time.strftime('%Y-%m-%d %H:%M:%S ') + json.dumps(u) + '\n')
            return json.loads(resp['candidates'][0]['content']['parts'][0]['text']), u
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            last = f'{m}: {e}'
    raise RuntimeError('AI 호출 실패(사용량 한도일 수 있어요. 잠시 후 다시 시도): ' + str(last))


def clean(s):  # LLM이 가끔 한글을 한자로 바꿔 쓴다("온"->"溫")
    return re.sub(r'[一-鿿]', '', str(s)).strip()


def max_scenes(length):
    return max(3, min(40, int((length - 8) / 2.2)))


@app.post('/api/plan')
def plan():
    b = request.json
    m = meta_of(b['job'])
    if not m['photos']:
        return jsonify(error='사진을 먼저 올려 주세요.'), 400
    length = max(15, min(600, int(b.get('length', 30))))
    folders = {p['folder'] for p in m['photos'] if p['folder']}
    hi = max_scenes(length)
    lo = min(max(3, len(folders)), hi, len(m['photos']))
    hi = max(lo, min(hi, len(m['photos'])))
    revise = ''
    if b.get('ratio') == 'portrait':  # 세로 화면은 폭이 좁아 긴 문구가 줄바꿈된다
        revise = ('세로(9:16) 영상이다. title은 6자 이내, 장면 ttl은 8자 이내, 마무리 1·2행은 10자 이내로 짧게 쓰고, '
                  '사진은 사람이나 주요 대상이 가운데에 있는 것을 우선 골라라(좌우가 잘린다).\n')
    if (b.get('narr') or {}).get('on'):  # 내레이션: 장면 길이에 맞는 글자 수 예산을 준다
        sl = narr_slots(length, lo); cap = lambda a, b_: max(4, int((b_ - a - 0.6) * CPS))
        revise += ('내레이션(성우가 읽는 말)도 써라. intro_narr(공백 제외 %d자 이내), 각 장면에 narr(공백 제외 %d자 이내), '
                   'outro_narr(공백 제외 %d자 이내, 감사·마무리 인사) 필드를 반드시 모두 추가한다. 화면 글자를 그대로 읽지 말고 듣기 편한 존댓말 한 문장으로.\n'
                   % (cap(*sl[0]), cap(*sl[1]), cap(*sl[-1])))
    if b.get('prev') and b.get('revise'):
        revise += '이전 구성(JSON): %s\n이 구성을 아래 수정 요청에 맞게 고쳐서 같은 스키마로 다시 답해라: %s' % (
            json.dumps(b['prev'], ensure_ascii=False), b['revise'])
    photos = m['photos']
    if len(photos) > MAX_VISION:
        photos = [photos[int(i * len(photos) / MAX_VISION)] for i in range(MAX_VISION)]
    parts = [{'text': PROMPT % (lo, hi, b.get('mood', '밝고 경쾌하게'), length, b.get('brief') or '(없음)', b.get('org') or '', revise)}]
    for p in photos:
        parts.append({'text': f'사진id={p["id"]} 폴더={p["folder"] or "(없음)"} 파일={p["path"].split("/")[-1]}'})
        parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(
            open(os.path.join(jobdir(b['job']), 'thumbs', p['id'] + '.jpg'), 'rb').read()).decode()}})
    try:
        d, usage = gemini(parts)
        ids = [p['id'] for p in m['photos']]
        fb = itertools.cycle(ids)
        pick = lambda v: v if v in ids else next(fb)
        out = {'year': clean(d.get('year', '')), 'title': clean(d['title']) or '홍보영상', 'tagline': clean(d.get('tagline', '')),
               'org': clean(d.get('org', '')) or (b.get('org') or ''),
               'intro_photo': pick(d.get('intro_photo')), 'outro_photo': pick(d.get('outro_photo')),
               'scenes': [{'ttl': clean(s['ttl']), 'sub': clean(s.get('sub', '')), 'photo': pick(s.get('photo')),
                           'narr': clean(s.get('narr', ''))} for s in d['scenes'][:hi]],
               'outro': [clean(x) for x in (d.get('outro') or [])[:3]] + [''] * 3,
               'intro_narr': clean(d.get('intro_narr', '')), 'outro_narr': clean(d.get('outro_narr', ''))}
        out['outro'] = out['outro'][:3]
        prev = b.get('prev') or {}  # 수정 요청 시 사용자가 고른 전환 효과는 유지
        for k in ('transition', 'outro_tr'):
            if prev.get(k):
                out[k] = prev[k]
        for s, ps in zip(out['scenes'], prev.get('scenes') or []):
            if ps.get('tr'):
                s['tr'] = ps['tr']
        if len(out['scenes']) < 1:
            raise RuntimeError('AI가 장면을 만들지 못했습니다. 다시 시도해 주세요.')
    except (RuntimeError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 502
    json.dump(out, open(os.path.join(jobdir(b['job']), 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return jsonify(plan=out, usage=usage)


# ---------- 내레이션 (edge-tts, 무료·키 불필요) ----------
VOICES = {'sunhi': 'ko-KR-SunHiNeural', 'injoon': 'ko-KR-InJoonNeural', 'hyunsu': 'ko-KR-HyunsuMultilingualNeural'}
CPS = 4.6  # 보통 속도에서 초당 글자 수(공백 제외). edge-tts 한국어 3종 실측 4.6~4.9


def narr_slots(length, n):
    """말할 수 있는 구간 [(시작, 끝)]: 오프닝, 장면 1..n, 엔딩. 장면 전환 직후 0.4초 뒤 시작, 다음 장면 0.1초 전 끝."""
    st = (length - 8) / n
    return ([(0.5, 3.5)] + [(3.6 + st * i + 0.4, 3.6 + st * (i + 1) - 0.1) for i in range(n)]
            + [(3.6 + st * n + 0.5, length - 0.3)])


def narr_texts(p):  # 내레이션이 비어 있으면 화면 문구로 대신 읽는다
    return ([p.get('intro_narr') or f"{p['title']}. {p['tagline']}"]
            + [s.get('narr') or f"{s['ttl']}. {s['sub']}" for s in p['scenes']]
            + [p.get('outro_narr') or ' '.join(p['outro'][:2])])


def duration(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                capture_output=True, text=True).stdout.strip())


def tts_many(job, items):
    """[(text, voice_key, rate%)] -> [(파일명, 길이)]. 같은 문장·목소리·속도는 캐시를 재사용."""
    import edge_tts, hashlib, asyncio
    out, todo = [], []
    for text, v, r in items:
        name = 'tts_' + hashlib.sha1(f'{text}|{v}|{r}'.encode()).hexdigest()[:12] + '.mp3'
        path = os.path.join(jobdir(job), 'assets', name)
        if not os.path.exists(path):
            todo.append(edge_tts.Communicate(text, VOICES.get(v, VOICES['sunhi']), rate=f'{r:+d}%').save(path))
        out.append((name, path))

    async def run():
        await asyncio.gather(*todo)
    try:
        if todo:
            asyncio.run(run())
    except Exception as e:
        raise RuntimeError('내레이션 음성을 만들지 못했습니다. 인터넷 연결을 확인해 주세요. (%s)' % e)
    return [(name, duration(path)) for name, path in out]


def make_narration(job, p, length, narr):
    """구간마다 음성을 만들고, 구간보다 길면 최대 +40%까지 빠르게 다시 만든다. 그래도 길면 구간 끝에서 잘린다."""
    slots, texts = narr_slots(length, len(p['scenes'])), narr_texts(p)
    v, base = narr.get('voice', 'sunhi'), int(narr.get('rate', 0))
    keep = [i for i, t in enumerate(texts) if t.strip()]
    res = dict(zip(keep, tts_many(job, [(texts[i], v, base) for i in keep])))
    slow = [i for i in keep if res[i][1] > slots[i][1] - slots[i][0]]
    if slow:
        rates = {i: min(40, base + int((res[i][1] / (slots[i][1] - slots[i][0]) - 1) * 100) + 5) for i in slow}
        res.update(zip(slow, tts_many(job, [(texts[i], v, rates[i]) for i in slow])))
    clips, cut = [], []
    for i in keep:
        name, d = res[i]; room = slots[i][1] - slots[i][0]
        if d > room + 0.05:
            cut.append('오프닝' if i == 0 else '엔딩' if i == len(slots) - 1 else f'{i}번 장면')
        clips.append((round(slots[i][0], 2), round(min(d, room), 2), name))
    return clips, cut


@app.post('/api/tts')
def tts():
    b = request.json
    try:
        (name, d), = tts_many(b['job'], [(b['text'][:300], b.get('voice', 'sunhi'), int(b.get('rate', 0)))])
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    return jsonify(url=f'/jobs/{b["job"]}/assets/{name}', dur=round(d, 2))


# ---------- 렌더 ----------
# 화면 전환 종류. 'mix'(기본)는 MIX 순서대로 돌아가며 섞는다. 장면별 지정(scene.tr)이 전체 설정보다 우선.
TRANSITIONS = ['panel', 'slide', 'fade', 'zoom', 'blur', 'wipe', 'wipe-up', 'split', 'circle', 'diagonal']
MIX = ['panel', 'wipe', 'zoom', 'circle', 'slide', 'split', 'fade', 'diagonal', 'wipe-up', 'blur']
TIMELINE_JS = '''<script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      const starts = __STARTS__, d = __DUR__, os = __OS__, total = __TOTAL__, TR = __TRS__;
      const CLIP = {
        wipe: ["inset(0 0 0 100%)", "inset(0 0 0 0%)"], "wipe-up": ["inset(100% 0 0 0)", "inset(0% 0 0 0)"],
        split: ["inset(0 50% 0 50%)", "inset(0 0% 0 0%)"], circle: ["circle(0% at 50% 50%)", "circle(150% at 50% 50%)"],
        diagonal: ["polygon(0% 0%, 0% 0%, -50% 100%, -50% 100%)", "polygon(0% 0%, 150% 0%, 100% 100%, -50% 100%)"] };
      function trans(kind, el, s, i) {
        if (kind === "panel") tl.fromTo(["#p_a", "#p_b", "#p_c"][i % 3], { x: "-100%" }, { x: "100%", duration: 0.9, ease: "power2.inOut" }, s - 0.35);
        else if (CLIP[kind]) tl.fromTo(el, { clipPath: CLIP[kind][0] }, { clipPath: CLIP[kind][1], duration: 0.85, ease: "power3.inOut" }, s);
        else if (kind === "slide") tl.fromTo(el, { xPercent: 100 }, { xPercent: 0, duration: 0.8, ease: "power3.inOut" }, s);
        else if (kind === "zoom") tl.fromTo(el, { opacity: 0, scale: 1.25 }, { opacity: 1, scale: 1, duration: 0.9, ease: "power3.out" }, s);
        else if (kind === "blur") tl.fromTo(el, { opacity: 0, filter: "blur(40px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.9, ease: "power2.out" }, s);
        else tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "power1.inOut" }, s);
      }

      tl.fromTo("#b1", { scale: 0 }, { scale: 1, duration: 1.0, ease: "back.out(1.6)" }, 0.05);
      tl.fromTo("#b2", { scale: 0 }, { scale: 1, duration: 1.0, ease: "back.out(1.6)" }, 0.2);
      tl.fromTo("#b3", { scale: 0 }, { scale: 1, duration: 0.8, ease: "back.out(2)" }, 0.35);
      tl.fromTo("#yr", { opacity: 0, y: -30 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 0.3);
      tl.fromTo("#big", { opacity: 0, y: 70, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: "power4.out" }, 0.5);
      tl.fromTo("#hanja", { opacity: 0 }, { opacity: 1, duration: 0.7 }, 1.2);
      tl.fromTo("#org", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 1.6);
      tl.to("#intro .photo", { scale: 1.08, duration: 4.4, ease: "none" }, 0);
      tl.to("#b1", { x: 40, y: 30, duration: 4, ease: "sine.inOut" }, 1);

      starts.forEach((s, i) => {
        const id = "#s" + (i + 1);
        trans(TR[i], id, s, i);
        const zoomIn = i % 2 === 0;
        tl.fromTo(id + " .photo", { scale: zoomIn ? 1.0 : 1.14, x: zoomIn ? 0 : 24 }, { scale: zoomIn ? 1.14 : 1.0, x: zoomIn ? -24 : 0, duration: d, ease: "none" }, s);
        tl.fromTo(id + " .num", { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.6, ease: "power3.out" }, s + 0.35);
        tl.fromTo(id + " .bar", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power3.out" }, s + 0.5);
        tl.fromTo(id + " .ttl", { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.6, ease: "power4.out" }, s + 0.55);
        tl.fromTo(id + " .sub", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, s + 0.8);
        tl.fromTo(id + " .tag", { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.5 }, s + 0.9);
      });

      trans(TR[starts.length], "#outro", os, starts.length);
      tl.fromTo("#ob1", { scale: 0 }, { scale: 1, duration: 0.9, ease: "back.out(1.6)" }, os + 0.5);
      tl.fromTo("#ob2", { scale: 0 }, { scale: 1, duration: 0.9, ease: "back.out(1.6)" }, os + 0.6);
      tl.fromTo("#o1", { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.7, ease: "power4.out" }, os + 0.7);
      tl.fromTo("#o2", { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.7, ease: "power4.out" }, os + 1.0);
      tl.fromTo("#o3", { opacity: 0 }, { opacity: 1, duration: 0.7 }, os + 1.6);
      tl.to("#outro .photo", { scale: 1.08, duration: 4.4, ease: "none" }, os);
      tl.to("#root", { opacity: 0, duration: 0.5, ease: "power1.in" }, total - 0.5);
      tl.fromTo("#progress", { scaleX: 0 }, { scaleX: 1, duration: total, ease: "none" }, 0);

      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>'''


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


def build(job, p, length, audio, name='index.html', extra='', ratio='landscape', narr=None):
    e = html.escape
    base = open(os.path.join(HERE, 'base_template.html'), encoding='utf-8').read()
    css = re.search(r'<style>.*?</style>', base, re.S).group(0)
    portrait = ratio == 'portrait'
    W, H = (1080, 1920) if portrait else (1920, 1080)
    if portrait:
        css += '\n    ' + PORTRAIT_CSS
    tl_ = max(1, len(p['title']))
    big_fs = min(190, int(940 / tl_)) if portrait else (230 if tl_ <= 8 else 170)
    n = len(p['scenes'])
    step = (length - 8) / n; dur = round(step + 0.6, 2)
    starts = [round(3.6 + step * i, 2) for i in range(n)]
    os_ = round(3.6 + step * n, 2); total = float(length)
    org = e(p['org'])
    scenes = ''.join(f'''
      <div id="s{i+1}" class="scene clip" data-start="{starts[i]}" data-duration="{dur}" data-track-index="1" style="--c:{COLORS[i%3]}">
        <img class="photo" src="assets/{s['photo']}.jpg" alt="" /><div class="shade"></div>
        <div class="num">{i+1:02d}</div><div class="bar"></div>
        <div class="ttl">{e(s['ttl'])}</div><div class="sub">{e(s['sub'])}</div><div class="tag">{org}</div>
      </div>''' for i, s in enumerate(p['scenes']))
    t = e(p['title']); o = [e(x) for x in p['outro']]
    clips, cut = make_narration(job, p, length, narr) if narr and narr.get('on') else ([], [])
    audio = (f'<audio id="bgm" src="assets/bgm.mp3" data-start="0" data-duration="{audio["dur"]}" data-media-start="{audio["start"]}" '
             f'data-track-index="9" data-volume="{0.25 if clips else 0.7}" data-fade-in="1" data-fade-out="2"></audio>') if audio else ''
    audio += ''.join(f'\n      <audio id="nr{i}" src="assets/{f}" data-start="{s}" data-duration="{d}" data-track-index="{20 + i}" data-volume="1"></audio>'
                     for i, (s, d, f) in enumerate(clips))  # 내레이션이 있으면 배경음악을 0.25로 낮춘다
    body = f'''
      <div id="intro" class="scene clip" data-start="0" data-duration="4.4" data-track-index="0">
        <img class="photo" src="assets/{p['intro_photo']}.jpg" alt="" />
        <div class="blob" id="b1" style="width:620px;height:620px;left:-160px;top:-140px;background:var(--coral);opacity:.9"></div>
        <div class="blob" id="b2" style="width:380px;height:380px;right:-90px;bottom:-110px;background:var(--sun);opacity:.95"></div>
        <div class="blob" id="b3" style="width:160px;height:160px;right:300px;top:90px;background:var(--mint);opacity:.9"></div>
        <div class="yr" id="yr">{e(p['year'])}</div>
        <div class="big" id="big" style="font-size:{big_fs}px"><span class="o">{t[:1]}</span>{t[1:]}</div>
        <div class="hanja" id="hanja">{e(p['tagline'])}</div>
        <div class="org" id="org"><b>{org}</b></div>
      </div>{scenes}
      <div id="outro" class="scene clip" data-start="{os_}" data-duration="4.4" data-track-index="2">
        <img class="photo" src="assets/{p['outro_photo']}.jpg" alt="" />
        <div class="blob" id="ob1" style="width:520px;height:520px;right:-120px;top:-140px;background:var(--coral);opacity:.9"></div>
        <div class="blob" id="ob2" style="width:300px;height:300px;left:-80px;bottom:-90px;background:var(--mint);opacity:.9"></div>
        <div class="o1" id="o1">{o[0]}</div><div class="o2" id="o2">{o[1]}</div><div class="o3" id="o3">{o[2]}</div>
      </div>
      <div class="panel" id="p_a" style="background:var(--coral)"></div>
      <div class="panel" id="p_b" style="background:var(--sun)"></div>
      <div class="panel" id="p_c" style="background:var(--mint)"></div>
      <div id="progress"></div>{audio}'''
    glob = p.get('transition') or 'mix'
    pick = lambda i, v: v if v in TRANSITIONS else glob if glob in TRANSITIONS else MIX[i % len(MIX)]
    trs = [pick(i, s.get('tr')) for i, s in enumerate(p['scenes'])] + [pick(n, p.get('outro_tr'))]
    js = (TIMELINE_JS.replace('__STARTS__', json.dumps(starts)).replace('__DUR__', str(dur)).replace('__OS__', str(os_))
          .replace('__TOTAL__', str(total)).replace('__TRS__', json.dumps(trs)))
    open(os.path.join(jobdir(job), name), 'w', encoding='utf-8').write(f'''<!doctype html>
<html lang="ko" data-resolution="{'portrait' if portrait else 'landscape'}">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/gsap.min.js"></script>
    {css}
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">{body}
    </div>
    {js}{extra}
  </body>
</html>''')
    return cut


def run_render(job):
    s = _status[job]
    with _render_lock:
        s.update(state='running', pct=0)
        out = os.path.join(jobdir(job), 'output.mp4')
        if os.path.exists(out):
            os.remove(out)
        pr = subprocess.Popen([shutil.which('npx') or 'npx', '-y', 'hyperframes', 'render', '-o', 'output.mp4'], cwd=jobdir(job),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        tail = []
        for line in pr.stdout:
            mm = re.search(r'"pct":(\d+)', line)
            if mm:
                s['pct'] = int(mm.group(1))
            tail = (tail + [line.rstrip()])[-8:]
        pr.wait()
        ok = pr.returncode == 0 and os.path.exists(out)
        s.update(state='done' if ok else 'error', pct=100 if ok else s['pct'], log='\n'.join(tail))


def build_from_request(b, **kw):
    m = meta_of(b['job'])
    length = max(15, min(600, int(b.get('length', 30))))
    a = b.get('audio') if m['audio'] else None  # {start, dur}: 음악에서 쓸 구간(초)
    if a:
        a = {'start': max(0.0, float(a['start'])), 'dur': max(1.0, min(float(a['dur']), length))}
    return build(b['job'], b['plan'], length, a, ratio='portrait' if b.get('ratio') == 'portrait' else 'landscape',
                 narr=b.get('narr'), **kw)


@app.post('/api/render')
def render():
    b = request.json
    try:
        cut = build_from_request(b)
        save_json(b['job'], 'plan.json', b['plan'])  # 렌더 시 화면에서 고친 구성도 저장
    except (KeyError, IndexError, ValueError) as e:
        return jsonify(error='구성 정보가 올바르지 않습니다: %s' % e), 400
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    _status[b['job']] = {'state': 'queued', 'pct': 0}
    threading.Thread(target=run_render, args=(b['job'],), daemon=True).start()
    return jsonify(ok=True, cut=cut)


# 브라우저 미리보기: HyperFrames 엔진 대신 data-start/duration에 맞춰 장면을 보이고 숨기며 GSAP 타임라인을 재생한다.
PREVIEW_JS = '''
    <script>
    (function () {
      const tl = window.__timelines.main, root = document.getElementById("root");
      const clips = [...root.querySelectorAll(":scope > [data-start]")].filter(c => c.tagName !== "AUDIO");
      const auds = [...root.querySelectorAll("audio[data-start]")];   // 배경음악 + 내레이션
      auds.forEach(a => a.volume = Math.min(1, +a.dataset.volume || 1));
      const total = +root.dataset.duration;
      let at = 0, playing = false, t0 = 0;
      function syncAudio(force) {   // 각 오디오를 자기 구간에서만, 맞는 위치로 재생
        auds.forEach(a => {
          const s = +a.dataset.start, d = +a.dataset.duration, inside = playing && at >= s && at < s + d;
          const want = (+a.dataset.mediaStart || 0) + at - s;
          if (!inside) { if (!a.paused) a.pause(); return; }
          if (force || a.paused || Math.abs(a.currentTime - want) > 0.3) a.currentTime = want;
          if (a.paused) a.play().catch(() => {});
        });
      }
      function draw() {
        tl.seek(at, false);
        clips.forEach(c => { const s = +c.dataset.start; c.style.visibility = at >= s && at < s + +c.dataset.duration ? "visible" : "hidden"; });
      }
      function frame() {
        if (!playing) return;
        at = (performance.now() - t0) / 1000;
        if (at >= total) { at = total - 0.001; playing = false; }
        syncAudio(false); draw(); requestAnimationFrame(frame);
      }
      window.__preview = {
        total, get time() { return at; }, get playing() { return playing; },
        play() { if (at >= total - 0.05) at = 0; playing = true; t0 = performance.now() - at * 1000; syncAudio(true); requestAnimationFrame(frame); },
        pause() { playing = false; syncAudio(true); },
        seek(t) { at = Math.max(0, Math.min(total - 0.001, t)); t0 = performance.now() - at * 1000; syncAudio(true); draw(); }
      };
      draw();
    })();
    </script>'''


@app.post('/api/preview')
def preview():
    b = request.json
    try:
        cut = build_from_request(b, name='preview.html', extra=PREVIEW_JS)
    except (KeyError, IndexError, ValueError) as e:
        return jsonify(error='구성 정보가 올바르지 않습니다: %s' % e), 400
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    return jsonify(url=f'/jobs/{b["job"]}/preview.html?t={int(time.time() * 1000)}', cut=cut)


# ---------- 프로젝트 저장 / 불러오기 ----------
def load_json(job, name, default=None):
    f = os.path.join(jobdir(job), name)
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else default


def save_json(job, name, data):
    json.dump(data, open(os.path.join(jobdir(job), name), 'w', encoding='utf-8'), ensure_ascii=False)


@app.post('/api/save')
def save():
    b = request.json
    if not os.path.exists(os.path.join(jobdir(b['job']), 'meta.json')):
        return jsonify(error='프로젝트를 찾을 수 없습니다.'), 404
    if b.get('plan'):
        save_json(b['job'], 'plan.json', b['plan'])
    save_json(b['job'], 'project.json', b.get('settings') or {})
    return jsonify(ok=True, saved=time.strftime('%H:%M'))


@app.get('/api/projects')
def projects():
    out = []
    for j in os.listdir(JOBS) if os.path.isdir(JOBS) else []:
        d = os.path.join(JOBS, j)
        if not re.fullmatch(r'[0-9a-f]{12}', j) or not os.path.exists(os.path.join(d, 'meta.json')):
            continue
        m = meta_of(j)
        if not m['photos']:
            continue
        pl, st = load_json(j, 'plan.json') or {}, load_json(j, 'project.json') or {}
        mt = max(os.path.getmtime(os.path.join(d, f)) for f in ('meta.json', 'plan.json', 'project.json', 'output.mp4')
                 if os.path.exists(os.path.join(d, f)))
        out.append({'job': j, 'title': pl.get('title') or '제목 없음', 'mtime': mt,
                    'updated': time.strftime('%Y-%m-%d %H:%M', time.localtime(mt)),
                    'photos': len(m['photos']), 'thumb': pl.get('intro_photo') or m['photos'][0]['id'],
                    'video': os.path.exists(os.path.join(d, 'output.mp4')), 'length': st.get('length'),
                    'scenes': len(pl.get('scenes', []))})
    return jsonify(projects=sorted(out, key=lambda x: -x['mtime']))


@app.get('/api/project/<job>')
def project(job):
    return jsonify(meta=meta_of(job), plan=load_json(job, 'plan.json'), settings=load_json(job, 'project.json', {}),
                   video=os.path.exists(os.path.join(jobdir(job), 'output.mp4')))


@app.get('/api/status/<job>')
def status(job):
    jobdir(job)
    return jsonify(_status.get(job, {'state': 'none', 'pct': 0}))


@app.get('/jobs/<job>/<path:f>')
def jobfile(job, f):
    return send_from_directory(jobdir(job), f, conditional=True)


@app.get('/')
def index():
    return app.send_static_file('index.html')


if __name__ == '__main__':
    os.makedirs(JOBS, exist_ok=True)
    app.run(port=5000, threaded=True)

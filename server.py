"""홍보영상 제작 웹앱. 업로드(폴더 포함) -> Gemini가 장면/사진 배정 -> HyperFrames 렌더.
실행: GEMINI_API_KEY 환경변수(또는 이 폴더의 .env)를 준비하고 `python server.py` -> http://localhost:5000
WORKER_TOKEN을 설정하면 렌더링을 이 서버에서 하지 않고 대기열에 넣어 두고, PC의 렌더 워커(worker/)가 가져가 처리한다."""
import base64, hmac, html, itertools, json, os, re, shutil, subprocess, threading, time, urllib.error, urllib.parse, urllib.request, uuid
from flask import Flask, abort, jsonify, request, send_from_directory
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, 'jobs')
MODELS = ['gemini-flash-lite-latest', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite']  # 한도 걸리면 다음 모델
COLORS = ['#ff6b4a', '#ffc93c', '#3ddc97']
MAX_VISION = 40  # Gemini에 보여줄 사진 수 상한(초과분은 균등 샘플링)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 워커가 올리는 완성 영상(최대 10분)까지 받는다
_render_lock = threading.Lock()  # 서버에서 직접 렌더할 때 1건씩만
_state_lock = threading.Lock()


def env(name):
    k = os.environ.get(name)
    p = os.path.join(HERE, '.env')
    if not k and os.path.exists(p):
        m = re.search(r'^%s=(.+)$' % name, open(p, encoding='utf-8').read(), re.M)
        k = m and m.group(1).strip().strip('"\'')
    return k


def api_key():
    return env('GEMINI_API_KEY')


WORKER_TOKEN = env('WORKER_TOKEN')  # 있으면 '워커 모드': 렌더링은 PC 워커가 한다


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
"scenes":[{"type":"장면 유형","ttl":"장면 제목 10자 이내","sub":"세부 내용 30자 이내","photo":"사진id", ...유형별 필드}],
"outro":["마무리 1행 12자 이내","마무리 2행 12자 이내","마무리 문장 35자 이내"]}
장면 유형(type)과 유형별 필드:
- "title": ttl, sub, photo. 사업·활동을 소개하는 기본 장면.
- "collage": ttl, sub, photos(같은 주제 사진 id 2~4개). 사진이 여러 장인 활동, 현장 분위기를 보여줄 때.
- "stat": ttl(무엇의 숫자인지 10자 이내), num(숫자만, 예 "320", "1,200"), unit(단위, 예 "명", "회", "%%"), sub, photo.
  요구사항에 실제 숫자가 적혀 있을 때만 쓴다. 숫자를 지어내지 마라.
- "quote": ttl(장면 이름, 화면에는 안 나옴), quote(인용문 40자 이내), who(말한 사람, 예 "참여 어머니"), photo.
  요구사항에 실제 후기·소감이 적혀 있을 때만 그 내용으로 쓴다. 후기를 지어내지 마라.
- "list": ttl, items(3~4개, 각 14자 이내. 일정이면 "3월 입학식"처럼 시기를 앞에), photo. 여러 활동이나 일정을 한 장면에 묶을 때.
규칙:
- scenes는 %d~%d개. 폴더가 여러 개면 폴더 하나가 장면 하나가 되게 하고, 폴더명을 제목에 반영한다.
- 주제와 내용에 맞게 장면 유형을 골라 섞어라. 같은 유형이 3번 넘게 연속되지 않게 하고, 근거 없는 stat·quote는 쓰지 않는다.
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


def normalize_scene(s, ids, pick):
    """AI 결과나 화면에서 고친 장면을 유형별로 정리. 필수 내용이 빠진 유형은 기본(title)으로 되돌린다."""
    t = s.get('type') if s.get('type') in SCENE_TYPES else 'title'
    out = {'type': t, 'ttl': clean(s.get('ttl', '')), 'sub': clean(s.get('sub', '')), 'photo': pick(s.get('photo')),
           'narr': clean(s.get('narr', ''))}
    if s.get('tr'):
        out['tr'] = s['tr']
    if t == 'collage':
        ps = [x for x in dict.fromkeys(s.get('photos') or []) if x in ids][:4]
        if s.get('photo') in ids and s['photo'] not in ps:
            ps = [s['photo']] + ps[:3]
        if len(ps) >= 2:
            out.update(photos=ps, photo=ps[0])
        else:
            out['type'] = 'title'
    elif t == 'stat':
        num = re.sub(r'[^0-9.,]', '', str(s.get('num', '')))[:9]
        if re.search(r'\d', num):
            out.update(num=num, unit=clean(s.get('unit', ''))[:6])
        else:
            out['type'] = 'title'
    elif t == 'quote':
        q = clean(s.get('quote', '')).strip('"“”\'')
        if q:
            out.update(quote=q[:80], who=clean(s.get('who', ''))[:20])
            out['ttl'] = out['ttl'] or q[:10]
        else:
            out['type'] = 'title'
    elif t == 'list':
        items = [clean(x)[:24] for x in (s.get('items') or []) if clean(x)][:5]
        if len(items) >= 2:
            out['items'] = items
        else:
            out['type'] = 'title'
    return out


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
               'scenes': [normalize_scene(s, ids, pick) for s in d['scenes'][:hi]],
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
            + [s.get('narr') or scene_speech(s) for s in p['scenes']]
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
TRANSITIONS = ['panel', 'slide', 'fade', 'zoom', 'blur', 'wipe', 'wipe-up', 'split', 'circle', 'diagonal', 'whip', 'flash', 'spin']
MIX = ['panel', 'wipe', 'zoom', 'circle', 'whip', 'slide', 'split', 'flash', 'fade', 'diagonal', 'spin', 'wipe-up', 'blur']
TIMELINE_JS = '''<script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      const starts = __STARTS__, d = __DUR__, os = __OS__, total = __TOTAL__, TR = __TRS__, TYPES = __TYPES__;
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
        else if (kind === "whip") tl.fromTo(el, { xPercent: 100, filter: "blur(24px)" }, { xPercent: 0, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }, s);
        else if (kind === "flash") {   // 하얗게 번쩍인 뒤 살짝 줌아웃
          tl.fromTo("#flash", { opacity: 1 }, { opacity: 0, duration: 0.55, ease: "power2.out", immediateRender: false }, s);
          tl.fromTo(el, { scale: 1.2 }, { scale: 1, duration: 0.7, ease: "expo.out" }, s);
        }
        else if (kind === "spin") tl.fromTo(el, { scale: 0.4, rotation: -10, opacity: 0 }, { scale: 1, rotation: 0, opacity: 1, duration: 0.6, ease: "back.out(1.4)" }, s);
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
        const T = TYPES[i], zoomIn = i % 2 === 0;
        const up = (sel, at, y = 50, dd = 0.6) => tl.fromTo(id + " " + sel, { opacity: 0, y }, { opacity: 1, y: 0, duration: dd, ease: "power4.out" }, s + at);
        if (T === "collage") {
          tl.fromTo(id + " .tile", { opacity: 0, scale: 0.86 }, { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.5)", stagger: 0.14 }, s + 0.15);
          tl.fromTo(id + " .tile img", { scale: 1.16 }, { scale: 1.0, duration: d, ease: "none" }, s);
          tl.fromTo(id + " .cbar", { scaleX: 0 }, { scaleX: 1, duration: d, ease: "none" }, s);
          up(".ttl", 0.55); up(".sub", 0.8, 30);
          return;
        }
        tl.fromTo(id + " .photo", { scale: zoomIn ? 1.0 : 1.14, x: zoomIn ? 0 : 24 }, { scale: zoomIn ? 1.14 : 1.0, x: zoomIn ? -24 : 0, duration: d, ease: "none" }, s);
        tl.fromTo(id + " .tag", { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.5 }, s + 0.9);
        if (T === "stat") {
          up(".stat-l", 0.3, -30);
          tl.fromTo(id + " .stat-n", { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, s + 0.35);
          tl.fromTo(id + " .strip", { yPercent: 0 }, { yPercent: (k, el) => -10 * +el.dataset.d, duration: 1.6, ease: "power3.out", stagger: 0.08 }, s + 0.4);
          up(".unit", 1.3, 20, 0.5); up(".stat-s", 1.5, 30);
        } else if (T === "quote") {
          tl.fromTo(id + " .qmark", { opacity: 0, scale: 0.3 }, { opacity: 1, scale: 1, duration: 0.7, ease: "back.out(2)" }, s + 0.3);
          up(".qtext", 0.6, 40, 0.9); up(".qwho", 1.4, 20);
        } else if (T === "list") {
          tl.fromTo(id + " .lpanel", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out" }, s + 0.1);
          up(".ttl", 0.35);
          tl.fromTo(id + " .bar", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power3.out" }, s + 0.5);
          tl.fromTo(id + " .items li", { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.5, ease: "power3.out", stagger: Math.min(0.45, (d - 1.8) / 5) }, s + 0.8);
        } else {
          tl.fromTo(id + " .num", { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.6, ease: "power3.out" }, s + 0.35);
          tl.fromTo(id + " .bar", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power3.out" }, s + 0.5);
          up(".ttl", 0.55); up(".sub", 0.8, 30, 0.55);
        }
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


# ---------- 장면 유형 ----------
# title(기본: 번호·제목·설명) / collage(사진 2~4장) / stat(큰 숫자) / quote(후기·인용문) / list(목록·일정)
SCENE_TYPES = ['title', 'collage', 'stat', 'quote', 'list']
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
      .qtext { position: absolute; left: 120px; top: 360px; width: 1080px; font-size: 76px; font-weight: 800; line-height: 1.38; letter-spacing: -0.03em; word-break: keep-all; }
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


def digits_html(num):
    """'1,200' -> 자릿수마다 0~9 띠(strip). 타임라인이 띠를 올려 숫자가 굴러가며 올라간다(렌더 시 결정적)."""
    out = []
    for ch in num:
        if ch.isdigit():
            out.append('<span class="dg"><span class="strip" data-d="%s">%s</span></span>' % (ch, ''.join(f'<b>{d}</b>' for d in range(10))))
        else:
            out.append(f'<span>{html.escape(ch)}</span>')
    return ''.join(out)


def scene_html(i, s, org, start, dur):
    e = html.escape
    t = s.get('type') if s.get('type') in SCENE_TYPES else 'title'
    head = f'<div id="s{i+1}" class="scene clip t-{t}" data-start="{start}" data-duration="{dur}" data-track-index="1" style="--c:{COLORS[i%3]}">'
    img = f'<img class="photo" src="assets/{s["photo"]}.jpg" alt="" />'
    tag = f'<div class="tag">{org}</div>'
    if t == 'collage':
        ps = (s.get('photos') or [s['photo']])[:4]
        tiles = ''.join(f'<div class="tile"><img src="assets/{p}.jpg" alt="" /></div>' for p in ps)
        body = (f'<div class="grid g{max(2, len(ps))}">{tiles}</div>'
                f'<div class="ttl">{e(s["ttl"])}</div><div class="sub">{e(s.get("sub", ""))}</div><div class="cbar"></div>')
    elif t == 'stat':
        body = (f'{img}<div class="dim"></div><div class="stat-l">{e(s["ttl"])}</div>'
                f'<div class="stat-n">{digits_html(s["num"])}<span class="unit">{e(s.get("unit", ""))}</span></div>'
                f'<div class="stat-s">{e(s.get("sub", ""))}</div>{tag}')
    elif t == 'quote':
        who = f'— {e(s["who"])}' if s.get('who') else ''
        body = (f'{img}<div class="qshade"></div><div class="qmark">“</div>'
                f'<div class="qtext">{e(s["quote"])}</div><div class="qwho">{who}</div>{tag}')
    elif t == 'list':
        lis = ''.join(f'<li><i></i><span>{e(x)}</span></li>' for x in s['items'][:5])
        body = (f'{img}<div class="lpanel"></div><div class="ttl">{e(s["ttl"])}</div><div class="bar"></div>'
                f'<ul class="items">{lis}</ul>{tag}')
    else:
        body = (f'{img}<div class="shade"></div><div class="num">{i+1:02d}</div><div class="bar"></div>'
                f'<div class="ttl">{e(s["ttl"])}</div><div class="sub">{e(s.get("sub", ""))}</div>{tag}')
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


def build(job, p, length, audio, name='index.html', extra='', ratio='landscape', narr=None):
    e = html.escape
    base = open(os.path.join(HERE, 'base_template.html'), encoding='utf-8').read()
    css = re.search(r'<style>.*?</style>', base, re.S).group(0) + '\n    ' + SCENE_CSS
    portrait = ratio == 'portrait'
    W, H = (1080, 1920) if portrait else (1920, 1080)
    if portrait:
        css += '\n    ' + PORTRAIT_CSS + '\n    ' + PORTRAIT_SCENE_CSS
    tl_ = max(1, len(p['title']))
    big_fs = min(190, int(940 / tl_)) if portrait else (230 if tl_ <= 8 else 170)
    n = len(p['scenes'])
    step = (length - 8) / n; dur = round(step + 0.6, 2)
    starts = [round(3.6 + step * i, 2) for i in range(n)]
    os_ = round(3.6 + step * n, 2); total = float(length)
    org = e(p['org'])
    scenes = ''.join(scene_html(i, s, org, starts[i], dur) for i, s in enumerate(p['scenes']))
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
      <div id="flash" style="position:absolute;inset:0;background:#fff;opacity:0;z-index:55;pointer-events:none"></div>
      <div id="progress"></div>{audio}'''
    glob = p.get('transition') or 'mix'
    pick = lambda i, v: v if v in TRANSITIONS else glob if glob in TRANSITIONS else MIX[i % len(MIX)]
    trs = [pick(i, s.get('tr')) for i, s in enumerate(p['scenes'])] + [pick(n, p.get('outro_tr'))]
    js = (TIMELINE_JS.replace('__STARTS__', json.dumps(starts)).replace('__DUR__', str(dur)).replace('__OS__', str(os_))
          .replace('__TOTAL__', str(total)).replace('__TRS__', json.dumps(trs))
          .replace('__TYPES__', json.dumps([s.get('type') if s.get('type') in SCENE_TYPES else 'title' for s in p['scenes']])))
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


# 렌더 상태는 작업 폴더의 render.json에 둔다(서버를 재시작해도 대기열이 남도록).
# {state: queued|running|done|error, pct, log, rev(렌더 요청마다 새 값), queued_at, updated}
def get_status(job):
    return load_json(job, 'render.json') or {'state': 'none', 'pct': 0}


def set_status(job, only_rev=None, **kw):
    """only_rev를 주면 그 렌더 요청이 아직 최신일 때만 바꾼다(사용자가 그 사이 다시 렌더를 누른 경우 무시)."""
    with _state_lock:
        s = get_status(job)
        if only_rev is not None and s.get('rev') != only_rev:
            return False
        s.update(kw, updated=time.time())
        f = os.path.join(jobdir(job), 'render.json')
        with open(f + '.tmp', 'w', encoding='utf-8') as fp:
            json.dump(s, fp, ensure_ascii=False)
        os.replace(f + '.tmp', f)
        return True


def run_render(job, rev):
    with _render_lock:
        set_status(job, rev, state='running', pct=0)
        out = os.path.join(jobdir(job), 'output.mp4')
        if os.path.exists(out):
            os.remove(out)
        pr = subprocess.Popen([shutil.which('npx') or 'npx', '-y', 'hyperframes', 'render', '-o', 'output.mp4'], cwd=jobdir(job),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        tail, pct = [], 0
        for line in pr.stdout:
            mm = re.search(r'"pct":(\d+)', line)
            if mm and int(mm.group(1)) != pct:
                pct = int(mm.group(1)); set_status(job, rev, pct=pct)
            tail = (tail + [line.rstrip()])[-8:]
        pr.wait()
        ok = pr.returncode == 0 and os.path.exists(out)
        set_status(job, rev, state='done' if ok else 'error', pct=100 if ok else pct, log='\n'.join(tail))


def build_from_request(b, **kw):
    m = meta_of(b['job'])
    length = max(15, min(600, int(b.get('length', 30))))
    a = b.get('audio') if m['audio'] else None  # {start, dur}: 음악에서 쓸 구간(초)
    if a:
        a = {'start': max(0.0, float(a['start'])), 'dur': max(1.0, min(float(a['dur']), length))}
    ids = [x['id'] for x in m['photos']]
    pick = lambda v: v if v in ids else ids[0]
    b['plan']['scenes'] = [normalize_scene(s, ids, pick) for s in b['plan']['scenes']]
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
    rev = uuid.uuid4().hex[:8]
    set_status(b['job'], state='queued', pct=0, log='', rev=rev, queued_at=time.time())
    if not WORKER_TOKEN:
        threading.Thread(target=run_render, args=(b['job'], rev), daemon=True).start()
    return jsonify(ok=True, cut=cut)


# ---------- PC 렌더 워커용 API (WORKER_TOKEN 설정 시) ----------
# 워커가 몇 초마다 /claim으로 일감을 묻고(PC -> 서버 방향이라 공유기 포트 개방 불필요),
# 받은 파일로 렌더한 뒤 /progress로 진행률, /done으로 완성 영상을 올린다.
STALE = 600  # 진행 보고가 이 시간(초) 동안 없으면 워커가 꺼진 것으로 보고 다시 대기열로
_worker = {'seen': 0.0, 'name': ''}


def worker_auth():
    if not WORKER_TOKEN:
        abort(404)
    got = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if not hmac.compare_digest(got.encode(), WORKER_TOKEN.encode()):
        abort(401)
    _worker.update(seen=time.time(), name=urllib.parse.unquote(request.headers.get('X-Worker-Name', ''))[:40])


def worker_online():
    return time.time() - _worker['seen'] < 30


@app.get('/api/worker/ping')
def worker_ping():  # 설치할 때 주소·토큰이 맞는지 확인용
    worker_auth()
    return jsonify(ok=True)


@app.get('/worker.zip')
def worker_zip():
    """PC 렌더 워커 설치 파일 묶음. 이 서버 주소를 미리 넣어 두어 설치 때 토큰만 입력하면 된다."""
    if not WORKER_TOKEN:
        abort(404)
    import io, zipfile
    buf, src = io.BytesIO(), os.path.join(HERE, 'worker')
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(src)):
            if f != 'config.json' and os.path.isfile(os.path.join(src, f)):
                z.write(os.path.join(src, f), 'createMovie-worker/' + f)
        z.writestr('createMovie-worker/server.txt', request.host_url.rstrip('/'))
    buf.seek(0)
    return app.response_class(buf.read(), mimetype='application/zip',
                              headers={'Content-Disposition': 'attachment; filename=createMovie-worker.zip'})


@app.post('/api/worker/claim')
def worker_claim():
    worker_auth()
    now, cands = time.time(), []
    for j in os.listdir(JOBS) if os.path.isdir(JOBS) else []:
        if not re.fullmatch(r'[0-9a-f]{12}', j):
            continue
        s = get_status(j)
        if s['state'] == 'queued' or (s['state'] == 'running' and now - s.get('updated', 0) > STALE):
            cands.append((s.get('queued_at', 0), j, s['rev']))
    for _, j, rev in sorted(cands):
        if set_status(j, rev, state='running', pct=0):
            page = open(os.path.join(jobdir(j), 'index.html'), encoding='utf-8').read()
            files = ['index.html'] + sorted(set(re.findall(r'(?:src|href)="(assets/[^"?#]+)"', page)))
            return jsonify(job=j, rev=rev, files=files)
    return jsonify(job=None)


@app.post('/api/worker/progress/<job>')
def worker_progress(job):
    worker_auth()
    ok = set_status(job, request.args.get('rev', ''), pct=max(0, min(99, int((request.json or {}).get('pct', 0)))))
    return jsonify(ok=ok, cancel=not ok)  # cancel: 사용자가 다시 렌더를 눌러 이 작업은 필요 없어짐


@app.post('/api/worker/done/<job>')
def worker_done(job):
    worker_auth()
    rev = request.args.get('rev', '')
    if get_status(job).get('rev') != rev:
        return jsonify(ok=False, cancel=True)
    tmp = os.path.join(jobdir(job), 'output.part')
    with open(tmp, 'wb') as f:
        shutil.copyfileobj(request.stream, f, 1024 * 1024)
    if os.path.getsize(tmp) < 1000:
        os.remove(tmp)
        set_status(job, rev, state='error', log='워커가 보낸 영상 파일이 비어 있습니다.')
        return jsonify(ok=False), 400
    os.replace(tmp, os.path.join(jobdir(job), 'output.mp4'))
    set_status(job, rev, state='done', pct=100, log='')
    return jsonify(ok=True)


@app.post('/api/worker/fail/<job>')
def worker_fail(job):
    worker_auth()
    set_status(job, request.args.get('rev', ''), state='error', log=str((request.json or {}).get('log', ''))[-3000:])
    return jsonify(ok=True)


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
    s = {k: v for k, v in get_status(job).items() if k in ('state', 'pct', 'log')}
    if WORKER_TOKEN:  # 화면에서 'PC 렌더 프로그램이 꺼져 있음'을 안내할 수 있게
        s.update(mode='worker', worker_online=worker_online(), worker_name=_worker['name'])
    return jsonify(s)


@app.get('/jobs/<job>/<path:f>')
def jobfile(job, f):
    return send_from_directory(jobdir(job), f, conditional=True)


@app.get('/')
def index():
    return app.send_static_file('index.html')


os.makedirs(JOBS, exist_ok=True)

if __name__ == '__main__':
    # HOST=0.0.0.0 이면 같은 네트워크의 다른 기기(폰 등)에서 접속 가능
    app.run(host=env('HOST') or '127.0.0.1', port=int(env('PORT') or 5000), threaded=True)

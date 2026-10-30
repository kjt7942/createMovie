"""홍보영상 제작 웹앱. 업로드(폴더 포함) -> Gemini가 장면/사진 배정 -> HyperFrames 렌더.
실행: GEMINI_API_KEY 환경변수(또는 이 폴더의 .env)를 준비하고 `python server.py` -> http://localhost:5000
WORKER_TOKEN을 설정하면 렌더링을 이 서버에서 하지 않고 대기열에 넣어 두고, PC의 렌더 워커(worker/)가 가져가 처리한다."""
import base64, hmac, html, itertools, json, os, random, re, shutil, subprocess, threading, time, urllib.error, urllib.parse, urllib.request, uuid
from flask import Flask, abort, jsonify, request, send_from_directory
from PIL import Image, ImageOps
import beats
import composer
import media
from composer import SCENE_TYPES, STYLES, scene_speech

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, 'jobs')
MODELS = ['gemini-flash-lite-latest', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite']  # 한도 걸리면 다음 모델
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


WORKER_TOKEN = env('WORKER_TOKEN')  # 있으면 '워커 모드': 렌더링은 PC 워커가 한다


def api_keys():
    p = os.path.join(HERE, '.env')
    ks = re.findall(r'^GEMINI_API_KEY(?:_\d+)?=(.+)$', open(p, encoding='utf-8').read(), re.M) if os.path.exists(p) else []
    ks = [k.strip().strip('"\'') for k in ks]
    if os.environ.get('GEMINI_API_KEY'):
        ks.insert(0, os.environ['GEMINI_API_KEY'])
    return list(dict.fromkeys(k for k in ks if k))


_key_rr = itertools.count()  # 호출마다 시작 키를 한 칸씩 돌린다


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
            ar = round(im.width / im.height, 4)
            im.thumbnail((384, 384)); im.save(os.path.join(d, 'thumbs', pid + '.jpg'), quality=75)
            parts = path.split('/')
            m['photos'].append(analyze_photo(d, {'id': pid, 'path': path, 'folder': parts[-2] if len(parts) > 1 else '', 'ar': ar}))
        elif ext in media.VIDEO_EXT:
            vid = f'v{len(m["photos"]) + 1:03d}'
            src = os.path.join(d, 'assets', vid + ext)
            f.save(src)
            info = media.probe(src)
            if not info:
                os.remove(src); skipped.append(path); continue
            dur, vw, vh = info
            try:   # 포스터(앞부분)·끝 장면: AI가 보고 고르는 사진, 동영상이 끝난 뒤 멈춰 보일 장면
                media.frame(src, min(1.0, dur / 3), os.path.join(d, 'assets', vid + '.jpg'))
                media.frame(src, max(0, dur - 0.15), os.path.join(d, 'assets', vid + '_end.jpg'))
                im = Image.open(os.path.join(d, 'assets', vid + '.jpg')); im.thumbnail((384, 384))
                im.save(os.path.join(d, 'thumbs', vid + '.jpg'), quality=75)
            except Exception:
                os.remove(src); skipped.append(path); continue
            parts = path.split('/')
            m['photos'].append(analyze_photo(d, {'id': vid, 'kind': 'video', 'src': vid + ext, 'dur': round(dur, 2), 'path': path,
                                                 'folder': parts[-2] if len(parts) > 1 else '', 'ar': round(vw / vh, 4)}))
        elif ext == '.mp3':
            f.save(os.path.join(d, 'assets', 'bgm.mp3')); m['audio'] = os.path.basename(path); m.pop('beats', None)
        else:
            skipped.append(path)
    save_meta(job, m)
    song_beats(job, m)
    return jsonify(job=job, **m, skipped=skipped)


def analyze_photo(d, p):
    """얼굴 위치와 화면 자를 때의 초점을 기록(세로 자동 맞춤·얼굴 모자이크용). 감지기가 없으면 건너뜀."""
    if 'faces' not in p:
        fb = media.faces(os.path.join(d, 'assets', p['id'] + '.jpg'))
        if fb is not None:
            p['faces'] = fb; p['focus'] = media.focus(fb)
    if 'ar' not in p:
        with Image.open(os.path.join(d, 'assets', p['id'] + '.jpg')) as im:
            p['ar'] = round(im.width / im.height, 4)
    return p


def ensure_media(job, m=None):
    """예전 프로젝트: 얼굴·비율 정보가 없으면 지금 채운다."""
    m = m or meta_of(job)
    if any('ar' not in p or ('faces' not in p and media._detector()) for p in m['photos']):
        m['photos'] = [analyze_photo(jobdir(job), p) for p in m['photos']]
        save_meta(job, m)
    return m


@app.post('/api/logo')
def logo():
    """기관 로고 올리기/지우기. 흰 배경은 자동으로 투명하게."""
    job = request.form.get('job', '')
    m = meta_of(job); dst = os.path.join(jobdir(job), 'assets', 'logo.png')
    if request.form.get('remove'):
        if os.path.exists(dst):
            os.remove(dst)
        m.pop('logo', None)
    else:
        f = request.files.get('file')
        if not f:
            return jsonify(error='로고 파일이 없습니다.'), 400
        try:
            w, h = media.clean_logo(f.stream, dst)
        except Exception:
            return jsonify(error='이미지를 읽지 못했습니다. PNG나 JPG로 올려 주세요.'), 400
        m['logo'] = {'w': w, 'h': h, 't': int(time.time())}
    save_meta(job, m)
    return jsonify(logo=m.get('logo'))


@app.post('/api/reset')
def reset():
    d = jobdir(request.json['job'])
    shutil.rmtree(d, ignore_errors=True)
    return jsonify(ok=True)


# ---------- Gemini 구성 ----------
PROMPT = """너는 홍보영상 기획자다. 사진은 폴더(주제)별로 정리돼 있고 폴더명은 사업/주제 이름이다.
아래 요구사항으로 영상 구성을 JSON으로만 답해라. 한국어, 한자 사용 금지.
요구사항에 없는 사실, 폴더명과 사진에서 확인되지 않는 프로그램은 지어내지 마라.
스키마: {"style":"연출 스타일","year":"2026","title":"행사/영상 제목 5~8자","tagline":"슬로건 20자 이내","org":"기관명",
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
연출 스타일(style)은 다음 중 하나: %s
규칙:
- scenes는 %d~%d개. 폴더가 여러 개면 폴더 하나가 장면 하나가 되게 하고, 폴더명을 제목에 반영한다.
- 주제와 내용에 맞게 장면 유형을 골라 섞어라. 같은 유형이 3번 넘게 연속되지 않게 하고, 근거 없는 stat·quote는 쓰지 않는다.
- 각 장면 photo는 장면 주제와 사진 내용이 가장 잘 맞는 사진 id. 같은 사진 중복은 피한다.
- intro_photo는 밝고 대표적인 사진, outro_photo는 화목한 단체/가족 사진.
- 문구 분위기: %s. 영상 길이: %d초. %s
요구사항: %s
기관/단체명(비어 있으면 요구사항에서 찾아라): %s
%s"""


def gemini(parts):
    keys = api_keys()
    if not keys:
        raise RuntimeError('GEMINI_API_KEY가 설정되어 있지 않습니다.')
    n = next(_key_rr) % len(keys)
    keys = keys[n:] + keys[:n]  # 한도 초과 등 실패 시 다음 키로 넘어간다
    last = None
    for key, m in itertools.product(keys, MODELS):
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
            last = f'{m}(키 …{key[-4:]}): {e}'
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
    if s.get('v') in (0, 1):
        out['v'] = s['v']
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
        sl = narr_slots(*beats.snap_times(length, lo), length); cap = lambda a, b_: max(4, int((b_ - a - 0.6) * CPS))
        revise += ('내레이션(성우가 읽는 말)도 써라. intro_narr(공백 제외 %d자 이내), 각 장면에 narr(공백 제외 %d자 이내), '
                   'outro_narr(공백 제외 %d자 이내, 감사·마무리 인사) 필드를 반드시 모두 추가한다. 화면 글자를 그대로 읽지 말고 듣기 편한 존댓말 한 문장으로.\n'
                   % (cap(*sl[0]), cap(*sl[1]), cap(*sl[-1])))
    if b.get('prev') and b.get('revise'):
        revise += '이전 구성(JSON): %s\n이 구성을 아래 수정 요청에 맞게 고쳐서 같은 스키마로 다시 답해라: %s' % (
            json.dumps(b['prev'], ensure_ascii=False), b['revise'])
    photos = m['photos']
    if len(photos) > MAX_VISION:
        photos = [photos[int(i * len(photos) / MAX_VISION)] for i in range(MAX_VISION)]
    want = b.get('style') if b.get('style') in STYLES else None   # None = AI가 고른다
    style_rule = (f'style은 반드시 "{want}"로 한다.' if want else '주제와 분위기에 가장 어울리는 style을 골라라.')
    parts = [{'text': PROMPT % (composer.STYLE_HINT, lo, hi, b.get('mood', '밝고 경쾌하게'), length, style_rule,
                                b.get('brief') or '(없음)', b.get('org') or '', revise)}]
    for p in photos:
        kind = f' 동영상({p["dur"]:.0f}초, 아래는 한 장면)' if p.get('kind') == 'video' else ''
        parts.append({'text': f'사진id={p["id"]}{kind} 폴더={p["folder"] or "(없음)"} 파일={p["path"].split("/")[-1]}'})
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
        out['style'] = want or (d.get('style') if d.get('style') in STYLES else 'classic')
        prev = b.get('prev') or {}  # 수정 요청 시 사용자가 고른 전환 효과·장면 배치는 유지
        out['seed'] = prev.get('seed') if isinstance(prev.get('seed'), int) else random.randrange(1000)
        for k in ('transition', 'outro_tr'):
            if prev.get(k):
                out[k] = prev[k]
        for s, ps in zip(out['scenes'], prev.get('scenes') or []):
            for k in ('tr', 'v'):
                if k in ps and k not in s:
                    s[k] = ps[k]
        if len(out['scenes']) < 1:
            raise RuntimeError('AI가 장면을 만들지 못했습니다. 다시 시도해 주세요.')
    except (RuntimeError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 502
    json.dump(out, open(os.path.join(jobdir(b['job']), 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return jsonify(plan=out, usage=usage)


# ---------- 내레이션 (edge-tts, 무료·키 불필요) ----------
VOICES = {'sunhi': 'ko-KR-SunHiNeural', 'injoon': 'ko-KR-InJoonNeural', 'hyunsu': 'ko-KR-HyunsuMultilingualNeural'}
CPS = 4.6  # 보통 속도에서 초당 글자 수(공백 제외). edge-tts 한국어 3종 실측 4.6~4.9


def narr_slots(starts, os_, length):
    """말할 수 있는 구간 [(시작, 끝)]: 오프닝, 장면 1..n, 엔딩. 장면 전환 직후 0.4초 뒤 시작, 다음 장면 0.1초 전 끝."""
    nexts = starts[1:] + [os_]
    return ([(0.5, starts[0] - 0.1)] + [(a + 0.4, b - 0.1) for a, b in zip(starts, nexts)]
            + [(os_ + 0.5, length - 0.3)])


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


def make_narration(job, p, length, narr, timing):
    """구간마다 음성을 만들고, 구간보다 길면 최대 +40%까지 빠르게 다시 만든다. 그래도 길면 구간 끝에서 잘린다."""
    slots, texts = narr_slots(*timing, length), narr_texts(p)
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
        clips.append((round(slots[i][0], 2), round(min(d, room), 2), name, texts[i]))
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
def song_beats(job, m=None):
    """배경음악 박자 분석 결과(meta.json에 저장해 두고 재사용). 음악이 없거나 분석할 수 없으면 None."""
    m = m or meta_of(job)
    if not m.get('audio'):
        return None
    if 'beats' not in m:
        try:
            m['beats'] = beats.analyze(os.path.join(jobdir(job), 'assets', 'bgm.mp3'))
        except Exception:
            m['beats'] = None
        save_meta(job, m)
    return m['beats']


def scene_timing(job, length, n, audio):
    """장면 시작 시각과 엔딩 시작. audio.sync가 켜져 있으면 장면 전환을 음악 박자에 맞춘다."""
    b = song_beats(job) if audio and audio.get('sync') else None
    if not b:
        return beats.snap_times(length, n)
    return beats.snap_times(length, n, b['beats'], b['down'], audio['start'], audio['dur'])


def build(job, p, length, audio, name='index.html', extra='', ratio='landscape', narr=None):
    """내레이션을 만들고 composer로 HTML을 조립해 작업 폴더에 쓴다. 잘린 내레이션 구간 목록을 돌려준다.
    plan의 blur(얼굴 모자이크)·logo('corner'|'ends'|'off'), narr.sub(자막)를 반영한다."""
    m = ensure_media(job)
    timing = scene_timing(job, length, len(p['scenes']), audio)
    clips, cut = make_narration(job, p, length, narr, timing) if narr and narr.get('on') else ([], [])
    audio = (f'<audio id="bgm" src="assets/bgm.mp3" data-start="0" data-duration="{audio["dur"]}" data-media-start="{audio["start"]}" '
             f'data-track-index="9" data-volume="{0.25 if clips else 0.7}" data-fade-in="1" data-fade-out="2"></audio>') if audio else ''
    audio += ''.join(f'\n      <audio id="nr{i}" src="assets/{f}" data-start="{s}" data-duration="{d}" data-track-index="{20 + i}" data-volume="1"></audio>'
                     for i, (s, d, f, _) in enumerate(clips))  # 내레이션이 있으면 배경음악을 0.25로 낮춘다
    logo = p.get('logo', 'corner') if m.get('logo') else None
    caps = [(s, d, t) for s, d, _, t in clips] if narr and narr.get('sub', True) else None
    page = composer.compose(jobdir(job), p, length, ratio=ratio, audio_html=audio, extra=extra, timing=timing,
                            photos={x['id']: x for x in m['photos']}, blur=bool(p.get('blur')),
                            logo=None if logo == 'off' else logo, captions=caps)
    open(os.path.join(jobdir(job), name), 'w', encoding='utf-8').write(page)
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


def finalize(job, rev):
    """새로 받은 영상(.new)을 제자리로 옮기고 썸네일을 만든 뒤 완료 처리. 하나라도 없으면 오류."""
    s = get_status(job)
    if s.get('rev') != rev:
        return False
    d = jobdir(job)
    for o in s.get('outputs') or [{'out': 'output.mp4', 'thumb': 'thumb.jpg'}]:
        new = os.path.join(d, o['out'] + '.new')
        if not os.path.exists(new):
            set_status(job, rev, state='error', log=f'{o["out"]} 영상을 받지 못했습니다.'); return False
        os.replace(new, os.path.join(d, o['out']))
        try:   # 썸네일: 오프닝 제목이 다 보이는 순간
            media.frame(os.path.join(d, o['out']), s.get('thumb_t', 3.0), os.path.join(d, o['thumb']))
        except Exception:
            pass
    set_status(job, rev, state='done', pct=100, log='')
    return True


def run_render(job, rev):
    """PC 한 대로 쓸 때: 이 서버에서 직접 렌더한다(출력이 여러 개면 차례로)."""
    with _render_lock:
        set_status(job, rev, state='running', pct=0)
        outs = get_status(job).get('outputs') or []
        tail, pct = [], 0
        for k, o in enumerate(outs):
            part = o['out'] + '.new.mp4'
            pr = subprocess.Popen([shutil.which('npx') or 'npx', '-y', 'hyperframes', 'render', '-c', o['html'], '-o', part],
                                  cwd=jobdir(job), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            for line in pr.stdout:
                mm = re.search(r'"pct":(\d+)', line)
                if mm:
                    v = int((k + int(mm.group(1)) / 100) / len(outs) * 100)
                    if v != pct:
                        pct = v; set_status(job, rev, pct=min(99, pct))
                tail = (tail + [line.rstrip()])[-8:]
            pr.wait()
            path = os.path.join(jobdir(job), part)
            if pr.returncode != 0 or not os.path.exists(path):
                set_status(job, rev, state='error', pct=pct, log='\n'.join(tail)); return
            os.replace(path, os.path.join(jobdir(job), o['out'] + '.new'))
        finalize(job, rev)


def build_from_request(b, **kw):
    m = meta_of(b['job'])
    length = max(15, min(600, int(b.get('length', 30))))
    a = b.get('audio') if m['audio'] else None  # {start, dur}: 음악에서 쓸 구간(초)
    if a:
        a = {'start': max(0.0, float(a['start'])), 'dur': max(1.0, min(float(a['dur']), length)), 'sync': a.get('sync', True) is not False}
    ids = [x['id'] for x in m['photos']]
    pick = lambda v: v if v in ids else ids[0]
    b['plan']['scenes'] = [normalize_scene(s, ids, pick) for s in b['plan']['scenes']]
    ratio = kw.pop('ratio', None) or ('portrait' if b.get('ratio') == 'portrait' else 'landscape')
    return build(b['job'], b['plan'], length, a, ratio=ratio, narr=b.get('narr'), **kw)


def outputs_for(ratio):
    """요청한 화면 비율 -> 만들 영상 목록. '둘 다'면 가로(output.mp4)와 세로(output_portrait.mp4)."""
    if ratio == 'both':
        return [{'ratio': 'landscape', 'html': 'index.html', 'out': 'output.mp4', 'thumb': 'thumb.jpg'},
                {'ratio': 'portrait', 'html': 'portrait.html', 'out': 'output_portrait.mp4', 'thumb': 'thumb_portrait.jpg'}]
    return [{'ratio': 'portrait' if ratio == 'portrait' else 'landscape', 'html': 'index.html', 'out': 'output.mp4', 'thumb': 'thumb.jpg'}]


@app.post('/api/render')
def render():
    b = request.json
    outs = outputs_for(b.get('ratio'))
    try:
        cut = []
        for o in outs:
            cut = build_from_request(b, name=o['html'], ratio=o['ratio'])
        save_json(b['job'], 'plan.json', b['plan'])  # 렌더 시 화면에서 고친 구성도 저장
        st0 = scene_timing(b['job'], max(15, min(600, int(b.get('length', 30)))), len(b['plan']['scenes']),
                           b.get('audio') if meta_of(b['job'])['audio'] else None)[0][0]
    except (KeyError, IndexError, ValueError) as e:
        return jsonify(error='구성 정보가 올바르지 않습니다: %s' % e), 400
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    rev = uuid.uuid4().hex[:8]
    set_status(b['job'], state='queued', pct=0, log='', rev=rev, queued_at=time.time(), outputs=outs, thumb_t=round(max(1.5, st0 - 0.3), 2))
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
            outs = get_status(j).get('outputs') or outputs_for('landscape')
            refs = set()
            for o in outs:
                page = open(os.path.join(jobdir(j), o['html']), encoding='utf-8').read()
                refs |= {a or b or c for a, b, c in re.findall(
                    r'(?:src|href)="(assets/[^"?#]+)"|url\(\'(assets/[^\'?#]+)\'\)|poster="(assets/[^"?#]+)"', page)}
            files = [o['html'] for o in outs] + sorted(refs)
            return jsonify(job=j, rev=rev, files=files, outputs=[{'html': o['html'], 'out': o['out']} for o in outs])
    return jsonify(job=None)


@app.post('/api/worker/progress/<job>')
def worker_progress(job):
    worker_auth()
    ok = set_status(job, request.args.get('rev', ''), pct=max(0, min(99, int((request.json or {}).get('pct', 0)))))
    return jsonify(ok=ok, cancel=not ok)  # cancel: 사용자가 다시 렌더를 눌러 이 작업은 필요 없어짐


def _receive(job, rev, out):
    """워커가 올린 영상을 <out>.new 로 받아 둔다(완료 때 한꺼번에 교체)."""
    tmp = os.path.join(jobdir(job), out + '.part')
    with open(tmp, 'wb') as f:
        shutil.copyfileobj(request.stream, f, 1024 * 1024)
    if os.path.getsize(tmp) < 1000:
        os.remove(tmp)
        set_status(job, rev, state='error', log='워커가 보낸 영상 파일이 비어 있습니다.')
        return False
    os.replace(tmp, os.path.join(jobdir(job), out + '.new'))
    return True


@app.post('/api/worker/upload/<job>')
def worker_upload(job):
    worker_auth()
    rev, out = request.args.get('rev', ''), request.args.get('out', '')
    s = get_status(job)
    if s.get('rev') != rev:
        return jsonify(ok=False, cancel=True)
    if out not in [o['out'] for o in s.get('outputs') or outputs_for('landscape')]:
        return jsonify(ok=False, error='알 수 없는 출력 파일'), 400
    return jsonify(ok=_receive(job, rev, out))


@app.post('/api/worker/done/<job>')
def worker_done(job):
    """모든 영상을 올린 뒤 호출. (예전 워커는 본문에 영상 하나를 실어 보낸다 -> output.mp4)"""
    worker_auth()
    rev = request.args.get('rev', '')
    if get_status(job).get('rev') != rev:
        return jsonify(ok=False, cancel=True)
    if (request.content_length or 0) > 1000 and not _receive(job, rev, 'output.mp4'):
        return jsonify(ok=False), 400
    return jsonify(ok=finalize(job, rev))


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
      const auds = [...root.querySelectorAll("audio[data-start], video[data-start]")];   // 배경음악·내레이션·동영상 클립
      auds.forEach(a => { if (a.tagName === "VIDEO") { a.muted = true; a.playbackRate = +a.dataset.playbackRate || 1; } else a.volume = Math.min(1, +a.dataset.volume || 1); });
      const total = +root.dataset.duration;
      let at = 0, playing = false, t0 = 0;
      function syncAudio(force) {   // 각 오디오를 자기 구간에서만, 맞는 위치로 재생
        auds.forEach(a => {
          const s = +a.dataset.start, d = +a.dataset.duration, r = +a.dataset.playbackRate || 1;
          const inside = at >= s && at < s + d, want = (+a.dataset.mediaStart || 0) + (at - s) * r;
          if (a.tagName === "VIDEO") { a.style.visibility = inside ? "visible" : "hidden"; if (!playing && inside && Math.abs(a.currentTime - want) > 0.05) a.currentTime = want; }
          if (!playing) { if (!a.paused) a.pause(); return; }
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
        view = 'portrait' if b.get('ratio') == 'portrait' or (b.get('ratio') == 'both' and b.get('view') == 'portrait') else 'landscape'
        cut = build_from_request(b, name='preview.html', extra=PREVIEW_JS, ratio=view)
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
    m = ensure_media(job); song_beats(job, m)
    return jsonify(meta=m, plan=load_json(job, 'plan.json'), outputs=done_outputs(job), settings=load_json(job, 'project.json', {}),
                   video=os.path.exists(os.path.join(jobdir(job), 'output.mp4')))


def done_outputs(job):
    """완성된 영상 목록 [{ratio, file, thumb}] (예전 프로젝트는 output.mp4 하나)."""
    d, full = jobdir(job), get_status(job)
    return [{'ratio': o['ratio'], 'file': o['out'], 'thumb': o['thumb'] if os.path.exists(os.path.join(d, o['thumb'])) else None}
            for o in full.get('outputs') or outputs_for('landscape') if os.path.exists(os.path.join(d, o['out']))]


@app.get('/api/status/<job>')
def status(job):
    full = get_status(job)
    s = {k: v for k, v in full.items() if k in ('state', 'pct', 'log')}
    if full.get('state') == 'done':
        s['outputs'] = done_outputs(job)
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

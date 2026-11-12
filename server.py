"""홍보영상 제작 웹앱. 업로드(폴더 포함) -> Gemini가 장면/사진 배정 -> HyperFrames 렌더.
실행: GEMINI_API_KEY 환경변수(또는 이 폴더의 .env)를 준비하고 `python server.py` -> http://localhost:5100
WORKER_TOKEN을 설정하면 렌더링을 이 서버에서 하지 않고 대기열에 넣어 두고, PC의 렌더 워커(worker/)가 가져가 처리한다.
이 PC에서 하는 작업(홍보 영상 렌더, /h3의 AI 영상 생성)은 studio.engine.Runner의 대기열 하나로 차례대로 처리한다."""
import base64, collections, hmac, html, itertools, json, os, random, re, shutil, subprocess, threading, time, urllib.error, urllib.parse, urllib.request, uuid, webbrowser
from flask import Flask, abort, jsonify, request, send_from_directory
from PIL import Image, ImageOps
import beats
import composer
import media
from composer import SCENE_TYPES, STYLES, scene_speech
from studio import engine, h3_routes

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, 'jobs')
MODELS = ['gemini-flash-lite-latest', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite']  # 한도 걸리면 다음 모델
MAX_VISION = 40  # Gemini에 보여줄 사진 수 상한(초과분은 균등 샘플링)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 워커가 올리는 완성 영상(최대 10분)까지 받는다
app.json.sort_keys = False  # 해상도 목록을 시험한 기본값이 먼저 오는 순서 그대로 보낸다
app.register_blueprint(h3_routes.app)
runner = h3_routes.runner
RENDER_SILENCE_S = 20 * 60  # 렌더가 이만큼 아무 출력이 없으면 멈춘 것으로 본다. 대기열 전체가 걸리면 안 된다.


@app.before_request
def same_site_only():
    """다른 사이트가 브라우저를 통해 이 서버를 조작하지 못하게 막는다. 워커는 토큰으로 인증하고 Origin을 보내지 않는다."""
    origin = request.headers.get('Origin')
    if origin and request.method not in ('GET', 'HEAD') and origin.split('//')[-1] != request.host:
        abort(403)
    if BOUND_LOCAL and request.host.rsplit(':', 1)[0] not in ('127.0.0.1', 'localhost'):
        abort(403)  # DNS rebinding 차단. 이 PC에서만 열어 둔 경우에만 주소를 알 수 있다.
_state_lock = threading.Lock()


def env(name):
    k = os.environ.get(name)
    p = os.path.join(HERE, '.env')
    if not k and os.path.exists(p):
        m = re.search(r'^%s=(.+)$' % name, open(p, encoding='utf-8').read(), re.M)
        k = m and m.group(1).strip().strip('"\'')
    return k


BOUND_LOCAL = False  # python server.py로 127.0.0.1에만 열었을 때 True(아래 __main__). 도커·HOST 지정은 주소를 미리 모른다.
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
    with open(os.path.join(jobdir(job), 'meta.json'), encoding='utf-8') as fp:
        return json.load(fp)


def save_meta(job, m):
    save_json(job, 'meta.json', m)


_job_locks = collections.defaultdict(threading.RLock)  # meta.json을 읽고 고쳐 쓰는 동안 같은 프로젝트의 다른 요청이 끼어들지 못하게


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
    with _job_locks[job]:
        m = meta_of(job) if os.path.exists(os.path.join(d, 'meta.json')) else {'photos': [], 'audio': None}
        skipped = []
        for f, path in zip(request.files.getlist('files'), request.form.getlist('paths')):
            path = path.replace('\\', '/').lstrip('/')
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.webp'):
                try:
                    src = Image.open(f.stream)
                    taken = media.photo_taken(src)   # 저장본에는 EXIF가 빠지므로 원본에서 먼저 읽는다
                    im = ImageOps.exif_transpose(src).convert('RGB')
                except Exception:
                    skipped.append(path); continue
                pid = f'p{len(m["photos"]) + 1:03d}'
                im.thumbnail((1920, 1920)); im.save(os.path.join(d, 'assets', pid + '.jpg'), quality=88)
                ar = round(im.width / im.height, 4)
                im.thumbnail((384, 384)); im.save(os.path.join(d, 'thumbs', pid + '.jpg'), quality=75)
                parts = path.split('/')
                m['photos'].append(analyze_photo(d, {'id': pid, 'path': path, 'folder': parts[-2] if len(parts) > 1 else '', 'ar': ar,
                                                     **({'taken': taken} if taken else {})}))
            elif ext in media.VIDEO_EXT:
                if not add_video(d, m, path, ext, f.save):
                    skipped.append(path)
            elif ext == '.mp3':
                f.save(os.path.join(d, 'assets', 'bgm.mp3')); m['audio'] = os.path.basename(path); m.pop('beats', None)
            else:
                skipped.append(path)
        save_meta(job, m)
        song_beats(job, m)
    return jsonify(job=job, **m, skipped=skipped)


def add_video(d, m, path, ext, save):
    """동영상을 자료에 추가한다. save(대상 경로)가 파일을 놓는다. 읽을 수 없는 파일이면 False."""
    vid = f'v{len(m["photos"]) + 1:03d}'
    src = os.path.join(d, 'assets', vid + ext)
    save(src)
    info = media.probe(src)
    if not info:
        os.remove(src); return False
    dur, vw, vh = info
    try:   # 포스터(앞부분)·끝 장면: AI가 보고 고르는 사진, 동영상이 끝난 뒤 멈춰 보일 장면
        media.frame(src, min(1.0, dur / 3), os.path.join(d, 'assets', vid + '.jpg'))
        media.frame(src, max(0, dur - 0.15), os.path.join(d, 'assets', vid + '_end.jpg'))
        im = Image.open(os.path.join(d, 'assets', vid + '.jpg')); im.thumbnail((384, 384))
        im.save(os.path.join(d, 'thumbs', vid + '.jpg'), quality=75)
    except Exception:
        os.remove(src); return False
    parts = path.split('/')
    taken = media.video_taken(src)
    m['photos'].append(analyze_photo(d, {'id': vid, 'kind': 'video', 'src': vid + ext, 'dur': round(dur, 2), 'path': path,
                                         'folder': parts[-2] if len(parts) > 1 else '', 'ar': round(vw / vh, 4),
                                         **({'taken': taken} if taken else {})}))
    return True


@app.post('/api/from_h3/<pid>')
def from_h3(pid):
    """완성된 AI 영상을 클립으로 넣은 새 홍보 영상 프로젝트를 만든다. 원본은 그대로 둔다."""
    if not h3_routes.is_local():
        abort(403)
    try:
        project = engine.load_project(pid)
    except (engine.StudioError, ValueError, OSError):
        return jsonify(error='AI 영상 프로젝트를 찾을 수 없습니다.'), 404
    final = engine.project_dir(pid) / 'final.mp4'
    if not final.is_file():
        return jsonify(error='완성된 영상이 없습니다.'), 400
    job = uuid.uuid4().hex[:12]
    d = jobdir(job)
    for sub in ('assets', 'thumbs'):
        os.makedirs(os.path.join(d, sub))
    shutil.copy(os.path.join(HERE, 'gsap.min.js'), os.path.join(d, 'assets', 'gsap.min.js'))
    m = {'photos': [], 'audio': None}
    name = re.sub(r'[\\/:*?"<>|]', '', project['script']['title']) + '.mp4'
    if not add_video(d, m, name, '.mp4', lambda dst: shutil.copy(final, dst)):
        shutil.rmtree(d, ignore_errors=True)
        return jsonify(error='영상을 읽지 못했습니다. FFmpeg 설치를 확인하세요.'), 500
    save_meta(job, m)
    return jsonify(job=job)


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
        with _job_locks[job]:
            m = meta_of(job)  # 기다리는 사이 바뀌었을 수 있다
            m['photos'] = [analyze_photo(jobdir(job), p) for p in m['photos']]
            save_meta(job, m)
    return m


@app.post('/api/logo')
def logo():
    """기관 로고 올리기/지우기. 흰 배경은 자동으로 투명하게."""
    job = request.form.get('job', '')
    dst = os.path.join(jobdir(job), 'assets', 'logo.png')
    with _job_locks[job]:
        m = meta_of(job)
        if request.form.get('remove'):
            if os.path.exists(dst):
                os.remove(dst)
            m.pop('logo', None)
        else:
            use_default = bool(request.form.get('default'))   # 문경시가족센터 기본 로고(static/default_logo.png)
            f = os.path.join(HERE, 'static', 'default_logo.png') if use_default else request.files.get('file')
            if not f:
                return jsonify(error='로고 파일이 없습니다.'), 400
            try:
                w, h = media.clean_logo(f if use_default else f.stream, dst)
            except Exception:
                return jsonify(error='이미지를 읽지 못했습니다. PNG나 JPG로 올려 주세요.'), 400
            m['logo'] = {'w': w, 'h': h, 't': int(time.time()), **({'default': True} if use_default else {})}
        save_meta(job, m)
    return jsonify(logo=m.get('logo'))


@app.post('/api/reset')
def reset():
    job = request.json['job']
    d = jobdir(job)
    if os.path.isdir(d) and get_status(job)['state'] in ('queued', 'running'):
        return jsonify(error='렌더링 중이거나 대기 중인 프로젝트는 지울 수 없습니다. 대기열에서 빼거나 멈춘 뒤 지워 주세요.'), 409
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
        except (OSError, KeyError, IndexError, ValueError) as e:  # URLError·TimeoutError·연결 끊김은 모두 OSError
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
    if s.get('cbar') is False:   # 사진 콜라주 하단 막대를 이 장면만 끈 경우
        out['cbar'] = False
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
    if stale(b):
        return CONFLICT
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
    order = b.get('order') if b.get('order') in ORDERS else 'ai'
    if order == 'time':
        revise += '장면은 사진의 촬영 시각이 이른 것부터 늦은 것 순서로 배치하라(행사의 진행 순서). 각 장면에는 시각이 가까운 사진을 함께 써라.\n'
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
        when = f' 촬영={p["taken"].replace("T", " ")[:16]}' if p.get('taken') else ''
        parts.append({'text': f'사진id={p["id"]}{kind} 폴더={p["folder"] or "(없음)"} 파일={p["path"].split("/")[-1]}{when}'})
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
        for k in ('transition', 'outro_tr', 'opening', 'ending'):
            if prev.get(k):
                out[k] = prev[k]
        for s, ps in zip(out['scenes'], prev.get('scenes') or []):
            for k in ('tr', 'v', 'cbar'):
                if k in ps and k not in s:
                    s[k] = ps[k]
        if len(out['scenes']) < 1:
            raise RuntimeError('AI가 장면을 만들지 못했습니다. 다시 시도해 주세요.')
        # 장면 순서: 시간순은 수정 요청 때도 다시 맞추고, 무작위·수동은 처음 만들 때만(사용자가 정리한 순서를 지킨다)
        if order == 'time' or (order != 'ai' and not b.get('revise')):
            out['scenes'] = arrange(out['scenes'], order, m['photos'])
    except (RuntimeError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 502
    with _job_locks[b['job']]:
        save_json(b['job'], 'plan.json', out)
        rev = bump_rev(b['job'])
    return jsonify(plan=out, usage=usage, rev=rev)


ORDERS = ('ai', 'time', 'random', 'manual')   # 장면 배치: AI 자동(기본) / 촬영 시간순 / 무작위 / 수동(올린 순서로 시작)


def arrange(scenes, order, photos):
    """장면 순서를 정한다. photos: meta의 사진 목록(올린 순서)."""
    if order == 'time':
        return sort_by_taken(scenes, {p['id']: p for p in photos})
    if order == 'random':
        return random.sample(scenes, len(scenes))
    if order == 'manual':   # 장면 대표 사진을 올린 순서대로. 이후 3단계에서 끌어서 정리한다
        idx = {p['id']: i for i, p in enumerate(photos)}
        return sorted(scenes, key=lambda s: idx.get(s.get('photo'), len(idx)))
    return scenes


def sort_by_taken(scenes, photos):
    """장면을 사진 촬영 시각 순으로(콜라주는 가장 이른 사진 기준). 시각을 모르는 장면은 원래 순서대로 맨 뒤로."""
    def key(s):
        ts = [photos.get(x, {}).get('taken') for x in (s.get('photos') or []) + [s.get('photo')]]
        ts = [t for t in ts if t]
        return (0, min(ts)) if ts else (1, '')
    return sorted(scenes, key=key)   # sorted는 같은 키끼리 원래 순서를 지킨다


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
    out, todo = [], {}
    for text, v, r in items:
        name = 'tts_' + hashlib.sha1(f'{text}|{v}|{r}'.encode()).hexdigest()[:12] + '.mp3'
        path = os.path.join(jobdir(job), 'assets', name)
        if not os.path.exists(path) and name not in todo:  # 같은 문장이 둘이면 한 번만 만든다
            todo[name] = (text, v, r, path)
        out.append((name, path))

    async def save_one(text, v, r, path):  # 실패하면 받다 만 파일이 캐시로 남지 않게 임시 파일에 받는다
        part = path + '.part'
        await edge_tts.Communicate(text, VOICES.get(v, VOICES['sunhi']), rate=f'{r:+d}%').save(part)
        os.replace(part, path)

    async def run():
        await asyncio.gather(*(save_one(*a) for a in todo.values()))
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
        with _job_locks[job]:
            m = meta_of(job)
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
        if not os.path.isdir(jobdir(job)):
            return False
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


def run_render(job, rev, on_pct=lambda pct: None, stopped=lambda: False):
    """PC 한 대로 쓸 때: 이 서버에서 직접 렌더한다(출력이 여러 개면 차례로). 대기열이 한 번에 하나만 부른다."""
    if not set_status(job, rev, state='running', pct=0):
        return
    outs = get_status(job).get('outputs') or []
    tail, pct = [], 0
    for k, o in enumerate(outs):
        if stopped():
            set_status(job, rev, state='error', pct=pct, log='멈추기를 눌러 렌더링을 중단했습니다.'); return
        part = o['out'] + '.new.mp4'
        pr = subprocess.Popen([shutil.which('npx') or 'npx', '-y', 'hyperframes', 'render', '-c', o['html'], '-o', part],
                              cwd=jobdir(job), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        last, started = [time.time()], time.time()

        def watchdog(p=pr, t0=started):
            # npx는 cmd를 거쳐 node를 띄운다. 시작 직후에 cmd만 죽이면 node가 고아로 남아 렌더가 계속되므로 잠깐 기다린다.
            while p.poll() is None:
                if stopped() and time.time() - t0 > 3:
                    engine.kill_tree(p.pid)
                    return
                if time.time() - last[0] > RENDER_SILENCE_S:
                    tail.append(f'{RENDER_SILENCE_S // 60}분 동안 렌더링 응답이 없어 중단했습니다.')
                    engine.kill_tree(p.pid)
                    return
                time.sleep(1)
        threading.Thread(target=watchdog, daemon=True).start()
        for line in pr.stdout:
            last[0] = time.time()
            mm = re.search(r'"pct":(\d+)', line)
            if mm:
                v = int((k + int(mm.group(1)) / 100) / len(outs) * 100)
                if v != pct:
                    pct = v; on_pct(pct)
                    if not set_status(job, rev, pct=min(99, pct)):  # 그 사이 렌더를 다시 눌렀다: 낡은 렌더는 그만둔다
                        engine.kill_tree(pr.pid)
            tail = (tail + [line.rstrip()])[-8:]
        pr.wait()
        if get_status(job).get('rev') != rev:
            return
        if stopped():
            set_status(job, rev, state='error', pct=pct, log='멈추기를 눌러 렌더링을 중단했습니다.'); return
        path = os.path.join(jobdir(job), part)
        if pr.returncode != 0 or not os.path.exists(path):
            set_status(job, rev, state='error', pct=pct, log='\n'.join(tail)); return
        os.replace(path, os.path.join(jobdir(job), o['out'] + '.new'))
    finalize(job, rev)


class PromoQueue:
    """홍보 영상 렌더를 AI 영상 생성과 같은 대기열에 세운다. 상태는 각 작업의 render.json에 있어 재시작해도 남는다.
    워커 모드에서는 렌더가 다른 PC에서 돌기 때문에 여기 서지 않는다."""

    def _jobs(self):
        if WORKER_TOKEN or not os.path.isdir(JOBS):
            return
        for j in os.listdir(JOBS):
            if re.fullmatch(r'[0-9a-f]{12}', j):
                try:
                    yield j, get_status(j)
                except (ValueError, OSError):
                    continue  # 망가졌거나 지우는 중인 폴더가 대기열 전체를 막으면 안 된다

    def queued(self):
        return [{'kind': 'promo', 'id': j, 'title': s.get('title') or '홍보 영상', 'at': s.get('queued_at', 0),
                 'estimate': s.get('length', 30) * 2 * len(s.get('outputs') or [0])}  # 화면 안내와 같은 기준: 영상 길이의 약 2배
                for j, s in self._jobs() if s['state'] == 'queued']

    def run(self, job, r):
        st = get_status(job)
        if st['state'] != 'queued':  # 고른 직후 대기열에서 뺐거나 지웠다
            return
        rev = st.get('rev')
        try:
            run_render(job, rev, lambda pct: r._set_live(stage='렌더링', fraction=pct / 100), r.stop_event.is_set)
        except Exception as e:
            set_status(job, rev, state='error', log=f'{type(e).__name__}: {e}')

    def set_at(self, job, at):
        set_status(job, get_status(job).get('rev'), queued_at=at)

    def remove(self, job):
        s = get_status(job)
        if s['state'] != 'queued':
            raise engine.StudioError('대기열에 없는 작업입니다.')
        set_status(job, s.get('rev'), state='none', pct=0)

    def recover(self):
        """렌더 도중 서버가 꺼졌으면 다시 대기열로(원래 순서 유지)."""
        for j, s in self._jobs():
            if s['state'] == 'running':
                set_status(j, s.get('rev'), state='queued', pct=0)


runner.external = PromoQueue()


@app.get('/api/queue')
def queue():
    """상단 막대가 쓰는 대기열 상태(읽기 전용). 조작은 /h3/api/queue/*로, 이 PC에서만 된다."""
    s = runner.snapshot()
    g = (s['gpu'] or [None])[-1]
    return jsonify(busy=s['busy'], current=s['current'], queue=s['queue'], paused=s['paused'], pause_reason=s['pause_reason'],
                   stage=s['live']['stage'], fraction=s['live']['fraction'], gpu=g, gpu_age=time.time() - g['t'] if g else None, local=h3_routes.is_local())


def build_from_request(b, **kw):
    m = meta_of(b['job'])
    length = max(15, min(600, int(b.get('length', 30))))
    a = b.get('audio') if m['audio'] else None  # {start, dur}: 음악에서 쓸 구간(초)
    if a:
        a = {'start': max(0.0, float(a['start'])), 'dur': max(1.0, min(float(a['dur']), length)), 'sync': a.get('sync', True) is not False}
    ids = [x['id'] for x in m['photos']]
    pick = lambda v: v if v in ids else ids[0]
    b['plan']['scenes'] = [normalize_scene(s, ids, pick) for s in b['plan']['scenes']]
    for k in ('intro_photo', 'outro_photo'):  # 그대로 HTML에 들어가는 값이라 실제 사진 id만 허용
        b['plan'][k] = pick(b['plan'].get(k))
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
    if not WORKER_TOKEN and not shutil.which('npx'):
        return jsonify(error='Node.js가 없어 렌더링할 수 없습니다. 상단의 "설치·점검"에서 설치해 주세요.'), 400
    if stale(b):
        return CONFLICT
    outs = outputs_for(b.get('ratio'))
    try:
        cut = []
        for o in outs:
            cut = build_from_request(b, name=o['html'], ratio=o['ratio'])
        with _job_locks[b['job']]:
            save_json(b['job'], 'plan.json', b['plan'])  # 렌더 시 화면에서 고친 구성도 저장
            edit_rev = bump_rev(b['job'])
        a = b.get('audio') if meta_of(b['job'])['audio'] else None  # build_from_request와 같은 규칙으로 맞춰야 썸네일 시각이 영상과 맞다
        if a:
            a = {'start': max(0.0, float(a['start'])), 'dur': max(1.0, min(float(a['dur']), max(15, min(600, int(b.get('length', 30)))))), 'sync': a.get('sync', True) is not False}
        st0 = scene_timing(b['job'], max(15, min(600, int(b.get('length', 30)))), len(b['plan']['scenes']), a)[0][0]
    except (KeyError, IndexError, ValueError) as e:
        return jsonify(error='구성 정보가 올바르지 않습니다: %s' % e), 400
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    rev = uuid.uuid4().hex[:8]
    length = max(15, min(600, int(b.get('length', 30))))

    def mark_queued():
        set_status(b['job'], state='queued', pct=0, log='', rev=rev, queued_at=time.time(), outputs=outs, title=b['plan'].get('title') or '',
                   length=length, thumb_t=round(max(1.5, st0 - 0.3), 2))
    if WORKER_TOKEN:
        mark_queued()
    else:
        runner.enqueue_external(mark_queued)
    return jsonify(ok=True, cut=cut, rev=edit_rev)


# ---------- PC 렌더 워커용 API (WORKER_TOKEN 설정 시) ----------
# 워커가 몇 초마다 /claim으로 일감을 묻고(PC -> 서버 방향이라 공유기 포트 개방 불필요),
# 받은 파일로 렌더한 뒤 /progress로 진행률, /done으로 완성 영상을 올린다.
STALE = 600  # 진행 보고가 이 시간(초) 동안 없으면 워커가 꺼진 것으로 보고 다시 대기열로
_worker = {'seen': 0.0, 'name': ''}
_claim_lock = threading.Lock()


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
        try:
            s = get_status(j)
            if (s['state'] == 'queued' or (s['state'] == 'running' and now - s.get('updated', 0) > STALE)) and s.get('rev'):
                cands.append((s.get('queued_at', 0), j, s['rev']))
        except (ValueError, OSError):
            continue  # 망가진 작업 하나 때문에 다른 작업까지 못 가져가면 안 된다
    with _claim_lock:  # 두 워커가 같은 작업을 동시에 가져가지 않게
        return claim_first(sorted(cands), now)


def claim_first(cands, now):
    for _, j, rev in cands:
        s = get_status(j)
        if s.get('rev') != rev or not (s['state'] == 'queued' or (s['state'] == 'running' and now - s.get('updated', 0) > STALE)):
            continue
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
    if not os.path.exists(f):
        return default
    with open(f, encoding='utf-8') as fp:
        return json.load(fp)


def save_json(job, name, data):
    """임시 파일에 쓰고 바꿔치기: 저장 중 꺼져도 망가진 파일이 남지 않는다."""
    f = os.path.join(jobdir(job), name)
    with open(f + '.tmp', 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False)
    os.replace(f + '.tmp', f)


# 같은 프로젝트를 두 탭이나 두 기기에서 고칠 때 낡은 화면이 새 내용을 덮어쓰지 못하게 한다.
# 저장할 때마다 project.json의 _rev가 바뀌고, 화면은 자기가 마지막으로 본 값을 보낸다.
CONFLICT = {'conflict': True, 'error': '다른 탭이나 기기에서 이 프로젝트가 바뀌었습니다.'}, 409


def stale(b):
    if 'rev' not in b or b.get('force'):
        return False
    return ((load_json(b['job'], 'project.json') or {}).get('_rev') or None) != (b['rev'] or None)


def bump_rev(job, settings=None):
    st = settings if settings is not None else (load_json(job, 'project.json') or {})
    st['_rev'] = uuid.uuid4().hex[:8]
    save_json(job, 'project.json', st)
    return st['_rev']


@app.post('/api/save')
def save():
    b = request.json
    if not os.path.exists(os.path.join(jobdir(b['job']), 'meta.json')):
        return jsonify(error='프로젝트를 찾을 수 없습니다.'), 404
    with _job_locks[b['job']]:
        if stale(b):
            return CONFLICT
        if b.get('plan'):
            save_json(b['job'], 'plan.json', b['plan'])
        rev = bump_rev(b['job'], b.get('settings') or {})
    return jsonify(ok=True, saved=time.strftime('%H:%M'), rev=rev)


@app.post('/api/export/<job>')
def export(job):
    """완성 영상을 설치·점검에서 정한 저장 폴더로 복사한다. 이 PC의 폴더에 쓰므로 이 PC에서만 된다."""
    if not h3_routes.is_local():
        abort(403)
    title = (load_json(job, 'plan.json') or {}).get('title') or '홍보영상'
    outs = done_outputs(job)
    try:
        paths = [str(engine.export_video(os.path.join(jobdir(job), o['file']), title + ('_세로' if len(outs) > 1 and o['ratio'] == 'portrait' else '_가로' if len(outs) > 1 else ''))[0]) for o in outs]
    except engine.StudioError as e:
        return jsonify(error=str(e)), 400
    if not paths:
        return jsonify(error='완성된 영상이 없습니다.'), 400
    return jsonify(paths=paths)


@app.get('/api/projects')
def projects():
    out = []
    for j in os.listdir(JOBS) if os.path.isdir(JOBS) else []:
        d = os.path.join(JOBS, j)
        if not re.fullmatch(r'[0-9a-f]{12}', j) or not os.path.exists(os.path.join(d, 'meta.json')):
            continue
        try:
            m = meta_of(j)
            pl, st = load_json(j, 'plan.json') or {}, load_json(j, 'project.json') or {}
        except (ValueError, OSError):
            continue  # 망가진 폴더 하나가 목록 전체를 막으면 안 된다
        if not m['photos']:
            continue
        mt = max(os.path.getmtime(os.path.join(d, f)) for f in ('meta.json', 'plan.json', 'project.json', 'output.mp4')
                 if os.path.exists(os.path.join(d, f)))
        out.append({'job': j, 'title': pl.get('title') or '제목 없음', 'mtime': mt,
                    'updated': time.strftime('%Y-%m-%d %H:%M', time.localtime(mt)),
                    'photos': len(m['photos']), 'thumb': pl.get('intro_photo') or m['photos'][0]['id'],
                    'video': os.path.exists(os.path.join(d, 'output.mp4')), 'portrait': os.path.exists(os.path.join(d, 'output_portrait.mp4')), 'length': st.get('length'),
                    'scenes': len(pl.get('scenes', []))})
    return jsonify(projects=sorted(out, key=lambda x: -x['mtime']))


@app.get('/api/project/<job>')
def project(job):
    m = ensure_media(job); song_beats(job, m)
    return jsonify(meta=m, plan=load_json(job, 'plan.json'), outputs=done_outputs(job), render=get_status(job)['state'], settings=load_json(job, 'project.json', {}),
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
    if full.get('state') == 'queued' and not WORKER_TOKEN:  # 몇 번째인지, 왜 안 도는지 안내
        q = runner.snapshot()
        s.update(ahead=next((i for i, x in enumerate(q['queue']) if x['id'] == job), 0) + (1 if q['busy'] else 0),
                 paused=q['paused'], pause_reason=q['pause_reason'])
    if WORKER_TOKEN:  # 화면에서 'PC 렌더 프로그램이 꺼져 있음'을 안내할 수 있게
        s.update(mode='worker', worker_online=worker_online(), worker_name=_worker['name'])
    return jsonify(s)


@app.get('/fonts/jua.ttf')
def logo_font():   # 로고 "크무"용 귀여운 글꼴. 영상용 글꼴 폴더(tools/get_fonts.py)에서 가져오며, 없으면 404(굵은 기본 글꼴로 대체)
    return send_from_directory(os.path.join(HERE, 'fonts'), 'Jua.ttf')


@app.get('/jobs/<job>/<path:f>')
def jobfile(job, f):
    return send_from_directory(jobdir(job), f, conditional=True)


@app.get('/')
def index():
    return app.send_static_file('index.html')


# ---------- 설치·점검 ----------
def setup_status():
    """서비스에 필요한 도구별 상태. 비밀값은 있는지만 본다."""
    def imports(*names):
        import importlib.util
        return all(importlib.util.find_spec(n) for n in names)
    node_ok = False
    if shutil.which('node'):
        try:
            major = subprocess.run(['node', '-p', "process.versions.node.split('.')[0]"], capture_output=True, text=True, timeout=20).stdout
            node_ok = int(major) >= 22
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    h3 = engine.availability()
    promo = [('Python 패키지', imports('flask', 'PIL', 'edge_tts', 'fontTools', 'numpy', 'cv2'), 'pip install -r requirements.txt'),
             ('FFmpeg', bool(shutil.which('ffmpeg') and shutil.which('ffprobe')), 'winget install -e --id Gyan.FFmpeg'),
             ('영상용 글꼴·얼굴 인식 모델', os.path.isdir(os.path.join(HERE, 'fonts')) and os.path.isdir(os.path.join(HERE, 'models')), 'python tools/get_fonts.py'),
             ('Gemini API 키 (AI 장면 구성)', bool(api_keys()), '.env 파일에 GEMINI_API_KEY=발급받은키')]
    if not WORKER_TOKEN:
        promo.insert(1, ('Node.js 22 이상 (렌더링)', node_ok, 'winget install -e --id OpenJS.NodeJS.LTS'))
    items = [{'group': '홍보 영상', 'name': n, 'ok': bool(ok), 'fix': f} for n, ok, f in promo]
    items += [{'group': 'AI 영상 생성', 'name': 'NVIDIA GPU (메모리 8GB 이상)', 'ok': h3['gpu_ok'], 'fix': '설치로 해결되지 않습니다. GPU가 없어도 홍보 영상은 쓸 수 있습니다.'},
              {'group': 'AI 영상 생성', 'name': 'Wan2GP와 모델 (약 80GB)', 'ok': h3['installed'], 'fix': 'setup.bat -H3'},
              {'group': 'AI 영상 생성', 'name': '캐릭터 영상용 모델 (약 21GB, 위 용량에 포함)', 'ok': h3['ref_installed'], 'fix': 'python tools/setup_h3.py'}]
    return {'items': items, 'h3': h3}


@app.get('/setup')
def setup_page():
    return app.send_static_file('setup.html')


@app.get('/guide')
def guide_page():
    return app.send_static_file('guide.html')


@app.get('/api/setup/status')
def setup_state():
    return jsonify(dict(setup_status(), local=h3_routes.is_local(), windows=os.name == 'nt'))


@app.post('/api/setup/run')
def setup_run():
    """설치 스크립트를 이 PC에 새 콘솔 창으로 띄운다. 인자는 고정값만 쓴다."""
    if not h3_routes.is_local() or os.name != 'nt':
        abort(403)
    args = ['-H3'] if (request.json or {}).get('h3') else []
    subprocess.Popen(['cmd', '/c', 'start', 'createMovie setup', os.path.join(HERE, 'setup.bat')] + args, cwd=HERE)
    return jsonify(ok=True)


os.makedirs(JOBS, exist_ok=True)

if __name__ == '__main__':
    runner.recover()
    # 기본은 0.0.0.0(같은 네트워크의 다른 기기도 http://<이 PC IP>:5100 으로 접속). AI 영상 생성은 그래도 이 PC에서만 된다.
    # 이 PC에서만 열려면 .env에 HOST=127.0.0.1
    host = env('HOST') or '0.0.0.0'
    BOUND_LOCAL = host == '127.0.0.1'
    port = int(env('PORT') or 5100)
    url = f'http://{h3_routes.LAN_IP if host == "0.0.0.0" else host}:{port}'
    print(f'createMovie: {url}', flush=True)
    threading.Timer(1.0, webbrowser.open, [url]).start()
    app.run(host=host, port=port, threaded=True, use_reloader=False)

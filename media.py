"""사진·동영상·로고 처리.
- 얼굴 감지(OpenCV YuNet, models/yunet.onnx): 세로 화면 자동 맞춤의 초점, 얼굴 모자이크에 쓴다.
- 동영상 클립: 길이, 포스터(첫 장면)·끝 장면 이미지.
- 로고: 흰 배경 자동 제거, 여백 자르기.
OpenCV나 모델이 없으면 얼굴 기능만 조용히 빠진다(나머지는 그대로 동작)."""
import json, os, subprocess, uuid
from PIL import Image, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, 'models', 'yunet.onnx')
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.webm')
_det = None


def _detector():
    global _det
    if _det is None:
        try:
            import cv2
            _det = cv2.FaceDetectorYN.create(MODEL, '', (320, 320), 0.5, 0.3, 5000) if os.path.exists(MODEL) else False
        except Exception:
            _det = False
    return _det


def faces(path):
    """얼굴 상자 [[x, y, w, h], ...] (0~1 비율). 감지기를 쓸 수 없으면 None."""
    det = _detector()
    if not det:
        return None
    import cv2
    im = cv2.imread(path)
    if im is None:
        return []
    h, w = im.shape[:2]
    det.setInputSize((w, h))
    _, f = det.detect(im)
    if f is None:
        return []
    return [[round(float(x) / w, 4), round(float(y) / h, 4), round(float(fw) / w, 4), round(float(fh) / h, 4)] for x, y, fw, fh, *_ in f]


def focus(boxes):
    """화면을 자를 때 중심에 둘 지점(0~1). 큰 얼굴일수록 무게를 크게. 얼굴이 없으면 가운데."""
    if not boxes:
        return [0.5, 0.45]
    wsum = sum(b[2] * b[3] for b in boxes)
    fx = sum((b[0] + b[2] / 2) * b[2] * b[3] for b in boxes) / wsum
    fy = sum((b[1] + b[3] / 2) * b[2] * b[3] for b in boxes) / wsum
    return [round(fx, 3), round(min(0.75, max(0.25, fy)), 3)]   # 위아래는 너무 치우치지 않게


def blurred(src, dst, boxes):
    """얼굴마다 넉넉한 타원 영역을 강하게 흐린 사본을 만든다."""
    im = Image.open(src).convert('RGB')
    W, H = im.size
    strong = im.filter(ImageFilter.GaussianBlur(max(8, W // 80)))
    mask = Image.new('L', im.size, 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    for x, y, w, h in boxes:
        cx, cy, rw, rh = (x + w / 2) * W, (y + h / 2) * H, w * W * 0.8, h * H * 0.95
        d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(2, W // 400)))
    part = dst + '.part'  # 있으면 재사용하는 캐시라, 쓰다 꺼진 파일이 남으면 안 된다
    Image.composite(strong, im, mask).save(part, format='JPEG', quality=88)
    os.replace(part, dst)


def object_pos(fx, fy, img_aspect, box_aspect):
    """object-fit: cover로 잘릴 때 초점(fx, fy)이 상자 가운데에 오도록 하는 object-position(%)."""
    def axis(f, r):   # r: 잘리는 방향으로 이미지가 상자보다 몇 배 큰지
        if r <= 1.001:
            return 50.0
        off = min(max(f * r - 0.5, 0), r - 1)
        return round(100 * off / (r - 1), 1)
    if img_aspect > box_aspect:
        return axis(fx, img_aspect / box_aspect), 50.0
    return 50.0, axis(fy, box_aspect / img_aspect)


# ---------------------------------------------------------------- 동영상
def photo_taken(im):
    """사진 EXIF의 촬영 일시 -> 'YYYY-MM-DDTHH:MM:SS'(카메라 시계 기준, 현지 시각) 또는 None.
    촬영 시각(DateTimeOriginal)이 없으면 디지털화 시각, 그다음 파일 기록 시각(DateTime)을 쓴다."""
    try:
        ex = im.getexif()
        sub = ex.get_ifd(0x8769)
        v = sub.get(36867) or sub.get(36868) or ex.get(306)
        d, t = str(v).strip().replace('\x00', '').split(' ')[:2]
        y, mo, da = d.split(':'); h, mi, se = t.split(':')[:3]
        if int(y) < 1990:   # 시계가 설정되지 않은 카메라(0000:00:00, 1970년 등)
            return None
        return f'{int(y):04d}-{int(mo):02d}-{int(da):02d}T{int(h):02d}:{int(mi):02d}:{int(float(se)):02d}'
    except Exception:
        return None


def video_taken(path):
    """동영상 메타데이터의 촬영 시각(creation_time, 보통 UTC) -> 이 PC 현지 시각 'YYYY-MM-DDTHH:MM:SS' 또는 None."""
    from datetime import datetime
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags=creation_time,com.apple.quicktime.creationdate',
                            '-of', 'json', path], capture_output=True, text=True, timeout=60)
        tags = json.loads(r.stdout).get('format', {}).get('tags', {})
        v = tags.get('com.apple.quicktime.creationdate') or tags.get('creation_time')   # 아이폰 값은 현지 시간대가 붙어 있다
        t = datetime.fromisoformat(v)   # 'Z', 소수 초, '+0900' 모두 처리(Python 3.11+)
        if t.tzinfo:
            t = t.astimezone().replace(tzinfo=None)
        return t.strftime('%Y-%m-%dT%H:%M:%S') if t.year >= 1990 else None
    except Exception:
        return None


def probe(path):
    """(길이초, 가로, 세로, 회전 반영) 또는 None."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                            'stream=width,height:stream_side_data=rotation:format=duration', '-of', 'json', path],
                           capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout)
        s = j['streams'][0]
        w, h = int(s['width']), int(s['height'])
        rot = next((abs(int(sd.get('rotation', 0))) for sd in s.get('side_data_list', []) if 'rotation' in sd), 0)
        if rot in (90, 270):
            w, h = h, w
        return float(j['format']['duration']), w, h
    except Exception:
        return None


def frame(path, t, dst, max_side=1920):
    """동영상의 t초 장면을 JPG로(포스터·썸네일용, 가벼운 작업)."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t):.2f}', '-i', path, '-frames:v', '1',
                    '-vf', f"scale='min({max_side},iw)':-2", '-q:v', '3', dst], check=True, timeout=120)


def blurred_video(src, dst, every=4):
    """동영상 속 얼굴을 흐린 사본을 만든다. 몇 프레임마다 감지하고, 움직여도 벗어나지 않게 앞뒤 감지 결과까지 합쳐 가린다.
    놓치는 것이 더 위험하므로 감지 기준을 낮춘다(실제 영상의 옆모습이 0.5에서는 빠졌다). 얼굴이 아닌 곳이 조금 흐려질 수 있다.
    영상 클립은 소리 없이 쓰이므로 소리는 뺀다. 실패하면 예외를 낸다: 얼굴이 그대로 나가면 안 된다.
    ponytail: 감지에 잡히지 않은 얼굴(옆모습, 아주 작은 얼굴)은 가리지 못한다. 완벽해야 하면 사람이 완성본을 확인해야 한다."""
    det = _detector()
    if not det:
        raise RuntimeError('얼굴 인식 모델이 없어 모자이크할 수 없습니다. python tools/get_fonts.py를 실행해 주세요.')
    import cv2, numpy as np
    found, cap, n, W, H = {}, cv2.VideoCapture(src), 0, 0, 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    det.setScoreThreshold(0.3)
    while True:
        if n % every:
            if not cap.grab():
                break
        else:
            ok, f = cap.read()
            if not ok:
                break
            H, W = f.shape[:2]
            det.setInputSize((W, H))
            _, r = det.detect(f)
            found[n] = [] if r is None else [tuple(float(v) for v in x[:4]) for x in r]
        n += 1
    cap.release()
    det.setScoreThreshold(0.5)  # 사진 감지·초점 계산과 함께 쓰는 감지기다
    if not n:
        raise RuntimeError('동영상을 읽지 못해 모자이크할 수 없습니다.')
    part = f'{dst}.{uuid.uuid4().hex}.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps:.4f}', '-i', '-',
                            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-an', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', part],
                           stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    sigma = max(8, W // 80)
    try:
        cap, i = cv2.VideoCapture(src), 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            k = i - i % every
            for x, y, w, h in found.get(k - every, []) + found.get(k, []) + found.get(k + every, []):
                cx, cy, rw, rh = x + w / 2, y + h / 2, w * 0.8, h * 0.95
                x0, y0, x1, y1 = max(0, int(cx - rw)), max(0, int(cy - rh)), min(W, int(cx + rw) + 1), min(H, int(cy + rh) + 1)
                if x1 <= x0 or y1 <= y0:
                    continue
                roi = f[y0:y1, x0:x1]
                mask = np.zeros(roi.shape[:2], np.uint8)
                cv2.ellipse(mask, (int(cx - x0), int(cy - y0)), (int(rw), int(rh)), 0, 0, 360, 255, -1)
                f[y0:y1, x0:x1] = np.where(mask[..., None] > 0, cv2.GaussianBlur(roi, (0, 0), sigma), roi)
            enc.stdin.write(f.tobytes())
            i += 1
        cap.release()
        enc.stdin.close()
        if enc.wait(timeout=600) != 0 or not i:
            raise RuntimeError('동영상 모자이크 파일을 만들지 못했습니다. FFmpeg 설치를 확인해 주세요.')
        os.replace(part, dst)
    except (OSError, subprocess.TimeoutExpired) as e:
        enc.kill()
        raise RuntimeError('동영상 모자이크 파일을 만들지 못했습니다: %s' % e)
    finally:
        if os.path.exists(part):
            enc.wait()
            os.remove(part)


# ---------------------------------------------------------------- 로고
def clean_logo(src, dst):
    """로고를 PNG(투명 배경)로. 투명도가 없고 네 귀퉁이가 흰색이면 흰 배경을 지운다. 여백은 자른다."""
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGBA')
    im.thumbnail((800, 800))
    px = im.load(); W, H = im.size
    corners = [px[0, 0], px[W - 1, 0], px[0, H - 1], px[W - 1, H - 1]]
    has_alpha = any(a < 250 for *_, a in corners)
    if not has_alpha and all(min(c[:3]) > 235 for c in corners):
        data = [(r, g, b, 0 if min(r, g, b) > 235 else (a if min(r, g, b) < 200 else int(255 * (255 - min(r, g, b)) / 55)))
                for r, g, b, a in im.getdata()]
        im.putdata(data)
    box = im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        im = im.crop(box)
    im.save(dst)
    return im.size

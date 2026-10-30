"""사진·동영상·로고 처리.
- 얼굴 감지(OpenCV YuNet, models/yunet.onnx): 세로 화면 자동 맞춤의 초점, 얼굴 모자이크에 쓴다.
- 동영상 클립: 길이, 포스터(첫 장면)·끝 장면 이미지.
- 로고: 흰 배경 자동 제거, 여백 자르기.
OpenCV나 모델이 없으면 얼굴 기능만 조용히 빠진다(나머지는 그대로 동작)."""
import json, os, subprocess
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
    Image.composite(strong, im, mask).save(dst, quality=88)


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

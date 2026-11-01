"""동영상 얼굴 모자이크 확인. 가짜 감지기로 실제 영상을 처리해, 얼굴 자리만 흐려지는지 본다. 실행: python test_blur_video.py"""
import os, subprocess, tempfile
import cv2
import numpy as np
import media

W, H, FRAMES, BOX = 320, 240, 30, (120, 80, 60, 60)


class FakeDetector:
    def __init__(self):
        self.calls = 0

    def setScoreThreshold(self, v):
        pass

    def setInputSize(self, size):
        assert size == (W, H)

    def detect(self, frame):
        self.calls += 1
        return None, np.array([[*BOX, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.9]], dtype=np.float32)


def noise_video(path):  # 격자무늬는 흐려지면 값이 뚜렷하게 바뀐다
    tile = np.indices((H, W)).sum(axis=0) % 16 < 8
    frame = (tile * 255).astype(np.uint8)[..., None].repeat(3, axis=2)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                          '-c:v', 'libx264', '-crf', '10', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    for _ in range(FRAMES):
        p.stdin.write(frame.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def sharpness(frame, x, y, w, h):
    return float(cv2.Laplacian(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


with tempfile.TemporaryDirectory() as tmp:
    src, dst = os.path.join(tmp, 'a.mp4'), os.path.join(tmp, 'b.mp4')
    noise_video(src)
    real, media._det = media._det, FakeDetector()
    media.blurred_video(src, dst)
    assert media._det.calls == 8, '4프레임마다 감지해야 한다'
    media._det = real

    cap = cv2.VideoCapture(dst)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    assert len(frames) == FRAMES, f'프레임 수가 달라졌다: {len(frames)}'
    assert not [n for n in os.listdir(tmp) if n not in ('a.mp4', 'b.mp4')], '임시 파일이 남았다'
    x, y, w, h = BOX
    for f in (frames[0], frames[FRAMES // 2], frames[-1]):   # 처음과 끝 프레임도 가려야 한다
        inside = sharpness(f, x + 15, y + 15, w - 30, h - 30)
        outside = sharpness(f, 10, 10, 60, 60)
        assert inside < outside * 0.2, f'얼굴 자리가 충분히 흐려지지 않았다: {inside} / {outside}'

    # 읽을 수 없는 파일은 조용히 넘어가지 않는다(얼굴이 그대로 나가면 안 된다)
    bad = os.path.join(tmp, 'bad.mp4')
    open(bad, 'wb').write(b'not a video')
    media._det = FakeDetector()
    try:
        media.blurred_video(bad, dst + '2')
        raise AssertionError('망가진 파일을 통과시켰다')
    except RuntimeError:
        pass
    media._det = real
print('통과')

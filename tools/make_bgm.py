"""사용: python tools/make_bgm.py 출력.wav [길이초=40] [BPM=128]
축제 홍보영상용 경쾌한 배경음악(128BPM) 합성. 저작권 걱정 없는 자체 제작 음원.
구성: 인트로(필터 열리며 빌드업) -> 메인(킥·클랩·하이햇·베이스·아르페지오·코드) -> 엔딩(마지막 히트 후 여운)"""
import sys
import numpy as np

SR = 44100
BPM = float(sys.argv[3]) if len(sys.argv) > 3 else 128
BEAT = 60 / BPM
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
N = int(SR * (DUR + 1.5))
rng = np.random.default_rng(7)
mix = np.zeros((N, 2))
kicks = np.zeros((N, 2))   # 킥은 사이드체인(누르기)에서 빼서 박자가 또렷하게


def t_(sec):
    return np.arange(int(SR * sec)) / SR


def put(sig, start, gain=1.0, pan=0.0, buf=None):
    i = int(start * SR)
    if i >= N:
        return
    sig = sig[:N - i]
    l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    b = mix if buf is None else buf
    b[i:i + len(sig), 0] += sig * gain * l
    b[i:i + len(sig), 1] += sig * gain * r


def lowpass(x, cutoff):
    """1차 저역통과. cutoff는 고정값 또는 샘플별 배열."""
    c = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x); z = 0.0
    for i in range(len(x)):
        z += a[i] * (x[i] - z); y[i] = z
    return y


def saw(f, t):
    return 2 * ((f * t) % 1) - 1


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def kick():
    t = t_(0.35)
    f = 50 + 120 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + 0.3 * np.sin(2 * np.pi * 3000 * t) * np.exp(-t * 300)


def clap():
    t = t_(0.25)
    n = rng.standard_normal(len(t))
    env = np.exp(-t * 25) + 0.6 * np.exp(-((t - 0.012) % 0.011) * 400) * (t < 0.035)
    return np.diff(np.concatenate([[0], n]), 1) * env * 0.6


def hat(open_=False):
    t = t_(0.18 if open_ else 0.05)
    n = rng.standard_normal(len(t))
    n = n - lowpass(n, 7000)
    return n * np.exp(-t * (18 if open_ else 90))


def pluck(m, length=BEAT / 2):
    t = t_(length)
    f = note(m)
    x = saw(f, t) + 0.5 * saw(f * 1.005, t)
    return lowpass(x * np.exp(-t * 9), 600 + 5000 * np.exp(-t * 18)) * 0.5


def bass(m, length):
    t = t_(length)
    f = note(m)
    x = saw(f, t) * 0.6 + np.sin(2 * np.pi * f * t)
    env = np.minimum(1, t * 200) * np.exp(-t * 2.2)
    return lowpass(x * env, 900)


def pad(ms, length, cutoff):
    t = t_(length)
    x = sum(saw(note(m) * d, t) for m in ms for d in (0.997, 1.003))
    env = np.minimum(1, t * 6) * np.minimum(1, (length - t) * 8)
    return lowpass(x * env / len(ms), cutoff) * 0.35


# I–V–vi–IV (C G Am F), 한 코드 = 1마디(4박)
CHORDS = [[60, 64, 67, 72], [55, 59, 62, 67], [57, 60, 64, 69], [53, 57, 60, 65]]
ROOTS = [36, 31, 33, 29]
BAR = 4 * BEAT
INTRO = 2 * BAR                      # 약 3.75초
END = DUR - 2.2                      # 마지막 히트 시점
bars = int(np.ceil(END / BAR))

for b in range(bars):
    t0 = b * BAR
    ch, root = CHORDS[b % 4], ROOTS[b % 4]
    main = t0 >= INTRO
    # 코드 패드(인트로는 필터가 점점 열림)
    cut = 500 + 2500 * (b / 2) if not main else 3200
    put(pad(ch, BAR, cut), t0, 0.5 if main else 0.6)
    # 아르페지오(16분음표)
    arp = ch + [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12]
    for k in range(16):
        tt = t0 + k * BEAT / 4
        if tt >= END:
            break
        put(pluck(arp[(k * 3) % len(arp)] + 12, BEAT / 3), tt, 0.28 if main else 0.18 * (k / 16 + b), pan=0.4 * np.sin(k))
    if not main:
        continue
    for k in range(4):
        tb = t0 + k * BEAT
        if tb >= END:
            break
        put(kick(), tb, 0.95, buf=kicks)
        if k in (1, 3):
            put(clap(), tb, 0.55)
        put(hat(True), tb + BEAT / 2, 0.22, pan=0.3)
        put(hat(), tb + BEAT / 4, 0.12, pan=-0.3); put(hat(), tb + 3 * BEAT / 4, 0.12, pan=-0.3)
        # 오프비트 베이스(펌핑)
        put(bass(root + (12 if k == 3 else 0), BEAT / 2), tb + BEAT / 2, 0.55)

# 인트로 끝 스네어 롤 + 상승 노이즈
for i in range(16):
    put(clap(), INTRO - BAR / 2 + i * BAR / 32, 0.15 + 0.35 * i / 16)
t = t_(INTRO)
riser = rng.standard_normal(len(t)) * (t / INTRO) ** 3
put(riser - lowpass(riser, 2000), 0, 0.25)

# 엔딩: 큰 히트 + 길게 울리는 코드
put(kick(), END, 1.1, buf=kicks); put(clap(), END, 0.7)
put(pad([48, 60, 64, 67, 72], 3.4, 2600), END, 0.9)
put(bass(24, 2.5), END, 0.7)

# 사이드체인 느낌: 킥마다 전체를 살짝 눌렀다 펴기
duck = np.ones(N)
for b in np.arange(INTRO, END, BEAT):
    i = int(b * SR); L = int(0.18 * SR)
    duck[i:i + L] *= 1 - 0.35 * np.exp(-np.arange(L) / SR * 18)
mix[:, 0] *= duck; mix[:, 1] *= duck
mix += kicks

mix = mix[:int(SR * DUR)]
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6) * 0.89   # 부드러운 리미터
fade = int(SR * 0.6)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
out = sys.argv[1] if len(sys.argv) > 1 else 'bgm.wav'
import wave
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', out, DUR)

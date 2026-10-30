"""배경음악 박자 분석: 템포(BPM), 비트 시각, 마디 첫 박(다운비트) 위치.
무거운 음악 라이브러리 없이 ffmpeg(디코딩) + numpy만 쓴다(NAS에서도 수 초 이내).
방법: 스펙트럼 플럭스 온셋 → 자기상관으로 템포 → 동적계획법 비트 추적(Ellis 2007) → 저음 에너지로 다운비트."""
import subprocess
import numpy as np

SR = 11025
HOP = 128
NFFT = 1024
FPS = SR / HOP


def _decode(path, max_sec=600):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-t', str(max_sec), '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _onsets(x):
    win = np.hanning(NFFT).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP] * win
    logm = np.log1p(100 * np.abs(np.fft.rfft(frames, axis=1)))
    d = np.maximum(0, np.diff(logm, axis=0))
    hz = SR / NFFT
    low = int(200 / hz) + 1                    # ~200Hz 이하(킥드럼)
    full, lowenv = d.sum(axis=1), d[:, :low].sum(axis=1)
    midenv = d[:, int(400 / hz):int(4000 / hz)].sum(axis=1)   # 스네어·박수 대역
    k = int(FPS * 0.4)                        # 지역 평균을 빼서 강세만 남김

    def norm(e):
        e = np.maximum(0, e - np.convolve(e, np.ones(k) / k, 'same'))
        return e / (e.std() + 1e-9)
    # 정박은 대개 킥(저음)이 친다: 엇박의 하이햇·베이스에 끌려가지 않도록 저음 강세를 더 크게
    return norm(full) + 2.0 * norm(lowenv), lowenv, norm(midenv)


def _tempo(env):
    n = len(env)
    f = np.fft.rfft(env - env.mean(), 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    lags = np.arange(int(FPS * 60 / 190), int(FPS * 60 / 60) + 1)
    bpm = 60 * FPS / lags
    prior = np.exp(-0.5 * (np.log2(bpm / 120) / 0.9) ** 2)   # 120BPM 근처를 약간 선호(배수 혼동 방지)
    score = ac[lags] * prior
    i = int(np.argmax(score))
    if 0 < i < len(lags) - 1:                  # 포물선 보간으로 소수점 lag
        a, b, c = score[i - 1], score[i], score[i + 1]
        off = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    else:
        off = 0
    return lags[i] + off


def _track(env, period, tight=100.0):
    """동적계획법: 비트 간격이 period에 가깝고 온셋이 강한 지점들의 최적 경로."""
    n = len(env)
    score = env.astype(float).copy()
    back = -np.ones(n, int)
    lo, hi = int(round(period / 2)), int(round(period * 2))
    prev = np.arange(-hi, -lo + 1)
    pen = -tight * np.log(-prev / period) ** 2
    for t in range(hi, n):
        cand = score[t + prev] + pen
        j = int(np.argmax(cand))
        score[t] += cand[j]; back[t] = t + prev[j]
    # 끝부분 최고점에서 거슬러 올라감
    t = int(np.argmax(score[max(0, n - hi):])) + max(0, n - hi)
    path = []
    while t >= 0:
        path.append(t); t = back[t]
    return np.array(path[::-1])


def analyze(path):
    """{'bpm', 'beats': [초...], 'down': 마디 첫 박의 인덱스 위상(0~3)} 또는 너무 짧으면 None."""
    x = _decode(path)
    if len(x) < SR * 6:
        return None
    env, lowenv, mid = _onsets(x)
    period = _tempo(env)
    fr = _track(env, period)
    # 정박/엇박 판정: 스네어·박수(중음 어택)는 대개 정박(2·4박)에 온다. 반 박 민 격자와 비교해 더 강한 쪽을 고른다.
    def peak(e, frames):
        f = np.clip(np.round(frames).astype(int), 2, len(e) - 3)
        return np.mean([e[i - 2:i + 3].max() for i in f]) if len(f) else 0
    alt = fr + period / 2
    alt = alt[alt < len(env) - 3]
    backbeat = lambda g: max(peak(mid, g[0::2]), peak(mid, g[1::2]))   # 2·4박(격박)만 강하게 치는 쪽
    if backbeat(alt) > 1.05 * backbeat(fr):
        fr = np.round(alt).astype(int)
    t = (fr + 1) * HOP / SR + NFFT / (2 * SR) + 0.035   # 프레임 -> 초(창 가운데 + 클릭 트랙으로 맞춘 보정값)
    t = t[t >= 0]
    # 다운비트: 4박 중 저음 강세가 가장 큰 위상
    li = np.clip(fr[-len(t):], 0, len(lowenv) - 1)
    down = int(np.argmax([lowenv[li[p::4]].mean() if len(li[p::4]) else 0 for p in range(4)]))
    return {'bpm': round(60 * FPS / period, 1), 'beats': [round(float(v), 3) for v in t], 'down': down}


# ---------------------------------------------------------------- 장면 시점 맞추기
def snap_times(length, n, beats=None, down=0, audio_start=0.0, audio_dur=None):
    """장면 시작 시각 [s1..sn]과 엔딩 시작 os를 돌려준다.
    기본은 균등 배분(오프닝 3.6초, 엔딩 4.4초). beats가 있으면 각 경계를 가장 가까운 비트로 옮기되,
    한 박 안쪽에 마디 첫 박이 있으면 그쪽을 우선한다. 화면(index.html timing())도 같은 규칙을 쓴다."""
    step = (length - 8) / n
    base = [3.6 + step * i for i in range(n)] + [3.6 + step * n]
    if not beats or n < 1:
        return [round(v, 2) for v in base[:-1]], round(base[-1], 2)
    end = length if audio_dur is None else min(length, audio_dur)
    bt = [(b - audio_start, (k - down) % 4 == 0) for k, b in enumerate(beats) if 0.5 < b - audio_start < end - 0.3]
    if len(bt) < 4:
        return [round(v, 2) for v in base[:-1]], round(base[-1], 2)
    ib = sorted(b2 - b1 for (b1, _), (b2, _) in zip(bt, bt[1:]))[len(bt) // 2]   # 비트 간격(중앙값)
    out, last = [], 0.0
    for k, want in enumerate(base):
        lo = last + (2.4 if k else 2.6)                       # 장면은 최소 2.4초(오프닝은 2.6초) 보장
        hi = (length - 3.4) if k == n else want + min(step * 0.45, 2 * ib)
        if k == n:
            lo = max(lo, length - 5.6)
        cands = [(t, d) for t, d in bt if lo <= t <= hi and abs(t - want) <= max(step * 0.45, ib)]
        if not cands:
            pick = min(max(want, lo), hi) if lo <= hi else want
        else:
            near = min(cands, key=lambda c: abs(c[0] - want))
            downs = [c for c in cands if c[1] and abs(c[0] - want) <= abs(near[0] - want) + ib * 1.01]
            pick = (min(downs, key=lambda c: abs(c[0] - want)) if downs else near)[0]
        out.append(pick); last = pick
    return [round(v, 2) for v in out[:-1]], round(out[-1], 2)

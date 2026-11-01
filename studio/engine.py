"""Script validation, job building and the render runner for H3 Studio.

A project lives in jobs/studio/<id>/ and its project.json is the only source of truth, written atomically, so
a crash or reboot at any moment can be resumed. A scene counts as finished only when its file passes validation
and its chain hash matches, so editing a scene automatically re-renders that scene and everything after it.
"""
import hashlib, io, json, math, os, random, re, shutil, subprocess, threading, time, uuid
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAN = ROOT / "Wan2GP"
PY = WAN / "env_venv" / "Scripts" / "python.exe"
FFMPEG = WAN / "ffmpeg_bins" / "ffmpeg.exe"
FFPROBE = WAN / "ffmpeg_bins" / "ffprobe.exe"
GPU_SAFE = ROOT / "tools" / "gpu-safe.ps1"
PROJECTS = ROOT / "jobs" / "studio"
CHARACTERS = ROOT / "jobs" / "characters"
SETTINGS = ROOT / "jobs" / "settings.json"

MODEL = "minimax_h3_fl2va_pruned_pdd"
REF_MODEL = "minimax_h3_ref2va_pruned_pdd"  # Same family, but also takes reference images that hold a character's design.
PINNED_COMMIT = "3a8ced9c"
FPS = 24
MIN_FRAMES, FRAME_STEP = 107, 17  # H3 accepts only 107 + 17n frames.
STEPS = 8

# Tested on this PC. Sizes are multiples of 32 because H3 snaps to that anyway.
# ponytail: per-size scene caps come from three test runs (peak 91C at 1280x704, 10s); retune if cooling changes.
PRESETS = {
    "480x832": {"label": "세로 480p (480x832)", "max_seconds": 10.0},
    "832x480": {"label": "가로 480p (832x480)", "max_seconds": 10.0},
    "704x1280": {"label": "세로 720p (704x1280)", "max_seconds": 8.0},
    "1280x704": {"label": "가로 720p (1280x704)", "max_seconds": 8.0},
}
MAX_SCENES, MAX_TOTAL_SECONDS = 12, 90
MIN_TEXT, MAX_TEXT = 20, 1500

# Safety limits. The GPU's own max operating temperature is 93C and it slows down at 95C.
# What proved stable on the RTX 3070 Ti (220W of 310W, 1800MHz of 2130MHz), as shares so they fit any card.
POWER_SHARE, CLOCK_SHARE = 220 / 310, 1800 / 2130
TEST_WARN_TEMP_C = 85  # A short test that gets this hot leaves no margin for longer scenes.
STOP_TEMP_C, STOP_SAMPLES = 93, 3
PAUSE_TEMP_C, RESUME_TEMP_C = 90, 85  # Freeze generation while the GPU cools, so a hot scene is slower instead of lost.
COOL_TEMP_C = 55
COOL_TIMEOUT_S = 15 * 60
STALL_TIMEOUT_S = 20 * 60  # Longest silent stretch before a render is treated as hung.
SAFE_TIMEOUT_S = 180       # Time allowed for the user to answer the UAC prompt.
MIN_DISK_GB, MIN_RAM_GB, MAX_START_VRAM_MB = 15, 16, 2500
SECONDS_PER_MEGAPIXEL_FRAME = 3.7  # Fit over 84 scenes on the RTX 3070 Ti. speed_factor() adapts it to other PCs.
LOAD_SECONDS = 113
PROJECT_OVERHEAD_S = 45  # Music and joining, measured across 16 finished projects.
MAX_RETRIES = 1
MIN_VRAM_MB = 7500  # Tested on an 8GB card, which reports slightly under 8192MB on some drivers.
MODEL_FILE = "MiniMax-H3-FL2VA-pruned_rank8_int8_convrot.safetensors"
REF_MODEL_FILE = "MiniMax-H3-Ref2VA-pruned_rank8_int8_convrot.safetensors"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# MiniMax H3 Community License (2026-08-02): the license is not granted in its Excluded Territories, and using or showing
# H3 outputs there is not allowed either. Set H3_LICENSE_REGION to where this PC runs, or H3_LICENSE_GRANTED=1 with a separate
# license from MiniMax (api@minimax.io). https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE
H3_EXCLUDED_REGIONS = {"KR", "US", "GB", "UK", "EU"} | {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


def _env(name):
    """Environment variable, or the same line in the project's .env (the server reads keys the same way)."""
    v = os.environ.get(name)
    p = ROOT / ".env"
    if v is None and p.is_file():
        m = re.search(r"^%s=(.*)$" % name, p.read_text(encoding="utf-8"), re.M)
        v = m and m.group(1).strip().strip("\"'")
    return v or ""


def license_notice():
    """A warning shown above the create form when the H3 license does not cover this region, or ''.
    It only informs: generation stays allowed, and the user decides."""
    if _env("H3_LICENSE_GRANTED").strip() == "1":
        return ""
    region = _env("H3_LICENSE_REGION").strip().upper() or "KR"
    if region not in H3_EXCLUDED_REGIONS:
        return ""
    return ("MiniMax H3 라이선스는 대한민국·미국·영국·EU에서 모델과 생성 영상의 사용을 허용하지 않습니다. "
            "공모전 출품이나 외부 게시용 영상에는 쓰지 마세요. "
            "MiniMax(api@minimax.io)에서 별도 라이선스를 받았다면 .env에 H3_LICENSE_GRANTED=1을 넣으면 이 안내가 사라집니다.")


ID_RE = re.compile(r"^[0-9a-f]{12}$")


class StudioError(Exception):
    """A failure with a message for the user. `resumable=False` means fix something else first."""
    def __init__(self, message, kind="error"):
        super().__init__(message)
        self.kind = kind


# ---------- Pure logic: calculation and validation ----------

def frames_for(seconds):
    """Nearest allowed frame count for a duration."""
    n = round((seconds * FPS - MIN_FRAMES) / FRAME_STEP)
    return MIN_FRAMES + FRAME_STEP * max(0, n)


def extract_json(text):
    """LLMs wrap JSON in fences and chatter, so take the outermost object."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("JSON을 찾지 못했습니다. LLM 답변의 { 부터 } 까지 전체를 붙여 넣으세요.")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 형식 오류 ({e.lineno}번째 줄, {e.colno}번째 글자): {e.msg}. "
                         "LLM에게 'JSON만 다시 출력해줘'라고 요청해 보세요.")


def _text_field(d, key, where, errors, required=True, max_len=MAX_TEXT, min_len=MIN_TEXT):
    v = d.get(key)
    if v is None or v == "":
        if required:
            errors.append(f"{where}: '{key}' 항목이 없습니다.")
        return ""
    if not isinstance(v, str):
        errors.append(f"{where}: '{key}'는 문자열이어야 합니다.")
        return ""
    v = " ".join(v.split())  # A stray newline inside a field would break H3's labelled prompt format.
    if len(v) < min_len:
        errors.append(f"{where}: '{key}'가 너무 짧습니다({len(v)}자). 구체적으로 묘사해야 합니다.")
    if len(v) > max_len:
        errors.append(f"{where}: '{key}'가 너무 깁니다({len(v)}자, 최대 {max_len}자).")
    return v


def validate_script(data, size):
    """Returns (clean script, errors, warnings). Accepts raw text or an already parsed dict."""
    errors, warnings = [], []
    if size not in PRESETS:
        return None, [f"지원하지 않는 해상도입니다: {size}"], []
    if isinstance(data, str):
        try:
            data = extract_json(data)
        except ValueError as e:
            return None, [str(e)], []
    if not isinstance(data, dict):
        return None, ["최상위가 JSON 객체({ ... })여야 합니다."], []

    clean = {
        "title": _text_field(data, "title", "제목", errors, max_len=80, min_len=1),
        "character": _text_field(data, "character", "캐릭터", errors),
        "style": _text_field(data, "style", "스타일", errors),
        "music": _text_field(data, "music", "음악", errors, required=False),
        "scenes": [],
    }
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("'scenes' 목록이 없습니다.")
        return clean, errors, warnings
    if len(scenes) > MAX_SCENES:
        errors.append(f"장면이 너무 많습니다({len(scenes)}개, 최대 {MAX_SCENES}개).")

    max_seconds = PRESETS[size]["max_seconds"]
    for i, s in enumerate(scenes, 1):
        where = f"장면 {i}"
        if not isinstance(s, dict):
            errors.append(f"{where}: 객체여야 합니다.")
            continue
        sec = s.get("seconds")
        if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not math.isfinite(sec) or sec <= 0:
            errors.append(f"{where}: 'seconds'는 양수여야 합니다.")
            sec = MIN_FRAMES / FPS
        elif sec > max_seconds + FRAME_STEP / FPS / 2:  # Tolerance: snapping can round a duration up slightly.
            errors.append(f"{where}: {sec}초는 이 해상도의 장면당 최대 {max_seconds:g}초를 넘습니다. 장면을 나누세요.")
        frames = frames_for(sec)
        if sec > 0 and sec < MIN_FRAMES / FPS - 0.01:
            warnings.append(f"{where}: H3 최소 길이 때문에 {frames / FPS:.1f}초로 늘어납니다.")
        action = _text_field(s, "action", where, errors)
        sound = _text_field(s, "sound", where, errors, min_len=5)
        clean["scenes"].append({"seconds": frames / FPS, "frames": frames, "action": action, "sound": sound})

    total = sum(s["seconds"] for s in clean["scenes"])
    if total > MAX_TOTAL_SECONDS:
        errors.append(f"전체 길이 {total:.0f}초가 최대 {MAX_TOTAL_SECONDS}초를 넘습니다.")
    joined = " ".join([clean["character"], clean["style"]] + [s["action"] + " " + s["sound"] for s in clean["scenes"]])
    if re.search(r"[가-힣]", joined):
        warnings.append("프롬프트에 한글이 있습니다. 영어 프롬프트로만 시험했으므로 결과가 달라질 수 있습니다.")
    if re.search(r"https?://", joined):
        errors.append("프롬프트에 URL이 있습니다. LLM 답변을 다시 확인하세요.")
    return clean, errors, warnings


def scene_prompt(script, scene):
    return (f"integrated_multimodal_description: [Shot 1] {scene['action']} Main character: {script['character']} "
            f"Style: {script['style']} Single continuous shot. No text, no subtitles, no logo."
            f"\noverall_soundscape: {scene['sound']}"
            "\nnon_diegetic_music: None. No music, sound effects only.")


def project_cast(project):
    """The project's characters in A, B, C order. Projects made when only one was possible keep their files and hashes."""
    if project.get("characters"):
        return project["characters"]
    c = project.get("character")
    return [dict(c, files=[f"{k}.png" for k in range(len(c["views"]))])] if c else []


def scene_cast(scene, count):
    """Indexes of the characters this scene names as 'Character A'. Naming none means all, so nobody silently loses their references."""
    named = {ord(x) - 65 for x in re.findall(r"\bCharacter ([A-Z])\b", scene["action"])}
    return sorted(i for i in named if i < count) or list(range(count))


def cast_errors(script, count):
    """A scene naming a character the project does not have would otherwise render a stranger."""
    if count < 2:
        return []
    errors = []
    for i, scene in enumerate(script["scenes"], 1):
        for x in sorted(set(re.findall(r"\bCharacter ([A-Z])\b", scene["action"]))):
            if ord(x) - 65 >= count:
                errors.append(f"장면 {i}: Character {x}는 고른 캐릭터에 없습니다. Character A~{chr(64 + count)}만 쓸 수 있습니다.")
    return errors


def cast_prompt(script, scene, cast, first_picture, has_start):
    """Ref2VA's format for several characters. Pictures number from first_picture in the order of `cast`, a list of (letter, character)."""
    defs, kept, picture = [], [], first_picture
    for n, (letter, c) in enumerate(cast, 1):
        views = ", ".join(f"<Picture {picture + k}> ({label})" for k, label in enumerate(c["views"]))
        picture += len(c["views"])
        defs.append(f"<Subject {n}>, called Character {letter}, is the character shown in {views}, preserving this exact design: {c['description']}")
        kept.append(f"<Subject {n}> (appears in [Shot 1]): fully_preserved - its body shape, colors, face and accessories remain unchanged, and it never takes the features of another character.")
    defs, kept = "\n".join(defs), "\n".join(kept)
    start = "<Picture 1> is the starting frame and the shot continues directly from it. " if has_start else ""
    count = f"Exactly {len(cast)} main characters in the shot, each fully visible. " if len(cast) > 1 else ""
    return (f"subject_definitions:\n{defs}"
            f"\nsummary:\n[reference generation] One continuous shot: {scene['action']}"
            f"\nretention_analysis:\n{kept}"
            f"\ndetailed_description:\n[Shot 1] {start}{scene['action']} Style: {script['style']} Single continuous shot. {count}"
            "The design of each character stays stable through the whole shot. No text, no subtitles, no logo."
            f"\noverall_soundscape: {scene['sound']}"
            "\nnon_diegetic_music: None. No music, sound effects only.")


def reference_prompt(script, scene, character, first_picture, has_start):
    """Ref2VA's labelled format. Start and end frames take the first picture numbers, so references start at first_picture."""
    views = ", ".join(f"<Picture {first_picture + k}> ({label})" for k, label in enumerate(character["views"]))
    start = "<Picture 1> is the starting frame and the shot continues directly from it. " if has_start else ""
    return (f"subject_definitions:\n<Subject 1> is the same character shown in {views}, preserving this exact design: {character['description']}"
            f"\nsummary:\n[reference generation] Place <Subject 1> in one continuous shot: {scene['action']}"
            "\nretention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved - body shape, colors, face and accessories remain "
            "recognizable and unchanged; only the location, lighting and action are new."
            f"\ndetailed_description:\n[Shot 1] {start}{scene['action']} Style: {script['style']} Single continuous shot. "
            "The design of <Subject 1> stays stable through the whole shot. No text, no subtitles, no logo."
            f"\noverall_soundscape: {scene['sound']}"
            "\nnon_diegetic_music: None. No music, sound effects only.")


def build_jobs(project, pdir):
    """One Wan2GP settings dict per scene, plus the chain hash that decides what is still valid."""
    script, size = project["script"], project["size"]
    frames_dir = (Path(pdir) / "frames").as_posix()
    jobs, prev = [], ""
    n = len(script["scenes"])
    for i, scene in enumerate(script["scenes"], 1):
        # Chained scenes on one seed built up a grainy texture in tests; a new seed per scene stayed clean.
        # Projects made before this have no flag, so their finished scenes keep matching their hashes.
        default_seed = project["seed"] + (i - 1) * 1009 if project.get("scene_seeds") else project["seed"]
        job = {
            "model_type": MODEL,
            "prompt": scene_prompt(script, scene),
            "resolution": size,
            "video_length": scene["frames"],
            "seed": int(scene.get("seed", default_seed)),
            "num_inference_steps": STEPS,
            "image_prompt_type": "T" if i == 1 else "S",
        }
        if i > 1:
            job["image_start"] = f"{frames_dir}/s{i - 1}_last.png"
        if i == n and n > 1 and project.get("loop"):
            job["image_prompt_type"] = "SE"
            job["image_end"] = f"{frames_dir}/s1_first.png"
        characters = project_cast(project)
        if characters:
            first = 1 + ("image_start" in job) + ("image_end" in job)
            cast = [(chr(65 + k), characters[k]) for k in scene_cast(scene, len(characters))]
            prompt = (reference_prompt(script, scene, characters[0], first, "image_start" in job) if len(characters) == 1
                      else cast_prompt(script, scene, cast, first, "image_start" in job))
            job.update(model_type=REF_MODEL, video_prompt_type="I", prompt=prompt,
                       image_refs=[(Path(pdir) / "refs" / f).as_posix() for _, c in cast for f in c["files"]])
        chain = {k: v for k, v in job.items() if k not in ("image_start", "image_end")}
        chain["loop_end"] = "image_end" in job
        prev = hashlib.sha256((prev + json.dumps(chain, sort_keys=True)).encode()).hexdigest()[:16]
        jobs.append((job, prev))
    return jobs


def music_job(script, seconds, seed):
    return {
        "model_type": "stable_audio3_small", "prompt": script["music"], "audio_prompt_type": "",
        "duration_seconds": min(30, math.ceil(seconds) + 2), "num_inference_steps": 8, "guidance_scale": 1.0,
        "audio_scale": 0.9, "negative_prompt": "poor quality, distorted, noisy, vocals",
        "sample_solver": "pingpong", "seed": seed,
    }


def _formula_seconds(size, frames):
    w, h = map(int, size.split("x"))
    return LOAD_SECONDS + SECONDS_PER_MEGAPIXEL_FRAME * w * h * frames / 1e6


_speed = (0.0, 1.0)


def speed_factor():
    """Measured time against the formula over the latest 40 scenes, so estimates fit this PC. Cached because it reads every project."""
    global _speed
    if time.time() - _speed[0] < 300:
        return _speed[1]
    rows = []
    for d in PROJECTS.iterdir() if PROJECTS.exists() else []:
        try:
            p = load_project(d.name)
            scenes = p["script"]["scenes"]
            rows += [(r["at"], r["seconds"], _formula_seconds(p["size"], scenes[int(i) - 1]["frames"]))
                     for i, r in p.get("scene_results", {}).items()]
        except (StudioError, ValueError, KeyError, IndexError, OSError):
            continue
    rows = sorted(rows)[-40:]
    factor = min(5.0, max(0.2, sum(r[1] for r in rows) / sum(r[2] for r in rows))) if rows else 1.0
    _speed = (time.time(), factor)
    return factor


def estimate_scene_seconds(size, frames):
    return _formula_seconds(size, frames) * speed_factor()


LINE_PROGRESS = re.compile(r"\[(\d+)/(\d+)\]\s*([^|\r\n]*)")
TQDM_PROGRESS = re.compile(r"denoising:\s*\d+%.*?(\d+)/(\d+)\s*\[")


def parse_progress(line):
    """Stage name and fraction from a Wan2GP console line, or None."""
    m = TQDM_PROGRESS.search(line)
    if m:
        total = int(m.group(2))
        return ("Denoising", int(m.group(1)) / total) if total else None
    m = LINE_PROGRESS.search(line)
    if not m or not int(m.group(2)):
        return None
    stage = m.group(3).strip()
    stage = re.sub(r"\s+\S+\.(mp4|wav)\S*.*$", "", stage)  # Drop the file name in "Saving File ...".
    return (stage[:60] or "작업 중", int(m.group(1)) / int(m.group(2)))


FAILURES = [  # (log text, kind, message). First match wins; kind "gpu" means retrying is pointless until a reboot.
    ("No CUDA GPUs are available", "gpu", "GPU가 응답하지 않습니다. 재부팅한 뒤 '이어서 생성'을 누르세요."),
    ("CUDA error 999", "gpu", "GPU 드라이버가 크래시했습니다. 재부팅한 뒤 '이어서 생성'을 누르세요."),
    ("device-side assert", "gpu", "GPU 오류가 발생했습니다. 재부팅한 뒤 '이어서 생성'을 누르세요."),
    ("out of memory", "memory", "메모리가 부족합니다. GPU를 쓰는 다른 프로그램을 닫거나, 장면 길이나 해상도를 줄이세요."),
    ("LocalEntryNotFoundError", "missing", "모델 파일이 없습니다. 이 PC에서 시험한 파일이 지워졌거나 옮겨졌는지 확인하세요."),
    ("No space left", "disk", "디스크 공간이 부족합니다."),
]


def classify_failure(log_tail):
    low = log_tail.lower()
    for needle, kind, message in FAILURES:
        if needle.lower() in low:
            return kind, message
    return "unknown", "생성이 실패했습니다. 아래 로그를 확인하세요."


def join_filter(frame_counts, has_music, total_seconds):
    """ffmpeg graph. Scenes after the first open on the previous last frame, so that duplicate is dropped."""
    parts, labels = [], ""
    frame = 1 / FPS
    for i, frames in enumerate(frame_counts):
        end = frames / FPS
        if i == 0:
            parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[{i}:a]atrim=0:{end:.6f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            parts.append(f"[{i}:v]trim=start_frame=1,setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[{i}:a]atrim={frame:.6f}:{end:.6f},asetpts=PTS-STARTPTS[a{i}]")
        labels += f"[v{i}][a{i}]"
    parts.append(f"{labels}concat=n={len(frame_counts)}:v=1:a=1[v][sfx]")
    if has_music:
        fade = max(0.0, total_seconds - 1.5)
        parts.append(f"[{len(frame_counts)}:a]volume=0.25,afade=t=out:st={fade:.3f}:d=1.5[m]")
        parts.append("[sfx][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5[a]")
    else:
        parts.append("[sfx]loudnorm=I=-16:TP=-1.5[a]")
    return ";".join(parts)


def llm_prompt(topic, audience, style, scene_count, total_seconds, size, loop, characters=()):
    """The instruction sheet the user pastes into a free LLM. characters: the chosen character records, in A, B, C order."""
    fixed = ""
    if len(characters) == 1:
        fixed = (f"MAIN CHARACTER (fixed by reference images): {characters[0]['description']}\n"
                 'Copy this sentence exactly into "character". In "action", refer to the main character only by a short name and describe what they do, not how they look.\n')
    elif characters:
        rows = "".join(f"- Character {chr(65 + k)} (the topic may call them \"{c['name']}\"): {c['description']}\n" for k, c in enumerate(characters))
        fixed = ("MAIN CHARACTERS (fixed by reference images):\n" + rows +
                 'Set "character" to exactly "The main characters are fixed by reference images." In every "action", call them exactly "Character A", "Character B" and so on, '
                 "name everyone who appears in that scene, say where each one stands in the frame, and describe what they do, not how they look. Use at most two main characters in one scene.\n")
    per_scene = total_seconds / scene_count
    limit = PRESETS[size]["max_seconds"]
    w, h = map(int, size.split("x"))
    shape = "vertical 9:16" if h > w else "horizontal 16:9"
    loop_rule = ("- The last scene must end on the same composition as the very first moment of scene 1, so the video "
                 "loops.\n") if loop else ""
    return f"""You are writing a video generation script for an AI video model. Reply with one JSON object only, no explanation and no code fence.

STORY TOPIC: {topic}
AUDIENCE: {audience}
VISUAL STYLE: {style}
{fixed}FORMAT: {shape}, {scene_count} scenes, about {total_seconds:g} seconds in total

JSON FORMAT:
{{
  "title": "short title",
  "character": "one sentence fixing the main character's look: species, colors, eyes, body proportions, clothing",
  "style": "one sentence fixing the rendering style, lighting and color palette",
  "music": "one sentence describing an original instrumental background track: instruments, mood, tempo",
  "scenes": [
    {{"seconds": {per_scene:.1f}, "action": "what happens in this scene", "sound": "sound effects in this scene"}}
  ]
}}

RULES:
- Write every value in English.
- Each scene is {MIN_FRAMES / FPS:.1f} to {limit:g} seconds. Scene seconds must add up to about {total_seconds:g}.
- Each scene is a single continuous shot in the same location with one or two simple actions. Do not use cuts.
- Every scene after the first starts exactly where the previous one ended, so each "action" must continue from the previous scene's final moment. Describe the end state of each scene clearly.
- Name concrete, visible things: exact colors, sizes, positions and motions. Avoid vague words like "magical moment". To change a color, say the entire object turns solid red, then solid blue.
- Keep the camera simple and name its behavior, such as "locked-off static camera" or "slow push-in".
- Keep the character count small and state it. If new characters appear, describe their colors and keep them consistent later.
- "sound" lists sound effects only. Do not put music in it, and do not write speech or dialogue unless the story requires it.
- No on-screen text, subtitles, logos or brand names. No copyrighted characters or famous songs. No frightening or violent content.
{loop_rule}- Write positive descriptions only. There is no negative prompt.
"""


# ---------- Project storage ----------

def project_dir(pid):
    if not ID_RE.match(pid or ""):
        raise StudioError("잘못된 프로젝트 ID입니다.")
    return PROJECTS / pid


def save_project(project):
    pdir = project_dir(project["id"])
    pdir.mkdir(parents=True, exist_ok=True)
    tmp = pdir / f"project.{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding="utf-8")
    for attempt in range(10):  # Windows refuses the replace while antivirus or a reader holds the file briefly.
        try:
            os.replace(tmp, pdir / "project.json")
            return
        except PermissionError:
            time.sleep(0.2 * (attempt + 1))
    os.unlink(tmp)
    raise StudioError("project.json을 저장하지 못했습니다.")


def load_project(pid):
    path = project_dir(pid) / "project.json"
    if not path.exists():
        raise StudioError("프로젝트를 찾을 수 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_cast(ids):
    """The chosen characters in order, refusing what H3 cannot take."""
    if not isinstance(ids, list) or len(ids) != len(set(ids)):
        raise StudioError("캐릭터 선택이 잘못됐습니다.")
    cast = [load_character(c) for c in ids]
    total = sum(len(c["views"]) for c in cast)
    if total > MAX_CAST_IMAGES:
        raise StudioError(f"고른 캐릭터의 이미지가 모두 {total}장입니다. H3는 참고 이미지를 {MAX_CAST_IMAGES}장까지 받습니다. 캐릭터를 줄이세요.")
    return cast


def create_project(script, size, loop, seed=None, characters=()):
    project = {
        "id": uuid.uuid4().hex[:12], "created": time.time(), "script": script, "size": size, "loop": bool(loop),
        "seed": random.randint(1, 2 ** 31 - 1) if seed is None else int(seed), "scene_seeds": True,
        "status": "ready", "message": "", "scene_results": {}, "version": 1, "warnings": [],
    }
    cast = load_cast(list(characters))
    errors = cast_errors(script, len(cast))
    if errors:
        raise StudioError(" / ".join(errors))
    if cast:
        script["character"] = " ".join(f"Character {chr(65 + k)}: {c['description']}" for k, c in enumerate(cast)) if len(cast) > 1 else cast[0]["description"]
        refs = project_dir(project["id"]) / "refs"  # A project keeps its own copy, so it can still resume after a character is deleted.
        refs.mkdir(parents=True)
        project["characters"] = []
        for n, c in enumerate(cast):
            files = [f"{n}_{k}.png" for k in range(len(c["views"]))]
            for k, f in enumerate(files):
                shutil.copyfile(character_dir(c["id"]) / f"{k}.png", refs / f)
            project["characters"].append({**{k: c[k] for k in ("id", "name", "description", "views")}, "files": files})
    save_project(project)
    return project


# ---------- Characters ----------

CHARACTER_VIEWS = {"front": "front view", "side": "side view", "back": "back view", "pose": "full-body pose"}
MAX_CHARACTER_IMAGE_BYTES = 30 * 1024 * 1024
MAX_CAST_IMAGES = 9  # H3's limit on reference images. Start and end frames are separate inputs.
CHARACTER_IMAGE_SIZE = 1024


def character_dir(cid):
    if not ID_RE.match(cid or ""):
        raise StudioError("잘못된 캐릭터 ID입니다.")
    return CHARACTERS / cid


def load_character(cid):
    try:
        return json.loads((character_dir(cid) / "character.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StudioError("캐릭터를 찾을 수 없습니다.")


def list_characters():
    out = []
    for d in CHARACTERS.iterdir() if CHARACTERS.exists() else []:
        try:
            out.append(load_character(d.name))
        except StudioError:
            continue
    return sorted(out, key=lambda c: c["created"])


def _character_image(data):
    """Any picture format in; a white-backed square PNG out, the form the character test used."""
    from PIL import Image, ImageOps
    if len(data) > MAX_CHARACTER_IMAGE_BYTES:
        raise StudioError("이미지가 너무 큽니다(최대 30MB).")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGBA")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise StudioError("이미지를 읽지 못했습니다. PNG나 JPG 파일을 올리세요.")
    back = Image.new("RGB", im.size, "white")
    back.paste(im, mask=im.getchannel("A"))
    side = CHARACTER_IMAGE_SIZE
    return ImageOps.pad(back, (side, side), color="white")


def create_character(name, description, images):
    """images: {view: bytes}, view being a CHARACTER_VIEWS key. Written to a temp folder first, so a bad image leaves nothing behind."""
    name = " ".join(str(name or "").split())
    description = " ".join(str(description or "").split())
    if not 1 <= len(name) <= 40:
        raise StudioError("캐릭터 이름을 40자 안으로 입력하세요.")
    if not MIN_TEXT <= len(description) <= MAX_TEXT:
        raise StudioError(f"생김새 설명을 {MIN_TEXT}~{MAX_TEXT}자로 입력하세요.")
    if re.search(r"[가-힣]", description):
        raise StudioError("생김새 설명은 영어로 입력하세요. 영어 프롬프트로만 시험했습니다.")
    views = [v for v in CHARACTER_VIEWS if images.get(v)]
    if not views:
        raise StudioError("이미지를 한 장 이상 올리세요.")
    pictures = [_character_image(images[v]) for v in views]
    cid = uuid.uuid4().hex[:12]
    tmp = CHARACTERS / f".new-{cid}"
    tmp.mkdir(parents=True)
    try:
        for k, im in enumerate(pictures):
            im.save(tmp / f"{k}.png")
        character = {"id": cid, "name": name, "description": description, "views": [CHARACTER_VIEWS[v] for v in views], "created": time.time()}
        (tmp / "character.json").write_text(json.dumps(character, ensure_ascii=False, indent=1), encoding="utf-8")
        os.rename(tmp, character_dir(cid))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return character


def delete_character(cid):
    load_character(cid)
    shutil.rmtree(character_dir(cid))


def list_projects():
    out = []
    if PROJECTS.exists():
        for d in PROJECTS.iterdir():
            try:
                p = load_project(d.name)
                if p.get("test"):
                    continue  # System tests show on the setup page.
                out.append({"id": p["id"], "title": p["script"]["title"], "status": p["status"], "created": p["created"]})
            except (StudioError, ValueError, KeyError, OSError):
                continue  # A damaged folder must not hide the other projects.
    return sorted(out, key=lambda p: -p["created"])


def archive_scenes(project, first_scene):
    """Moves scene files from first_scene on and the final video into versions/, instead of deleting them."""
    pdir = project_dir(project["id"])
    moved = []
    for i in range(first_scene, MAX_SCENES + 1):
        f = pdir / "scenes" / f"s{i}.mp4"
        if f.exists():
            moved.append(f)
    final = pdir / "final.mp4"
    if final.exists():
        moved.append(final)
    if moved:
        dest = pdir / "versions" / f"v{project['version']}"
        dest.mkdir(parents=True, exist_ok=True)
        for f in moved:
            os.replace(f, dest / f.name)
        project["version"] += 1
    for i in range(first_scene, MAX_SCENES + 1):
        project["scene_results"].pop(str(i), None)


# ---------- Settings and exporting ----------

_settings_lock = threading.Lock()


def load_settings():
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def update_settings(**kw):
    with _settings_lock:
        data = load_settings()
        data.update(kw)
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, SETTINGS)


def videos_folder():
    """The user's Videos folder, which Windows lets people move, so the registry knows it and the home folder may not."""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                return Path(os.path.expandvars(winreg.QueryValueEx(k, "My Video")[0]))
        except OSError:
            pass
    return Path.home() / "Videos"


def export_dir():
    return Path(load_settings().get("export_dir") or videos_folder())


def set_export_dir(path):
    """Empty goes back to the default. Otherwise the folder must be usable now, not at the first copy."""
    path = str(path or "").strip().strip('"')
    if path:
        if not os.path.isabs(path):
            raise StudioError("전체 경로를 입력하세요. 예: D:\\내 영상")
        try:
            os.makedirs(path, exist_ok=True)
            probe = Path(path) / f".write-test-{uuid.uuid4().hex}"
            probe.write_bytes(b"")
            probe.unlink()
        except OSError as e:
            raise StudioError(f"이 폴더에 저장할 수 없습니다: {e}")
    update_settings(export_dir=path)


def safe_name(title):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip(" .") or "untitled"


def same_file(a, b):
    x, y = Path(a).stat(), Path(b).stat()
    return x.st_size == y.st_size and int(x.st_mtime) == int(y.st_mtime)


def export_video(src, title, target=None):
    """Copies a video in as NN_title.mp4 under the next number. Returns (path, copied).
    The same file is not copied twice, and an existing file with the same title is never replaced."""
    target, name = Path(target or export_dir()), safe_name(title)
    tmp = None
    try:
        target.mkdir(parents=True, exist_ok=True)
        top = 0
        for f in target.iterdir():
            m = re.fullmatch(r"(\d+)_(.*)\.mp4", f.name)
            if m:
                top = max(top, int(m[1]))
                if m[2] == name and same_file(src, f):
                    return f, False
        out = target / f"{top + 1:02d}_{name}.mp4"
        tmp = out.with_suffix(".tmp")
        shutil.copy2(src, tmp)
        os.replace(tmp, out)
        return out, True
    except OSError as e:
        if tmp:
            tmp.unlink(missing_ok=True)
        raise StudioError(f"{target}에 복사하지 못했습니다: {e}")


def _dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def storage_report():
    """Disk use per project. The numbers are for choosing what to delete, so a folder that cannot be read just counts less."""
    rows = []
    jobs = PROJECTS.parent
    for d in jobs.iterdir() if jobs.exists() else []:
        if not ID_RE.match(d.name):
            continue
        try:
            title = json.loads((d / "plan.json").read_text(encoding="utf-8")).get("title")
        except (OSError, ValueError, AttributeError):
            title = None
        rows.append({"kind": "promo", "id": d.name, "title": title or "제목 없음", "size": _dir_size(d)})
    spare = 0
    for d in PROJECTS.iterdir() if PROJECTS.exists() else []:
        spare += sum(_dir_size(d / n) for n in ("versions", "work")) if ID_RE.match(d.name) else _dir_size(d)
        try:
            p = load_project(d.name)
            rows.append({"kind": "h3", "id": d.name, "title": p["script"]["title"], "size": _dir_size(d), "status": p["status"]})
        except (StudioError, ValueError, KeyError, OSError):
            continue
    try:
        free = shutil.disk_usage(jobs).free
    except OSError:
        free = None
    return {"items": sorted(rows, key=lambda r: -r["size"]), "spare": spare, "free": free}


# ---------- System helpers ----------

def run_cmd(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=NO_WINDOW)


def gpu_sample():
    """Current GPU numbers, or None when the driver does not answer."""
    try:
        r = run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,power.limit,clocks.gr,memory.used,"
                     "memory.total,utilization.gpu,fan.speed", "--format=csv,noheader,nounits"], timeout=15)
        if r.returncode != 0:
            return None
        v = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        num = lambda s: float(s) if re.fullmatch(r"[\d.]+", s) else None
        return {"t": time.time(), "temp": num(v[0]), "power": num(v[1]), "limit": num(v[2]), "clock": num(v[3]),
                "mem": num(v[4]), "mem_total": num(v[5]), "util": num(v[6]), "fan": num(v[7])}
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def gpu_card():
    """The card's fixed numbers, or None. A number is None where this card does not report or allow it."""
    try:
        r = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,power.min_limit,power.default_limit,power.max_limit,clocks.max.gr",
                     "--format=csv,noheader,nounits"], timeout=15)
        if r.returncode != 0:
            return None
        v = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        num = lambda t: float(t) if re.fullmatch(r"[\d.]+", t) else None
        return {"name": v[0], "mem": num(v[1]), "power_min": num(v[2]), "power_default": num(v[3]), "power_max": num(v[4]), "clock_max": num(v[5])}
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def suggested_limits(card):
    power = clock = None
    if card and card["power_default"] and card["power_min"] and card["power_max"]:
        power = int(min(card["power_max"], max(card["power_min"], 5 * round(card["power_default"] * POWER_SHARE / 5))))
    if card and card["clock_max"]:
        clock = int(15 * round(card["clock_max"] * CLOCK_SHARE / 15))
    return {"power": power, "clock": clock}


def gpu_limits(card=None):
    """The limits to hold: what the user applied on this card, otherwise the suggestion for it."""
    card = card or gpu_card()
    limits, saved = suggested_limits(card), load_settings().get("gpu_limits") or {}
    if card and saved.get("card") == card["name"]:  # A swapped card must not inherit numbers meant for the old one.
        limits.update({k: saved[k] for k in ("power", "clock") if saved.get(k)})
    return limits


def run_gpu_safe(limits):
    """The UAC prompt appears here if the startup task did not already apply these numbers. Returns whether the script succeeded."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GPU_SAFE),
                            "-PowerLimit", str(int(limits["power"] or 0)), "-MaxClock", str(int(limits["clock"] or 0))],
                           timeout=SAFE_TIMEOUT_S, creationflags=NO_WINDOW)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def apply_gpu_limits(power, clock):
    """Validates against the card, applies, and remembers the numbers only once the card reports them."""
    card = gpu_card()
    if not card:
        raise StudioError("GPU가 응답하지 않습니다.")
    try:
        power, clock = int(power) if power else None, int(clock) if clock else None
    except (TypeError, ValueError):
        raise StudioError("전력과 클럭은 숫자로 입력하세요.")
    if power and card["power_min"] and not card["power_min"] <= power <= card["power_max"]:
        raise StudioError(f"이 GPU의 전력 제한은 {card['power_min']:.0f}~{card['power_max']:.0f}W입니다.")
    if clock and not 300 <= clock <= (card["clock_max"] or 4000):
        raise StudioError(f"클럭은 300~{card['clock_max'] or 4000:.0f}MHz로 입력하세요.")
    ok = run_gpu_safe({"power": power, "clock": clock})
    now = gpu_sample()
    if power and not (now and now["limit"] is not None and now["limit"] <= power + 1):
        raise StudioError("전력 제한을 적용하지 못했습니다. 관리자 확인 창에서 '예'를 눌렀는지 확인하세요.")
    if not ok:
        raise StudioError("일부 설정을 적용하지 못했습니다. 이 GPU가 클럭 제한을 지원하지 않거나 관리자 확인이 취소됐을 수 있습니다.")
    update_settings(gpu_limits={"card": card["name"], "power": power, "clock": clock})


def create_test_project(size):
    """The shortest scene the model takes, through the same path as a real video, marked so it stays out of the project list."""
    script = {"title": "시스템 시험 생성", "music": "",
              "character": "A small round yellow chick with big brown eyes and short orange legs.",
              "style": "Polished 3D children's animation with soft light and vivid colors.",
              "scenes": [{"seconds": MIN_FRAMES / FPS, "frames": MIN_FRAMES, "sound": "Soft footsteps on grass and light wind.",
                          "action": "The chick walks slowly across a green meadow from left to right under a locked-off static camera."}]}
    project = create_project(script, size, False)
    project["test"] = True
    save_project(project)
    return project


def test_verdict(status, kind, message, peak_temp, power, card):
    """(ok|warn|bad, words for the user, a lower power limit to try or None)."""
    lower = None
    if power and card and card["power_min"]:
        lower = int(max(card["power_min"], 5 * (power * 0.9 // 5)))
        lower = lower if lower < power else None
    step = f" 전력을 {lower}W로 낮춰 적용한 뒤 다시 시험해 보세요." if lower else " 더 낮출 수 없으니 케이스 환기와 팬을 점검하세요."
    if status == "done":
        if peak_temp is not None and peak_temp >= TEST_WARN_TEMP_C:
            return "warn", f"완료했지만 최고 {peak_temp:.0f}°C까지 올랐습니다. 긴 장면에서는 더 뜨거워집니다." + step, lower
        return "ok", "이 설정과 해상도로 안정적으로 완료했습니다. 긴 장면은 온도가 더 오를 수 있으니 처음에는 지켜봐 주세요.", None
    if status == "stopped":
        return "warn", "시험을 멈췄습니다.", None
    if kind in ("gpu", "overheat"):
        return "bad", f"{message}{step}", lower
    if kind == "memory":
        return "bad", "메모리가 부족합니다. GPU를 쓰는 다른 프로그램을 닫거나 더 낮은 해상도를 쓰세요.", None
    return "bad", message or "시험이 실패했습니다.", None


def powershell(command, timeout=60):
    return run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], timeout=timeout)


def count_driver_resets(since):
    """Display event 4101 is the driver reset behind the black screens. Returns None when the log cannot be read."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since))
    try:
        r = powershell("try { @(Get-WinEvent -FilterHashtable @{LogName='System';Id=4101;StartTime=[datetime]'" + ts +
                       "'} -ErrorAction Stop).Count } catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { 0 } else { -1 } }")
        n = int(r.stdout.strip().splitlines()[-1])
        return None if n < 0 else n
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def wgp_processes():
    """(pid, command line) for every running Wan2GP, including one left behind by a crashed studio."""
    try:
        r = powershell("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                       "Where-Object { $_.CommandLine -like '*wgp.py*' } | "
                       "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
        return [(int(a), b) for a, b in (ln.split("\t", 1) for ln in r.stdout.splitlines() if "\t" in ln)]
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []


_availability = (0.0, None)


def availability():
    """Whether H3 can run on this machine, with reasons in the user's words. nvidia-smi present but silent is a crash, not a missing GPU.
    Cached for 5s because any visitor can ask, and each check starts a process."""
    global _availability
    if time.time() - _availability[0] < 5 and _availability[1]:
        return dict(_availability[1])
    state = _check_availability()
    _availability = (time.time(), state)
    return dict(state)


def _check_availability():
    reasons = []
    if os.name != "nt":
        reasons.append("AI 영상 생성은 NVIDIA GPU가 있는 Windows PC에서만 쓸 수 있습니다.")
    elif not shutil.which("nvidia-smi"):
        reasons.append("NVIDIA GPU를 찾지 못했습니다. AI 영상 생성에는 GPU 메모리 8GB 이상의 NVIDIA GPU가 필요합니다.")
    else:
        gpu = gpu_sample()
        if gpu is None:
            reasons.append("GPU가 응답하지 않습니다. PC를 재부팅한 뒤 다시 확인하세요.")
        elif gpu["mem_total"] is not None and gpu["mem_total"] < MIN_VRAM_MB:
            reasons.append(f"GPU 메모리가 {gpu['mem_total'] / 1024:.0f}GB입니다. AI 영상 생성에는 8GB 이상이 필요합니다.")
    gpu_ok = not reasons
    installed = PY.is_file() and (WAN / "wgp.py").is_file() and (WAN / "ckpts" / MODEL_FILE).is_file()
    if gpu_ok and not installed:
        reasons.append("AI 영상 생성 도구(Wan2GP와 모델)가 설치되어 있지 않습니다. 설치·점검 화면에서 설치하세요.")
    return {"ok": gpu_ok and installed, "gpu_ok": gpu_ok, "installed": installed, "reasons": reasons,
            "license_notice": license_notice(),
            "ref_installed": (WAN / "ckpts" / REF_MODEL_FILE).is_file()}


def process_tree(pid):
    """pid and all its descendants. Windows only: the venv python.exe is a launcher, so the real work runs in a child."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    if snap in (None, wintypes.HANDLE(-1).value):
        raise OSError("process snapshot failed")
    children, entry = {}, Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    try:
        more = k32.Process32FirstW(wintypes.HANDLE(snap), ctypes.byref(entry))
        while more:
            children.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
            more = k32.Process32NextW(wintypes.HANDLE(snap), ctypes.byref(entry))
    finally:
        k32.CloseHandle(wintypes.HANDLE(snap))
    tree, todo = [], [pid]
    while todo:
        p = todo.pop()
        if p not in tree:
            tree.append(p)
            todo += children.get(p, [])
    return tree


def suspend_tree(pid, suspend=True):
    """Freezes or thaws a process tree. Nothing is lost: memory, VRAM and progress stay in place. Returns how many processes changed."""
    import ctypes
    from ctypes import wintypes
    k32, ntdll = ctypes.WinDLL("kernel32"), ctypes.WinDLL("ntdll")
    k32.OpenProcess.restype = wintypes.HANDLE
    call = ntdll.NtSuspendProcess if suspend else ntdll.NtResumeProcess
    done = 0
    for p in process_tree(pid):
        handle = k32.OpenProcess(0x0800, False, p)  # PROCESS_SUSPEND_RESUME
        if handle:
            done += call(wintypes.HANDLE(handle)) == 0
            k32.CloseHandle(wintypes.HANDLE(handle))
    return done


def kill_tree(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 9)
        except OSError:
            pass
        return
    try:
        run_cmd(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass


def free_ram_gb():
    import ctypes

    class Mem(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in
                    ("total", "avail", "pt", "apt", "virt", "avirt", "ext")]
    m = Mem(len=ctypes.sizeof(Mem))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def probe_video(path):
    """(frames, width, height, has_audio) of a video, or None when it cannot be read."""
    try:
        r = run_cmd([str(FFPROBE), "-v", "error", "-count_packets", "-show_entries",
                     "stream=codec_type,width,height,nb_read_packets", "-of", "json", str(path)], timeout=120)
        streams = json.loads(r.stdout).get("streams", [])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        return None
    return (int(video.get("nb_read_packets", 0)), video.get("width"), video.get("height"),
            any(s.get("codec_type") == "audio" for s in streams))


def scene_file_ok(path, frames, size):
    if not Path(path).is_file():
        return False
    info = probe_video(path)
    w, h = map(int, size.split("x"))
    return bool(info and info[0] == frames and info[1] == w and info[2] == h and info[3])


def extract_frame(video, index, out):
    tmp = Path(out).with_name(Path(out).stem + ".tmp.png")
    r = run_cmd([str(FFMPEG), "-v", "error", "-y", "-i", str(video), "-vf", f"select=eq(n\\,{index})",
                 "-fps_mode", "vfr", "-frames:v", "1", str(tmp)], timeout=120)
    if r.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        raise StudioError(f"프레임 추출 실패: {r.stderr.strip()[:200]}")
    os.replace(tmp, out)


def preflight(size, frames_list, fix_power=True):
    """List of {name, ok, detail, fatal}. Nothing starts while a fatal check fails."""
    checks = []

    def add(name, ok, detail="", fatal=True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "fatal": fatal})

    add("Wan2GP 설치", PY.is_file() and (WAN / "wgp.py").is_file() and FFMPEG.is_file() and FFPROBE.is_file(),
        str(WAN))
    try:
        head = run_cmd(["git", "-C", str(WAN), "rev-parse", "--short=8", "HEAD"]).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        head = ""
    add("Wan2GP 버전 고정", head == PINNED_COMMIT, f"현재 {head or '알 수 없음'}, 시험한 버전 {PINNED_COMMIT}", fatal=False)
    try:  # Local Wan2GP patch for a Windows crash on a null region address. A reinstall or update loses it.
        patched = "info.BaseAddress or 0" in (WAN / "mmgp" / "offload.py").read_text(encoding="utf-8")
        add("Wan2GP 로컬 패치", patched, "" if patched else "mmgp/offload.py의 패치가 없습니다", fatal=False)
    except OSError as e:
        add("Wan2GP 로컬 패치", False, str(e), fatal=False)
    try:
        cfg = json.loads((WAN / "wgp_config.json").read_text(encoding="utf-8"))
        add("INT8 설정", cfg.get("int8_kernels") == "triton", f"int8_kernels={cfg.get('int8_kernels')}, 시험한 값 triton")
    except (OSError, ValueError) as e:
        add("INT8 설정", False, f"wgp_config.json을 읽지 못함: {e}")

    others = wgp_processes()
    add("다른 Wan2GP 없음", not others, f"실행 중: PID {', '.join(str(p) for p, _ in others)}" if others else "")

    gpu = gpu_sample()
    add("GPU 응답", gpu is not None, "" if gpu else "nvidia-smi 응답 없음. 재부팅이 필요합니다.")
    if gpu:
        limits = gpu_limits()
        target = limits["power"]
        if target is None:  # Laptops often lock this. The temperature watch still protects them.
            add("GPU 전력 제한", False, "이 GPU는 전력 제한을 바꿀 수 없어 온도 감시로만 보호합니다.", fatal=False)
        else:
            limit_ok = gpu["limit"] is not None and gpu["limit"] <= target + 1
            if not limit_ok and fix_power:
                run_gpu_safe(limits)
                gpu = gpu_sample() or gpu
                limit_ok = gpu["limit"] is not None and gpu["limit"] <= target + 1
            add("GPU 전력 제한", limit_ok, f"{gpu['limit']:.0f}W, 기준 {target}W 이하" if gpu["limit"] else "확인 불가")
        add("GPU 메모리 여유", gpu["mem"] is not None and gpu["mem"] <= MAX_START_VRAM_MB,
            f"사용 중 {gpu['mem']:.0f}MB, 기준 {MAX_START_VRAM_MB}MB 이하. GPU를 쓰는 프로그램을 닫으세요." if gpu["mem"] is not None else "")

    try:
        free = shutil.disk_usage(ROOT).free / 2 ** 30
        add("디스크 공간", free >= MIN_DISK_GB, f"{free:.0f}GB 남음, 기준 {MIN_DISK_GB}GB")
    except OSError as e:
        add("디스크 공간", False, str(e))
    ram = free_ram_gb()
    add("RAM 여유", ram >= MIN_RAM_GB, f"{ram:.0f}GB 남음, 기준 {MIN_RAM_GB}GB", fatal=False)

    try:
        r = run_cmd([str(PY), "-c", "import torch;x=torch.ones(64,64).cuda();print(float((x@x).sum()))"], timeout=120)
        add("CUDA 연산", r.returncode == 0, "" if r.returncode == 0 else (r.stderr.strip().splitlines() or [""])[-1][:200])
    except (OSError, subprocess.TimeoutExpired) as e:
        add("CUDA 연산", False, str(e)[:200])
    return checks


# ---------- Runner ----------

class Stopped(Exception):
    pass


# Failures tied to one script. Anything else (GPU, heat, preflight, disk) would hit the next project too, so the queue pauses.
PROJECT_ONLY_FAILURES = ("unknown", "output", "join", "error")


class Runner:
    """Runs queued projects one at a time, oldest first. All shared state sits behind self.lock.

    The queue is the "queued" status plus queued_at in each project.json, so it survives a restart.
    `external` adds other work to the same line, so nothing that competes for the machine ever overlaps. It needs
    queued() -> [{kind, id, title, estimate, at}], run(id, runner), remove(id) and recover().
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.paused = False
        self.pause_reason = ""
        self.stop_event = threading.Event()
        self.proc = None
        self.project_id = None
        self.history = deque(maxlen=1800)
        self.log = deque(maxlen=200)
        self.live = {"phase": "idle", "scene": None, "stage": "", "fraction": 0.0, "stage_since": 0.0,
                     "started": 0.0, "eta": None, "checks": []}
        self.pending_kill = None
        self.heat_paused = None  # (pid, since) while generation is frozen to cool the GPU
        self.external = None
        self.current = None
        self._scan = (0.0, [])
        threading.Thread(target=self._monitor, daemon=True).start()

    # ----- Public API -----

    def recover(self):
        """After a studio crash or reboot: running projects go back to the queue front and strays are stopped.

        The queue stays paused until the user resumes it, because a reboot resets the GPU limits and needs a UAC prompt.
        """
        if not PROJECTS.exists():
            return
        for d in PROJECTS.iterdir():
            try:
                p = load_project(d.name)
            except (StudioError, ValueError, OSError):
                continue
            if p.get("status") in ("running", "preflight"):
                pid = p.get("pid")
                if pid and any(pid == q and str(d.name) in cmd for q, cmd in wgp_processes()):
                    kill_tree(pid)
                p.update(status="queued", queued_at=p.get("queued_at", 0), pid=None,
                         message="프로그램이나 PC가 생성 도중 종료됐습니다. 대기열을 재개하면 완료된 장면은 건너뛰고 이어서 만듭니다.")
                save_project(p)
        if self.external:
            self.external.recover()
        if self._items():
            self.paused, self.pause_reason = True, "프로그램이 다시 시작됐습니다. 준비되면 재개를 누르세요."

    def enqueue(self, pid):
        """Adds a project to the end of the queue. It starts at once when nothing else is running."""
        with self.lock:
            p = load_project(pid)
            if p["status"] == "queued" or (self.active and self.project_id == pid):
                raise StudioError("이미 대기열에 있거나 생성 중입니다.")
            if not self._items():
                self.paused = False  # An empty queue has nothing left to protect, so a stopped project can simply restart.
            p.update(status="queued", queued_at=time.time(), message="")
            save_project(p)
            self._dispatch()

    def enqueue_external(self, mark_queued):
        """Same rules as enqueue, for external work. mark_queued() records it as waiting."""
        with self.lock:
            if not self._items():
                self.paused = False
            mark_queued()
            self._dispatch()

    def remove_external(self, item_id):
        with self.lock:
            self.external.remove(item_id)
            self._scan = (0.0, [])

    def dequeue(self, pid):
        with self.lock:
            p = load_project(pid)
            if p["status"] != "queued":
                raise StudioError("대기열에 없는 프로젝트입니다.")
            p.update(status="ready", message="대기열에서 뺐습니다.")
            save_project(p)
            self._scan = (0.0, [])

    def move(self, kind, item_id, step):
        """Swaps an item with its neighbour. Order is only the two timestamps, so a restart keeps it."""
        with self.lock:
            items = self._items()
            i = next((n for n, x in enumerate(items) if x["kind"] == kind and x["id"] == item_id), None)
            if i is None:
                raise StudioError("대기열에 없는 작업입니다.")
            j = i + step
            if not 0 <= j < len(items):
                return
            a, b = items[i]["at"], items[j]["at"]
            self._set_at(items[i], b + step * 0.001 if a == b else b)
            self._set_at(items[j], a)
            self._scan = (0.0, [])

    def _set_at(self, item, at):
        if item["kind"] == "h3":
            p = load_project(item["id"])
            p["queued_at"] = at
            save_project(p)
        else:
            self.external.set_at(item["id"], at)

    def delete(self, pid):
        """Renames first: a file held open fails here, before anything is lost, instead of leaving half a project."""
        with self.lock:
            p = load_project(pid)
            if p["status"] == "queued" or (self.active and self.project_id == pid):
                raise StudioError("대기 중이거나 생성 중인 프로젝트는 지울 수 없습니다. 대기열에서 빼거나 멈춘 뒤 지우세요.")
            trash = PROJECTS / f".trash-{pid}"
            try:
                os.rename(project_dir(pid), trash)
            except OSError:
                raise StudioError("파일을 쓰는 중이라 지우지 못했습니다. 이 영상을 재생 중인 탭을 닫고 다시 시도하세요.")
            self._scan = (0.0, [])
        shutil.rmtree(trash, ignore_errors=True)

    def clean(self):
        """Removes what a finished video does not need: archived versions, scratch folders and failed deletions. Returns bytes freed."""
        before = storage_report()["spare"]
        with self.lock:
            active = self.project_id if self.active else None
        for d in PROJECTS.iterdir() if PROJECTS.exists() else []:
            if d.name.startswith(".trash-"):
                shutil.rmtree(d, ignore_errors=True)
            elif d.name != active:
                for n in ("versions", "work"):
                    shutil.rmtree(d / n, ignore_errors=True)
        return before - storage_report()["spare"]

    def test_running(self):
        return any(p.get("test") and p.get("status") in ("queued", "preflight", "running") for p in
                   (self._load_quiet(d.name) for d in (PROJECTS.iterdir() if PROJECTS.exists() else [])))

    @staticmethod
    def _load_quiet(pid):
        try:
            return load_project(pid)
        except (StudioError, ValueError, OSError):
            return {}

    def start_test(self, size):
        if size not in PRESETS:
            raise StudioError("해상도를 선택하세요.")
        if self.test_running():
            raise StudioError("시험 생성이 이미 대기 중이거나 진행 중입니다.")
        for d in PROJECTS.iterdir() if PROJECTS.exists() else []:
            if self._load_quiet(d.name).get("test"):
                self.delete(d.name)
        self.enqueue(create_test_project(size)["id"])

    def _record_test(self, pid, started):
        """A failed record must never disturb the queue."""
        try:
            p = load_project(pid)
            with self.lock:
                samples = [x for x in self.history if x["t"] >= started]
            peak = lambda k: max((x[k] for x in samples if x.get(k) is not None), default=None)
            card, limits = gpu_card(), gpu_limits()
            level, words, lower = test_verdict(p["status"], p.get("failure_kind"), p.get("message"), peak("temp"), limits["power"], card)
            result = p.get("scene_results", {}).get("1")
            update_settings(gpu_test={"at": time.time(), "size": p["size"], "status": p["status"], "level": level, "message": words,
                                      "suggest_power": lower, "peak_temp": peak("temp"), "peak_power": peak("power"), "peak_mem": peak("mem"),
                                      "power": limits["power"], "clock": limits["clock"], "scene_seconds": result["seconds"] if result else None,
                                      "video_seconds": p["script"]["scenes"][0]["seconds"]})
        except Exception as e:
            with self.lock:
                self.log.append(f"[studio] 시험 결과를 저장하지 못했습니다: {type(e).__name__}: {e}")

    def resume_queue(self):
        with self.lock:
            self.paused, self.pause_reason = False, ""
            self._dispatch()

    def edit(self, pid, change, base=None):
        """Applies change(project) and saves, under the lock so the queue cannot pick the project up halfway.
        base is the edit count the page last saw, so a page left open in another tab cannot undo a newer edit."""
        with self.lock:
            if self.active and self.project_id == pid:
                raise StudioError("이 프로젝트는 생성 중입니다. 끝나거나 멈춘 뒤에 수정하세요.")
            p = load_project(pid)
            if base is not None and p.get("edits", 0) != base:
                raise StudioError("다른 탭에서 이 프로젝트가 바뀌어 저장하지 않았습니다. 입력한 내용을 복사해 둔 뒤 새로고침하세요.")
            change(p)
            p["edits"] = p.get("edits", 0) + 1
            save_project(p)

    def _queued(self):
        """Queued projects, next first."""
        out = []
        if PROJECTS.exists():
            for d in PROJECTS.iterdir():
                try:
                    p = load_project(d.name)
                    if p["status"] == "queued":
                        out.append(p)
                except (StudioError, ValueError, OSError, KeyError):
                    continue
        return sorted(out, key=lambda p: p.get("queued_at", 0))

    def _items_cached(self):
        """For polling pages: at most one disk scan every 2s, and never under self.lock."""
        now = time.time()
        if now - self._scan[0] < 2:
            return self._scan[1]
        items = self._items()
        self._scan = (time.time(), items)
        return items

    def _items(self):
        """Everything waiting in the one queue, next first."""
        items = [{"kind": "h3", "id": p["id"], "title": p["script"]["title"], "at": p.get("queued_at", 0),
                  "estimate": PROJECT_OVERHEAD_S + sum(estimate_scene_seconds(p["size"], s["frames"]) for s in p["script"]["scenes"])}
                 for p in self._queued()]
        if self.external:
            items += self.external.queued()
        return sorted(items, key=lambda x: x["at"])

    def _dispatch(self):
        """Starts the next waiting item if the runner is free. The caller holds self.lock."""
        self._scan = (0.0, [])  # Every change to the queue passes through here or the methods that call it.
        if self.active or self.paused:
            return
        items = self._items()
        if not items:
            return
        item = items[0]
        h3 = item["kind"] == "h3"
        self.active = True
        self.current = item
        self.stop_event.clear()
        self.project_id = item["id"] if h3 else None
        self.log.clear()
        self.live.update(phase="preflight" if h3 else item["kind"], scene=None, stage="시작 전 점검" if h3 else "렌더링 준비",
                         fraction=0.0, eta=None, started=time.time(), stage_since=time.time(), checks=[])
        target = self._run if h3 else self._run_external
        threading.Thread(target=target, args=(item["id"],), daemon=True).start()

    def _run_external(self, item_id):
        """external.run records its own failures, so only a stop or a failure to record one holds the queue."""
        reason = ""
        try:
            self.external.run(item_id, self)
        except Exception as e:  # Left as waiting, so dispatching again could retry forever.
            reason = f"문제가 생겨 대기열을 멈췄습니다: {type(e).__name__}: {e}"
        if self.stop_event.is_set():
            reason = "멈추기를 눌러 대기열도 멈췄습니다."
        with self.lock:
            self.active, self.current = False, None
            items = self._items()
            if reason and items:
                self.paused, self.pause_reason = True, reason
            elif not items:
                self.paused = False  # Nothing left to hold.
            self._dispatch()

    def stop(self):
        """Stops the current project and holds the rest of the queue, because the next one would start right away."""
        self.stop_event.set()
        with self.lock:
            proc = self.proc  # External work watches stop_event itself. See run_render in server.py.
            if self.active:  # Sticky: the next item must not start even if this one finishes before it notices the stop.
                self.paused, self.pause_reason = True, "멈추기를 눌러 대기열도 멈췄습니다."
        if proc and proc.poll() is None:
            kill_tree(proc.pid)

    def busy(self):
        with self.lock:
            return self.active

    def snapshot(self):
        queue = self._items_cached()
        with self.lock:
            return {"project": self.project_id, "current": self.current, "busy": self.active, "queue": queue, "paused": self.paused,
                    "pause_reason": self.pause_reason,
                    "live": dict(self.live), "gpu": list(self.history)[-120:], "log": list(self.log)[-60:]}

    # ----- Monitoring -----

    def _monitor(self):
        """Polls the GPU continuously, so the graph also works while idle and overheating is caught during a render."""
        hot, missing, ticks = 0, 0, 0
        while True:
            ticks += 1
            if ticks % 3 == 0:
                with self.lock:
                    self._dispatch()  # A file locked by antivirus at the wrong moment must not strand the queue.
            sample = gpu_sample()
            with self.lock:
                proc = self.proc
                if sample:
                    self.history.append(sample)
            rendering = proc is not None and proc.poll() is None
            missing = 0 if sample else missing + 1
            hot = hot + 1 if sample and sample["temp"] is not None and sample["temp"] >= STOP_TEMP_C else 0
            self._manage_heat(proc if rendering else None, sample["temp"] if sample else None)
            if rendering and hot >= STOP_SAMPLES:
                self._abort(proc, "overheat", f"GPU가 {STOP_TEMP_C}°C에 도달해 생성을 멈췄습니다. 식은 뒤 '이어서 생성'을 누르세요. "
                            "반복되면 케이스 환기를 점검하거나 장면을 짧게 나누세요.")
            elif rendering and missing >= 5:
                self._abort(proc, "gpu", "GPU가 응답하지 않아 생성을 멈췄습니다. 재부팅한 뒤 '이어서 생성'을 누르세요.")
            time.sleep(3 if self.active else 10)  # Each sample starts a process, and idle numbers barely change.

    def _manage_heat(self, proc, temp):
        """Freezes generation at PAUSE_TEMP_C and thaws it at RESUME_TEMP_C. STOP_TEMP_C stays as the last resort."""
        paused = self.heat_paused
        if paused and (not proc or paused[0] != proc.pid):  # That process ended or was killed while frozen.
            paused = self.heat_paused = None
        if not proc or temp is None:
            return
        try:
            if not paused and temp >= PAUSE_TEMP_C:
                suspend_tree(proc.pid)
                self.heat_paused = (proc.pid, time.time())
                self._set_live(stage=f"GPU 식히는 중 ({temp:.0f}°C, {RESUME_TEMP_C}°C에서 이어서 생성)")
            elif paused and temp <= RESUME_TEMP_C:
                suspend_tree(proc.pid, False)
                self.heat_paused = None
                self._set_live(stage="이어서 생성하는 중")
            elif paused and time.time() - paused[1] > COOL_TIMEOUT_S:
                self._abort(proc, "overheat", f"GPU가 {COOL_TIMEOUT_S // 60}분 동안 {RESUME_TEMP_C}°C 아래로 식지 않아 생성을 멈췄습니다. 팬과 환기를 점검하세요.")
        except (OSError, AttributeError) as e:  # Pausing is a convenience; STOP_TEMP_C still protects the card.
            with self.lock:
                self.log.append(f"[studio] 온도 조절 실패: {e}")

    def _abort(self, proc, kind, message):
        with self.lock:
            self.pending_kill = (kind, message)
        kill_tree(proc.pid)

    def _set_live(self, **kw):
        with self.lock:
            if "stage" in kw and kw["stage"] != self.live["stage"]:
                kw["stage_since"] = time.time()
            self.live.update(kw)

    # ----- The job -----

    def _run(self, pid):
        project, started = None, time.time()
        keep_going, reason = False, "예상하지 못한 오류로 대기열을 멈췄습니다."  # Holds the queue even if saving the failure fails.
        try:
            project = load_project(pid)
            if project["status"] != "queued":  # Taken out of the queue just after it was picked.
                keep_going, project = True, None
                return
            self._update(project, status="preflight", message="", warnings=[])
            self._check_ready(project)
            self._update(project, status="running")
            self._render_scenes(project)
            self._make_music(project)
            self._join(project)
            self._update(project, status="done", message="완료. 영상을 재생해 검수하세요.", pid=None, finished=time.time())
            self._set_live(phase="done", stage="완료", fraction=1.0, eta=0)
            keep_going = True
        except Stopped:
            reason = "멈추기를 눌러 대기열도 멈췄습니다."
            self._finish(project, "stopped", "사용자가 멈췄습니다. '이어서 생성'으로 계속할 수 있습니다.")
        except StudioError as e:
            reason = f"문제가 생겨 대기열을 멈췄습니다: {e}"
            self._finish(project, "failed", str(e), e.kind)
            keep_going = project is not None and e.kind in PROJECT_ONLY_FAILURES
        except Exception as e:  # The runner thread must always leave a resumable state behind.
            self._finish(project, "failed", f"예상하지 못한 오류: {type(e).__name__}: {e}", "unknown")
            keep_going = project is not None
        finally:  # A project that could not be marked failed stays queued, so keep_going False also prevents a retry loop.
            if project and project.get("test"):
                self._record_test(pid, started)
            with self.lock:
                self.active, self.current = False, None
                items = self._items()
                if not keep_going and items:
                    self.paused, self.pause_reason = True, reason
                elif not items:
                    self.paused = False  # Nothing left to hold.
                self._dispatch()

    def _finish(self, project, status, message, kind=None):
        if project:
            self._update(project, status=status, message=message, failure_kind=kind, pid=None)
        self._set_live(phase=status, stage=message[:60])

    def _update(self, project, **kw):
        project.update(kw)
        save_project(project)

    def _check_ready(self, project):
        frames = [s["frames"] for s in project["script"]["scenes"]]
        checks = preflight(project["size"], frames)
        self._set_live(checks=checks)
        bad = [c for c in checks if not c["ok"] and c["fatal"]]
        warn = [f"{c['name']}: {c['detail']}" for c in checks if not c["ok"] and not c["fatal"]]
        if warn:
            self._update(project, warnings=warn)
        if bad:
            raise StudioError("시작 전 점검 실패: " + " / ".join(f"{c['name']} ({c['detail']})" for c in bad), "preflight")

    def _render_scenes(self, project):
        pdir = project_dir(project["id"])
        (pdir / "frames").mkdir(exist_ok=True)
        (pdir / "scenes").mkdir(exist_ok=True)
        (pdir / "logs").mkdir(exist_ok=True)
        jobs = build_jobs(project, pdir)
        size = project["size"]
        # Anything after the first stale scene is stale too, because it starts from a frame of the stale scene.
        for i, (job, chain) in enumerate(jobs, 1):
            result = project["scene_results"].get(str(i), {})
            ok = result.get("chain") == chain and scene_file_ok(pdir / "scenes" / f"s{i}.mp4", job["video_length"], size)
            if not ok:
                archive_scenes(project, i)
                save_project(project)
                break
        ratio = 1.0
        for i, (job, chain) in enumerate(jobs, 1):
            video = pdir / "scenes" / f"s{i}.mp4"
            if str(i) not in project["scene_results"]:
                self._cool()
                self._set_eta(project, i, ratio)
                seconds = self._render_scene(project, i, job, video)
                project["scene_results"][str(i)] = {"chain": chain, "seconds": seconds, "at": time.time()}
                save_project(project)
                ratio = seconds / estimate_scene_seconds(size, job["video_length"])
            if i == 1:
                extract_frame(video, 0, pdir / "frames" / "s1_first.png")
            extract_frame(video, job["video_length"] - 1, pdir / "frames" / f"s{i}_last.png")

    def _set_eta(self, project, scene, ratio):
        left = sum(estimate_scene_seconds(project["size"], s["frames"])
                   for s in project["script"]["scenes"][scene - 1:])
        self._set_live(eta=left * ratio + PROJECT_OVERHEAD_S, eta_at=time.time())

    def _cool(self):
        limit = time.time() + COOL_TIMEOUT_S
        self._set_live(phase="cooling", stage=f"GPU 식히는 중 ({COOL_TEMP_C}°C 이하까지)", fraction=0.0)
        while True:
            if self.stop_event.is_set():
                raise Stopped()
            sample = gpu_sample()
            if sample is None:
                raise StudioError("GPU가 응답하지 않습니다. 재부팅한 뒤 '이어서 생성'을 누르세요.", "gpu")
            if sample["temp"] is not None and sample["temp"] <= COOL_TEMP_C:
                return
            if time.time() > limit:
                raise StudioError(f"GPU가 {COOL_TIMEOUT_S // 60}분 동안 {COOL_TEMP_C}°C 아래로 식지 않았습니다. 팬과 환기를 점검하세요.", "overheat")
            time.sleep(5)

    def _render_scene(self, project, i, job, video):
        pdir = project_dir(project["id"])
        for key in ("image_start", "image_end"):
            if key in job and not Path(job[key]).is_file():
                raise StudioError(f"장면 {i}의 입력 프레임이 없습니다: {job[key]}")
        for ref in job.get("image_refs", []):
            if not Path(ref).is_file():
                raise StudioError(f"캐릭터 이미지가 없습니다: {ref}")
        job_file = pdir / f"s{i}.json"
        job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        last_kind, last_message = "unknown", ""
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                self._cool()
            out = pdir / "work" / f"s{i}"
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir(parents=True)
            self._set_live(phase="rendering", scene=i, stage="모델 불러오는 중", fraction=0.0)
            resets_from = time.time()
            started = time.time()
            ok, tail = self._run_wgp(project, job_file, out, pdir / "logs" / f"s{i}_try{attempt + 1}.log")
            resets = count_driver_resets(resets_from)
            if resets:
                raise StudioError(f"장면 {i} 생성 중 GPU 드라이버가 재시작됐습니다(이벤트 4101). 재부팅한 뒤 '이어서 생성'을 누르세요.", "gpu")
            if ok:
                produced = list(out.glob("*.mp4"))
                if produced and scene_file_ok(produced[0], job["video_length"], job["resolution"]):
                    os.replace(produced[0], video)
                    shutil.rmtree(out, ignore_errors=True)
                    return time.time() - started
                last_kind, last_message = "output", f"장면 {i} 결과 파일이 검증에 실패했습니다(프레임 수, 크기 또는 오디오)."
            else:
                last_kind, last_message = classify_failure(tail)
                last_message = f"장면 {i}: {last_message}"
            if last_kind in ("gpu", "memory", "missing", "disk"):
                break  # The same run would fail again.
            with self.lock:
                self.log.append(f"[studio] 장면 {i} 실패, 재시도합니다: {last_message}")
        raise StudioError(last_message, last_kind)

    def _run_wgp(self, project, job_file, out_dir, log_path):
        """Runs Wan2GP once. Returns (success, tail of the log)."""
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        args = [str(PY), "wgp.py", "--process", str(job_file), "--output-dir", str(out_dir), "--offline"]
        tail = deque(maxlen=120)
        last_output = [time.time()]
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(args, cwd=WAN, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
            with self.lock:
                self.proc, self.pending_kill = proc, None
                stopping = self.stop_event.is_set()
            if stopping:  # Stop arrived between two steps, when nothing was registered to kill.
                kill_tree(proc.pid)
            self._update(project, pid=proc.pid)

            def watchdog():
                while proc.poll() is None:
                    if self.heat_paused:  # Frozen on purpose: silence here is not a stall.
                        last_output[0] = time.time()
                    if time.time() - last_output[0] > STALL_TIMEOUT_S:
                        self._abort(proc, "stall", f"Wan2GP가 {STALL_TIMEOUT_S // 60}분 동안 응답이 없어 멈췄습니다. '이어서 생성'을 누르세요.")
                        return
                    time.sleep(5)
            threading.Thread(target=watchdog, daemon=True).start()

            buf = b""
            try:
                while True:
                    chunk = proc.stdout.read1(4096)
                    if not chunk:
                        break
                    log.write(chunk)
                    log.flush()
                    last_output[0] = time.time()
                    buf += chunk
                    *lines, buf = re.split(rb"[\r\n]", buf)
                    for raw in lines:
                        self._on_line(raw.decode("utf-8", "replace"), tail)
                code = proc.wait()
            except BaseException:  # A full disk, say. Wan2GP must not stay on the GPU behind a failed project.
                kill_tree(proc.pid)
                with self.lock:
                    self.proc = None
                raise
        if buf:
            self._on_line(buf.decode("utf-8", "replace"), tail)
        with self.lock:
            self.proc = None
            pending, self.pending_kill = self.pending_kill, None
        if self.stop_event.is_set():
            raise Stopped()
        if pending:
            raise StudioError(pending[1], pending[0])
        return code == 0, "\n".join(tail)

    def _on_line(self, line, tail):
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if not line:
            return
        tail.append(line)
        progress = parse_progress(line)
        with self.lock:
            if not self.log or self.log[-1] != line:
                if progress and self.log and parse_progress(self.log[-1]) and parse_progress(self.log[-1])[0] == progress[0]:
                    self.log[-1] = line  # A progress bar updates in place instead of filling the log.
                else:
                    self.log.append(line)
        if progress:
            self._set_live(stage=progress[0], fraction=progress[1])

    def _make_music(self, project):
        script = project["script"]
        pdir = project_dir(project["id"])
        if not script.get("music") or list((pdir / "bgm").glob("bgm.*")):
            return
        self._cool()
        self._set_live(phase="music", scene=None, stage="배경음악 생성", fraction=0.0)
        out = pdir / "work" / "bgm"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        job_file = pdir / "bgm.json"
        total = sum(s["seconds"] for s in script["scenes"])
        job_file.write_text(json.dumps(music_job(script, total, project["seed"]), ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            ok, tail = self._run_wgp(project, job_file, out, pdir / "logs" / "bgm.log")
            produced = [f for f in out.iterdir() if f.suffix.lower() in (".wav", ".mp3", ".flac", ".mp4")] if ok else []
            if not produced:
                raise StudioError(classify_failure(tail)[1])
            (pdir / "bgm").mkdir(exist_ok=True)
            os.replace(produced[0], pdir / "bgm" / f"bgm{produced[0].suffix.lower()}")
            shutil.rmtree(out, ignore_errors=True)
        except StudioError as e:  # Music is optional: the video is still usable with its own sound effects.
            if e.kind in ("gpu", "overheat", "stall"):  # But a sick GPU must hold the queue, as it does during a scene.
                raise
            self._update(project, warnings=project.get("warnings", []) + [f"배경음악 없이 합쳤습니다: {e}"])

    def _join(self, project):
        self._set_live(phase="joining", scene=None, stage="영상 합치는 중", fraction=0.0)
        pdir = project_dir(project["id"])
        scenes = project["script"]["scenes"]
        frames = [s["frames"] for s in scenes]
        expected = sum(frames) - (len(frames) - 1)
        total = expected / FPS
        music = next(iter(sorted((pdir / "bgm").glob("bgm.*"))), None) if (pdir / "bgm").exists() else None
        args = [str(FFMPEG), "-v", "error", "-y"]
        for i in range(1, len(scenes) + 1):
            args += ["-i", str(pdir / "scenes" / f"s{i}.mp4")]
        if music:
            args += ["-stream_loop", "-1", "-i", str(music)]  # Stable Audio caps at 30s, so longer videos repeat it.
        tmp = pdir / "final.tmp.mp4"
        args += ["-filter_complex", join_filter(frames, bool(music), total), "-map", "[v]", "-map", "[a]",
                 "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                 "-movflags", "+faststart", str(tmp)]
        r = run_cmd(args, timeout=900)
        if r.returncode != 0:
            raise StudioError(f"영상 합치기 실패: {r.stderr.strip()[:300]}", "join")
        if not scene_file_ok(tmp, expected, project["size"]):
            raise StudioError("합친 영상이 검증에 실패했습니다(프레임 수, 크기 또는 오디오).", "join")
        os.replace(tmp, pdir / "final.mp4")

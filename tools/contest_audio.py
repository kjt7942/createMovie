"""공모전 내레이션(Qwen3-TTS VoiceDesign, Apache 2.0)과 배경음악(ACE-Step 1.5, MIT)을 만든다.
결과: jobs/contest/<출력폴더>/narr_XX/out/*.wav, music_N/out/*.wav. 사용: python tools/contest_audio.py audio_v1
"""
import sys, time
import contest_test as t

t.OUT = t.ROOT / "jobs" / "contest" / (sys.argv[1] if len(sys.argv) > 1 else "audio_v1")
t.REPORT = t.OUT / "report.json"
VOICE = ("A bright, cheerful young Korean female narrator, friendly and playful like a children's travel vlog host, "
         "clear articulation, upbeat but not rushed, warm smile in the voice.")
LINES = {
    "01": "관문에 가 봐! 좋은 일이 생길 거야!",
    "02": "손잡고 관문을 넘자, 처음 보는 문경이 펼쳐졌어요!",
    "03": "형, 셀카 제대로 찍어! 맨발 황톳길 브이로그 시작!",
    "04": "사극 세트장? 형한텐 그냥 동네잖아!",
    "05": "내 손으로 빚는 문경 찻사발!",
    "06": "어사화에 달린 사과랑 오미자, 진짜는 더 꿀맛!",
    "07": "레일바이크 타고 GO! 가을 철길을 달려요!",
    "08": "하늘에서 내려다본 문경, 최고야!",
    "09": "오늘 찾은 좋은 일, 전부 찰칵!",
    "10": "좋은 소식을 듣는 고을, 문경. 다음 주인공은 바로 당신!",
}
MUSIC = [
    "bright cheerful Korean fusion instrumental for a cute travel vlog, opens with a short calm daegeum flute phrase, then "
    "upbeat pop drums, bass and gayageum melody join, 120 BPM, playful and warm, a big festive buk drum hit near the end, "
    "no vocals",
    "playful upbeat K-pop style instrumental with gayageum plucks, light piano, handclaps and bouncy bass, 118 BPM, "
    "happy autumn travel mood, no vocals",
]


def main():
    t.report["gpu_now"] = t.engine.gpu_sample()
    t.save()
    for num, line in LINES.items():
        t.run_step(f"narr_{num}", {
            "model_type": "qwen3_tts_voicedesign", "prompt": line, "alt_prompt": VOICE, "model_mode": "korean",
            "duration_seconds": 10, "seed": t.SEED,
        }, {".wav", ".mp3", ".flac"})
    for k, caption in enumerate(MUSIC, 1):
        t.run_step(f"music_{k}", {
            "model_type": "ace_step_v1_5", "prompt": "[Instrumental]", "alt_prompt": caption,
            "duration_seconds": 85, "seed": t.SEED + k,
        }, {".wav", ".mp3", ".flac"})
    t.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    t.save()
    print("\n끝. 결과:", t.REPORT)


if __name__ == "__main__":
    main()

"""3단계: 140BPM 국악 인트로 + 힙합 후보를 ACE-Step 1.5로 만든다(공모전 배치). 후보당 시드 2개.
  A 랩(장소 이름 나열)  B 후크 구호만  C 보컬 없음(둥이 TTS용)
사용: python tools/contest_music_v3.py audio_v3   -> jobs/contest/audio_v3/<후보>_s<n>/out/*.wav
실존 곡·가수 이름을 프롬프트에 쓰지 말 것(기획 v3). 프롬프트·시드는 batch.json에 남는다.
"""
import json, sys, urllib.request

SEED = 20261300
BASE = ("140 BPM energetic Korean hip hop track, 60 seconds. The first 4 seconds are traditional Korean music only: daegeum bamboo flute and "
        "janggu drum, calm and misty, then a sharp record scratch and the beat drops hard with a deep 808 bass, crisp snare, fast hi-hat rolls and a "
        "short catchy daegeum sample hook. Around 28 seconds the beat cuts out for one calm daegeum phrase, then comes back louder. "
        "The last 4 bars end on a shout and then the beat stops suddenly. ")
VOCAL = {
    "A": ("confident young Korean male rapper, clear Korean pronunciation, rhythmic fast rap on the beat", """[intro]

[verse]
새재 말고 문경 열아홉 곳 한 고개 더 넘어가자
돌리네 쌍룡 용추 운달 선유구곡 물소리 따라
대승사 김룡사 봉암사 주흘 대야 조령산
가은 세트장 에코월드 철로자전거 하늘을 날아

[chorus]
문경 넥스트 스텝 한 고개 더
문경 넥스트 스텝 한 고개 더

[outro]
넥스트 스텝"""),
    "B": ("group shout chant, energetic Korean crowd vocals, short repeated hook only, clear Korean pronunciation", """[intro]

[chorus]
문경 넥스트 스텝
한 고개 더
문경 넥스트 스텝
한 고개 더

[outro]
넥스트 스텝"""),
    "C": ("instrumental only, no vocals, no lyrics, no singing", "[instrumental]"),
}
items = [{"name": f"{k}_s{s}", "job": {"model_type": "ace_step_v1_5", "prompt": lyr, "alt_prompt": BASE + style + ".",
                                       "duration_seconds": 60, "seed": SEED + 10 * s + ord(k) - 64}}
         for k, (style, lyr) in VOCAL.items() for s in (1, 2)]
req = urllib.request.Request("http://127.0.0.1:5000/h3/api/batches", method="POST", headers={"Content-Type": "application/json"},
                             data=json.dumps({"name": sys.argv[1], "title": "음악 v3 후보 A/B/C", "items": items, "start": True}).encode())
print(len(items), urllib.request.urlopen(req).read().decode())

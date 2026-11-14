"""기획 v3 콘티(28카드) -> jobs/contest/conti_v3/conti_v3.html (한눈에 보는 한 장) + cuts_v3.json (2단계 생성용 데이터).
사용: python tools/contest_conti_v3.py
근거: jobs/contest/PLAN_v3.md, INFO_문경_17곳_상세.md, INFO_문경_추가수집.md. 확인 못 한 외관은 note에 '연출'로 표시.
"""
import html, json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "jobs" / "contest" / "conti_v3"
SEED = 20261130  # contest_test.SEED와 동일. 컷 시드 = SEED + 1000*s + 컷번호(s=1,2)

DONGI = ("Character 1 (image 1) is a small cute 3D boy with a big round head and a short slim body about two heads tall (never fat), "
         "in a light green hanbok with a dark navy belt, wearing a dark navy-gray official's hat with flat wings at ear height and two thin "
         "wire stems on top holding red apples and red omija berries. Keep his design, exact body proportions, line work and colors as in image 1; "
         "add no sunglasses, no new clothes, no extra accessories except the safety gear named below. ")
DUNGI = ("Character 2 (image 2) wears a round lime-green hooded costume with a scalloped face opening and white drawstrings, with a small dark navy "
         "hat on the hood that has thin wire stems holding red apples and omija berries; short slim body, never fat. ")
END = "Cinematic 16:9 film still, rich natural detail, no text, no watermark."
NOPPL = " No people and no characters anywhere in the image. "
SMALL = " The character is small in the frame (about one fifth of the image height); the landscape dominates. "
MED = " Medium shot, the character fills about half of the frame height. "
CU = " Close-up, the character's face fills most of the frame. "
GATE = ("The gate is Juheulgwan of Mungyeong Saejae in Korea: a long, low, wide fortress wall of large pale beige-gray granite blocks running horizontally across the "
        "frame, with small square parapet notches along its top edge, one low rounded stone arch opening in the middle, and a single-story wooden gate pavilion with a dark "
        "gray tiled hip-and-gable roof and dark brown wood on top of the arch; a wide flat sandy-gravel path leads straight to the arch across an open lawn plaza with short "
        "grass (dry golden-yellow in autumn) and a small stone guardian statue beside the path; forested mountains with a pale rocky ridge behind. Not tall, not a narrow tower, "
        "not Chinese style, no multi-tier roof, no pagoda. ")
QE, T2I = "qwen_image_edit_plus2_20B", "qwen_image_2512_20B"  # 캐릭터 컷 / 풍경 컷(z_image와 2단계에서 비교)
D1 = ["dongi_front.png"]
D2 = ["dongi_front.png", "dungi_front.png"]


def C(id, t0, t1, cnt, title, place, cam, who, model, refs, prompt, motion, note, sk):
    return dict(id=id, t0=t0, t1=t1, cnt=cnt, title=title, place=place, cam=cam, who=who, model=model, refs=refs, prompt=prompt, motion=motion, note=note, sk=sk)


# sk: hor=지평선 높이(0~1), sky/gnd=색, o=[(kind,x,y,w,h,color)], ch=[(x,y,h)] 캐릭터, ar=(x0,y0,x1,y1) 카메라 이동
CUTS = [
    C("c01", 0, 3.4, "1/19", "옛길 안개 속 제1관문", "문경새재 제1관문(주흘관)·문경읍", "안개 낀 느린 와이드, 국악", "동이 뒷모습(작게)", QE, ["dongi_back.png"],
      "Wide shot from behind at dawn: a tiny " + "character 1 (image 1, seen from behind) walks along an old red-clay forest road toward a stone fortress gate in thick morning mist. " + GATE + DONGI + SMALL + END,
      "Very slow push-in along the old road, drifting mist, the small character walks away from camera toward the gate.",
      "주흘관 외형은 INFO상 '석축 홍예문+단층 문루'까지만 확정(공식 수치 없음). 지시문 GATE는 기존 storyboard 검증본 재사용.",
      dict(hor=.5, sky="#dfe6e9", gnd="#8a7f6a", o=[("rect", .35, .25, .3, .3, "#777")], ch=[(.5, .75, .13)], ar=(.5, .9, .5, .6))),
    C("c02", 3.4, 5.1, "-", "둥이 폰 화면 · '리믹스 간다!'", "(그래픽)", "스크래치, REC 표시, 자막 '새재 말고 문경 19곳'", "둥이 목소리만", "-", [],
      "(새 이미지 없음) c01 이미지를 폰 화면 프레임 안에 넣고 편집에서 REC·좋아요·자막 오버레이. 실제 SNS 로고 금지, 직접 디자인한 하트·말풍선만.", "-",
      "그래픽/편집 컷. 이미지 생성 불필요.", dict(hor=.5, sky="#222", gnd="#222", o=[("rect", .3, .08, .4, .84, "#555"), ("ell", .62, .14, .05, .05, "#e33")], ch=[], ar=None)),
    C("c03", 5.1, 6.9, "2/19", "새재 오픈세트장 — 조선 궁궐", "문경새재 오픈세트장·문경읍", "크래시 줌, 비트 드롭", "동이 점프", QE, D1,
      "Wide low-angle shot of a Joseon-dynasty palace film set: a huge grand palace gate and tiled-roof halls with a large paved courtyard under a blue sky, with forested mountains behind. Character 1 (image 1) leaps in the air in the courtyard. " + DONGI + SMALL + END,
      "Fast crash zoom toward the palace gate, the character jumps up with joy.",
      "INFO: 광화문·경복궁·동궁·궐내각사 등 103동(+초가·기와 130동), 조선 배경. 가은 세트장(고구려풍)과 구분.",
      dict(hor=.55, sky="#bcd9ec", gnd="#b9a88a", o=[("rect", .3, .3, .4, .28, "#8a4b3a")], ch=[(.5, .62, .14)], ar=(.5, .5, .5, .4))),
    C("c04", 6.9, 9.2, "3/19", "돌리네습지 — 산꼭대기 생태 찻사발", "문경돌리네습지·산북면", "탑뷰에서 푸시인, 둥근 웅덩이 지형", "없음", T2I, [],
      "Aerial top-down view of a bowl-shaped natural depression (doline) on a forested mountain summit: a round meadow basin floor in golden-brown and yellowish-ochre wet grassland with silver miscanthus reeds, pools of shallow water, a few willow trees partly in the water and one tall poplar, a raised wooden boardwalk deck winding across it, a small wooden lookout tower at the rim, ring of autumn forest around, soft mountains in the distance. " + NOPPL + END,
      "High aerial camera slowly descends and pushes in toward the bowl-shaped basin, reeds sway.",
      "공식 문장: 접시모양 웅덩이, 물억새·사초 군락, 물에 잠긴 버드나무, 미루나무, 높이 올린 데크, 전망대, 황토빛 습지. 계절=가을(촬영 시기 연출). 겨울 풍경 미확인.",
      dict(hor=.0, sky="#6f8f5a", gnd="#6f8f5a", o=[("ell", .2, .15, .6, .7, "#c9a85a"), ("rect", .3, .5, .4, .06, "#7a5a3a")], ch=[], ar=(.5, .5, .5, .5))),
    C("c05", 9.2, 11.4, "4/19", "쌍룡계곡 — 물보라 점프", "쌍룡계곡·농암면", "로앵글 물보라 슬로모션", "동이 물 건너 점프", QE, D1,
      "Low-angle shot at water level in a deep mountain valley: crystal-clear green stream between gray granite cliffs and layered rock walls like a folding screen, dense autumn forest above, mist rising. Character 1 (image 1) jumps across the stream between rocks, water splashing. " + DONGI + SMALL + END,
      "Slow motion, water spray flies around as the character leaps across the stream.",
      "공식: 도장산·불일산 기암괴석·층암절벽 병풍, 옥계수. 청룡·황룡 전설(용유동·선녀탕은 로케이션 페이지).",
      dict(hor=.4, sky="#9db8a2", gnd="#4f8f8a", o=[("rect", .0, .1, .3, .6, "#777"), ("rect", .7, .05, .3, .65, "#777")], ch=[(.5, .55, .14)], ar=(.5, .8, .5, .6))),
    C("c06", 11.4, 13.6, "5/19", "용추계곡 — 2단 폭포·하트 소", "용추계곡(대야산)·가은읍", "폭포 틸트다운", "없음", T2I, [],
      "A two-tiered waterfall flowing over huge smooth white granite rocks in a lush valley; below the lower fall a deep emerald pool naturally shaped like a heart; on both walls of the rock faces faint scale-like dragon marks; smooth sloping rock slide below; strong light through trees. " + NOPPL + END,
      "Camera tilts down from the upper fall to the heart-shaped pool, water flows continuously.",
      "공식 문장: 2단 용추폭포, 하트형 소(沼), 용비늘 흔적, 매끈한 암반 미끄럼틀.",
      dict(hor=.0, sky="#7fa28a", gnd="#7fa28a", o=[("rect", .4, .0, .2, .55, "#e8f1f4"), ("ell", .38, .6, .24, .3, "#2f8f7a")], ch=[], ar=(.5, .1, .5, .8))),
    C("c07", 13.6, 15.8, "6/19", "운달계곡 — 전나무 숲 FPV", "운달계곡·산북면", "계곡 FPV 달리기", "없음", T2I, [],
      "First-person view running along a narrow cold mountain stream through an ancient fir forest: tall straight old fir trees with 300-year-old trunks blocking the sky, dead old trees like sculptures, cold mist hanging low, rocks in the clear stream, dim green light with a few sun rays. " + NOPPL + END,
      "First-person fast forward run along the stream under the tall firs, mist streaks past.",
      "공식: 수령 300년 넘는 전나무, 얼음 같은 냉골 물, 고목. ⚠ 운달계곡=김룡사 사유지(야영·취사 금지) — 영상에 캠핑·취사 장면 금지.",
      dict(hor=.45, sky="#2f4a38", gnd="#2c3d30", o=[("rect", .05, .0, .08, .7, "#1d2a1d"), ("rect", .85, .0, .08, .7, "#1d2a1d")], ch=[], ar=(.5, .9, .5, .5))),
    C("c08", 15.8, 18.0, "7/19", "선유구곡 — 흰 암반과 소", "선유구곡(선유동계곡)·가은읍", "바위와 소 와이드 팬", "없음", T2I, [],
      "Wide panoramic view of a mountain valley stream flowing over huge white marble-like rock slabs laid out like polished stone, clear water pooling in pale pools between giant stacked boulders, old pine trees, and a small traditional Korean pavilion with a gray tiled roof on a rock above the pool, quiet morning light. " + NOPPL + END,
      "Slow pan right across the white rock slabs and the pool toward the pavilion.",
      "공식: 대리석을 깔아 놓은 듯한 흰 암반, 수정보다 맑은 물, 노송, 학천정·칠우정 정자. 정자 외관 세부 미확인(일반 한옥 정자로 연출).",
      dict(hor=.45, sky="#cfe3f2", gnd="#e5e7e3", o=[("rect", .6, .28, .15, .15, "#6b4a3a")], ch=[], ar=(.2, .5, .8, .5))),
    C("c09", 18.0, 18.9, "-", "오미자 — 빨간 스플래시", "오미자(특산물)", "잎 클로즈업, 빨간 스플래시", "동이 원샷", QE, D1,
      "Close-up of ripe red omija (five-flavor berry) clusters hanging on a green vine with leaves, a sparkle of red juice splashing; at the right side character 1 (image 1) holds up a bunch of berries with a happy face. " + DONGI + CU + END,
      "Camera pushes in on the berries, red juice splash bursts, the character raises the bunch.",
      "공식: 문경오미자(동로면 일대 산지, 전국 생산 45%). 수확철(9월 중순~말)은 민간 자료. 상표·포장 표시 금지.",
      dict(hor=.5, sky="#5a8a3a", gnd="#5a8a3a", o=[("ell", .2, .3, .2, .3, "#c8203a"), ("ell", .35, .4, .15, .25, "#c8203a")], ch=[(.72, .62, .35)], ar=(.5, .5, .5, .45))),
    C("c10", 18.9, 21.0, "8/19", "대승사 — 사불산 산중 사찰", "대승사·산북면", "산중 사찰 로앵글", "없음", T2I, [],
      "Low-angle shot of a quiet Korean Buddhist mountain temple: traditional wooden halls with painted dancheong eaves and gray tile roofs, stone steps, ancient pines, a steep forested mountain (Sabulsan) rising behind, morning light and light mist. " + NOPPL + END,
      "Slow upward tilt from the stone steps to the temple roofs and the mountain.",
      "공식: 사불산 자락, 신라 진평왕 창건 전승, 사면석불 설화. 가람 배치·건물 색 미확인 → 일반 산중 사찰로 연출. 공식 사찰 이미지 대조 필요.",
      dict(hor=.4, sky="#d6e2d2", gnd="#6e8f5a", o=[("rect", .3, .25, .4, .22, "#7a5a3a"), ("poly", 0, .0, .25, .5, "#4b6e4b")], ch=[], ar=(.5, .8, .5, .4))),
    C("c11", 21.0, 23.1, "9/19", "김룡사 — 운달산 숲속 사찰", "김룡사·산북면", "일주문 푸시인", "없음", T2I, [],
      "A mountain temple entrance seen from a forest path: a wooden gate with a gray tile roof, a milky pale-green stream beside the path, a broad old wooden hall with many connected buildings behind, huge old fir trees around, fierce guardian statues glimpsed in the dark gate. " + NOPPL + END,
      "Slow push-in toward the temple gate along the path.",
      "공식: 전각 30여 채, 사천왕 신장상, 물빛이 우윳빛. 일주문 형태는 미확인 → 연출. 운달계곡과 같은 숲이라 c07과 겹치지 않게 사찰 위주.",
      dict(hor=.45, sky="#a8c4a0", gnd="#7a7a5a", o=[("rect", .35, .3, .3, .2, "#6b4a3a")], ch=[], ar=(.5, .8, .5, .5))),
    C("c12", 23.1, 25.0, "10/19", "봉암사 — 희양산 외경만", "봉암사·가은읍", "외경 와이드(내부·방문 연출 금지)", "없음", T2I, [],
      "Distant wide shot of a huge steep granite cliff face of Huiyangsan mountain (rock wall about one kilometer high) rising above dense forest, with the small gray tile roofs of a secluded temple far below at its foot, mist, morning light. Keep it far away, no gate close-up. " + NOPPL + END,
      "Very slow tilt up the granite cliff, mist drifting.",
      "⚠ 평소 일반 출입 금지(초파일만 개방, 2026은 5/23~24). 영상에서 '방문 가능' 오해 금지, 외경 원경만. 희양산 998m 암벽 웅장(공식).",
      dict(hor=.7, sky="#c9d3d6", gnd="#5f7f5a", o=[("poly", .3, .05, .4, .6, "#8a8f90")], ch=[], ar=(.5, .9, .5, .3))),
    C("c13", 25.0, 25.8, "11/19", "주흘산 능선 — 정상 포즈", "주흘산(1,106m)·문경읍", "능선 휩팬(0.8초)", "동이 정상 포즈", QE, D1,
      "Wide view of a long forested ridge with a rocky summit of Juheulsan (1,106 m) under a clear sky, wind blowing; character 1 (image 1) stands on the summit rock with both fists raised in a victory pose. " + DONGI + SMALL + END,
      "Fast whip pan along the ridge to the summit.",
      "공식: 해발 1,106m, 새재 북쪽, 오픈세트장 근거로 '송악산과 흡사한 산세'. 정상부 형태 미확인 → 바위 정상 연출.",
      dict(hor=.55, sky="#9ec6e8", gnd="#4f7f4a", o=[("poly", .55, .2, .2, .35, "#7a7a6a")], ch=[(.65, .3, .1)], ar=(.2, .5, .8, .5))),
    C("c14", 25.8, 26.7, "12/19", "대야산 암봉", "대야산(930.7m)·가은읍", "능선 휩팬(0.9초)", "없음", T2I, [],
      "Dramatic view of Daeyasan mountain: sheer granite peaks and strange-shaped boulders rising from dense lush forest, like a mix of Bukhansan and Dobongsan, clear blue sky. " + NOPPL + END,
      "Fast whip pan across the granite peaks.", "공식: 930.7m, 깎아지른 암봉·기암괴석, 북한산+도봉산 비유.",
      dict(hor=.6, sky="#8fc0e8", gnd="#4f7f4a", o=[("poly", .3, .1, .15, .5, "#9a9a9a"), ("poly", .55, .2, .15, .4, "#9a9a9a")], ch=[], ar=(.2, .5, .8, .5))),
    C("c15", 26.7, 27.5, "13/19", "조령산 능선", "조령산(1,026m)·문경읍", "능선 휩팬(0.8초)", "없음", T2I, [],
      "View of Joryeongsan mountain: a long ridge of forest-covered slopes on the south side with rocky peaks and steep cliffs along the main ridge, with the old Saejae pass road faint in the valley, clear sky. " + NOPPL + END,
      "Fast whip pan along the ridge line.",
      "높이: 문경시 공식 1,026m, 민간 1,017m(불일치) → 영상 자막에 높이 넣지 말 것.",
      dict(hor=.6, sky="#8fc0e8", gnd="#4f7f4a", o=[("poly", .15, .15, .5, .4, "#6f8f6a")], ch=[], ar=(.2, .5, .8, .5))),
    C("c16", 27.5, 30.0, "-", "감홍사과 — 브레이크, 동이 얼굴", "감홍사과(특산물)", "동이 얼굴 클로즈업 → 줌아웃, 대금 솔로", "동이 사과 한 입", QE, D1,
      "Close-up of character 1 (image 1) happily biting a big deep-red apple with almost no green near the bottom, sparkling juice droplets, sunny apple orchard softly blurred behind. " + DONGI + CU + END,
      "Start extreme close-up on the bite, slow pull-back reveals the orchard.",
      "공식: 문경사과 감홍 평균 15브릭스, 꼭지 반대편에 녹색이 거의 없음. 수확 10월(민간). 브랜드 표시 금지.",
      dict(hor=.5, sky="#a8d4a0", gnd="#a8d4a0", o=[("ell", .55, .35, .22, .3, "#b81f2a")], ch=[(.35, .6, .5)], ar=(.5, .5, .5, .8))),
    C("c17", 30.0, 32.0, "14/19", "가은 오픈세트장 — 고구려·신라", "가은오픈세트장·가은읍", "사극 거리 크래시 줌", "없음", T2I, [],
      "A historical drama film set of the ancient Goguryeo and Silla kingdoms: a vivid fortress with a stone wall, a palace with bright red, green and gold paintwork inspired by Goguryeo tomb murals, tiled roofs, a street with houses and thatched roofs, blue sky. " + NOPPL + END,
      "Crash zoom down the main street toward the palace.",
      "공식: 고구려 고분벽화의 화려한 색채, 평양성·안시성·요동성, 신라마을. 새재 세트장(조선, 차분한 갈색)과 색으로 구분.",
      dict(hor=.5, sky="#a9d3f0", gnd="#c9a679", o=[("rect", .3, .25, .4, .28, "#b8453a")], ch=[], ar=(.5, .55, .5, .4))),
    C("c18", 32.0, 34.0, "15/19", "문경에코월드 — 석탄 테마파크", "문경에코월드·가은읍", "시설 전경 크레인샷", "없음", T2I, [],
      "Crane shot over a mountain-valley eco theme park with a coal-mining history theme: a plaza and mine-themed buildings, an old coal-mine headframe tower, a mini train, a monorail track curving over green forest, bright daylight. " + NOPPL + END,
      "Crane camera rises over the plaza, a small train and monorail pass.",
      "공식 가이드맵: 석탄박물관·거미열차·은성갱도·탄광사택촌·에코타운·자이언트포레스트·모노레일. 건물 외관 미확인 → 연출. 시설 간판·상호 글자 금지.",
      dict(hor=.45, sky="#b9dcf2", gnd="#7fa86a", o=[("rect", .55, .15, .06, .35, "#555"), ("rect", .2, .45, .5, .04, "#aaa")], ch=[], ar=(.5, .8, .5, .4))),
    C("c19", 34.0, 37.2, "16/19", "철로자전거 — 속도 램프", "철로자전거(진남교반)·마성면", "둥이 옆자리 시점, 속도 램프", "동이 페달", QE, D2,
      "Side view of an old railway along a river valley full of autumn colors with a tunnel: a low open pedal rail car with steel wheels, a clear canopy roof, seat belts and four seats; character 1 (image 1) pedals hard in the front seat while character 2 (image 2) sits beside him, both wearing seat belts. " + DONGI + DUNGI + SMALL + END,
      "Camera runs alongside, speed ramps up fast then slows, autumn leaves swirl.",
      "공식: 2·4인승, 캐노피(폴리카보네이트)·안전벨트·스테인리스 차대, 진남교반 강·터널. 차량 색 미확인. 선로 위 빈 레일 규칙(c19 FPV 시험 시 둥이 시점 손만).",
      dict(hor=.5, sky="#c9a45a", gnd="#7a6a4a", o=[("rect", .25, .5, .5, .1, "#6a8a9a")], ch=[(.4, .55, .12), (.55, .55, .12)], ar=(.2, .6, .8, .6))),
    C("c20", 37.2, 40.2, "17/19", "활공랜드 — 탠덤 비행", "문경 활공랜드·문경읍", "탠덤 이륙 FPV, 강사 동승", "동이 안전장비 착용", QE, D1,
      "Epic aerial view of a vast autumn valley: a complete tandem paraglider with a large colorful arc-shaped wing overhead, many thin suspension lines down to the harness, a helmeted instructor pilot seated behind, and character 1 (image 1) strapped in the harness in front wearing a white safety helmet with chin strap over his hat and a harness. " + DONGI + SMALL + END,
      "Smooth glide forward over the valley, the wing sways slightly, lines taut.",
      "공식: 전문 강사 동승 체험비행(스탠다드 약 10분 등), 체중 20~100kg. 날개·하네스 세부 미확인 → 일반 탠덤 장비로 연출. 안전모 필수, 장비 누락 시 재생성.",
      dict(hor=.8, sky="#9bc8ee", gnd="#c97f3a", o=[("ell", .3, .1, .4, .18, "#e33"), ], ch=[(.5, .4, .1)], ar=(.5, .6, .5, .6))),
    C("c21", 40.2, 42.8, "18/19", "관광사격장 — 접시 표적 명중", "문경관광사격장·문경 시내(불정동)", "접시 표적 줌인, 명중 이펙트", "동이 보호안경·귀마개", QE, D1,
      "Outdoor clay target shooting range in a green hilly valley: a bright orange clay disc flying through the blue sky bursts into sparkling pieces. Character 1 (image 1) stands in the lower corner seen from behind and side wearing clear protective glasses and big red ear muffs, only his shoulder and the sky are shown, no gun barrel, no weapon aimed at any person. " + DONGI + END,
      "Camera follows the orange disc, it shatters into glittering fragments, small cheer from the character.",
      "연출 수정(승인 반영): 주종목=야외 클레이 사격(지름11cm 주황 접시). 총기 묘사 최소화, 사람 겨냥 금지. 보호안경은 공식 미확인이라 연출로 넣음(귀마개는 민간 후기).",
      dict(hor=.75, sky="#a9d3f0", gnd="#6f9a5a", o=[("ell", .55, .15, .1, .08, "#f58a1f")], ch=[(.25, .7, .22)], ar=(.4, .6, .6, .3))),
    C("c22a", 42.8, 44.2, "19/19", "도자기 — 발물레 위 흙이 찻사발로", "문경 찻사발(연출: 전통 사기장 작업)", "물레 위 흙→찻사발 변신", "동이 물레", QE, D1,
      "Close-up of character 1 (image 1) sitting at a traditional wooden kick potter's wheel in a rustic earthen workshop with a thatched roof, shaping a lump of grey-brown clay into a tea bowl with wet hands, warm firelight from an earthen kiln behind. " + DONGI + MED + END,
      "Clay on the spinning wheel rises and turns into a finished tea bowl, hands smoothing it.",
      "연출 ①(승인): 공공 체험장은 물레 체험이 아님(판성형). 이 컷은 공식 문장 '발 물레 차는 사기장·망댕이 가마' 전통 묘사를 연출한 것. 체험 컷은 c22b.",
      dict(hor=.5, sky="#6a4a3a", gnd="#6a4a3a", o=[("ell", .5, .55, .2, .1, "#c8b79a")], ch=[(.4, .6, .35)], ar=(.5, .5, .5, .5))),
    C("c22b", 44.2, 45.6, "19/19", "도자기 체험 — 판성형·도장", "문경도자기박물관 체험장·문경읍", "손 클로즈업, 완성 찻사발 컷", "동이(손)", QE, D1,
      "Close-up of hands pressing white clay into a round mold on a table, then stamping a small pattern on the finished bowl, a row of finished plain white bowls beside it, bright workshop. Character 1 (image 1) smiles at the finished bowl in the corner. " + DONGI + MED + END,
      "Hands press the clay and stamp, a finished bowl is lifted toward camera.",
      "공식: 자유성형·판성형, 개인 15,000원, 소성은 전통 망댕이 가마(소나무 장작), 택배 수령. 체험장 내부 미확인 → 연출.",
      dict(hor=.5, sky="#e8dcc8", gnd="#e8dcc8", o=[("ell", .3, .5, .3, .15, "#fff")], ch=[(.75, .6, .3)], ar=None)),
    C("c23", 45.6, 47.0, "-", "약돌한우 — 구이 한 점", "약돌한우(특산물)", "구이 위 한 점 클로즈업", "없음", T2I, [],
      "Extreme close-up of a thin slice of beef sizzling on a charcoal grill, smoke curling, juicy marbling, glowing coals, shallow depth of field, no brand, no restaurant sign. " + NOPPL + END,
      "Slow push-in, the slice sizzles and flips, smoke rises.",
      "특산물 소개용. 식당·카페 상호 노출 금지. 공식 5미 페이지는 약돌돼지구이만 있어 한우 외형은 일반 구이로 연출(과장 표현 없음).",
      dict(hor=.5, sky="#3a2a22", gnd="#3a2a22", o=[("ell", .35, .35, .3, .2, "#b85a4a")], ch=[], ar=(.5, .5, .5, .5))),
    C("c24", 47.0, 50.6, "19/19", "문경 지도 — 핀 19개 점등", "(그래픽)", "줌아웃, 핀이 차례로 점등", "-", "-", [],
      "(이미지 생성 안 함) 직접 그린 문경 윤곽 지도 + 핀 19개를 HyperFrames/SVG로 점등. 실제 지도 서비스 이미지 사용 금지.", "-",
      "그래픽 컷. 핀 위치는 소재지 읍·면 기준 개략 배치(정밀도 불필요).", dict(hor=.5, sky="#cde0c0", gnd="#cde0c0", o=[("ell", .3, .2, .4, .6, "#e8f1d8")], ch=[], ar=None)),
    C("c25", 50.6, 53.0, "-", "하이파이브 — '저장됨'", "(합성: 문경새재 석축 성문 앞)", "하이파이브 점프, 폰 '저장됨'", "동이+둥이", QE, D2,
      "The two characters jump in the air and high-five each other joyfully in front of a stone fortress gate at sunset, autumn leaves flying. " + GATE + DONGI + DUNGI + MED + END,
      "Both jump and high-five, leaves burst around them.", "기존 storyboard 25번 검증 구도 재사용. 두 캐릭터 역할 뒤바뀜 시 ONLY_REFS 방식으로 분리 생성.",
      dict(hor=.6, sky="#f2a05a", gnd="#8a7f6a", o=[("rect", .35, .3, .3, .28, "#777")], ch=[(.42, .5, .2), (.58, .5, .2)], ar=None)),
    C("c26", 53.0, 57.0, "-", "슬로건 — 문경, Next Step", "(그래픽)", "타이포 모션", "-", "-", [],
      "(이미지 생성 안 함) '문경, Next Step' + 부제 '한 고개 더' + #문경NextStep. 폰트는 라이선스 확인된 것만.", "-",
      "그래픽 컷. 폰트 라이선스 확인 필요.", dict(hor=.5, sky="#222", gnd="#222", o=[("rect", .2, .4, .6, .12, "#eee")], ch=[], ar=None)),
    C("c27", 57.0, 60.0, "-", "엔딩 — 공식 시그니처 + AI 고지", "(그래픽)", "화면 고정", "-", "-", [],
      "(이미지 생성 안 함) 공식 시그니처(사용자 보유 자산) + '본 영상은 생성형 AI를 활용해 제작되었습니다.' 화면 고정.", "-",
      "그래픽 컷. 공식 시그니처는 문경시 자산(외부 업로드 금지).", dict(hor=.5, sky="#fff", gnd="#fff", o=[("rect", .2, .45, .6, .1, "#555")], ch=[], ar=None)),
]


# ---- V4: 사진 분석 반영(jobs/contest/INFO_문경_사진분석_공통특징.md). 위 CUTS의 prompt/note를 덮어쓴다 ----
V4 = {
    "c01": GATE + "Wide shot at dawn with thin morning mist: a tiny character 1 (image 1, seen from behind) walks along the sandy path toward the gate; no vehicles, no motorcycles. " + DONGI + SMALL + END,
    "c03": "Wide low-angle shot of a Joseon-dynasty film set: a compound of low single-story hanok halls with dark charcoal-gray tiled roofs, pale sand-colored earthen courtyards, orange-brown clay walls topped with tile, stone-edged paths, a pond with a small stone bridge and stone lanterns, tree-covered hills and blue sky. Character 1 (image 1) leaps in the air in the courtyard. " + DONGI + SMALL + END,
    "c04": "Aerial view of an irregular marshy valley basin on a mountaintop: a patchwork of yellow-ochre and brown wetland grass, scattered green shrubs and round willow trees, several small blue-green ponds, a narrow wooden boardwalk winding through it, harvested golden rice-paddy terraces nearby, surrounded by forested hills in autumn red-brown and green. Not a perfect circle, no tower. " + NOPPL + END,
    "c05": "Low-angle shot at water level in a wide shallow rocky creek: large smooth pale gray granite boulders and slabs, clear green-teal pools, steep green forested slopes, open sky, a few autumn leaves. Character 1 (image 1) jumps across the creek from boulder to boulder, water splashing. " + DONGI + SMALL + END,
    "c06": "Smooth pale gray-white rounded granite bedrock sculpted by water into chutes and channels in a forest; small waterfalls slide through the smooth channels into deep round emerald pools, one pool shaped like a heart; dense green forest above; strong light. No tall waterfall, no carvings. " + NOPPL + END,
    "c07": "First-person view along a forest stream: small cascades and riffles over dark moss-covered rounded boulders, a streambed of round stones, fresh green broadleaf and pine forest, soft misty light. " + NOPPL + END,
    "c08": "Wide panoramic view of a valley stream flowing as thin sheets of water over a huge flat pale-gray granite bedrock slab, golden tea-brown reflective pools, big rounded boulders (one huge boulder perched on others), pine and broadleaf trees, open blue sky. No building. " + NOPPL + END,
    "c09": "Inside a trellis tunnel of omija vines: long hanging clusters of bright red berries among heart-shaped green leaves overhead, sunlight through the leaves. Character 1 (image 1) stands in the tunnel holding up a berry cluster with a happy face. " + DONGI + MED + END,
    "c10": "Low-angle view of a Korean mountain temple compound in a hillside valley: a cluster of halls with dark gray tiled roofs, walls in dark red-brown with cream and teal wooden panels, multi-level stacked fieldstone retaining walls, stone steps, a small stone pagoda on a lawn, bare-treed dry mountains behind, soft light. " + NOPPL + END,
    "c11": "A Korean temple courtyard: halls with dark gray tiled roofs, red columns with cream and yellow panel walls, stone staircases and stone retaining walls, a sandy gravel courtyard, a small hexagonal pavilion, tall pines and green mountains behind. " + NOPPL + END,
    "c12": "Distant wide shot: low gray-tiled temple halls and a white granite stone pagoda with a white stone railing in front of a huge pale-gray jagged granite peak (Huiyangsan) rising above pine forest, clear sky, sandy courtyard. Keep it far away, no close gate. " + NOPPL + END,
    "c13": "A summit rock outcrop with a carved stone summit marker (vertical carved characters, no readable text), low shrubs, distant layered blue ridges; character 1 (image 1) stands next to the marker with both fists raised in a victory pose. " + DONGI + SMALL + END,
    "c14": "Rounded gray granite boulders and rock outcrops along a ridge with a metal-pipe railing and stairs, green pine and broadleaf forest, a wide layered mountain view under big clouds. " + NOPPL + END,
    "c15": "Jagged pale-gray rock spires and crags lined along a steep green forested ridge, pine trees clinging to the rocks, layered ridge lines in light haze. " + NOPPL + END,
    "c16": "Close-up of character 1 (image 1) happily biting a big apple that is deep red with small pale-yellow dots on its skin and slightly flattened round shape, juice droplets sparkling, apple orchard softly blurred behind. " + DONGI + CU + END,
    "c17": "Wide shot of an ancient Korean palace film set: a two-story main hall with red columns and red-orange painted walls under a dark gray tiled roof, a beige sandy courtyard with rows of rounded boxwood shrubs, stone-edged paths, mountains behind under a blue sky. " + NOPPL + END,
    "c18": "Wide shot of a bright modern eco theme park in a green mountain valley: a low white flat-roofed ticket building with a colorful rainbow-colored sign (no readable text), a railway track beside the gate, a large colorful children's playground with artificial boulder sculptures and rope bridges, mountains behind. " + NOPPL + END,
    "c19": "Side view of open pedal rail cars with red-and-white bodies, silver frames and blue translucent canopy roofs and four seats in two rows, riding on rusty rails across a bridge with white decorative railings over a green river in a lush mountain valley; character 1 (image 1) pedals hard in the front seat and character 2 (image 2) sits beside him, both wearing seat belts. " + DONGI + DUNGI + SMALL + END,
    "c20": "Epic aerial view of a wide valley with farmland and a grassy slope launch site: a complete tandem paraglider with a bright multicolor wing and many thin colored lines to the harness; a helmeted instructor pilot sits behind and character 1 (image 1) sits strapped in the harness in front wearing a helmet with chin strap over his hat. " + DONGI + SMALL + END,
    "c21": "An outdoor clay target range: a shooter's stand under a green steel roof with green pillars, facing a grass field with white concrete walls and a forested hill behind; a bright orange clay disc flying in the sky bursts into sparkling pieces. Character 1 (image 1) stands in the lower corner seen from behind wearing clear protective glasses and big red ear muffs; no gun barrel visible, nothing aimed at any person. " + DONGI + END,
    "c22b": "A bright indoor workshop with long wooden tables with blue steel legs and stools; character 1 (image 1) rolls a flat slab of grey clay with a long grey rolling pin on the table and smiles, finished bowls on shelves behind. " + DONGI + MED + END,
    "c23": "Close-up of thin slices of richly marbled red beef on a grill over glowing charcoal, held with metal tongs, smoke curling, shallow depth of field, no brand, no sign. " + NOPPL + END,
    "c25": "The two characters jump in the air and high-five each other joyfully in front of a stone fortress gate at sunset, autumn leaves flying. " + GATE + DONGI + DUNGI + MED + END,
}
for _c in CUTS:
    if _c["id"] in V4:
        _c["prompt"] = V4[_c["id"]]
        _c["note"] += " [v4: 사진 분석 반영 프롬프트]"


def svg(sk):
    W, H = 160, 90
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%"><rect width="{W}" height="{H}" fill="{sk["sky"]}"/>',
         f'<rect y="{sk["hor"]*H:.0f}" width="{W}" height="{H-sk["hor"]*H:.0f}" fill="{sk["gnd"]}"/>']
    for k, x, y, w, h, col in sk["o"]:
        X, Y, Wd, Hd = x * W, y * H, w * W, h * H
        if k == "rect":
            s.append(f'<rect x="{X:.0f}" y="{Y:.0f}" width="{Wd:.0f}" height="{Hd:.0f}" fill="{col}" opacity=".85"/>')
        elif k == "ell":
            s.append(f'<ellipse cx="{X+Wd/2:.0f}" cy="{Y+Hd/2:.0f}" rx="{Wd/2:.0f}" ry="{Hd/2:.0f}" fill="{col}" opacity=".85"/>')
        else:
            s.append(f'<polygon points="{X:.0f},{Y+Hd:.0f} {X+Wd/2:.0f},{Y:.0f} {X+Wd:.0f},{Y+Hd:.0f}" fill="{col}" opacity=".85"/>')
    for x, y, h in sk["ch"]:
        X, Y, Hd = x * W, y * H, h * H
        s.append(f'<circle cx="{X:.0f}" cy="{Y-Hd*.35:.0f}" r="{Hd*.3:.1f}" fill="#8fd16a"/><rect x="{X-Hd*.2:.0f}" y="{Y-Hd*.05:.0f}" width="{Hd*.4:.0f}" height="{Hd*.5:.0f}" rx="3" fill="#6aa84f"/>')
    if sk["ar"]:
        x0, y0, x1, y1 = (sk["ar"][0] * W, sk["ar"][1] * H, sk["ar"][2] * W, sk["ar"][3] * H)
        s.append(f'<defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#e33"/></marker></defs>'
                 f'<line x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y1:.0f}" stroke="#e33" stroke-width="2" marker-end="url(#a)"/>')
    return "".join(s) + "</svg>"


def card(c):
    gen = c["model"] != "-"
    e = html.escape
    bar = f'<span style="left:{c["t0"]/60*100:.1f}%;width:{(c["t1"]-c["t0"])/60*100:.1f}%"></span>'
    return (f'<section class="card{"" if gen else " gfx"}" id="{c["id"]}"><div class="sk">{svg(c["sk"])}</div><div class="bd">'
            f'<h3>{c["id"]} · {e(c["title"])} <small>{c["t0"]}~{c["t1"]}초 · 카운터 {c["cnt"]}</small></h3>'
            f'<div class="tl">{bar}</div>'
            f'<p><b>소재</b> {e(c["place"])} &nbsp; <b>카메라</b> {e(c["cam"])} &nbsp; <b>캐릭터</b> {e(c["who"])}</p>'
            f'<p class="nt"><b>근거·주의</b> {e(c["note"])}</p>'
            + (f'<details><summary>이미지 프롬프트 ({c["model"]}, 참조 {", ".join(c["refs"]) or "없음"})</summary><pre>{e(c["prompt"])}</pre>'
               f'<b>영상(i2v) 지시</b><pre>{e(c["motion"])}</pre></details>' if gen else f'<p>{e(c["prompt"])}</p>')
            + '</div></section>')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = sum(c["who"].startswith(("동이", "둥이", "동이+")) and c["model"] != "-" for c in CUTS)
    css = ("body{font-family:'Malgun Gothic',sans-serif;background:#f4f1ea;margin:20px;color:#222}h1{margin:.2em 0}.card{display:flex;gap:12px;background:#fff;border:1px solid #ddd;"
           "border-radius:8px;margin:10px 0;padding:10px}.gfx{background:#eef3f8}.sk{width:240px;flex:none}.bd{flex:1}h3{margin:0 0 4px}small{color:#777;font-weight:400}"
           ".tl{position:relative;height:6px;background:#e5e5e5;margin:4px 0}.tl span{position:absolute;top:0;height:6px;background:#e33}p{margin:4px 0;font-size:14px}"
           ".nt{color:#7a4a00}pre{white-space:pre-wrap;background:#f7f7f7;padding:6px;font-size:12px}")
    head = (f'<h1>〈문경, Next Step〉 콘티 v3 — {len(CUTS)}카드 (이미지 생성 {sum(c["model"]!="-" for c in CUTS)}컷, 그래픽 {sum(c["model"]=="-" for c in CUTS)}컷)</h1>'
            f'<p>140BPM · 16:9 · 60초(최대 70초). 동이 포함 이미지 컷 {n}/{sum(c["model"]!="-" for c in CUTS)}. 빨간 화살표=카메라 이동, 초록=캐릭터(개략 위치), 파란 카드=그래픽(이미지 생성 안 함). '
            f'시드={SEED}+1000×s+컷번호(s=1,2). 모델: 캐릭터 컷 {QE}, 풍경 컷 {T2I}(z_image와 2단계에서 비교).</p>')
    (OUT / "conti_v3.html").write_text(f'<!doctype html><meta charset="utf-8"><title>콘티 v3</title><style>{css}</style>{head}' + "".join(card(c) for c in CUTS), encoding="utf-8")
    (OUT / "cuts_v3.json").write_text(json.dumps([{k: v for k, v in c.items() if k != "sk"} for c in CUTS], ensure_ascii=False, indent=1), encoding="utf-8")
    ids = [c["id"] for c in CUTS]
    assert len(set(ids)) == len(ids) and CUTS[-1]["t1"] == 60 and all(a["t1"] == b["t0"] for a, b in zip(CUTS, CUTS[1:])), "타임라인 불연속"
    print(len(CUTS), "cards ->", OUT)


if __name__ == "__main__":
    main()

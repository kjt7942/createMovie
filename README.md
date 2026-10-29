# createMovie

사진·배경음악을 올리면 AI(Gemini)가 장면을 구성하고 [HyperFrames](https://github.com/heygen-com/hyperframes)로 홍보 영상(MP4)을 렌더링하는 웹 서비스.

- 폴더째 드래그앤드롭 업로드, 배경음악 구간 편집, 영상 길이 15~600초
- AI 장면 구성·수정 요청, 장면별 화면 전환 효과, 브라우저 미리보기
- 가로(16:9)/세로(9:16), 한국어 내레이션(edge-tts), 프로젝트 저장·불러오기

## 실행
필요: Python 3.11+, Node.js 22+, FFmpeg

```
pip install -r requirements.txt
echo GEMINI_API_KEY=발급받은키 > .env
python server.py   # http://localhost:5000
```

## NAS + PC 렌더 워커 구성 (권장)
영상 렌더링은 CPU를 많이 써서, 사양이 낮은 NAS에서는 화면·AI 구성·저장만 하고 렌더링은 PC가 맡습니다.
PC가 NAS에 일감을 물어보는 방식이라 공유기 포트를 열 필요가 없고, PC가 꺼져 있으면 켜질 때까지 대기열에 남아 있습니다.

**1. NAS (Synology Container Manager)**
- 이 저장소를 NAS 폴더에 받고, 같은 폴더에 `.env` 작성:
  ```
  GEMINI_API_KEY=발급받은키
  WORKER_TOKEN=아무도-모르는-긴-문자열
  ```
- Container Manager > 프로젝트 > 생성 > `docker-compose.yml` 선택 > 빌드·실행
- 폰/PC 브라우저에서 `http://NAS주소:5000` 접속

**2. PC (Windows 10/11)**
- 브라우저에서 `http://NAS주소:5000/worker.zip` 내려받아 압축 풀기
- `setup-worker.bat` 더블클릭 → Node.js·FFmpeg 자동 설치, 토큰 입력, 시작 프로그램 등록까지 한 번에
- 이후 윈도우를 켜면 워커가 최소화 상태로 자동 실행됩니다(바탕화면 바로가기로도 실행 가능)
- macOS/Linux: Node.js 22+·FFmpeg 설치 후 `node worker.mjs --setup`, `node worker.mjs`

`WORKER_TOKEN`을 비워 두면 예전처럼 서버가 직접 렌더링합니다(PC 한 대로 쓸 때). 다른 기기에서 접속하려면 `.env`에 `HOST=0.0.0.0`.

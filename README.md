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

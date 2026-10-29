# NAS(Synology Container Manager 등)용: 화면·AI 구성·저장만 담당. 렌더링은 PC 워커가 한다(WORKER_TOKEN 필수).
FROM python:3.12-slim
# ffprobe(내레이션 길이 측정)용. 렌더링용 Node/Chrome은 넣지 않는다.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt waitress
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--threads=8", "--max-request-body-size=2147483648", "server:app"]

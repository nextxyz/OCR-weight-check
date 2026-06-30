# CPU 전용 체중계 OCR 웹앱 이미지
FROM python:3.12-slim

# opencv-headless / torch 실행에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8077 \
    WEIGHT_DB=/data/weights.db \
    UPLOAD_DIR=/data/uploads

# 1) 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2) EasyOCR 모델을 빌드 시 미리 받아 이미지에 구워넣기
#    (서버 첫 실행 시 인터넷 다운로드 불필요 + 첫 요청 지연 제거)
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# 3) 앱 코드 복사
COPY . .

# 데이터(volume)는 /data 에 보관 → 컨테이너 재생성에도 보존
VOLUME ["/data"]
EXPOSE 8077

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}"]

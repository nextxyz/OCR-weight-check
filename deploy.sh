#!/usr/bin/env bash
# 레지스트리 없이 도커 이미지를 빌드 → tar.gz 로 추출하는 스크립트.
# 추출한 tar.gz 를 다른 서버로 복사한 뒤 docker load 로 띄우면 된다.
#
# 사용법:
#   ./deploy.sh                      # linux/amd64 용으로 빌드 (일반적인 서버)
#   PLATFORM=linux/arm64 ./deploy.sh # arm64 서버(라즈베리파이/ARM VM)면 이렇게
#
# ⚠ 빌드 머신과 배포 서버의 CPU 아키텍처가 같아야 한다.
#   Mac(Apple Silicon)에서 amd64 서버로 보내려면 기본값(linux/amd64) 그대로 두면
#   buildx 가 에뮬레이션으로 교차 빌드한다(느릴 수 있음).

set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-ocr-weight-check:latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
OUT="${OUT:-ocr-weight-check.tar.gz}"

echo "[1/2] 이미지 빌드 ($PLATFORM) → $IMAGE"
docker buildx build --platform "$PLATFORM" -t "$IMAGE" --load .

echo "[2/2] tar.gz 추출 → $OUT"
docker save "$IMAGE" | gzip > "$OUT"

echo
echo "완료: $OUT ($(du -h "$OUT" | cut -f1))"
cat <<EOF

── 다른 서버에서 띄우기 ─────────────────────────────
1) 파일 복사:
   scp $OUT  사용자@서버:~

2) 서버에 접속해서 이미지 로드:
   gunzip -c $OUT | docker load

3) 컨테이너 실행 (데이터는 ./data 폴더에 영속 저장):
   docker run -d --name weightcheck \\
     -p 8077:8077 \\
     -v \$PWD/data:/data \\
     --restart unless-stopped \\
     $IMAGE

   → http://서버IP:8077 접속
─────────────────────────────────────────────────
EOF

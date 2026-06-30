#!/usr/bin/env bash
# 몸무게 기록 웹앱 실행 스크립트 (CPU 전용, .venv 사용)
#
# 사용법:
#   ./run.sh              # 기본 포트 8077
#   ./run.sh 9000         # 포트 지정
#   PORT=9000 ./run.sh    # 환경변수로 포트 지정

set -euo pipefail

# 스크립트 위치 기준으로 이동 (어디서 실행하든 동작)
cd "$(dirname "$0")"

PYTHON=".venv/bin/python"
PORT="${1:-${PORT:-8077}}"
HOST="${HOST:-0.0.0.0}"

if [ ! -x "$PYTHON" ]; then
  echo "오류: $PYTHON 를 찾을 수 없습니다. 이 프로젝트의 .venv 가 필요합니다." >&2
  exit 1
fi

# 같은 네트워크의 폰에서 접속할 IP 안내
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
echo "몸무게 기록 웹앱 시작..."
echo "  로컬:   http://localhost:${PORT}"
if [ -n "$LAN_IP" ]; then
  echo "  같은 와이파이(폰 등): http://${LAN_IP}:${PORT}"
fi
echo "  종료: Ctrl+C"
echo

exec "$PYTHON" -m uvicorn app:app --host "$HOST" --port "$PORT"

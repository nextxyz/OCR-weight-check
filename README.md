# OCR Weight Check ⚖️

체중계 사진을 올리면 **숫자 표시부를 검출·OCR해서 몸무게를 인식**하고, 기록을 저장한 뒤 **시간에 따른 몸무게 변화를 그래프**로 보여주는 웹앱입니다.

- 🧠 **GPU 불필요** — EasyOCR을 CPU 전용(`gpu=False`)으로 실행
- 📷 사진 업로드 → OCR → **사용자가 값 확인·수정 후 저장**
- 📈 Chart.js 라인차트 (X축: 올린 시간, Y축: 몸무게)
- 💾 SQLite 파일 1개(`weights.db`)에 기록 저장

## 동작 방식

1. **검출(crop)**: EasyOCR의 텍스트 검출로 화면에서 **가장 키 큰 숫자**(=몸무게)를 찾습니다. 온도·단위처럼 작은 글자는 자연히 배제됩니다.
2. **인식(OCR)**: 숫자/소수점만 인식한 뒤, 7-세그먼트 표시의 작은 소수점이 자주 누락되는 점을 보완하려고 **사람 몸무게 범위(기본 20~250kg)에 맞춰 소수점 위치를 복원**합니다.
3. **확인 후 저장**: OCR이 완벽하지 않으므로(특히 흐릿/저대비 LCD), 검출값과 crop 미리보기를 보여주고 **사용자가 확인·수정한 뒤 저장**합니다. 신뢰도가 낮으면 입력칸을 강조합니다.

> ⚠️ **정확도 한계**: 7-세그먼트 디지털 폰트는 범용 OCR이 어려워하는 대상입니다. 깨끗한 LED 표시는 정확하지만, 흐릿한 경우 끝자리 오인식이 있을 수 있어 **저장 전 확인 단계**를 둔 구조입니다.

## 설치

Python 3.10+ 권장.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 실행

```bash
./run.sh              # 기본 포트 8077
./run.sh 9000         # 포트 지정
```

브라우저에서 `http://localhost:8077` 접속. 같은 와이파이의 휴대폰에서 접속하려면 실행 시 출력되는 LAN 주소(`http://<PC_IP>:8077`)를 사용하세요.

## 구조

```
app.py             FastAPI 앱: API + HTML 서빙 + 업로드 정적 제공
ocr_core.py        OCR 코어 (EasyOCR Reader 싱글톤, 검출 + 소수점 복원) — 웹/CLI 공용
weight_ocr.py      폴더/파일 일괄 처리용 CLI
db.py              SQLite 저장소
static/index.html  프론트엔드 (촬영 버튼 + 확인 후 저장 + Chart.js)
run.sh             실행 스크립트 (.venv 사용)
```

### API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET`  | `/` | 웹 페이지 |
| `POST` | `/api/detect` | 이미지 업로드 → OCR만 수행(저장 안 함), 검출값·crop 반환 |
| `POST` | `/api/measurements` | 확인된 `{weight}`를 시각과 함께 저장 |
| `GET`  | `/api/measurements` | 기록 전체(JSON) |
| `PATCH`| `/api/measurements/{id}` | 기록의 몸무게 수정 |
| `DELETE`| `/api/measurements/{id}` | 기록 삭제 |

## CLI (일괄 처리)

폴더 안 사진들을 한 번에 OCR하고 결과를 CSV로 저장합니다.

```bash
python weight_ocr.py path/to/folder --csv results.csv
python weight_ocr.py photo.jpg --min 20 --max 200 --conf 0.6
```

## 저장 동작 참고

- 업로드된 **원본·crop 이미지는 `uploads/` 폴더(파일)**에 저장되고, **DB에는 파일명만** 저장됩니다(이미지 바이너리 아님).
- `uploads/`, `crops/`, `weights.db` 등 런타임 생성물과 `.venv/`는 저장소에 포함되지 않습니다(`.gitignore`).
- **샘플 이미지(`weight_pic/`)는 저작권 문제로 저장소에 포함하지 않습니다.** 직접 체중계 사진을 준비해 사용하세요.

## 라이선스

MIT

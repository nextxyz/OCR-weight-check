#!/usr/bin/env python
"""
체중계 사진에서 몸무게 숫자를 검출/인식하는 공용 코어 모듈.

CLI(weight_ocr.py)와 웹앱(app.py)이 함께 사용한다.
- GPU 미사용 (EasyOCR 을 gpu=False 로 CPU 전용 실행)
- EasyOCR Reader 는 무거우므로 get_reader() 로 1회만 만들어 재사용한다.
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# 체중계에 흔히 같이 찍히는 단위/노이즈 문자
NOISE_TOKENS = ("kg", "lb", "st", "℃", "%", "°c")

# 사람 몸무게로 그럴듯한 범위 (소수점 위치 복원에 사용)
PLAUSIBLE_MIN = 20.0
PLAUSIBLE_MAX = 250.0

# 이 신뢰도 미만이면 '확인 필요'로 표시 (경험적으로 오인식은 대부분 저신뢰)
CONF_THRESHOLD = 0.55

# EasyOCR Reader 싱글톤 (스레드 안전하게 1회 생성)
_reader = None
_reader_lock = threading.Lock()


def get_reader():
    """EasyOCR Reader 를 1회만 생성해 재사용한다 (CPU 전용)."""
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import easyocr  # 무거운 import 는 최초 호출 때만

                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def box_to_rect(box) -> tuple[int, int, int, int]:
    """EasyOCR 의 4점 polygon -> (x1, y1, x2, y2) 사각형."""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def clean_token(text: str) -> str:
    """OCR 텍스트에서 단위/공백을 떼고 숫자와 소수점만 남긴다."""
    t = text.lower().replace(",", ".")
    for tok in NOISE_TOKENS:
        t = t.replace(tok, "")
    return "".join(ch for ch in t if ch.isdigit() or ch == ".")


def restore_decimal(token: str) -> str | None:
    """
    숫자 문자열에서 몸무게 값을 복원한다.

    EasyOCR 은 7-세그먼트의 작은 소수점을 자주 놓치므로,
    '사람 몸무게 범위(PLAUSIBLE_MIN~MAX)' 에 들어오도록 소수점 위치를
    추정한다. 우선순위: OCR이 찾은 소수점 → 소수 1자리 → 정수 → 소수 2자리.
    """
    digits = "".join(ch for ch in token if ch.isdigit())
    if not digits:
        return None

    def fmt(value: float, decimals: int) -> str:
        return f"{value:.{decimals}f}"

    candidates: list[tuple[float, str]] = []

    # 1) OCR이 소수점을 직접 찾은 경우 가장 우선 신뢰
    if "." in token:
        try:
            v = float(token)
            decs = len(token.split(".", 1)[1])
            candidates.append((v, fmt(v, decs)))
        except ValueError:
            pass

    # 2) 소수점 위치를 k자리로 가정해서 후보 생성 (1자리 → 정수 → 2자리)
    for k in (1, 0, 2):
        if k == 0:
            v = float(int(digits))
            candidates.append((v, str(int(v))))
        elif len(digits) > k:
            v = int(digits) / (10 ** k)
            candidates.append((v, fmt(v, k)))

    # 범위 안에 드는 첫 후보 채택
    for value, text in candidates:
        if PLAUSIBLE_MIN <= value <= PLAUSIBLE_MAX:
            return text

    # 어떤 후보도 범위 밖이면, 그래도 첫 후보를 반환 (값 확인용)
    return candidates[0][1] if candidates else None


def pick_weight(results) -> tuple[str | None, tuple | None, float]:
    """
    EasyOCR readtext 결과(list of [box, text, conf])에서 몸무게 토큰을 고른다.

    몸무게는 화면에서 '가장 키가 큰 숫자'다. 온도/단위 같은 작은 글자는
    글자 높이(height)가 작아 자연히 배제된다.
    점수 = 글자높이 * (신뢰도 + 0.1).
    반환: (복원된 숫자, box, conf)
    """
    best = (None, None, 0.0)
    best_score = -1.0
    for box, text, conf in results:
        token = clean_token(text)
        num = restore_decimal(token)
        if num is None:
            continue
        x1, y1, x2, y2 = box_to_rect(box)
        height = max(1, y2 - y1)
        score = height * (conf + 0.1)
        if score > best_score:
            best_score = score
            best = (num, box, conf)
    return best


def crop_with_margin(img: np.ndarray, box, margin: float = 0.12) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box_to_rect(box)
    mx = int((x2 - x1) * margin)
    my = int((y2 - y1) * margin)
    x1 = clamp(x1 - mx, 0, w - 1)
    y1 = clamp(y1 - my, 0, h - 1)
    x2 = clamp(x2 + mx, 0, w)
    y2 = clamp(y2 + my, 0, h)
    return img[y1:y2, x1:x2]


def detect_array(img: np.ndarray) -> dict:
    """
    이미지(BGR ndarray)에서 몸무게를 검출한다.

    반환 dict:
      성공: {"weight": "66.6", "conf": 0.97, "low_conf": False, "crop": <ndarray>}
      실패: {"weight": None, "error": "...", "crop": None}
    """
    if img is None:
        return {"weight": None, "error": "이미지를 읽을 수 없음", "crop": None}

    reader = get_reader()
    results = reader.readtext(img, allowlist="0123456789.")
    num, box, conf = pick_weight(results)
    if num is None:
        return {"weight": None, "error": "숫자 검출 실패", "crop": None}

    return {
        "weight": num,
        "conf": round(float(conf), 3),
        "low_conf": float(conf) < CONF_THRESHOLD,
        "crop": crop_with_margin(img, box),
    }


def detect_bytes(data: bytes) -> dict:
    """업로드된 이미지 바이트에서 몸무게를 검출한다."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return detect_array(img)

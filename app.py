#!/usr/bin/env python
"""
체중계 사진 → 몸무게 OCR → 기록 → 그래프 웹앱 (FastAPI, CPU 전용).

흐름:
  1) /              HTML 페이지 (촬영 버튼 + 차트)
  2) POST /api/detect        이미지 업로드 → OCR만 수행 (저장 안 함)
  3) POST /api/measurements  사용자가 확인/수정한 값 저장
  4) GET  /api/measurements  기록 전체 (차트 데이터)
  5) DELETE /api/measurements/{id}
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import ocr_core

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
# 배포 시 볼륨 경로로 바꿀 수 있도록 환경변수 우선 (예: UPLOAD_DIR=/data/uploads)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or (BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # StaticFiles 마운트 전에 존재해야 함


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(exist_ok=True)
    db.init_db()
    # EasyOCR Reader 를 시작 시 미리 로드 (첫 요청 지연 방지)
    print("EasyOCR 모델 로딩 중... (CPU 모드)")
    ocr_core.get_reader()
    print("준비 완료.")
    yield


app = FastAPI(title="Weight Check", lifespan=lifespan)


class MeasurementIn(BaseModel):
    weight: float
    conf: float | None = None
    image_file: str | None = None
    crop_file: str | None = None
    taken_at: str | None = None  # 미지정 시 서버 현재시각


@app.post("/api/detect")
async def detect(file: UploadFile = File(...)):
    """업로드 이미지를 OCR. 원본/crop 을 저장하고 검출값을 반환(아직 DB 저장 안 함)."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "빈 파일입니다.")

    result = ocr_core.detect_bytes(data)

    # 원본 저장 (기록 보존)
    stem = uuid.uuid4().hex
    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    image_name = f"{stem}{suffix}"
    (UPLOAD_DIR / image_name).write_bytes(data)

    crop_name = None
    if result.get("crop") is not None:
        crop_name = f"{stem}_crop.png"
        cv2.imwrite(str(UPLOAD_DIR / crop_name), result["crop"])

    if result["weight"] is None:
        return {
            "ok": False,
            "error": result.get("error", "검출 실패"),
            "image_file": image_name,
            "image_url": f"/uploads/{image_name}",
        }

    return {
        "ok": True,
        "weight": result["weight"],
        "conf": result["conf"],
        "low_conf": result["low_conf"],
        "image_file": image_name,
        "crop_file": crop_name,
        "image_url": f"/uploads/{image_name}",
        "crop_url": f"/uploads/{crop_name}" if crop_name else None,
    }


@app.post("/api/measurements")
async def create_measurement(m: MeasurementIn):
    """사용자가 확인/수정한 몸무게를 저장한다."""
    taken_at = m.taken_at or datetime.now().isoformat(timespec="seconds")
    row = db.add_measurement(
        weight=m.weight,
        taken_at=taken_at,
        conf=m.conf,
        image_file=m.image_file,
        crop_file=m.crop_file,
    )
    return row


@app.get("/api/measurements")
async def get_measurements():
    return db.list_measurements()


class WeightUpdate(BaseModel):
    weight: float


@app.patch("/api/measurements/{measurement_id}")
async def update_measurement(measurement_id: int, body: WeightUpdate):
    """기존 기록의 몸무게 값을 수정한다."""
    if not (body.weight > 0):
        raise HTTPException(400, "올바른 몸무게가 아닙니다.")
    row = db.update_weight(measurement_id, body.weight)
    if row is None:
        raise HTTPException(404, "해당 기록이 없습니다.")
    return row


@app.delete("/api/measurements/{measurement_id}")
async def remove_measurement(measurement_id: int):
    if not db.delete_measurement(measurement_id):
        raise HTTPException(404, "해당 기록이 없습니다.")
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# 업로드된 원본/crop 이미지 정적 제공
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

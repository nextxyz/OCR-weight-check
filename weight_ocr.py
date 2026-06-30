#!/usr/bin/env python
"""
체중계 사진에서 숫자 표시부를 crop 하고 몸무게를 OCR 하는 CLI 스크립트.

핵심 OCR 로직은 ocr_core.py 에 있고, 이 파일은 폴더/파일 일괄 처리용 CLI 다.

사용법:
    python weight_ocr.py                    # weight_pic 폴더 전체
    python weight_ocr.py path/to/img.jpg    # 단일 파일
    python weight_ocr.py path/to/folder     # 폴더
    python weight_ocr.py --out-dir crops --min 20 --max 200 --conf 0.6
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

import ocr_core
from ocr_core import IMAGE_EXTS, detect_array


def gather_images(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        p for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def process(path: Path, out_dir: Path) -> dict:
    img = cv2.imread(str(path))
    r = detect_array(img)
    r["file"] = path.name
    if r["weight"] is not None:
        out_path = out_dir / f"{path.stem}_crop.png"
        cv2.imwrite(str(out_path), r["crop"])
        r["crop_file"] = out_path.name
    return r


def main() -> int:
    parser = argparse.ArgumentParser(description="체중계 숫자 OCR (CPU 전용)")
    parser.add_argument(
        "target", nargs="?", default="weight_pic",
        help="이미지 파일 또는 폴더 (기본: weight_pic)",
    )
    parser.add_argument("--out-dir", default="crops", help="crop 저장 폴더 (기본: crops)")
    parser.add_argument(
        "--min", type=float, default=ocr_core.PLAUSIBLE_MIN,
        help=f"몸무게 하한 kg (기본: {ocr_core.PLAUSIBLE_MIN:g})",
    )
    parser.add_argument(
        "--max", type=float, default=ocr_core.PLAUSIBLE_MAX,
        help=f"몸무게 상한 kg (기본: {ocr_core.PLAUSIBLE_MAX:g})",
    )
    parser.add_argument(
        "--conf", type=float, default=ocr_core.CONF_THRESHOLD,
        help=f"이 신뢰도 미만은 '확인 필요' 표시 (기본: {ocr_core.CONF_THRESHOLD:g})",
    )
    parser.add_argument(
        "--csv", default="weight_results.csv", help="결과 CSV 경로 (기본: weight_results.csv)"
    )
    args = parser.parse_args()
    ocr_core.PLAUSIBLE_MIN = args.min
    ocr_core.PLAUSIBLE_MAX = args.max
    ocr_core.CONF_THRESHOLD = args.conf

    target = Path(args.target)
    if not target.exists():
        print(f"경로를 찾을 수 없음: {target}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = gather_images(target)
    if not images:
        print(f"처리할 이미지가 없음: {target}", file=sys.stderr)
        return 1

    print("EasyOCR 모델 로딩 중... (최초 1회 다운로드, CPU 모드)")
    ocr_core.get_reader()

    rows = []
    print(f"\n{'파일':40s} {'몸무게':>8s} {'conf':>6s}  비고")
    print("-" * 78)
    for path in images:
        r = process(path, out_dir)
        if r["weight"] is None:
            print(f"{r['file']:40s} {'-':>8s} {'-':>6s}  검출실패({r.get('error', '')})")
            rows.append((r["file"], "", "", r.get("error", "검출실패")))
        else:
            flag = "⚠ 확인필요" if r["low_conf"] else ""
            print(f"{r['file']:40s} {r['weight']:>8s} {r['conf']:>6.3f}  {flag}")
            rows.append((r["file"], r["weight"], r["conf"], flag))

    csv_path = Path(args.csv)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "weight_kg", "conf", "note"])
        w.writerows(rows)

    print(f"\ncrop 이미지: {out_dir.resolve()}")
    print(f"결과 CSV  : {csv_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

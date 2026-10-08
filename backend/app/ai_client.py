"""API 서버 → AI 서버 호출.

AI 서버와의 약속(인터페이스):
  POST /segment  (image)                         → {wall_count, regions, mask_png_base64}
  POST /refine   (image, mask, regions_json)     → {wall_count, regions, mask_png_base64}
  POST /compose  (image, mask, assignments_json) → {result_jpeg_base64}

regions: [{"region_id": 1, "class": "wall", "area_ratio": 0.31, "bbox": [x0, y0, x1, y1]}]
mask   : 원본과 같은 크기의 흑백 PNG, 픽셀값 = region_id (0 = 영역 없음)
가짜 AI 서버(ai_mock)와 진짜 AI 서버가 같은 모양으로 답하면, AI_SERVER_URL만 바꿔 끼울 수 있습니다.
"""
import base64
import json

import httpx

from .config import settings
from .errors import AppError

VALID_CLASSES = {"wall", "floor", "ceiling", "molding", "window"}


def _post(endpoint: str, files: dict, data: dict | None = None) -> dict:
    try:
        with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
            res = client.post(f"{settings.ai_server_url}{endpoint}", files=files, data=data)
    except httpx.TimeoutException:
        raise AppError(504, "AI_TIMEOUT", "AI 처리 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
    except httpx.HTTPError:
        raise AppError(502, "AI_SERVER_UNAVAILABLE", "AI 서버에 연결할 수 없습니다. AI 서버가 켜져 있는지 확인하세요.")
    if res.status_code != 200:
        raise AppError(502, "AI_SERVER_ERROR", f"AI 서버 오류 ({res.status_code})", res.text[:300])
    try:
        return res.json()
    except ValueError:
        raise AppError(502, "AI_SERVER_ERROR", "AI 서버 응답을 읽을 수 없습니다.")


def _parse_segmentation(body: dict) -> dict:
    try:
        mask = base64.b64decode(body["mask_png_base64"])
        regions = body["regions"]
        wall_count = int(body["wall_count"])
    except (KeyError, TypeError, ValueError):
        raise AppError(502, "AI_SERVER_ERROR", "AI 분석 결과 형식이 약속과 다릅니다.")
    for r in regions:
        if r.get("class") not in VALID_CLASSES:
            raise AppError(502, "AI_SERVER_ERROR", f"알 수 없는 영역 종류: {r.get('class')}")
    return {"mask_png": mask, "regions": regions, "wall_count": wall_count}


def segment(image_jpeg: bytes) -> dict:
    body = _post("/segment", files={"image": ("image.jpg", image_jpeg, "image/jpeg")})
    return _parse_segmentation(body)


def refine(image_jpeg: bytes, mask_png: bytes, regions: list[dict]) -> dict:
    body = _post(
        "/refine",
        files={
            "image": ("image.jpg", image_jpeg, "image/jpeg"),
            "mask": ("mask.png", mask_png, "image/png"),
        },
        data={"regions_json": json.dumps(regions)},
    )
    return _parse_segmentation(body)


def compose(image_jpeg: bytes, mask_png: bytes, assignments: list[dict]) -> bytes:
    """assignments: [{"region_id", "color_hex", "texture_base64"(선택)}]"""
    body = _post(
        "/compose",
        files={
            "image": ("image.jpg", image_jpeg, "image/jpeg"),
            "mask": ("mask.png", mask_png, "image/png"),
        },
        data={"assignments_json": json.dumps(assignments)},
    )
    try:
        return base64.b64decode(body["result_jpeg_base64"])
    except (KeyError, TypeError, ValueError):
        raise AppError(502, "AI_SERVER_ERROR", "AI 합성 결과 형식이 약속과 다릅니다.")

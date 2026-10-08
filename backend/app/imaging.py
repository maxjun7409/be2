"""이미지 처리 도구: 업로드 정규화, 썸네일, 영역 오버레이, 브러시 수정 반영."""
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from .errors import AppError

# 영역 표시 색 (R, G, B). 벽은 벽 1, 벽 2, 벽 3 순서로 색이 달라집니다.
WALL_COLORS = [(66, 133, 244), (52, 168, 83), (251, 140, 0)]
CLASS_COLORS = {
    "floor": (141, 110, 99),
    "ceiling": (158, 158, 158),
    "molding": (229, 57, 53),
    "window": (0, 172, 193),
}
OVERLAY_ALPHA = 110


def open_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise AppError(400, "INVALID_IMAGE", "이미지 파일을 읽을 수 없습니다. JPG 또는 PNG로 올려주세요.")
    return img


def normalize_upload(data: bytes, max_side: int) -> Image.Image:
    """휴대폰 사진의 회전 정보(EXIF)를 실제로 적용하고, 긴 변을 max_side 이하로 줄입니다."""
    img = ImageOps.exif_transpose(open_image(data))
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    return img


def to_jpeg(img: Image.Image, quality: int = 90) -> bytes:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def to_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def thumbnail_jpeg(data: bytes, size: int = 400) -> bytes:
    img = open_image(data).convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    return to_jpeg(img, quality=80)


def brightness(img: Image.Image) -> float:
    """사진 전체 평균 밝기 (0~1)."""
    small = img.convert("L").resize((64, 64))
    return float(np.asarray(small, dtype=np.float32).mean() / 255)


def average_color(img: Image.Image) -> tuple[int, int, int]:
    small = img.convert("RGB").resize((32, 32))
    arr = np.asarray(small, dtype=np.float32).reshape(-1, 3).mean(axis=0)
    return int(arr[0]), int(arr[1]), int(arr[2])


def make_overlay(label_png: bytes, regions: list[dict]) -> bytes:
    """라벨 마스크를 반투명 색칠 이미지(RGBA PNG)로 만듭니다. 앱은 원본 위에 겹쳐 그리면 됩니다."""
    label = np.asarray(open_image(label_png).convert("L"))
    out = np.zeros((*label.shape, 4), dtype=np.uint8)
    wall_index = 0
    for r in sorted(regions, key=lambda x: x["region_id"]):
        if r["class"] == "wall":
            color = WALL_COLORS[wall_index % len(WALL_COLORS)]
            wall_index += 1
        else:
            color = CLASS_COLORS.get(r["class"], (120, 120, 120))
        mask = label == r["region_id"]
        out[mask] = (*color, OVERLAY_ALPHA)
    return to_png(Image.fromarray(out))


def apply_strokes(label_png: bytes, strokes: list[dict]) -> bytes:
    """브러시/지우개 기록을 라벨 마스크에 반영합니다.

    strokes: [{"region_id": 1, "width": 30, "points": [[x, y], ...]}]
      - 좌표는 '원본 이미지의 픽셀 좌표'여야 합니다 (화면 좌표 X).
      - region_id=0 은 지우개 (어떤 영역도 아님).
    """
    img = open_image(label_png).convert("L")
    draw = ImageDraw.Draw(img)
    for s in strokes:
        value = int(s["region_id"])
        width = max(1, int(round(s["width"])))
        r = width / 2
        pts = [(float(x), float(y)) for x, y in s["points"]]
        if len(pts) > 1:
            draw.line(pts, fill=value, width=width, joint="curve")
        for x, y in pts:                      # 끝부분과 꺾이는 곳을 둥글게
            draw.ellipse([x - r, y - r, x + r, y + r], fill=value)
    return to_png(img)


def image_size(data: bytes) -> tuple[int, int]:
    return open_image(data).size

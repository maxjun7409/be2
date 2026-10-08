"""가짜 AI 엔진.

- fake_segment : 사진 크기만 보고 '천장 / 벽 2개 / 몰딩 / 바닥'을 정해진 비율로 나눕니다 (진짜 모델 자리).
- refine       : 사용자가 수정한 마스크를 정리하고 영역 정보를 다시 계산합니다.
- compose      : 영역별로 색 또는 텍스처를 입히되, 원본의 명암(그림자)을 유지하는 실제 합성입니다.

진짜 모델로 바꿀 때는 fake_segment만 교체하면 되고, 나머지는 그대로 써도 됩니다.
"""
import base64
from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter

TILE_PX = 256   # 텍스처 한 장을 사진 위에서 몇 픽셀 크기로 반복할지


def decode_image(data: bytes) -> Image.Image:
    img = Image.open(BytesIO(data))
    img.load()
    return img


def png_base64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def jpeg_base64(img: Image.Image, quality: int = 90) -> str:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def regions_from_label(label: np.ndarray, classes: dict[int, str]) -> tuple[list[dict], int]:
    """라벨 마스크에서 영역 목록과 벽 개수를 계산합니다. 면적이 0인 영역은 빠집니다."""
    total = label.size
    regions = []
    for rid in sorted(classes):
        ys, xs = np.nonzero(label == rid)
        if len(xs) == 0:
            continue
        regions.append({
            "region_id": int(rid),
            "class": classes[rid],
            "area_ratio": round(len(xs) / total, 4),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        })
    wall_count = sum(1 for r in regions if r["class"] == "wall")
    return regions, wall_count


def fake_segment(img: Image.Image) -> tuple[np.ndarray, dict[int, str]]:
    """region_id: 1=벽1(왼쪽) 2=벽2(오른쪽) 3=바닥 4=천장 5=몰딩. 벽 번호는 '왼쪽부터' 규칙."""
    w, h = img.size
    label = np.zeros((h, w), dtype=np.uint8)
    ceil_y = int(h * 0.12)
    floor_y = int(h * 0.72)
    mold_h = max(2, int(h * 0.015))
    split_x = int(w * 0.45)
    label[:ceil_y, :] = 4
    label[ceil_y:floor_y - mold_h, :split_x] = 1
    label[ceil_y:floor_y - mold_h, split_x:] = 2
    label[floor_y - mold_h:floor_y, :] = 5
    label[floor_y:, :] = 3
    return label, {1: "wall", 2: "wall", 3: "floor", 4: "ceiling", 5: "molding"}


def refine(mask: Image.Image, classes: dict[int, str]) -> np.ndarray:
    """브러시 경계의 자잘한 노이즈를 정리합니다 (진짜 AI라면 여기서 경계를 다듬음)."""
    cleaned = mask.convert("L").filter(ImageFilter.ModeFilter(size=5))
    label = np.asarray(cleaned).copy()
    label[~np.isin(label, list(classes) + [0])] = 0      # 모르는 값은 '영역 없음'
    return label


def _hex_to_rgb01(hex_color: str) -> np.ndarray:
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def _tiled_texture(texture_b64: str, w: int, h: int) -> np.ndarray:
    tex = decode_image(base64.b64decode(texture_b64)).convert("RGB")
    scale = TILE_PX / max(tex.size)
    tex = tex.resize((max(1, int(tex.width * scale)), max(1, int(tex.height * scale))))
    arr = np.asarray(tex, dtype=np.float32) / 255
    reps_y = h // arr.shape[0] + 1
    reps_x = w // arr.shape[1] + 1
    return np.tile(arr, (reps_y, reps_x, 1))[:h, :w]


def compose(img: Image.Image, label: np.ndarray, assignments: list[dict]) -> Image.Image:
    """원본의 밝기 변화(그림자, 조명)를 유지하면서 영역의 색을 바꿉니다."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = label.shape
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = rgb.copy()
    for a in assignments:
        mask = label == int(a["region_id"])
        if not mask.any():
            continue
        # 영역 평균 밝기 대비 각 픽셀의 상대 밝기 = 명암 정보
        shade = gray[mask] / max(float(gray[mask].mean()), 1e-3)
        shade = np.clip(shade, 0.35, 1.6)[:, None]
        if a.get("texture_base64"):
            base = _tiled_texture(a["texture_base64"], w, h)[mask]
        else:
            base = np.broadcast_to(_hex_to_rgb01(a["color_hex"]), (int(mask.sum()), 3))
        new = np.clip(base * shade, 0, 1)
        out[mask] = 0.9 * new + 0.1 * rgb[mask]          # 원본 질감을 10% 남겨 자연스럽게
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))

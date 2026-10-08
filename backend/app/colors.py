"""색상 계산: 색 계열(color_family)과 밝기 톤(tone)을 자동으로 정합니다."""
import colorsys

FAMILY_KO = {
    "white": "화이트", "gray": "그레이", "black": "블랙", "beige": "베이지", "brown": "브라운",
    "red": "레드", "orange": "오렌지", "yellow": "옐로", "green": "그린",
    "blue": "블루", "purple": "퍼플", "pink": "핑크",
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def luminance(rgb) -> float:
    """0(검정) ~ 1(흰색)"""
    r, g, b = rgb[:3]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def tone_of(rgb) -> str:
    return "bright" if luminance(rgb) >= 0.6 else "dark"


def family_of(rgb) -> str:
    r, g, b = (c / 255 for c in rgb[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360
    if s < 0.10:
        if v > 0.85:
            return "white"
        if v < 0.25:
            return "black"
        return "gray"
    if 15 <= hue < 50 and s < 0.45 and v >= 0.6:
        return "beige"
    if 10 <= hue < 45 and v < 0.7:
        return "brown"
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 70:
        return "yellow"
    if hue < 170:
        return "green"
    if hue < 260:
        return "blue"
    if hue < 300:
        return "purple"
    return "pink"

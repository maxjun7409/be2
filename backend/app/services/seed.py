"""기본 마감재 데이터. 서버가 처음 켜질 때 materials 테이블이 비어 있으면 자동으로 넣습니다."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..colors import family_of, hex_to_rgb, tone_of
from ..models import Material

DEFAULT_MATERIALS = [
    # (material_id, category, name, color_hex, pattern, tags)
    ("wall_0001", "wall", "퓨어 화이트", "#F5F5F2", "solid", ["모던", "미니멀"]),
    ("wall_0002", "wall", "린넨 웜화이트", "#EDE6DA", "solid", ["내추럴"]),
    ("wall_0003", "wall", "라이트 그레이", "#D3D4D2", "solid", ["모던"]),
    ("wall_0004", "wall", "베이지 샌드", "#D9C7A7", "solid", ["내추럴", "아늑한"]),
    ("wall_0005", "wall", "세이지 그린", "#A8B5A0", "solid", ["내추럴"]),
    ("wall_0006", "wall", "더스티 블루", "#8FA3B8", "solid", ["모던"]),
    ("wall_0007", "wall", "차콜 그레이", "#4A4D50", "solid", ["모던", "시크"]),
    ("wall_0008", "wall", "테라코타", "#B86F52", "solid", ["아늑한", "빈티지"]),
    ("wall_0009", "wall", "딥 네이비", "#2F3A4F", "solid", ["시크"]),
    ("floor_0001", "floor", "화이트 오크", "#CDB79A", "wood", ["내추럴", "밝은"]),
    ("floor_0002", "floor", "내추럴 오크", "#A9825A", "wood", ["내추럴"]),
    ("floor_0003", "floor", "월넛", "#5E4130", "wood", ["아늑한", "클래식"]),
    ("floor_0004", "floor", "그레이 타일", "#9A9A96", "tile", ["모던"]),
    ("floor_0005", "floor", "폴리싱 화이트", "#E4E2DD", "tile", ["모던", "미니멀"]),
    ("molding_0001", "molding", "화이트", "#F7F7F5", "solid", ["모던"]),
    ("molding_0002", "molding", "아이보리", "#EEE7D8", "solid", ["내추럴"]),
    ("molding_0003", "molding", "그레이", "#8C8F92", "solid", ["모던"]),
    ("molding_0004", "molding", "우드 브라운", "#6B4A33", "wood", ["아늑한"]),
    ("molding_0005", "molding", "블랙", "#1F1F1F", "solid", ["시크"]),
]


def seed_if_empty(db: Session) -> int:
    count = db.scalar(select(func.count()).select_from(Material).where(Material.source == "default"))
    if count:
        return 0
    for mid, cat, name, hex_color, pattern, tags in DEFAULT_MATERIALS:
        rgb = hex_to_rgb(hex_color)
        db.add(Material(
            material_id=mid, category=cat, name=name, source="default",
            color_hex=hex_color, color_family=family_of(rgb), tone=tone_of(rgb),
            pattern=pattern, tags=tags,
        ))
    db.commit()
    return len(DEFAULT_MATERIALS)

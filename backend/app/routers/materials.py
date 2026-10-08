"""마감재 API: 목록(추천 포함), 스타일 추천 조합, 사용자 마감재 업로드."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import storage
from ..auth import CurrentUser, get_any_user
from ..colors import family_of, rgb_to_hex, tone_of
from ..config import settings
from ..db import get_db
from ..errors import AppError
from ..ids import new_id
from ..imaging import average_color, normalize_upload, thumbnail_jpeg, to_jpeg
from ..models import Material, Project
from ..serializers import ser_material
from ..services import recommend
from ..services.presets import PRESETS

router = APIRouter(prefix="/materials", tags=["materials"])
CATEGORIES = {"wall", "floor", "molding"}


def accessible_materials_query(user: CurrentUser):
    """기본 마감재 + 내가 올린 마감재"""
    return select(Material).where(
        Material.is_active.is_(True),
        or_(Material.source == "default", Material.owner_id == user.uid),
    )


def _optional_project(db: Session, user: CurrentUser, project_id: str | None) -> Project | None:
    if not project_id:
        return None
    p = db.get(Project, project_id)
    if p is None or p.owner_id != user.uid:
        raise AppError(404, "PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다.")
    return p


@router.get("", summary="마감재 목록 (추천 정보와 공간 팁 포함)")
def list_materials(category: str | None = None, project_id: str | None = None,
                   user: CurrentUser = Depends(get_any_user), db: Session = Depends(get_db)):
    if category and category not in CATEGORIES:
        raise AppError(422, "INVALID_CATEGORY", "category는 wall, floor, molding 중 하나여야 합니다.")
    q = accessible_materials_query(user)
    if category:
        q = q.where(Material.category == category)
    materials = db.scalars(q.order_by(Material.material_id)).all()

    project = _optional_project(db, user, project_id)
    recs = recommend.score_materials(db, user, materials, project)
    items = [ser_material(m, recs.get(m.material_id)) for m in materials]
    # 추천 점수가 높은 것부터, 같으면 내가 올린 것 → 기본 순서
    items.sort(key=lambda x: (-(x["recommendation"] or {}).get("score", 0), x["source"] != "user"))
    return {"items": items, "tips": recommend.space_tips(project)}


@router.get("/presets", summary="스타일 추천 조합 (밝은 공간, 아늑한 공간 등)")
def list_presets(project_id: str | None = None,
                 user: CurrentUser = Depends(get_any_user), db: Session = Depends(get_db)):
    project = _optional_project(db, user, project_id)
    by_id = {m.material_id: m for m in db.scalars(accessible_materials_query(user)).all()}
    items = []
    for p in PRESETS:
        mats = {cat: ser_material(by_id[mid]) for cat, mid in p["materials"].items() if mid in by_id}
        reason = None
        if p["preset_id"] == "bright" and recommend.is_dark(project):
            reason = {"code": "DARK_ROOM", "message": "채광이 적은 공간이라 이 조합을 추천해요"}
        items.append({**p, "materials": mats, "recommended_reason": reason})
    items.sort(key=lambda x: x["recommended_reason"] is None)
    return {"items": items}


@router.post("/uploads", status_code=201, summary="내 마감재 사진 업로드 (벽지·바닥재 사진)")
def upload_material(image: UploadFile = File(...), category: str = Form("wall"),
                    name: str = Form("내 마감재"),
                    user: CurrentUser = Depends(get_any_user), db: Session = Depends(get_db)):
    if category not in CATEGORIES:
        raise AppError(422, "INVALID_CATEGORY", "category는 wall, floor, molding 중 하나여야 합니다.")
    data = image.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(413, "IMAGE_TOO_LARGE", f"{settings.max_upload_mb}MB 이하의 사진을 올려주세요.")

    img = normalize_upload(data, 1024)
    rgb = average_color(img)
    mid = new_id("user")
    folder = f"materials/user/{user.uid}/{mid}"
    texture = to_jpeg(img)
    texture_path = storage.save_bytes(f"{folder}/texture.jpg", texture)
    thumb_path = storage.save_bytes(f"{folder}/thumb.jpg", thumbnail_jpeg(texture, 200))

    m = Material(
        material_id=mid, category=category, name=name[:100], source="user", owner_id=user.uid,
        texture_path=texture_path, thumbnail_path=thumb_path,
        color_hex=rgb_to_hex(rgb), color_family=family_of(rgb), tone=tone_of(rgb),
        pattern="custom", tags=[],
    )
    db.add(m)
    db.commit()
    return ser_material(m)


@router.delete("/{material_id}", summary="내가 올린 마감재 삭제")
def delete_material(material_id: str, user: CurrentUser = Depends(get_any_user),
                    db: Session = Depends(get_db)):
    m = db.get(Material, material_id)
    if m is None or m.owner_id != user.uid:
        raise AppError(404, "MATERIAL_NOT_FOUND", "마감재를 찾을 수 없습니다.")
    # 이미 저장된 시안은 스냅샷을 갖고 있어서 영향 없음. 단, 파일은 시안 정보보기 썸네일에 쓰이므로 비활성화만 합니다.
    m.is_active = False
    db.commit()
    return {"deleted": True}

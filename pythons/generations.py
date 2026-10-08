"""최종 시안 생성 API.

흐름: 요청 검증 → 영역별 마감재 배정 → AI 합성 → 결과 이미지 저장 → 시안 '초안'(saved=False) 생성
저장 버튼을 누르면 scenarios 라우터의 /save 가 초안을 저장 상태로 바꿉니다.
"""
import base64

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import ai_client, storage
from ..auth import CurrentUser, get_any_user
from ..db import get_db
from ..errors import AppError
from ..ids import new_id
from ..imaging import thumbnail_jpeg
from ..models import Material, Project, Scenario
from ..permissions import get_owned_project, get_project_analysis
from ..schemas import GenerationRequest
from ..serializers import ser_scenario
from ..services import history
from ..services.project_service import project_folder

router = APIRouter(prefix="/projects/{project_id}/generations", tags=["generations"])
CATEGORIES = ("wall", "floor", "molding")


def _load_material(db: Session, user: CurrentUser, material_id: str, category: str) -> Material:
    m = db.get(Material, material_id)
    if m is None or not m.is_active or (m.source != "default" and m.owner_id != user.uid):
        raise AppError(404, "MATERIAL_NOT_FOUND", f"마감재를 찾을 수 없습니다: {material_id}")
    if m.category != category:
        raise AppError(422, "MATERIAL_CATEGORY_MISMATCH",
                       f"{material_id}는 {category}용 마감재가 아닙니다.")
    return m


def _snapshot(m: Material, role: str, region_ids: list[int]) -> dict:
    return {
        "category": m.category, "role": role, "region_ids": region_ids,
        "material_id": m.material_id, "name": m.name, "color_hex": m.color_hex,
        "color_family": m.color_family, "tone": m.tone, "pattern": m.pattern,
        "thumbnail_path": m.thumbnail_path,
    }


@router.post("", status_code=201, summary="최종 시안 생성")
def generate(body: GenerationRequest, project: Project = Depends(get_owned_project),
             user: CurrentUser = Depends(get_any_user), db: Session = Depends(get_db)):
    analysis = get_project_analysis(db, project, body.analysis_id)
    regions = {r["region_id"]: r for r in analysis.regions}
    wall_ids = sorted(rid for rid, r in regions.items() if r["class"] == "wall")

    # 1) 카테고리별 기본 마감재
    unknown = set(body.materials) - set(CATEGORIES)
    if unknown:
        raise AppError(422, "INVALID_CATEGORY", f"알 수 없는 카테고리: {', '.join(unknown)}")
    chosen = {cat: _load_material(db, user, mid, cat) for cat, mid in body.materials.items()}
    if not chosen and not body.region_overrides:
        raise AppError(422, "NO_MATERIAL_SELECTED", "적용할 마감재를 하나 이상 선택해주세요.")

    # 2) 포인트 벽지 규칙: 벽 개수 - 1 개까지
    limit = max(0, len(wall_ids) - 1)
    if len(body.region_overrides) > limit:
        raise AppError(422, "POINT_LIMIT_EXCEEDED",
                       f"벽이 {len(wall_ids)}개인 공간에서는 포인트 벽지를 최대 {limit}개까지 쓸 수 있어요.")
    overrides: dict[int, Material] = {}
    for o in body.region_overrides:
        if o.region_id not in wall_ids:
            raise AppError(422, "INVALID_REGION", f"포인트 벽지는 벽 영역에만 쓸 수 있어요: {o.region_id}")
        if o.region_id in overrides:
            raise AppError(422, "DUPLICATE_REGION", f"같은 벽이 두 번 지정되었습니다: {o.region_id}")
        overrides[o.region_id] = _load_material(db, user, o.material_id, "wall")

    # 3) 영역별 배정 + 시안에 남길 마감재 스냅샷
    assignments, used = [], []
    textures: dict[str, str] = {}

    def assign(region_id: int, m: Material):
        if m.texture_path and m.material_id not in textures:
            textures[m.material_id] = base64.b64encode(storage.read_bytes(m.texture_path)).decode()
        assignments.append({"region_id": region_id, "color_hex": m.color_hex,
                            "texture_base64": textures.get(m.material_id)})

    base_wall_ids = [rid for rid in wall_ids if rid not in overrides]
    if "wall" in chosen:
        for rid in base_wall_ids:
            assign(rid, chosen["wall"])
        if base_wall_ids:
            used.append(_snapshot(chosen["wall"], "base", base_wall_ids))
    for rid, m in overrides.items():
        assign(rid, m)
        used.append(_snapshot(m, "point", [rid]))
    for cat in ("floor", "molding"):
        if cat in chosen:
            ids = sorted(rid for rid, r in regions.items() if r["class"] == cat)
            for rid in ids:
                assign(rid, chosen[cat])
            if ids:
                used.append(_snapshot(chosen[cat], "base", ids))
    if not assignments:
        raise AppError(422, "NOTHING_TO_APPLY", "선택한 마감재를 적용할 영역이 사진에 없습니다.")

    # 4) AI 합성
    image = storage.read_bytes(project.original_image_path)
    label = storage.read_bytes(analysis.label_path)
    result = ai_client.compose(image, label, assignments)

    # 5) 결과 저장 + 초안 생성
    sid = new_id("s")
    folder = f"{project_folder(project.owner_id, project.project_id)}/results"
    result_path = storage.save_bytes(f"{folder}/{sid}.jpg", result)
    thumb_path = storage.save_bytes(f"{folder}/{sid}_thumb.jpg", thumbnail_jpeg(result))
    scenario = Scenario(
        scenario_id=sid, project_id=project.project_id, owner_id=user.uid,
        analysis_id=analysis.analysis_id, result_image_path=result_path,
        thumbnail_path=thumb_path, materials_used=used, saved=False,
    )
    scenario.project = project
    db.add(scenario)
    db.flush()
    if not user.is_anonymous:
        history.record(db, user.uid, scenario, "generated")
    db.commit()
    return ser_scenario(scenario)

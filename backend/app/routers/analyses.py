"""AI 공간 분석 API: 분석 요청, 사용자 영역 수정, 결과 조회."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import ai_client, storage
from ..db import get_db
from ..errors import AppError
from ..ids import new_id
from ..imaging import apply_strokes, image_size, make_overlay
from ..models import Analysis, Project
from ..permissions import get_owned_project, get_project_analysis
from ..schemas import MaskEditRequest
from ..serializers import ser_analysis
from ..services.project_service import project_folder

router = APIRouter(prefix="/projects/{project_id}/analyses", tags=["analyses"])


def _store(db: Session, project: Project, result: dict, source: str, parent_id: str | None) -> Analysis:
    if image_size(result["mask_png"]) != (project.width, project.height):
        raise AppError(502, "AI_SERVER_ERROR", "AI가 돌려준 마스크 크기가 원본 사진과 다릅니다.")
    aid = new_id("a")
    folder = f"{project_folder(project.owner_id, project.project_id)}/analyses/{aid}"
    label_path = storage.save_bytes(f"{folder}/label.png", result["mask_png"])
    overlay_path = storage.save_bytes(f"{folder}/overlay.png",
                                      make_overlay(result["mask_png"], result["regions"]))
    analysis = Analysis(
        analysis_id=aid, project_id=project.project_id,
        label_path=label_path, overlay_path=overlay_path,
        regions=result["regions"], wall_count=result["wall_count"],
        source=source, parent_analysis_id=parent_id,
    )
    db.add(analysis)
    project.current_analysis_id = aid
    db.commit()
    return analysis


@router.post("", status_code=201, summary="AI 공간 분석 요청")
def analyze(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    image = storage.read_bytes(project.original_image_path)
    result = ai_client.segment(image)
    analysis = _store(db, project, result, source="auto", parent_id=None)
    return ser_analysis(analysis)


@router.get("/{analysis_id}", summary="분석 결과 조회")
def get_analysis(analysis_id: str, project: Project = Depends(get_owned_project),
                 db: Session = Depends(get_db)):
    return ser_analysis(get_project_analysis(db, project, analysis_id))


@router.post("/{analysis_id}/edits", status_code=201, summary="브러시·지우개 수정 반영 (새 분석 버전 생성)")
def edit_analysis(analysis_id: str, body: MaskEditRequest,
                  project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    base = get_project_analysis(db, project, analysis_id)
    valid_ids = {r["region_id"] for r in base.regions} | {0}
    for s in body.strokes:
        if s.region_id not in valid_ids:
            raise AppError(422, "INVALID_REGION", f"존재하지 않는 영역입니다: {s.region_id}")
        for x, y in s.points:
            if not (0 <= x <= project.width and 0 <= y <= project.height):
                raise AppError(422, "POINT_OUT_OF_IMAGE",
                               "좌표가 사진 범위를 벗어났습니다. 화면 좌표가 아닌 원본 이미지 픽셀 좌표로 보내주세요.")

    edited = apply_strokes(storage.read_bytes(base.label_path), [s.model_dump() for s in body.strokes])
    image = storage.read_bytes(project.original_image_path)
    result = ai_client.refine(image, edited, base.regions)
    analysis = _store(db, project, result, source="user_edited", parent_id=base.analysis_id)
    return ser_analysis(analysis)

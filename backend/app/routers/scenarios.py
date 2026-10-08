"""시안 API: 저장, 목록, 상세, 이름 변경, 삭제, 비교 (회원 전용)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import storage
from ..auth import CurrentUser, get_member
from ..db import get_db, utcnow
from ..errors import AppError
from ..models import Scenario
from ..permissions import get_owned_scenario
from ..schemas import CompareRequest, SaveRequest, TitleUpdate
from ..serializers import ser_scenario
from ..services import history
from ..services.project_service import delete_project

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _saved_count(db: Session, project_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Scenario)
                     .where(Scenario.project_id == project_id, Scenario.saved.is_(True))) or 0


@router.post("/{scenario_id}/save", summary="시안 저장 (초안 → 저장됨). 여러 번 눌러도 안전")
def save_scenario(body: SaveRequest | None = None,
                  scenario: Scenario = Depends(get_owned_scenario),
                  user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    if scenario.saved:
        return ser_scenario(scenario)
    count = _saved_count(db, scenario.project_id)
    scenario.saved = True
    scenario.saved_at = utcnow()
    scenario.title = (body.title if body and body.title else None) or f"시안 {count + 1}"
    history.record(db, user.uid, scenario, "saved")
    db.commit()
    return ser_scenario(scenario)


@router.get("", summary="저장된 시안 목록 (최신순)")
def list_scenarios(limit: int = 20, offset: int = 0,
                   user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 50))
    rows = db.scalars(
        select(Scenario)
        .where(Scenario.owner_id == user.uid, Scenario.saved.is_(True))
        .order_by(Scenario.created_at.desc())
        .offset(offset).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    return {"items": [ser_scenario(s) for s in rows[:limit]],
            "next_offset": offset + limit if has_more else None}


@router.post("/compare", summary="시안 비교 (2~3개)")
def compare(body: CompareRequest, user: CurrentUser = Depends(get_member),
            db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.scenario_ids))          # 중복 제거, 순서 유지
    if not 2 <= len(ids) <= 3:
        raise AppError(422, "COMPARE_COUNT_INVALID", "비교는 서로 다른 시안 2~3개로 할 수 있어요.")
    rows = {s.scenario_id: s for s in db.scalars(
        select(Scenario).where(Scenario.scenario_id.in_(ids))).all()}
    if any(i not in rows or rows[i].owner_id != user.uid or not rows[i].saved for i in ids):
        raise AppError(404, "SCENARIO_NOT_FOUND", "비교할 시안을 찾을 수 없습니다.")
    items = [rows[i] for i in ids]

    def signature(s: Scenario, category: str):
        return sorted((e["material_id"], e["role"], tuple(e["region_ids"]))
                      for e in s.materials_used if e["category"] == category)

    same, different = [], []
    for cat in ("wall", "floor", "molding"):
        sigs = [signature(s, cat) for s in items]
        (same if all(sig == sigs[0] for sig in sigs) else different).append(cat)

    return {
        "items": [ser_scenario(s) for s in items],
        "same_project": len({s.project_id for s in items}) == 1,
        "same_categories": same,
        "different_categories": different,
    }


@router.get("/{scenario_id}", summary="시안 상세 (정보 보기)")
def get_scenario(scenario: Scenario = Depends(get_owned_scenario)):
    return ser_scenario(scenario)


@router.patch("/{scenario_id}", summary="시안 이름 변경")
def rename_scenario(body: TitleUpdate, scenario: Scenario = Depends(get_owned_scenario),
                    user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    scenario.title = body.title
    db.commit()
    return ser_scenario(scenario)


@router.delete("/{scenario_id}", summary="시안 삭제. 프로젝트의 마지막 저장 시안이면 프로젝트도 삭제")
def delete_scenario(scenario: Scenario = Depends(get_owned_scenario),
                    user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    project = scenario.project
    files = [scenario.result_image_path, scenario.thumbnail_path]
    db.delete(scenario)
    db.flush()
    project_deleted = False
    if _saved_count(db, project.project_id) == 0:
        delete_project(db, project)       # 원본 사진은 여러 시안이 공유하므로 마지막일 때만 삭제
        project_deleted = True
    db.commit()
    storage.delete_paths(files)
    return {"deleted": True, "project_deleted": project_deleted}

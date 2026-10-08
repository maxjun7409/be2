"""정리 작업: 저장하지 않은 초안과, 저장된 시안이 하나도 없는 오래된 프로젝트를 지웁니다."""
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..config import settings
from ..db import utcnow
from ..models import Project, Scenario
from .project_service import delete_project

logger = logging.getLogger("matelier")


def cleanup_expired(db: Session) -> dict:
    cutoff = utcnow() - timedelta(hours=settings.draft_ttl_hours)

    has_saved = (select(Scenario.scenario_id)
                 .where(Scenario.project_id == Project.project_id, Scenario.saved.is_(True))
                 .exists())
    old_projects = db.scalars(
        select(Project).where(Project.created_at < cutoff, ~has_saved)).all()
    for p in old_projects:
        delete_project(db, p)

    old_drafts = db.scalars(
        select(Scenario).where(Scenario.saved.is_(False), Scenario.created_at < cutoff)).all()
    for s in old_drafts:
        storage.delete_paths([s.result_image_path, s.thumbnail_path])
        db.delete(s)

    db.commit()
    result = {"projects": len(old_projects), "drafts": len(old_drafts)}
    if any(result.values()):
        logger.info("정리 완료: %s", result)
    return result

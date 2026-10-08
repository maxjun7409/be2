"""프로젝트 삭제. DB 행(분석·시안 포함)과 이미지 폴더를 함께 지웁니다."""
from sqlalchemy.orm import Session

from .. import storage
from ..models import Project


def project_folder(owner_id: str, project_id: str) -> str:
    return f"users/{owner_id}/projects/{project_id}"


def delete_project(db: Session, project: Project) -> None:
    """호출한 쪽에서 db.commit() 해야 합니다."""
    folder = project_folder(project.owner_id, project.project_id)
    db.delete(project)          # analyses, scenarios는 cascade로 함께 삭제
    db.flush()
    storage.delete_prefix(folder)   # DB 먼저, 파일은 나중에 (실패해도 사용자에게는 안 보임)

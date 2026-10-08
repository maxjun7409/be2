"""회원 탈퇴: 데이터 → 파일 → Firebase 계정 순서로 삭제 (계정은 맨 마지막에)."""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import storage
from ..auth import delete_firebase_user
from ..models import Material, MaterialHistory, Project, User
from .project_service import delete_project


def delete_account(db: Session, uid: str) -> None:
    for p in db.scalars(select(Project).where(Project.owner_id == uid)).all():
        delete_project(db, p)
    db.execute(delete(MaterialHistory).where(MaterialHistory.user_id == uid))
    db.execute(delete(Material).where(Material.owner_id == uid))
    user = db.get(User, uid)
    if user:
        db.delete(user)
    db.commit()

    storage.delete_prefix(f"users/{uid}")
    storage.delete_prefix(f"materials/user/{uid}")
    delete_firebase_user(uid)

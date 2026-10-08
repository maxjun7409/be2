"""프로젝트 API: 원본 사진 업로드 = 프로젝트 생성."""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..auth import CurrentUser, get_any_user, get_member
from ..config import settings
from ..db import get_db
from ..errors import AppError
from ..ids import new_id
from ..imaging import brightness, normalize_upload, to_jpeg
from ..models import Project
from ..permissions import get_owned_project
from ..schemas import TitleUpdate
from ..serializers import ser_project
from ..services.project_service import delete_project, project_folder

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, summary="공간 사진 업로드 (프로젝트 생성)")
def create_project(image: UploadFile = File(..., description="실내 공간 사진 (JPG/PNG)"),
                   user: CurrentUser = Depends(get_any_user), db: Session = Depends(get_db)):
    data = image.file.read()
    if not data:
        raise AppError(400, "INVALID_IMAGE", "빈 파일입니다.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(413, "IMAGE_TOO_LARGE", f"{settings.max_upload_mb}MB 이하의 사진을 올려주세요.")

    img = normalize_upload(data, settings.max_image_side)
    pid = new_id("p")
    path = f"{project_folder(user.uid, pid)}/original.jpg"
    storage.save_bytes(path, to_jpeg(img))

    project = Project(project_id=pid, owner_id=user.uid, original_image_path=path,
                      width=img.width, height=img.height, brightness=brightness(img))
    db.add(project)
    db.commit()
    return ser_project(project)


@router.get("", summary="내 프로젝트 목록")
def list_projects(limit: int = 20, offset: int = 0,
                  user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 50))
    rows = db.scalars(select(Project).where(Project.owner_id == user.uid)
                      .order_by(Project.created_at.desc()).offset(offset).limit(limit + 1)).all()
    has_more = len(rows) > limit
    return {"items": [ser_project(p) for p in rows[:limit]],
            "next_offset": offset + limit if has_more else None}


@router.get("/{project_id}", summary="프로젝트 상세")
def get_project(project: Project = Depends(get_owned_project)):
    return ser_project(project)


@router.patch("/{project_id}", summary="프로젝트 이름 변경")
def rename_project(body: TitleUpdate, project: Project = Depends(get_owned_project),
                   db: Session = Depends(get_db)):
    project.title = body.title
    db.commit()
    return ser_project(project)


@router.delete("/{project_id}", summary="프로젝트 삭제 (분석, 시안, 이미지 모두)")
def remove_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    delete_project(db, project)
    db.commit()
    return {"deleted": True}

"""회원 정보 API (회원 전용)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_member
from ..db import get_db, utcnow
from ..errors import AppError
from ..models import User
from ..schemas import UserUpdate, UserUpsert
from ..serializers import ser_user
from ..services import recommend
from ..services.account_service import delete_account

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me", summary="로그인 직후 호출: 회원 정보 생성 또는 갱신")
def upsert_me(body: UserUpsert | None = None,
              user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    body = body or UserUpsert()
    u = db.get(User, user.uid)
    if u is None:
        u = User(uid=user.uid, email=user.email, display_name=body.display_name,
                 provider=body.provider or user.provider, settings={})
        db.add(u)
    else:
        u.last_login_at = utcnow()
        if user.email:
            u.email = user.email
        if body.display_name:
            u.display_name = body.display_name
    db.commit()
    return ser_user(u)


def _get_user(db: Session, uid: str) -> User:
    u = db.get(User, uid)
    if u is None:
        raise AppError(404, "USER_NOT_FOUND", "회원 정보가 없습니다. POST /users/me를 먼저 호출하세요.")
    return u


@router.get("/me", summary="내 정보 조회")
def get_me(user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    return ser_user(_get_user(db, user.uid))


@router.patch("/me", summary="내 정보 수정 (이름, 설정)")
def update_me(body: UserUpdate, user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    u = _get_user(db, user.uid)
    if body.display_name is not None:
        u.display_name = body.display_name
    if body.settings is not None:
        u.settings = {**(u.settings or {}), **body.settings}
    db.commit()
    return ser_user(u)


@router.delete("/me", summary="회원 탈퇴 (모든 데이터와 이미지 삭제)")
def delete_me(user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    delete_account(db, user.uid)
    return {"deleted": True}


@router.get("/me/preferences", summary="내 취향 분석 결과 (추천 근거 확인용)")
def my_preferences(user: CurrentUser = Depends(get_member), db: Session = Depends(get_db)):
    return recommend.preference_summary(db, user.uid)

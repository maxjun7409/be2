"""Firebase ID 토큰 검증.

- get_any_user : 회원 + 게스트(Firebase 익명 로그인) 모두 허용
- get_member   : 회원만 허용 (저장, 저장 목록, 마이페이지)

개발 중에는 .env에서 DEV_AUTH=true로 두면 'X-Debug-Uid: test-user' 헤더만으로 테스트할 수 있습니다.
"""
import logging
import os
from dataclasses import dataclass

from fastapi import Depends, Header

from .config import settings
from .errors import AppError

logger = logging.getLogger("matelier")
_firebase_ready = False


@dataclass
class CurrentUser:
    uid: str
    is_anonymous: bool
    email: str | None = None
    provider: str | None = None


def init_firebase() -> bool:
    """서비스 계정 키가 있으면 Firebase Admin을 초기화합니다."""
    global _firebase_ready
    if _firebase_ready:
        return True
    path = settings.firebase_credentials
    if not path or not os.path.exists(path):
        return False
    import firebase_admin
    from firebase_admin import credentials
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.Certificate(path))
    _firebase_ready = True
    return True


def get_any_user(
    authorization: str | None = Header(default=None),
    x_debug_uid: str | None = Header(default=None),
    x_debug_anonymous: str | None = Header(default=None),
) -> CurrentUser:
    # 개발용 우회: DEV_AUTH=true 일 때만 동작
    if settings.dev_auth and x_debug_uid:
        return CurrentUser(
            uid=x_debug_uid,
            is_anonymous=(x_debug_anonymous or "").lower() == "true",
            provider="debug",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    if not init_firebase():
        raise AppError(500, "AUTH_NOT_CONFIGURED",
                       "서버에 Firebase 인증 설정이 없습니다. .env의 FIREBASE_CREDENTIALS를 확인하세요.")

    from firebase_admin import auth
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = auth.verify_id_token(token)
    except auth.ExpiredIdTokenError:
        raise AppError(401, "TOKEN_EXPIRED", "로그인이 만료되었습니다. 다시 시도해주세요.")
    except Exception:
        raise AppError(401, "INVALID_TOKEN", "인증 정보가 올바르지 않습니다.")

    provider = decoded.get("firebase", {}).get("sign_in_provider")
    return CurrentUser(
        uid=decoded["uid"],
        is_anonymous=provider == "anonymous",
        email=decoded.get("email"),
        provider=provider,
    )


def get_member(user: CurrentUser = Depends(get_any_user)) -> CurrentUser:
    if user.is_anonymous:
        raise AppError(403, "GUEST_NOT_ALLOWED", "회원가입 후 이용할 수 있는 기능이에요.")
    return user


def delete_firebase_user(uid: str) -> None:
    """회원 탈퇴 시 Firebase 계정까지 삭제 (설정이 있을 때만)."""
    if not init_firebase():
        return
    from firebase_admin import auth
    try:
        auth.delete_user(uid)
    except Exception:
        logger.exception("Firebase 계정 삭제 실패: %s", uid)

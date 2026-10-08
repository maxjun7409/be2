"""이미지 파일 저장소 (서버 로컬 폴더).

DB에는 항상 '경로'만 저장하고, 앱에 응답할 때 url()로 주소를 만들어 줍니다.
나중에 Supabase Storage나 Firebase Storage로 바꿀 때는 이 파일만 고치면 됩니다.
"""
import shutil
from pathlib import Path

from .config import settings

ROOT = Path(settings.storage_dir).resolve()
ROOT.mkdir(parents=True, exist_ok=True)


def _full(path: str) -> Path:
    full = (ROOT / path).resolve()
    if not full.is_relative_to(ROOT):        # ../ 같은 경로 공격 방지
        raise ValueError(f"잘못된 저장 경로: {path}")
    return full


def save_bytes(path: str, data: bytes) -> str:
    full = _full(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return path


def read_bytes(path: str) -> bytes:
    return _full(path).read_bytes()


def exists(path: str | None) -> bool:
    return bool(path) and _full(path).exists()


def delete(path: str | None) -> None:
    if path:
        _full(path).unlink(missing_ok=True)


def delete_paths(paths: list[str | None]) -> None:
    for p in paths:
        delete(p)


def delete_prefix(prefix: str) -> None:
    """폴더 통째로 삭제 (예: users/{uid}/projects/{pid})"""
    full = _full(prefix)
    if full.is_dir():
        shutil.rmtree(full, ignore_errors=True)


def url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{settings.public_base_url}/files/{path}"

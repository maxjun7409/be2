"""DB 연결. DATABASE_URL만 바꾸면 SQLite ↔ PostgreSQL(Supabase)이 전환됩니다."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

IS_SQLITE = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
)

if IS_SQLITE:
    # SQLite는 기본적으로 외래 키(ON DELETE CASCADE)가 꺼져 있어서 켜줍니다.
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """UTC 현재 시각 (DB 호환을 위해 시간대 정보 없이 저장)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    """라우터에서 Depends(get_db)로 쓰는 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

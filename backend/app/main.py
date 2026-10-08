"""Matelier API 서버 진입점.

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
문서:  http://localhost:8000/docs  (모든 API를 브라우저에서 바로 테스트 가능)
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import storage
from .config import settings
from .db import Base, SessionLocal, engine
from .handlers import register_handlers
from .routers import analyses, generations, materials, projects, scenarios, users
from .services.cleanup import cleanup_expired
from .services.seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("matelier")


def _run_cleanup():
    with SessionLocal() as db:
        cleanup_expired(db)


async def _cleanup_loop():
    while True:
        try:
            await asyncio.to_thread(_run_cleanup)
        except Exception:
            logger.exception("정리 작업 실패")
        await asyncio.sleep(3600)          # 1시간마다


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)       # 테이블이 없으면 생성
    with SessionLocal() as db:
        added = seed_if_empty(db)
        if added:
            logger.info("기본 마감재 %d개를 추가했습니다.", added)
    if settings.dev_auth:
        logger.warning("DEV_AUTH=true: X-Debug-Uid 헤더 인증이 켜져 있습니다. 배포 전에 꼭 끄세요!")
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Matelier API", version="0.1.0", lifespan=lifespan)

# 모바일 앱에는 CORS가 적용되지 않지만, Expo 웹이나 관리자 웹을 위해 열어둡니다.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
register_handlers(app)

# 저장된 이미지 제공: /files/<저장 경로>
app.mount("/files", StaticFiles(directory=storage.ROOT), name="files")

API_PREFIX = "/api/v1"
for r in (users.router, projects.router, analyses.router, materials.router,
          generations.router, scenarios.router):
    app.include_router(r, prefix=API_PREFIX)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}

"""예외 핸들러. 어떤 오류든 공통 에러 형식으로 바꿔서 응답합니다."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import AppError, error_body

logger = logging.getLogger("matelier")


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse(status_code=e.status, content=error_body(e.code, e.message, e.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        details = [{"loc": list(err.get("loc", [])), "msg": err.get("msg")} for err in e.errors()]
        return JSONResponse(status_code=422, content=error_body(
            "VALIDATION_ERROR", "요청 형식이 올바르지 않습니다.", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = "NOT_FOUND" if e.status_code == 404 else f"HTTP_{e.status_code}"
        return JSONResponse(status_code=e.status_code, content=error_body(code, str(e.detail)))

    @app.exception_handler(Exception)
    async def _unknown(_: Request, e: Exception):
        logger.exception("처리되지 않은 오류")
        return JSONResponse(status_code=500, content=error_body(
            "INTERNAL_ERROR", "서버 내부 오류가 발생했습니다."))

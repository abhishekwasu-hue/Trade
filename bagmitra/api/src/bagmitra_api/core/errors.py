"""Uniform error envelope: {"error": {"code", "message", "request_id"}}."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from bagmitra_api.core.middleware import current_request_id


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(HTTPException):
    """HTTP error carrying a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str | None = None) -> None:
        super().__init__(status_code=status_code, detail=message or code)
        self.code = code


def _default_code(status: int) -> str:
    return HTTPStatus(status).phrase.lower().replace(" ", "_")


def _envelope(request: Request, status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=current_request_id(request))
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = exc.code if isinstance(exc, ApiError) else _default_code(exc.status_code)
        return _envelope(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors: list[Any] = list(exc.errors())
        message = f"{len(errors)} validation error(s)"
        return _envelope(request, 422, "validation_error", message)

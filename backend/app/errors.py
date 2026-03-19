from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        code: str,
        detail: str | None = None,
    ):
        self.status_code = status_code
        self.error = error
        self.code = code
        self.detail = detail


class NotFoundError(ApiError):
    def __init__(self, resource: str = "Resource", detail: str | None = None):
        super().__init__(404, f"{resource} not found", "NOT_FOUND", detail)


class ConflictError(ApiError):
    def __init__(self, error: str, detail: str | None = None):
        super().__init__(409, error, "CONFLICT", detail)


class BadRequestError(ApiError):
    def __init__(self, error: str, detail: str | None = None):
        super().__init__(400, error, "BAD_REQUEST", detail)


class ForbiddenError(ApiError):
    def __init__(self, error: str = "Access denied", detail: str | None = None):
        super().__init__(403, error, "FORBIDDEN", detail)


def _error_body(
    error: str,
    code: str,
    detail: str | None = None,
    field_errors: list | None = None,
) -> dict:
    body: dict = {"success": False, "error": error, "code": code}
    if detail is not None:
        body["detail"] = detail
    if field_errors is not None:
        body["errors"] = field_errors
    return body


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.error, exc.code, exc.detail),
    )


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(
            str(exc.detail),
            code_map.get(exc.status_code, "ERROR"),
        ),
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(part) for part in err["loc"])
        field_errors.append({"field": loc, "message": err["msg"]})
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "Validation failed",
            "VALIDATION_ERROR",
            field_errors=field_errors,
        ),
    )

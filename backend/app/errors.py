"""Barcha xatolar bir xil ko'rinishda qaytadi:

    {"error": {"code": "shop_closed", "message": "Kafe hozir yopiq"}}

`code` ilova ichida shartlar uchun, `message` esa mijozga to'g'ridan-to'g'ri ko'rsatish uchun.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


def _body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


_HTTP_MESSAGES = {
    401: ("unauthorized", "Avval ro'yxatdan o'ting"),
    403: ("forbidden", "Ruxsat yo'q"),
    404: ("not_found", "Topilmadi"),
    405: ("method_not_allowed", "Bu amal qo'llab-quvvatlanmaydi"),
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message, **exc.extra), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        fields = []
        message = "Ma'lumotlar noto'g'ri kiritilgan"
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", ()) if part != "body"]
            fields.append({"field": ".".join(loc), "message": err.get("msg", "")})
            # O'zimiz yozgan validatorlar o'zbekcha matn qaytaradi: uni asosiy xabar qilamiz
            ctx_error = (err.get("ctx") or {}).get("error")
            if isinstance(ctx_error, ValueError) and len(exc.errors()) == 1:
                message = str(ctx_error)
        return JSONResponse(_body("validation_error", message, fields=fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code, message = _HTTP_MESSAGES.get(exc.status_code, ("error", str(exc.detail)))
        return JSONResponse(
            _body(code, message), status_code=exc.status_code, headers=exc.headers
        )

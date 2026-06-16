from fastapi.responses import JSONResponse


def ok_response(data: dict | list | None = None, message: str = "Success", status_code: int = 200):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data if data is not None else {},
            "message": message,
        },
    )


def error_response(message: str, status_code: int = 400, data: dict | list | None = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": message,
        },
    )

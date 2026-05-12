import time
import uuid

from fastapi import (
    FastAPI,
    Request,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from backend.core.config import (
    settings,
)

from backend.core.logging import (
    get_logger,
)


logger = get_logger(
    "middleware"
)


# =========================================================
# CORS Middleware
# =========================================================
def setup_cors(
    app: FastAPI
):

    app.add_middleware(

        CORSMiddleware,

        allow_origins=settings.cors_origin_list,

        allow_credentials=True,

        allow_methods=["*"],

        allow_headers=["*"],
    )


# =========================================================
# Request Logging Middleware
# =========================================================
async def log_requests(
    request: Request,
    call_next,
):

    request_id = str(
        uuid.uuid4()
    )[:8]

    start_time = time.time()

    try:

        response = await call_next(
            request
        )

        duration_ms = round(
            (
                time.time()
                - start_time
            ) * 1000
        )

        logger.info(

            "request_completed",

            request_id=request_id,

            method=request.method,

            path=request.url.path,

            status=response.status_code,

            duration_ms=duration_ms,
        )

        response.headers[
            "X-Request-ID"
        ] = request_id

        return response

    except Exception as e:

        duration_ms = round(
            (
                time.time()
                - start_time
            ) * 1000
        )

        logger.exception(

            "request_failed",

            request_id=request_id,

            method=request.method,

            path=request.url.path,

            duration_ms=duration_ms,

            error=str(e),
        )

        raise
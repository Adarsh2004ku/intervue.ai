from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.logging import get_logger

"""
CORS middleware configuration.
Request logging middleware.
"""
logger = get_logger("middleware")

def setup_cors(app:FastAPI):
    """ Add cors middleware to the fastapi app"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins = settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
async def log_requests(request :Request,call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) *1000)

    logger.info(
        " request_completed",
        method = request.method,
        path = request.url.path,
        status = response.status_code,
        duration_ms = duration_ms
    )
    return response



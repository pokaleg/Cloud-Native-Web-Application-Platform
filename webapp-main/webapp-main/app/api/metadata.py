"""
GET /v1/metadata endpoint.
Returns cloud platform instance metadata.
Public endpoint — no authentication required.
"""
import time
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.metadata import get_metadata
from app.core.logger import setup_logger
from app.core.metrics import record_api_call, record_api_time

router = APIRouter()
logger = setup_logger(__name__)

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
}


@router.api_route("/v1/metadata", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def metadata_endpoint(request: Request):
    start = time.time()
    record_api_call("get_metadata")

    # Return 405 for non-GET methods
    if request.method != "GET":
        logger.warning(f"metadata: method not allowed — {request.method}")
        record_api_time("get_metadata", (time.time() - start) * 1000)
        return Response(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            headers=NO_CACHE_HEADERS,
        )

    # Reject query parameters
    if request.query_params:
        logger.warning("metadata: rejected — query parameters present")
        record_api_time("get_metadata", (time.time() - start) * 1000)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Query parameters are not allowed"},
            headers=NO_CACHE_HEADERS,
        )

    # Reject request body
    body = await request.body()
    if body:
        logger.warning("metadata: rejected — request body present")
        record_api_time("get_metadata", (time.time() - start) * 1000)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Request body is not allowed"},
            headers=NO_CACHE_HEADERS,
        )

    # Retrieve metadata
    try:
        data = await get_metadata()
        logger.info(f"metadata: success — platform={data.get('cloud_platform')}")
        record_api_time("get_metadata", (time.time() - start) * 1000)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=data,
            headers=NO_CACHE_HEADERS,
        )
    except RuntimeError as e:
        logger.error(f"metadata: error — {str(e)}")
        record_api_time("get_metadata", (time.time() - start) * 1000)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": str(e)},
            headers=NO_CACHE_HEADERS,
        )

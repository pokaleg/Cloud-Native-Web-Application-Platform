import time
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import HealthCheck
from app.core.logger import setup_logger
from app.core.metrics import record_api_call, record_api_time, record_db_query_time

router = APIRouter()
logger = setup_logger(__name__)

HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff"
}


@router.get("/healthz")
async def health_check(request: Request, db: Session = Depends(get_db)):
    start = time.time()
    record_api_call("healthz")

    # Reject query parameters
    if request.query_params:
        logger.warning("healthz: rejected — query parameters present")
        record_api_time("healthz", (time.time() - start) * 1000)
        return Response(content="", status_code=400, headers=HEADERS, media_type="text/plain")

    # Reject request body
    body = await request.body()
    if body:
        logger.warning("healthz: rejected — request body present")
        record_api_time("healthz", (time.time() - start) * 1000)
        return Response(content="", status_code=400, headers=HEADERS, media_type="text/plain")

    # Insert health check record — verifies DB connectivity
    try:
        db_start = time.time()
        health = HealthCheck()
        db.add(health)
        db.commit()
        record_db_query_time("healthcheck_insert", (time.time() - db_start) * 1000)

        logger.info("healthz: OK — database connectivity verified")
        record_api_time("healthz", (time.time() - start) * 1000)
        return Response(content="", status_code=200, headers=HEADERS, media_type="text/plain")

    except Exception as e:
        db.rollback()
        logger.error(f"healthz: database error — {str(e)}")
        record_api_time("healthz", (time.time() - start) * 1000)
        return Response(content="", status_code=503, headers=HEADERS, media_type="text/plain")


@router.api_route("/healthz", methods=["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def health_not_allowed():
    logger.warning("healthz: method not allowed")
    record_api_call("healthz.method_not_allowed")
    return Response(content="", status_code=405, headers=HEADERS, media_type="text/plain")

@router.get("/healthz123")
async def health_check_123(request: Request, db: Session = Depends(get_db)):
    start = time.time()
    record_api_call("healthz123")
    if request.query_params:
        record_api_time("healthz123", (time.time() - start) * 1000)
        return Response(content="", status_code=400, headers=HEADERS, media_type="text/plain")
    body = await request.body()
    if body:
        record_api_time("healthz123", (time.time() - start) * 1000)
        return Response(content="", status_code=400, headers=HEADERS, media_type="text/plain")
    try:
        db_start = time.time()
        health = HealthCheck()
        db.add(health)
        db.commit()
        record_db_query_time("healthcheck_insert", (time.time() - db_start) * 1000)
        logger.info("healthz123: OK")
        record_api_time("healthz123", (time.time() - start) * 1000)
        return Response(content="", status_code=200, headers=HEADERS, media_type="text/plain")
    except Exception as e:
        db.rollback()
        logger.error(f"healthz123: database error — {str(e)}")
        record_api_time("healthz123", (time.time() - start) * 1000)
        return Response(content="", status_code=503, headers=HEADERS, media_type="text/plain")

@router.api_route("/healthz123", methods=["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def health_not_allowed_123():
    logger.warning("healthz123: method not allowed")
    record_api_call("healthz123.method_not_allowed")
    return Response(content="", status_code=405, headers=HEADERS, media_type="text/plain")

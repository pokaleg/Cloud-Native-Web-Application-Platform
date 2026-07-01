from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime

from app.core.database import init_db
from app.api import health, user
from app.api.metadata import router as metadata_router
from app.api.courses import router as courses_router
from app.core.logger import setup_logger

app = FastAPI(
    title="CSYE 6225 - Cloud Native Web Application",
    description="RESTful API for user account management with authentication support",
    version="1.0.0"
)

# Module-level logger for exception handlers and middleware
logger = setup_logger(__name__)


# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db()
    logger.info("Database initialized — application startup complete")


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(user.router, tags=["user"])
app.include_router(metadata_router)
app.include_router(courses_router)


# Custom error response helper
def create_error_response(error_type: str, message: str, path: str, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": path
        }
    )


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors — return 400 not 422"""
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        error_type = first_error.get('type', '')
        if error_type == 'extra_forbidden':
            field_name = first_error.get('loc', [''])[-1]
            message = f"Field '{field_name}' cannot be updated"
        else:
            message = first_error.get('msg', 'Validation error')
    else:
        message = "Validation error"

    logger.warning(f"Validation error on {request.method} {request.url.path} — {message}")
    return create_error_response("Validation Error", message, str(request.url.path), 400)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with standardized error format"""
    error_type_map = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        415: "Unsupported Media Type",
        503: "Service Unavailable"
    }

    headers = {}
    message = exc.detail

    if exc.status_code == 401:
        headers["WWW-Authenticate"] = 'Basic realm="Access to user account"'
        if message == "Not authenticated":
            message = "Authentication credentials are missing or invalid"

    # Log at appropriate level based on status code
    if exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code} on {request.method} {request.url.path} — {message}"
        )
    elif exc.status_code >= 400:
        logger.warning(
            f"HTTP {exc.status_code} on {request.method} {request.url.path} — {message}"
        )

    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "error": error_type_map.get(exc.status_code, "Error"),
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors — log with full stack trace"""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path} — {str(exc)}",
        exc_info=True
    )
    return create_error_response(
        "Internal Server Error",
        "An unexpected error occurred",
        str(request.url.path),
        500
    )


# Content-Type validation middleware
@app.middleware("http")
async def check_content_type(request: Request, call_next):
    """Validate Content-Type for POST/PUT/PATCH requests."""
    if request.url.path == "/healthz":
        return await call_next(request)

    # Syllabus upload uses multipart/form-data — exempt from JSON check
    if request.url.path.endswith("/syllabus") and request.method == "POST":
        return await call_next(request)

    if request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            logger.warning(
                f"Unsupported Media Type on {request.method} {request.url.path}"
            )
            return create_error_response(
                "Unsupported Media Type",
                "Content-Type must be application/json",
                str(request.url.path),
                415
            )

    response = await call_next(request)
    return response


# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

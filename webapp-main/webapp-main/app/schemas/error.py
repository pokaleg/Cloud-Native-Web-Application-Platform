from pydantic import BaseModel
from datetime import datetime, timezone

class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: str
    path: str

def make_error(error: str, message: str, path: str) -> dict:
    return {
        "error": error,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z"),
        "path": path,
    }

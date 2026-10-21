from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.infrastructure.config import settings
from src.infrastructure.db.session import get_db

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        status.HTTP_200_OK: {"description": "Platform services healthy"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database or dependent service unavailable"},
    },
)
def get_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(
            status="healthy",
            database="connected",
            version=settings.API_VERSION,
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "version": settings.API_VERSION,
            },
        )

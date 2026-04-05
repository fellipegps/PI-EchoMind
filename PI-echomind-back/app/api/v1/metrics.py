from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.admin import Admin
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["Analytics"])


@router.get("/overview")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Retorna métricas gerais do sistema.  Requer autenticação."""
    return await MetricsService.get_overview(db)

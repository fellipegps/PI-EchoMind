from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.admin import Admin
from app.schemas.event import EventCreate, EventUpdate, EventResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


# ─── Rotas PÚBLICAS ───────────────────────────────────────────────────────────

@router.get("/", response_model=List[EventResponse])
async def list_events(db: AsyncSession = Depends(get_db)):
    """Lista todos os eventos. Público."""
    return await EventService.get_all(db)


@router.get("/upcoming", response_model=List[EventResponse])
async def list_upcoming_events(db: AsyncSession = Depends(get_db)):
    """Lista apenas eventos futuros. Público (usado pelo totem)."""
    return await EventService.get_upcoming(db)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna um evento pelo ID. Público."""
    return await EventService.get_by_id(db, event_id)


# ─── Rotas PROTEGIDAS ────────────────────────────────────────────────────────

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Cria um novo evento. Requer autenticacao."""
    return await EventService.create_event(db, event_in)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    event_in: EventUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Atualiza um evento. Requer autenticacao."""
    return await EventService.update_event(db, event_id, event_in)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Deleta um evento. Requer autenticacao."""
    await EventService.delete_event(db, event_id)

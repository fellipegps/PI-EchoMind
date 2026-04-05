from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.event import EventCreate, EventUpdate, EventResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


# ─── Rotas PÚBLICAS ───────────────────────────────────────────────────────────

@router.get("/", response_model=List[EventResponse])
async def list_events(db: AsyncSession = Depends(get_db)):
    """Lista todos os eventos."""
    return await EventService.get_all(db)


@router.get("/upcoming", response_model=List[EventResponse])
async def list_upcoming_events(db: AsyncSession = Depends(get_db)):
    """Lista apenas eventos futuros (usado pelo totem)."""
    return await EventService.get_upcoming(db)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna um evento pelo ID."""
    return await EventService.get_by_id(db, event_id)


# ─── Rotas de ESCRITA (sem auth por ora — será protegido quando o login for integrado) ──

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo evento."""
    return await EventService.create_event(db, event_in)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    event_in: EventUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Atualiza um evento."""
    return await EventService.update_event(db, event_id, event_in)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deleta um evento."""
    await EventService.delete_event(db, event_id)

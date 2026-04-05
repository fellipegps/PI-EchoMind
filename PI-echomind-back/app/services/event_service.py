from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate
from datetime import datetime


class EventService:

    @staticmethod
    async def create_event(db: AsyncSession, event_in: EventCreate) -> Event:
        new_event = Event(
            title=event_in.title,
            description=event_in.description,
            event_date=event_in.event_date,
            event_type=event_in.event_type,
        )
        db.add(new_event)
        await db.commit()
        await db.refresh(new_event)
        return new_event

    @staticmethod
    async def get_all(db: AsyncSession) -> list[Event]:
        """Retorna todos os eventos ordenados por data."""
        result = await db.execute(
            select(Event).order_by(Event.event_date.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_upcoming(db: AsyncSession) -> list[Event]:
        """Retorna apenas eventos futuros (util para o totem)."""
        result = await db.execute(
            select(Event)
            .where(Event.event_date >= datetime.utcnow())
            .order_by(Event.event_date.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_id(db: AsyncSession, event_id: str) -> Event:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento nao encontrado")
        return event

    @staticmethod
    async def update_event(db: AsyncSession, event_id: str, event_in: EventUpdate) -> Event:
        event = await EventService.get_by_id(db, event_id)
        for field, value in event_in.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def delete_event(db: AsyncSession, event_id: str) -> None:
        event = await EventService.get_by_id(db, event_id)
        await db.delete(event)
        await db.commit()

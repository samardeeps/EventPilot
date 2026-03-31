import uuid
import io
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.core.database import get_session
from app.models.models import Event, ScanCategory, Participant, Attendance, BadgeTemplate
from app.services.export_service import ExportService

router = APIRouter(prefix="/events", tags=["Events"])


class EventCreate(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime


class EventUpdate(BaseModel):
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


def _auto_create_day_categories(session: Session, event: Event):
    """Auto-create Day 1, Day 2, ... scan categories for an event."""
    for day in range(1, event.num_days + 1):
        cat = ScanCategory(
            event_id=event.id,
            name=f"Day {day} Attendance",
            category_type="attendance",
            sort_order=day,
        )
        session.add(cat)


@router.post("/")
def create_event(event: EventCreate, session: Session = Depends(get_session)):
    if event.end_date < event.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    db_event = Event(
        name=event.name,
        start_date=event.start_date,
        end_date=event.end_date,
    )
    session.add(db_event)
    session.flush()  # Get the id before creating categories

    _auto_create_day_categories(session, db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@router.get("/")
def list_events(session: Session = Depends(get_session)):
    events = session.exec(select(Event)).all()
    result = []
    for e in events:
        result.append({
            "id": str(e.id),
            "name": e.name,
            "start_date": e.start_date.isoformat(),
            "end_date": e.end_date.isoformat(),
            "num_days": e.num_days,
            "created_at": e.created_at.isoformat(),
        })
    return result


@router.get("/{event_id}")
def get_event(event_id: uuid.UUID, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "id": str(event.id),
        "name": event.name,
        "start_date": event.start_date.isoformat(),
        "end_date": event.end_date.isoformat(),
        "num_days": event.num_days,
        "created_at": event.created_at.isoformat(),
    }


@router.put("/{event_id}")
def update_event(event_id: uuid.UUID, payload: EventUpdate, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if payload.name is not None:
        event.name = payload.name
    if payload.start_date is not None:
        event.start_date = payload.start_date
    if payload.end_date is not None:
        event.end_date = payload.end_date
    if event.end_date < event.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.delete("/{event_id}")
def delete_event(event_id: uuid.UUID, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    from sqlalchemy import delete as sa_delete

    # Clean up badge template files first
    templates = session.exec(
        select(BadgeTemplate).where(BadgeTemplate.event_id == event_id)
    ).all()
    for t in templates:
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "badge_templates", t.background_image_path
        )
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

    # Bulk delete all related records using raw SQL (fast!)
    session.exec(sa_delete(Attendance).where(Attendance.event_id == event_id))
    session.exec(sa_delete(ScanCategory).where(ScanCategory.event_id == event_id))
    session.exec(sa_delete(BadgeTemplate).where(BadgeTemplate.event_id == event_id))
    session.exec(sa_delete(Participant).where(Participant.event_id == event_id))

    session.delete(event)
    session.commit()
    return {"status": "success", "message": f"Event '{event.name}' deleted"}


@router.get("/{event_id}/export")
def export_event_xls(event_id: uuid.UUID, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    svc = ExportService(session)
    data = svc.export_event_data(event_id)
    if not data:
        raise HTTPException(status_code=404, detail="No data available to export for this event.")

    # Clean filename: replace spaces and special chars
    safe_name = event.name.replace(" ", "_").replace("/", "-")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-"))

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_export.xlsx"'},
    )


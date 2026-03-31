import uuid
import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.models import Event, Participant, ScanCategory

router = APIRouter(tags=["Frontend"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@router.get("/")
async def get_dashboard(request: Request, session: Session = Depends(get_session)):
    events = session.exec(select(Event)).all()
    event_data = []
    for e in events:
        count = len(
            session.exec(
                select(Participant).where(
                    Participant.event_id == e.id,
                    Participant.is_deleted == False,
                )
            ).all()
        )
        event_data.append({
            "id": str(e.id),
            "name": e.name,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "num_days": e.num_days,
            "participant_count": count,
        })
    return templates.TemplateResponse(
        request=request, name="dashboard.html", context={"events": event_data}
    )


@router.get("/manage/{event_id}")
async def get_manage_page(
    request: Request,
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return templates.TemplateResponse(
        request=request,
        name="manage_event.html",
        context={
            "event_id": str(event.id),
            "event_name": event.name,
            "start_date": event.start_date.strftime("%Y-%m-%d"),
            "end_date": event.end_date.strftime("%Y-%m-%d"),
            "num_days": event.num_days,
        },
    )


@router.get("/scan/{event_id}")
async def get_scanner(
    request: Request,
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={
            "event_id": str(event.id),
            "event_name": event.name,
            "num_days": event.num_days,
        },
    )

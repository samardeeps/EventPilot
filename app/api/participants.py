import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.core.database import get_session
from app.models.models import Participant
from app.services.excel_service import ExcelImportService

router = APIRouter(prefix="/participants", tags=["Participants"])


class ManualParticipantCreate(BaseModel):
    event_id: uuid.UUID
    data: Dict[str, Any]


@router.post("/upload")
async def upload_excel(
    event_id: uuid.UUID = Form(...),
    duplicate_strategy: str = Form("skip"),  # "skip" or "overwrite"
    unique_key_column: str = Form("email"),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.endswith((".xlsx", ".csv")):
        raise HTTPException(status_code=400, detail="Invalid file format. Use .xlsx or .csv")

    file_bytes = await file.read()
    service = ExcelImportService(session)
    result = service.process_import(
        event_id=event_id,
        file_bytes=file_bytes,
        duplicate_strategy=duplicate_strategy,
        unique_key_column=unique_key_column,
    )
    return result


@router.post("/manual")
def add_participant_manual(
    payload: ManualParticipantCreate,
    session: Session = Depends(get_session),
):
    """Add a single participant manually with a JSON data payload."""
    from app.models.models import Event

    event = session.get(Event, payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    new_participant = Participant(
        event_id=payload.event_id,
        data=payload.data,
        qr_id=uuid.uuid4(),
    )
    session.add(new_participant)
    session.commit()
    session.refresh(new_participant)
    return {
        "status": "success",
        "participant": {
            "id": str(new_participant.id),
            "event_id": str(new_participant.event_id),
            "data": new_participant.data,
            "qr_id": str(new_participant.qr_id),
            "created_at": new_participant.created_at.isoformat(),
        },
    }


@router.get("/")
def get_participants(
    event_id: Optional[uuid.UUID] = None,
    session: Session = Depends(get_session),
):
    query = select(Participant).where(Participant.is_deleted == False)
    if event_id:
        query = query.where(Participant.event_id == event_id)

    participants = session.exec(query).all()
    result = []
    for p in participants:
        result.append(
            {
                "id": str(p.id),
                "event_id": str(p.event_id),
                "data": p.data,
                "qr_id": str(p.qr_id),
                "is_deleted": p.is_deleted,
                "created_at": p.created_at.isoformat(),
            }
        )
    return result


@router.get("/{participant_id}")
def get_participant(
    participant_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    participant = session.get(Participant, participant_id)
    if not participant or participant.is_deleted:
        raise HTTPException(status_code=404, detail="Participant not found")
    return {
        "id": str(participant.id),
        "event_id": str(participant.event_id),
        "data": participant.data,
        "qr_id": str(participant.qr_id),
        "created_at": participant.created_at.isoformat(),
    }


@router.put("/{participant_id}")
def update_participant(
    participant_id: uuid.UUID,
    data: dict,
    session: Session = Depends(get_session),
):
    participant = session.get(Participant, participant_id)
    if not participant or participant.is_deleted:
        raise HTTPException(status_code=404, detail="Participant not found")

    participant.data = data
    session.add(participant)
    session.commit()
    session.refresh(participant)
    return {
        "status": "success",
        "participant": {
            "id": str(participant.id),
            "data": participant.data,
            "qr_id": str(participant.qr_id),
        },
    }


@router.delete("/{participant_id}")
def delete_participant(
    participant_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    participant = session.get(Participant, participant_id)
    if not participant or participant.is_deleted:
        raise HTTPException(status_code=404, detail="Participant not found")

    participant.is_deleted = True  # Soft delete
    session.add(participant)
    session.commit()
    return {"status": "success", "message": "Participant soft deleted"}

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_session
from app.models.models import Participant, Attendance, Event, ScanCategory

router = APIRouter(tags=["Attendance & Scanning"])


# ─── Scan Categories CRUD ───────────────────────────────────────────────────

class ScanCategoryCreate(BaseModel):
    event_id: uuid.UUID
    name: str
    category_type: str = "custom"  # attendance | kit | seminar | custom


@router.get("/categories/")
def list_categories(event_id: uuid.UUID, session: Session = Depends(get_session)):
    cats = session.exec(
        select(ScanCategory)
        .where(ScanCategory.event_id == event_id)
        .order_by(ScanCategory.sort_order, ScanCategory.created_at)
    ).all()
    return [
        {
            "id": str(c.id),
            "event_id": str(c.event_id),
            "name": c.name,
            "category_type": c.category_type,
            "sort_order": c.sort_order,
        }
        for c in cats
    ]


@router.post("/categories/")
def create_category(payload: ScanCategoryCreate, session: Session = Depends(get_session)):
    event = session.get(Event, payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get max sort_order for this event
    existing = session.exec(
        select(ScanCategory)
        .where(ScanCategory.event_id == payload.event_id)
        .order_by(ScanCategory.sort_order.desc())
    ).first()
    next_order = (existing.sort_order + 1) if existing else 1

    cat = ScanCategory(
        event_id=payload.event_id,
        name=payload.name,
        category_type=payload.category_type,
        sort_order=next_order,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return {
        "status": "success",
        "category": {
            "id": str(cat.id),
            "name": cat.name,
            "category_type": cat.category_type,
        },
    }


@router.delete("/categories/{category_id}")
def delete_category(category_id: uuid.UUID, session: Session = Depends(get_session)):
    cat = session.get(ScanCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    # Also delete attendance records for this category
    records = session.exec(
        select(Attendance).where(Attendance.scan_category_id == category_id)
    ).all()
    for r in records:
        session.delete(r)
    session.delete(cat)
    session.commit()
    return {"status": "success", "message": f"Category '{cat.name}' deleted"}


# ─── QR Scanning ────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    event_id: uuid.UUID
    qr_id: str
    scan_category_id: uuid.UUID


@router.post("/scan")
def record_scan(scan_req: ScanRequest, session: Session = Depends(get_session)):
    """Record attendance by scanning a QR code for a specific category."""
    # 1. Validate Event
    event = session.get(Event, scan_req.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Validate category
    category = session.get(ScanCategory, scan_req.scan_category_id)
    if not category or category.event_id != scan_req.event_id:
        raise HTTPException(status_code=400, detail="Invalid scan category for this event")

    # 3. Find Participant by QR ID
    try:
        qr_uuid = uuid.UUID(scan_req.qr_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid QR payload")

    participant = session.exec(
        select(Participant).where(
            Participant.qr_id == qr_uuid,
            Participant.event_id == scan_req.event_id,
            Participant.is_deleted == False,
        )
    ).first()

    if not participant:
        raise HTTPException(
            status_code=404,
            detail="Participant not found or not registered for this event",
        )

    # 4. Record Attendance
    new_attendance = Attendance(
        participant_id=participant.id,
        event_id=scan_req.event_id,
        scan_category_id=scan_req.scan_category_id,
    )

    try:
        session.add(new_attendance)
        session.commit()
        session.refresh(new_attendance)
        return {
            "status": "success",
            "message": f"Recorded: {category.name}",
            "participant_name": participant.data.get("name", "Unknown"),
            "participant_company": participant.data.get("company", ""),
            "category_name": category.name,
        }
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Already scanned for '{category.name}'",
        )


# ─── Attendance Records ─────────────────────────────────────────────────────

@router.get("/attendance/")
def list_attendance(
    event_id: uuid.UUID,
    scan_category_id: Optional[uuid.UUID] = None,
    session: Session = Depends(get_session),
):
    """List attendance records, optionally filtered by category."""
    query = select(Attendance).where(Attendance.event_id == event_id)
    if scan_category_id:
        query = query.where(Attendance.scan_category_id == scan_category_id)

    records = session.exec(query.order_by(Attendance.scanned_at.desc())).all()

    # Pre-load categories for name lookup
    cats = session.exec(
        select(ScanCategory).where(ScanCategory.event_id == event_id)
    ).all()
    cat_map = {c.id: c.name for c in cats}

    result = []
    for r in records:
        p = session.get(Participant, r.participant_id)
        result.append({
            "id": r.id,
            "participant_id": str(r.participant_id),
            "participant_name": p.data.get("name", "Unknown") if p else "Unknown",
            "participant_company": p.data.get("company", "") if p else "",
            "category_name": cat_map.get(r.scan_category_id, "Unknown"),
            "scan_category_id": str(r.scan_category_id),
            "scanned_at": r.scanned_at.isoformat(),
        })
    return result


@router.get("/attendance/summary")
def attendance_summary(
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """Summary counts per scan category."""
    cats = session.exec(
        select(ScanCategory)
        .where(ScanCategory.event_id == event_id)
        .order_by(ScanCategory.sort_order)
    ).all()

    result = []
    for c in cats:
        count = len(
            session.exec(
                select(Attendance).where(
                    Attendance.event_id == event_id,
                    Attendance.scan_category_id == c.id,
                )
            ).all()
        )
        result.append({
            "id": str(c.id),
            "name": c.name,
            "category_type": c.category_type,
            "count": count,
        })
    return result

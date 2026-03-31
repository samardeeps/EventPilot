import uuid
import io
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from PIL import Image

from app.core.database import get_session
from app.models.models import Participant, BadgeTemplate
from app.services.badge_service import BadgeEngineService

router = APIRouter(prefix="/badges", tags=["Badges"])


@router.get("/preview/{template_id}")
def preview_badge(
    template_id: uuid.UUID,
    participant_id: uuid.UUID,
    mode: str = Query("full", regex="^(full|minimal|qr_only)$"),
    session: Session = Depends(get_session),
):
    """Preview a single badge as PNG image.
    Modes: full (background + info), minimal (white bg + info), qr_only (just QR)
    """
    template = session.get(BadgeTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    participant = session.get(Participant, participant_id)
    if not participant or participant.is_deleted:
        raise HTTPException(status_code=404, detail="Participant not found")

    engine = BadgeEngineService()
    img_bytes = engine.generate_badge(participant, template, mode=mode)

    return StreamingResponse(io.BytesIO(img_bytes), media_type="image/png")


@router.get("/generate/{template_id}")
def generate_badges_pdf(
    template_id: uuid.UUID,
    event_id: uuid.UUID,
    mode: str = Query("full", regex="^(full|minimal|qr_only)$"),
    width: Optional[float] = None,
    height: Optional[float] = None,
    limit: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """Generate a PDF with one badge per page.
    Modes: full (background + info), minimal (white bg + info), qr_only (just QR)
    """
    template = session.get(BadgeTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Override size if specified
    w = width or template.width_inches
    h = height or template.height_inches

    query = select(Participant).where(
        Participant.event_id == event_id,
        Participant.is_deleted == False,
    )
    if limit:
        query = query.limit(limit)

    participants = session.exec(query).all()
    if not participants:
        raise HTTPException(status_code=404, detail="No participants found")

    engine = BadgeEngineService()
    images = []

    for p in participants:
        try:
            img_bytes = engine.generate_badge(p, template, mode=mode)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            # Resize to exact print dimensions
            target_w = int(w * template.dpi)
            target_h = int(h * template.dpi)
            img = img.resize((target_w, target_h), Image.LANCZOS)
            images.append(img)
        except Exception as e:
            print(f"Failed badge for {p.id}: {e}")

    if not images:
        raise HTTPException(status_code=500, detail="Failed to generate badges")

    pdf_buffer = io.BytesIO()
    images[0].save(
        pdf_buffer,
        format="PDF",
        resolution=float(template.dpi),
        save_all=True,
        append_images=images[1:],
    )
    pdf_buffer.seek(0)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=badges_{event_id}.pdf"},
    )


@router.get("/qr/{qr_id}")
def get_qr_code(qr_id: str):
    """Generate a QR code image for a given UUID."""
    engine = BadgeEngineService()
    img = engine.generate_qr_image(qr_id)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

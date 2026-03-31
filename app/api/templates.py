import uuid
import os
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlmodel import Session, select
import json
from typing import Optional

from app.core.database import get_session
from app.models.models import BadgeTemplate

router = APIRouter(prefix="/templates", tags=["Badge Templates"])

# Local storage directory
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "badge_templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)


@router.post("/upload")
async def upload_template(
    event_id: uuid.UUID = Form(...),
    name: str = Form(...),
    layout_config: str = Form('{"name":{"x":50,"y":30,"font_size":28,"color":"black","align":"center"},"qr":{"x":50,"y":50,"size":25},"company":{"x":50,"y":72,"font_size":18,"color":"#333333","align":"center"}}'),
    width_inches: float = Form(4.0),
    height_inches: float = Form(6.0),
    dpi: int = Form(300),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Upload a badge template background image with layout configuration.
    
    Layout config uses PERCENTAGE coordinates (0-100) relative to badge dimensions.
    This makes positioning work regardless of actual pixel size.
    Example: {"name": {"x": 50, "y": 55, "font_size": 28, "color": "black", "align": "center"}}
    """
    try:
        config_dict = json.loads(layout_config)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON layout_config")

    # Save file locally
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"{file_id}{ext}"
    filepath = os.path.join(TEMPLATES_DIR, filename)

    file_bytes = await file.read()
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    template = BadgeTemplate(
        event_id=event_id,
        name=name,
        background_image_path=filename,  # Just the filename, not full path
        layout_config=config_dict,
        width_inches=width_inches,
        height_inches=height_inches,
        dpi=dpi,
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    return {
        "status": "success",
        "template": {
            "id": str(template.id),
            "name": template.name,
            "event_id": str(template.event_id),
            "width_inches": template.width_inches,
            "height_inches": template.height_inches,
        },
    }


@router.get("/")
def list_templates(
    event_id: Optional[uuid.UUID] = None,
    session: Session = Depends(get_session),
):
    query = select(BadgeTemplate)
    if event_id:
        query = query.where(BadgeTemplate.event_id == event_id)
    templates = session.exec(query).all()
    return [
        {
            "id": str(t.id),
            "event_id": str(t.event_id),
            "name": t.name,
            "background_image_path": t.background_image_path,
            "layout_config": t.layout_config,
            "width_inches": t.width_inches,
            "height_inches": t.height_inches,
            "dpi": t.dpi,
        }
        for t in templates
    ]


@router.delete("/{template_id}")
def delete_template(template_id: uuid.UUID, session: Session = Depends(get_session)):
    template = session.get(BadgeTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Delete the file
    filepath = os.path.join(TEMPLATES_DIR, template.background_image_path)
    if os.path.exists(filepath):
        os.remove(filepath)

    session.delete(template)
    session.commit()
    return {"status": "success", "message": f"Template '{template.name}' deleted"}

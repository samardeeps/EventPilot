import io
import pandas as pd
import uuid
from sqlmodel import Session, select

from app.models.models import Participant, Attendance, ScanCategory


class ExportService:
    def __init__(self, session: Session):
        self.session = session

    def export_event_data(self, event_id: uuid.UUID) -> bytes:
        """
        Exports participants with per-category attendance columns.
        Creates columns like: "Day 1 Attendance", "Welcome Kit", etc.
        """
        participants = self.session.exec(
            select(Participant).where(
                Participant.event_id == event_id,
                Participant.is_deleted == False,
            )
        ).all()

        if not participants:
            return None

        # Get all scan categories for this event
        categories = self.session.exec(
            select(ScanCategory)
            .where(ScanCategory.event_id == event_id)
            .order_by(ScanCategory.sort_order)
        ).all()

        # Get all attendance records
        attendances = self.session.exec(
            select(Attendance).where(Attendance.event_id == event_id)
        ).all()

        # Build lookup: { (participant_id, category_id): scanned_at }
        att_map = {}
        for a in attendances:
            att_map[(a.participant_id, a.scan_category_id)] = a.scanned_at

        export_data = []
        for p in participants:
            row = p.data.copy()
            row["qr_id"] = str(p.qr_id)
            row["participant_id"] = str(p.id)

            # Add per-category columns
            for cat in categories:
                scanned_at = att_map.get((p.id, cat.id))
                row[cat.name] = "Yes" if scanned_at else "No"
                row[f"{cat.name} Time"] = (
                    scanned_at.strftime("%Y-%m-%d %H:%M:%S") if scanned_at else ""
                )

            export_data.append(row)

        df = pd.DataFrame(export_data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Participants")

        output.seek(0)
        return output.read()

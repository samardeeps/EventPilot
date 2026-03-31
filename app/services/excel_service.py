import uuid
import pandas as pd
from typing import List, Tuple, Any
from io import BytesIO
from sqlmodel import Session, select
from fastapi import HTTPException

from app.models.models import Participant, Event

class ExcelImportService:
    def __init__(self, session: Session):
        self.session = session

    def process_import(
        self, 
        event_id: uuid.UUID, 
        file_bytes: bytes, 
        duplicate_strategy: str = "skip", # 'skip' or 'overwrite'
        unique_key_column: str = "email" # The column in excel used to check for duplicates
    ) -> dict:
        """
        Parses an excel file and imports participants using a transaction block.
        """
        # Ensure event exists
        event = self.session.get(Event, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        try:
            df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")

        # Replace nan with None
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")
        
        if not records:
            return {"status": "success", "imported": 0, "skipped": 0, "overwritten": 0}

        metrics = {"imported": 0, "skipped": 0, "overwritten": 0}

        try:
            for row in records:
                unique_val = row.get(unique_key_column)
                
                if unique_val:
                    # Check for duplicate
                    # In postgres JSONB, we can query by json field, but since we are doing logic in python for safety:
                    # We will use a standard query if data inside JSONB matched
                    existing = self.session.exec(
                        select(Participant).where(
                            Participant.event_id == event_id,
                            Participant.is_deleted == False
                            # SQLAlchemy JSONB containment for postgres: Participant.data.contains({unique_key_column: unique_val})
                        )
                    ).all()
                    
                    # Filter existing python-side if JSONB query via SQLModel is tricky
                    existing_match = next((p for p in existing if p.data.get(unique_key_column) == unique_val), None)
                    
                    if existing_match:
                        if duplicate_strategy == "skip":
                            metrics["skipped"] += 1
                            continue
                        elif duplicate_strategy == "overwrite":
                            existing_match.data = row
                            self.session.add(existing_match)
                            metrics["overwritten"] += 1
                            continue
                
                # New record
                new_participant = Participant(
                    event_id=event_id,
                    data=row,
                    qr_id=uuid.uuid4()
                )
                self.session.add(new_participant)
                metrics["imported"] += 1

            self.session.commit()
            metrics["status"] = "success"
            return metrics

        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=500, detail=f"Database transaction failed: {str(e)}")

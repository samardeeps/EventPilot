import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlmodel import Field, SQLModel, JSON, Column
from sqlalchemy import UniqueConstraint


def get_utc_now():
    return datetime.now(timezone.utc)


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str = Field(index=True)
    start_date: datetime
    end_date: datetime
    created_at: datetime = Field(default_factory=get_utc_now)

    @property
    def num_days(self) -> int:
        delta = self.end_date.date() - self.start_date.date()
        return max(delta.days + 1, 1)


class Participant(SQLModel, table=True):
    __tablename__ = "participants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True)
    data: Dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    qr_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True, index=True)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_utc_now)


class ScanCategory(SQLModel, table=True):
    """Flexible scan checkpoint: day attendance, welcome kit, seminar, custom."""
    __tablename__ = "scan_categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True)
    name: str  # "Day 1 Attendance", "Welcome Kit", "Seminar A"
    category_type: str = Field(default="attendance")  # attendance | kit | seminar | custom
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=get_utc_now)


class Attendance(SQLModel, table=True):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "event_id", "scan_category_id",
            name="uq_participant_event_category"
        ),
    )

    id: int = Field(default=None, primary_key=True)
    participant_id: uuid.UUID = Field(foreign_key="participants.id", index=True)
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True)
    scan_category_id: uuid.UUID = Field(foreign_key="scan_categories.id", index=True)
    scanned_at: datetime = Field(default_factory=get_utc_now)


class BadgeTemplate(SQLModel, table=True):
    __tablename__ = "badge_templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True)
    name: str  # "Delegate", "Media", "Speaker"
    background_image_path: str  # Local path in app/static/badge_templates/
    layout_config: Dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    width_inches: float = Field(default=4.0)
    height_inches: float = Field(default=6.0)
    dpi: int = Field(default=300)

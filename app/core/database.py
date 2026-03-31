from typing import Generator
from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings

# Supabase direct postgres connection URL
engine = create_engine(
    settings.database_url,
    echo=True if settings.environment == "development" else False,
    pool_pre_ping=True
)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)

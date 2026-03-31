from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.core.database import init_db
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        print("Database tables verified.")
    except Exception as e:
        print(f"Warning: Could not connect to DB on startup: {e}")
    yield


from app.api import participants, events, templates, badges, attendance, views

app = FastAPI(
    title="EventPilot — Event Registration & Attendance",
    description="Backend API for managing events, participants, badges, and attendance.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware for mobile app support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend / Dashboard views (mounted first so "/" works)
app.include_router(views.router)

# API routes
app.include_router(events.router)
app.include_router(participants.router)
app.include_router(templates.router)
app.include_router(badges.router)
app.include_router(attendance.router)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

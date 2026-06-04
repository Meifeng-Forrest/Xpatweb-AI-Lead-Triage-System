from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.leads import router as leads_router
from app.config import get_settings
from app.database import lifespan
from app.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.settings = settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(leads_router)
app.include_router(extraction_router)

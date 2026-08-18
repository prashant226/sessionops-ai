import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import get_settings
from .db import Base, SessionLocal, engine
from .routers import auth, exceptions, google_auth, insights, overview, schedule, search, smes, sync
from .services.rsvp_poller import rsvp_polling_loop
from .services.seed import seed_source_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    db = SessionLocal()
    try:
        has_smes = db.query(models.Sme).first() is not None
        # Only auto-seed the bundled mock fixtures in mock mode -- in live
        # mode an empty database should stay empty until Ops explicitly
        # clicks Sync Data to pull the real Google Sheet.
        if not has_smes and not settings.is_live:
            seed_source_data(db)
    finally:
        db.close()

    poll_task = asyncio.create_task(rsvp_polling_loop()) if settings.is_live else None
    yield
    if poll_task:
        poll_task.cancel()


app = FastAPI(title="SessionOps AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(google_auth.router)
app.include_router(sync.router)
app.include_router(overview.router)
app.include_router(schedule.router)
app.include_router(exceptions.router)
app.include_router(insights.router)
app.include_router(smes.router)
app.include_router(search.router)


@app.get("/health")
def health():
    return {"status": "ok"}

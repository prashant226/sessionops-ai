from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .db import Base, SessionLocal, engine
from .routers import auth, exceptions, insights, overview, schedule, search, smes, sync
from .services.seed import seed_source_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        has_smes = db.query(models.Sme).first() is not None
        if not has_smes:
            seed_source_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="SessionOps AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
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

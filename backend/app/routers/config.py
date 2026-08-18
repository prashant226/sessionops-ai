from fastapi import APIRouter

from .. import schemas
from ..config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/demo", response_model=schemas.DemoConfigOut)
def demo_config():
    settings = get_settings()
    return schemas.DemoConfigOut(
        demo_mode=settings.demo_mode,
        demo_calendar_email=settings.demo_calendar_email or None,
    )

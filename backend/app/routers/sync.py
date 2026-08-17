from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..services.sheets_adapter import sync_from_sheets

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("")
def sync(db: DbSession = Depends(get_db)):
    result = sync_from_sheets(db)
    return {"status": "ok", **result}

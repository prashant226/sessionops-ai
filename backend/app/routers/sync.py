from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..services.sheets_adapter import sync_from_sheets

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("")
def sync(db: DbSession = Depends(get_db)):
    try:
        result = sync_from_sheets(db)
    except RuntimeError as exc:
        # Surface expected setup issues (e.g. Google not connected yet) as a
        # clean 400 with the real message, instead of a generic 500 that
        # makes the frontend show "could not reach the server".
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", **result}

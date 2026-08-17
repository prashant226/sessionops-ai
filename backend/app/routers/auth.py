from fastapi import APIRouter, HTTPException

from .. import schemas
from ..config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest):
    settings = get_settings()
    if payload.ops_id != settings.demo_ops_id or payload.password != settings.demo_ops_password:
        raise HTTPException(status_code=401, detail="Invalid Ops ID or password.")
    return schemas.LoginResponse(token="demo-session-token", ops_name="Ops Team")

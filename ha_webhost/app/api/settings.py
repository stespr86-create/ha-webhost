from fastapi import APIRouter
from pydantic import BaseModel

from core import settings as settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    public_base_url: str | None = None


@router.get("")
def get_settings():
    return {"public_base_url": settings_store.get_public_base_url()}


@router.put("")
def update_settings(payload: SettingsPayload):
    settings_store.set_public_base_url(payload.public_base_url)
    return {"public_base_url": settings_store.get_public_base_url()}

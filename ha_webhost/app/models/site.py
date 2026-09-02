from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class SourceType(str, Enum):
    upload = "upload"
    git = "git"


class SiteStatus(str, Enum):
    active = "active"
    deploying = "deploying"
    failed = "failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Site(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    source_type: SourceType
    git_url: Optional[str] = None
    git_branch: str = "main"
    git_token: Optional[str] = None
    status: SiteStatus = SiteStatus.active
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_deploy_at: Optional[datetime] = None
    last_error: Optional[str] = None

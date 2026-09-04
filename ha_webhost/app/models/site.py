from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class SourceType(str, Enum):
    upload = "upload"
    git = "git"
    gallery = "gallery"
    wordpress = "wordpress"
    php = "php"
    python = "python"


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
    gallery_link_url: Optional[str] = None
    gallery_link_label: Optional[str] = None
    wordpress_db_name: Optional[str] = None
    wordpress_db_user: Optional[str] = None
    wordpress_db_password: Optional[str] = None
    wordpress_admin_user: Optional[str] = None
    wordpress_admin_password: Optional[str] = None
    wordpress_admin_email: Optional[str] = None
    wordpress_blog_name: Optional[str] = None
    status: SiteStatus = SiteStatus.active
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_deploy_at: Optional[datetime] = None
    last_error: Optional[str] = None


class SitePublic(SQLModel):
    """API-Response-Form von Site - lässt git_token und wordpress_db_password bewusst weg.

    Geheime Werte (Token, Passwörter) dürfen niemals über die API zurückgegeben werden, auch
    nicht an den authentifizierten Admin selbst: sie werden einmalig beim
    Anlegen eingegeben und danach nur noch intern verwendet.
    """

    id: Optional[int] = None
    name: str
    source_type: SourceType
    git_url: Optional[str] = None
    git_branch: str = "main"
    gallery_link_url: Optional[str] = None
    gallery_link_label: Optional[str] = None
    wordpress_db_name: Optional[str] = None
    wordpress_db_user: Optional[str] = None
    wordpress_admin_user: Optional[str] = None
    wordpress_admin_email: Optional[str] = None
    wordpress_blog_name: Optional[str] = None
    status: SiteStatus = SiteStatus.active
    created_at: datetime
    updated_at: datetime
    last_deploy_at: Optional[datetime] = None
    last_error: Optional[str] = None

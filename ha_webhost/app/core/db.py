from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from core.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

# SQLModel.metadata.create_all() legt nur fehlende TABELLEN an, aendert aber
# keine bestehenden - neue, optionale Spalten muessen daher per einfacher
# Mini-Migration nachgezogen werden, damit ein Update auf einer bereits
# laufenden Instanz (mit vorhandenen Sites in der DB) nicht bricht.
_NEW_SITE_COLUMNS = {
    "gallery_link_url": "VARCHAR",
    "gallery_link_label": "VARCHAR",
    "wordpress_db_name": "VARCHAR",
    "wordpress_db_user": "VARCHAR",
    "wordpress_db_password": "VARCHAR",
    "wordpress_admin_user": "VARCHAR",
    "wordpress_admin_password": "VARCHAR",
    "wordpress_admin_email": "VARCHAR",
    "wordpress_blog_name": "VARCHAR",
}


def _run_migrations() -> None:
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(site)"))}
        for column, sql_type in _NEW_SITE_COLUMNS.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE site ADD COLUMN {column} {sql_type}"))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session():
    with Session(engine) as session:
        yield session

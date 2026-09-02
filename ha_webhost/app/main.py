import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import files, sites
from core.db import get_session, init_db
from services import site_service

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Caddyfile bei jedem Start neu aus dem DB-Stand generieren, damit sie
    # nie gegenueber der Datenbank veraltet (z.B. nach Konfig-Aenderungen
    # an der Caddy-Vorlage oder falls die Datei manuell entfernt wurde).
    session = next(get_session())
    try:
        site_service.sync_proxy(session)
    finally:
        session.close()
    yield


app = FastAPI(title="HA WebHost", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(files.router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

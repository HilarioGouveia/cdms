"""API configurável com identidade central e bancos operacionais por workspace."""
from contextlib import asynccontextmanager
from pathlib import Path
import os
import secrets
import sqlite3

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cdms.adapters.api.routers import auth, growth, workspaces, rituals, automation
from cgs.adapters.api.routers import growth_phase2, growth_phase3
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.config.security import get_password_hash, get_secret_key
from cdms.config.settings import settings


def create_app(*, identity_db_path=None, workspace_data_dir=None, secret_key=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.secret_key = get_secret_key(secret_key)
        app.state.identity = SQLiteIdentityRepository(Path(identity_db_path or settings.DATA_DIR / "identity.db"))
        app.state.workspace_data_dir = Path(workspace_data_dir or settings.DATA_DIR / "workspaces")
        app.state.dummy_password_hash = get_password_hash(secrets.token_urlsafe(32))
        yield

    app = FastAPI(title="CDMS Workspace API", version="2.4.0", lifespan=lifespan)
    origins = [value.strip() for value in os.getenv("CDMS_CORS_ORIGINS", "").split(",") if value.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                           allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    for router in (auth.router, workspaces.router, growth.router, rituals.router,
                   automation.router, growth_phase2.router, growth_phase3.router):
        app.include_router(router, prefix="/api/v1")

    @app.exception_handler(ValueError)
    async def invalid_input(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflict(request: Request, exc: sqlite3.IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "A operação conflita com um registro existente."})

    @app.get("/health")
    def health_check():
        return {"status": "ok", "version": "2.4.0", "multi_tenant": True}

    return app


app = create_app()

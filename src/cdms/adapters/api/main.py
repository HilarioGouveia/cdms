"""Ponto de entrada da aplicação FastAPI do CDMS (Fase 2)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cdms.adapters.api.routers import auth, growth

app = FastAPI(
    title="Creator Data Marketing System (CDMS) API",
    version="2.4.0",
    description="API REST Multi-Tenant para Rituais de Governança e Experimentação (CGS).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(growth.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.4.0", "multi_tenant": True}
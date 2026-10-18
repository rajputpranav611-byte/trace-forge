from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.client import db_client
from app.api.routes import health, graph, investigation, surgery, debt, recovery, memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt lazy or pre-flight DB connect on startup
    try:
        db_client.connect()
    except Exception as exc:
        # Don't crash container on startup if DB is still booting
        print(f"[Lifespan] Warning: Initial FalkorDB connection failed: {exc}")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TraceForge Backend",
        description="Trace intelligence and root cause investigation engine powered by FalkorDB",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Enable CORS for frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(investigation.router, prefix="/api/v1")
    app.include_router(surgery.router, prefix="/api/v1")
    app.include_router(debt.router, prefix="/api/v1")
    app.include_router(recovery.router, prefix="/api/v1")
    app.include_router(memory.router, prefix="/api/v1")

    return app


app = create_app()

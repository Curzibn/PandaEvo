from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import engine
from app.logger import setup_logging
from app.mcp import initialize_mcp_servers, shutdown_mcp_servers
from app.repo_sync import startup_sync_repositories
from app.routers.fs import router as fs_router
from app.routers.mcp import router as mcp_router
from app.routers.providers import router as providers_router
from app.routers.purposes import router as purposes_router
from app.routers.reload import router as reload_router
from app.routers.sessions import router as sessions_router
from app.routers.skills import router as skills_router
from app.sandbox import sandbox_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    
    from app.db.migration import run_migrations
    await run_migrations()
    
    await initialize_mcp_servers()
    await startup_sync_repositories()
    try:
        yield
    finally:
        await shutdown_mcp_servers()
        await sandbox_manager.shutdown()
        await engine.dispose()


app = FastAPI(title="PandaEvo Python Service", lifespan=lifespan)

app.include_router(providers_router)
app.include_router(purposes_router)
app.include_router(sessions_router)
app.include_router(fs_router)
app.include_router(mcp_router)
app.include_router(skills_router)
app.include_router(reload_router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})

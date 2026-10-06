from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.seed import init_db
from app.services.redis_state import close_redis
from app.telemetry.otel import setup_otel

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("startup", env=settings.app_env, agent_mode=settings.agent_mode)
    try:
        await init_db()
    except Exception as exc:
        logger.warning("db_init_deferred", error=str(exc))
    yield
    await close_redis()
    logger.info("shutdown")


app = FastAPI(
    title="OpsPilot API",
    description=(
        "AI SRE Incident Commander — diagnose incidents from telemetry + runbooks, "
        "rank evidence-backed root causes, and gate remediation behind human approval."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_otel(app)
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/v1/health",
        "proof": (
            "This agent can diagnose a synthetic production incident using telemetry "
            "and cannot execute remediation without approval."
        ),
    }

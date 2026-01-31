import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.domain import models  # noqa: F401 - Import models to register with Base
from app.routers import auth, geo, observability, preference, travel_planning, unified_chat

# ログレベル設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Travel AI Agent",
    description="体験型旅行企画マルチエージェントシステム",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)  # 認証
app.include_router(unified_chat.router, prefix="/api")  # 統合チャット（新）
app.include_router(preference.router, prefix="/api")
app.include_router(travel_planning.router, prefix="/api")
app.include_router(geo.router)  # ジオコーディング・ルーティング
app.include_router(observability.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

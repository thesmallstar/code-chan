import os
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chunks, github, re_reviews, reviews, threads

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = Config(ALEMBIC_INI)
    command.upgrade(alembic_cfg, "head")
    yield


app = FastAPI(title="code-chan API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{os.getenv('FRONTEND_PORT', '3000')}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github.router)
app.include_router(reviews.router)
app.include_router(re_reviews.router)
app.include_router(chunks.router)
app.include_router(threads.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/providers")
def list_providers():
    from app.ai import ProviderRegistry
    return ProviderRegistry.available()

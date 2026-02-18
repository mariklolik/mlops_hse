from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import models, versions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Model Registry", lifespan=lifespan)
app.include_router(models.router)
app.include_router(versions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

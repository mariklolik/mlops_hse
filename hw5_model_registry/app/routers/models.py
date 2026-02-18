from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Model
from app.schemas import ModelCreate, ModelResponse

router = APIRouter(prefix="/api/models", tags=["models"])


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(data: ModelCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Model).where(Model.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Model '{data.name}' already exists")
    model = Model(name=data.name, description=data.description, team=data.team)
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("", response_model=list[ModelResponse])
async def list_models(team: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Model)
    if team:
        q = q.where(Model.team == team)
    result = await db.execute(q.order_by(Model.created_at.desc()))
    return result.scalars().all()


@router.get("/{name}", response_model=ModelResponse)
async def get_model(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).where(Model.name == name))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, f"Model '{name}' not found")
    return model


@router.delete("/{name}", status_code=204)
async def delete_model(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).where(Model.name == name))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, f"Model '{name}' not found")
    await db.delete(model)
    await db.commit()

import json
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Model, ModelVersion
from app.schemas import ModelVersionResponse, StageUpdate

STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")
STAGE_ORDER = ["none", "staging", "production", "archived"]

router = APIRouter(prefix="/api/models/{name}/versions", tags=["versions"])


async def _get_model(name: str, db: AsyncSession) -> Model:
    result = await db.execute(select(Model).where(Model.name == name))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, f"Model '{name}' not found")
    return model


def _safe_filename(filename: str) -> str:
    return os.path.basename(filename).lstrip(".")


@router.post("", response_model=ModelVersionResponse, status_code=201)
async def create_version(
    name: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    metrics: str = Form("{}"),
    params: str = Form("{}"),
    tags: str = Form("{}"),
    db: AsyncSession = Depends(get_db),
):
    model = await _get_model(name, db)

    try:
        parsed_metrics = json.loads(metrics)
        parsed_params = json.loads(params)
        parsed_tags = json.loads(tags)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    result = await db.execute(
        select(func.coalesce(func.max(ModelVersion.version), 0))
        .where(ModelVersion.model_id == model.id)
    )
    next_version = result.scalar() + 1

    safe_name = _safe_filename(file.filename or "model.bin")
    model_dir = os.path.join(STORAGE_DIR, name, str(next_version))
    os.makedirs(model_dir, exist_ok=True)
    file_path = os.path.join(model_dir, safe_name)

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_size = os.path.getsize(file_path)

        version = ModelVersion(
            model_id=model.id,
            version=next_version,
            description=description,
            file_path=file_path,
            file_size=file_size,
            metrics=parsed_metrics,
            params=parsed_params,
            tags=parsed_tags,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
    except Exception:
        if os.path.isdir(model_dir):
            shutil.rmtree(model_dir)
        raise

    return version


@router.get("", response_model=list[ModelVersionResponse])
async def list_versions(name: str, db: AsyncSession = Depends(get_db)):
    model = await _get_model(name, db)
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model.id)
        .order_by(ModelVersion.version.desc())
    )
    return result.scalars().all()


@router.get("/{version}", response_model=ModelVersionResponse)
async def get_version(name: str, version: int, db: AsyncSession = Depends(get_db)):
    model = await _get_model(name, db)
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model.id, ModelVersion.version == version)
    )
    ver = result.scalar_one_or_none()
    if not ver:
        raise HTTPException(404, f"Version {version} not found")
    return ver


@router.patch("/{version}/stage", response_model=ModelVersionResponse)
async def update_stage(
    name: str, version: int, data: StageUpdate, db: AsyncSession = Depends(get_db)
):
    model = await _get_model(name, db)
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model.id, ModelVersion.version == version)
    )
    ver = result.scalar_one_or_none()
    if not ver:
        raise HTTPException(404, f"Version {version} not found")

    current_idx = STAGE_ORDER.index(ver.stage)
    target_idx = STAGE_ORDER.index(data.stage)
    if target_idx < current_idx:
        raise HTTPException(400, f"Cannot transition from '{ver.stage}' to '{data.stage}'")

    ver.stage = data.stage
    await db.commit()
    await db.refresh(ver)
    return ver


@router.get("/{version}/download")
async def download_version(name: str, version: int, db: AsyncSession = Depends(get_db)):
    model = await _get_model(name, db)
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model.id, ModelVersion.version == version)
    )
    ver = result.scalar_one_or_none()
    if not ver:
        raise HTTPException(404, f"Version {version} not found")
    if not os.path.exists(ver.file_path):
        raise HTTPException(404, "Artifact file not found")
    return FileResponse(ver.file_path, filename=os.path.basename(ver.file_path))

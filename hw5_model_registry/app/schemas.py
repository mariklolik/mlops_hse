from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ModelCreate(BaseModel):
    name: str
    description: str = ""
    team: str


class ModelResponse(BaseModel):
    id: int
    name: str
    description: str
    team: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelVersionResponse(BaseModel):
    id: int
    model_id: int
    version: int
    description: str
    stage: str
    file_path: str
    file_size: int
    metrics: dict
    params: dict
    tags: dict
    created_at: datetime

    class Config:
        from_attributes = True


class StageUpdate(BaseModel):
    stage: Literal["none", "staging", "production", "archived"]

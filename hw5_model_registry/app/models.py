from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    team = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_version"),
        Index("idx_versions_stage", "stage"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text, default="")
    stage = Column(String(50), default="none")
    file_path = Column(String(512), nullable=False)
    file_size = Column(BigInteger, default=0)
    metrics = Column(JSON, default=dict)
    params = Column(JSON, default=dict)
    tags = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("Model", back_populates="versions")

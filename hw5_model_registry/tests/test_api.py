import io

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_model(client):
    resp = await client.post("/api/models", json={
        "name": "test_model",
        "description": "test",
        "team": "team1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_model"
    assert data["team"] == "team1"


@pytest.mark.asyncio
async def test_list_models(client):
    await client.post("/api/models", json={"name": "m1", "team": "t1"})
    await client.post("/api/models", json={"name": "m2", "team": "t2"})
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_create_version(client):
    await client.post("/api/models", json={"name": "vmodel", "team": "t1"})
    resp = await client.post(
        "/api/models/vmodel/versions",
        files={"file": ("model.pkl", io.BytesIO(b"fake model data"), "application/octet-stream")},
        data={"description": "v1", "metrics": '{"acc": 0.9}', "params": '{"lr": 0.01}'},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["metrics"]["acc"] == 0.9


@pytest.mark.asyncio
async def test_stage_transition(client):
    await client.post("/api/models", json={"name": "smodel", "team": "t1"})
    await client.post(
        "/api/models/smodel/versions",
        files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
    )
    resp = await client.patch(
        "/api/models/smodel/versions/1/stage",
        json={"stage": "staging"},
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "staging"


@pytest.mark.asyncio
async def test_model_not_found(client):
    resp = await client.get("/api/models/nonexistent")
    assert resp.status_code == 404

import io

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
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
async def test_create_duplicate_model(client):
    await client.post("/api/models", json={"name": "dup", "team": "t1"})
    resp = await client.post("/api/models", json={"name": "dup", "team": "t1"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_models(client):
    await client.post("/api/models", json={"name": "m1", "team": "t1"})
    await client.post("/api/models", json={"name": "m2", "team": "t2"})
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_models_filter_team(client):
    await client.post("/api/models", json={"name": "a1", "team": "alpha"})
    await client.post("/api/models", json={"name": "b1", "team": "beta"})
    resp = await client.get("/api/models", params={"team": "alpha"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["team"] == "alpha"


@pytest.mark.asyncio
async def test_list_models_filter_name(client):
    await client.post("/api/models", json={"name": "fraud_detector", "team": "t1"})
    await client.post("/api/models", json={"name": "spam_filter", "team": "t1"})
    resp = await client.get("/api/models", params={"name": "fraud"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "fraud_detector"


@pytest.mark.asyncio
async def test_get_model(client):
    await client.post("/api/models", json={"name": "gm", "team": "t1"})
    resp = await client.get("/api/models/gm")
    assert resp.status_code == 200
    assert resp.json()["name"] == "gm"


@pytest.mark.asyncio
async def test_model_not_found(client):
    resp = await client.get("/api/models/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_model(client):
    await client.post("/api/models", json={"name": "del_me", "team": "t1"})
    resp = await client.delete("/api/models/del_me")
    assert resp.status_code == 204
    resp = await client.get("/api/models/del_me")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_model(client):
    resp = await client.delete("/api/models/nope")
    assert resp.status_code == 404


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
async def test_create_version_bad_json(client):
    await client.post("/api/models", json={"name": "bjm", "team": "t1"})
    resp = await client.post(
        "/api/models/bjm/versions",
        files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
        data={"metrics": "not json"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_versions(client):
    await client.post("/api/models", json={"name": "lv", "team": "t1"})
    for _ in range(3):
        await client.post(
            "/api/models/lv/versions",
            files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
        )
    resp = await client.get("/api/models/lv/versions")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_get_version(client):
    await client.post("/api/models", json={"name": "gv", "team": "t1"})
    await client.post(
        "/api/models/gv/versions",
        files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
    )
    resp = await client.get("/api/models/gv/versions/1")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


@pytest.mark.asyncio
async def test_version_not_found(client):
    await client.post("/api/models", json={"name": "vnf", "team": "t1"})
    resp = await client.get("/api/models/vnf/versions/999")
    assert resp.status_code == 404


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
async def test_stage_transition_invalid_order(client):
    await client.post("/api/models", json={"name": "stio", "team": "t1"})
    await client.post(
        "/api/models/stio/versions",
        files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
    )
    await client.patch("/api/models/stio/versions/1/stage", json={"stage": "production"})
    resp = await client.patch(
        "/api/models/stio/versions/1/stage",
        json={"stage": "staging"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stage_invalid_value(client):
    await client.post("/api/models", json={"name": "siv", "team": "t1"})
    await client.post(
        "/api/models/siv/versions",
        files={"file": ("m.pkl", io.BytesIO(b"data"), "application/octet-stream")},
    )
    resp = await client.patch(
        "/api/models/siv/versions/1/stage",
        json={"stage": "garbage"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_download_version(client):
    await client.post("/api/models", json={"name": "dl", "team": "t1"})
    await client.post(
        "/api/models/dl/versions",
        files={"file": ("m.pkl", io.BytesIO(b"model bytes"), "application/octet-stream")},
    )
    resp = await client.get("/api/models/dl/versions/1/download")
    assert resp.status_code == 200
    assert resp.content == b"model bytes"

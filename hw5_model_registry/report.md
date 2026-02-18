# Model Registry: Design and Implementation

## 1. Problem Analysis

Current state: ML teams dump models into a shared directory with no structure.

```
models/
models/mlds_1/my_model_v1/
models/mlds_3/sft_modell_v_123/
models/mlds_180/model_v1_v0_with_rank_dataset_0/
...
```

**Problems identified**:

1. **No metadata** - no information about what each model does, who trained it, when, with what data or params.
2. **No versioning** - naming is inconsistent (`v1`, `v_123`, `v1_v0`), no way to track model lineage.
3. **No status tracking** - unclear which models are in production, staging, or deprecated.
4. **No access control** - any team can overwrite another team's models.
5. **No search/discovery** - finding the right model requires knowing the exact path.
6. **No reproducibility** - no link between model artifacts and training code/data/params.
7. **Naming chaos** - no naming convention (`my_model_v1` vs `sft_modell_v_123` vs `model_v1_v0_with_rank_dataset_0`).

---

## 2. Requirements

### Functional Requirements

- **FR1**: Register a new model with name, description, owner (team).
- **FR2**: Upload model versions (files) linked to a registered model.
- **FR3**: Attach metadata to each version: training params, metrics, dataset info, tags.
- **FR4**: Transition model versions through stages: `none` -> `staging` -> `production` -> `archived`.
- **FR5**: List and search models by name, team, tags.
- **FR6**: Download model artifacts by model name and version/stage.
- **FR7**: View version history for any model.

### Non-Functional Requirements

- **NFR1**: API response time < 200ms for metadata operations.
- **NFR2**: Support model files up to 5 GB.
- **NFR3**: Data integrity - no partial uploads, atomic version creation.
- **NFR4**: Simple deployment - single binary/container, minimal dependencies.

---

## 3. Architecture

```
+------------------+         +-----------------+        +----------------+
|   CLI / Client   | ------> |   FastAPI App    | -----> |     SQLite     |
+------------------+  HTTP   |   (REST API)     |        |   (metadata)   |
                             +-----------------+        +----------------+
                                    |
                                    v
                             +-----------------+
                             |   File Storage  |
                             |   (local disk)  |
                             +-----------------+
```

**Components**:

- **FastAPI App** - REST API server. Chosen for async support, auto-generated OpenAPI docs, and Python ecosystem compatibility.
- **SQLite** - Embedded DB for model metadata, versions, tags. Chosen for zero-config deployment and sufficient performance at this scale. Can be swapped with PostgreSQL later.
- **File Storage** - Local disk for model artifacts. Simple and sufficient for the scale. Can be swapped with S3-compatible storage later.

**Technology choices**:

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| API framework | FastAPI | Async, auto-docs, Pydantic validation |
| Database | SQLite (aiosqlite) | Zero-config, embedded, sufficient for MVP |
| ORM | SQLAlchemy | Mature, async support |
| File storage | Local FS | Simple, sufficient for MVP |

---

## 4. API Design

### Models

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/models` | Register new model |
| GET | `/api/models` | List models (filter by team, name) |
| GET | `/api/models/{name}` | Get model details |
| DELETE | `/api/models/{name}` | Delete model and all versions |

### Versions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/models/{name}/versions` | Create new version (multipart upload) |
| GET | `/api/models/{name}/versions` | List versions |
| GET | `/api/models/{name}/versions/{version}` | Get version details |
| PATCH | `/api/models/{name}/versions/{version}/stage` | Transition stage |
| GET | `/api/models/{name}/versions/{version}/download` | Download artifact |

### Request/Response Examples

**Register model:**
```json
POST /api/models
{
    "name": "fraud_detector",
    "description": "Fraud detection model for payments",
    "team": "mlds_1"
}
```

**Create version:**
```
POST /api/models/fraud_detector/versions
Content-Type: multipart/form-data

file: <model_file>
description: "Trained on 2024-01 data"
metrics: {"roc_auc": 0.95, "f1": 0.87}
params: {"n_estimators": 200, "max_depth": 5}
```

**Transition stage:**
```json
PATCH /api/models/fraud_detector/versions/1/stage
{
    "stage": "production"
}
```

---

## 5. Database Schema

```sql
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    team VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER REFERENCES models(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    description TEXT DEFAULT '',
    stage VARCHAR(50) DEFAULT 'none',
    file_path VARCHAR(512) NOT NULL,
    file_size BIGINT DEFAULT 0,
    metrics JSON DEFAULT '{}',
    params JSON DEFAULT '{}',
    tags JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, version)
);

CREATE INDEX idx_versions_model_id ON model_versions(model_id);
CREATE INDEX idx_versions_stage ON model_versions(stage);
CREATE INDEX idx_models_team ON models(team);
```

Stage transitions: `none` -> `staging` -> `production` -> `archived`.

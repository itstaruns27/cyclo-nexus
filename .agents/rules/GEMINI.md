# CYCLO-NEXUS Agent Guardrails
# ════════════════════════════
# These rules are loaded by Antigravity for all agents working in this repo.
# They supplement AI_AGENT_SKILLS_DIRECTIVE.md with collision-prevention rules.

## Rule 1: Schema-First Development
Every agent MUST import types from `schemas/` or `frontend/src/types/` before
writing any implementation code that produces or consumes cyclone data.
Hallucinating ad-hoc interfaces is a fatal violation.

## Rule 2: No Cross-Boundary Writes
An agent may only create or modify files within its designated directories.
Reading from `schemas/`, `fixtures/`, and `docs/` is universally permitted.

- **Agent ALPHA**: `data_pipeline/`, `colab_notebooks/01*`
- **Agent BRAVO**: `vision/`, `colab_notebooks/02*`, `colab_notebooks/03*`
- **Agent CHARLIE**: `forecaster/`, `colab_notebooks/04*`, `colab_notebooks/05*`, `colab_notebooks/06*`
- **Agent DELTA**: `backend/`
- **Agent ECHO**: `frontend/`

## Rule 3: Additive-Only Database Changes
No `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, or destructive DDL.
New columns must use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ... NULL`.

## Rule 4: Dependency Quarantine
- Python: New pip packages only in the agent's own `requirements.txt`.
- Node.js: New npm packages require PR justification.
- **Prohibited on Hostinger backend**: torch, tensorflow, rasterio, h5py, gdal, opencv-python, ultralytics.

## Rule 5: No Shared Mutable State
Inter-agent communication flows exclusively through:
1. Webhook HTTP payloads (Colab → Hostinger)
2. MySQL database (Hostinger ↔ Frontend)
3. REST API responses (Frontend ← Hostinger)

## Rule 6: RFC Process for Schema Changes
To modify any file in `schemas/`:
1. Open an issue titled `RFC: [description]`
2. Document backward-compatibility impact
3. All consuming agents must acknowledge
4. Only the ARCHITECT merges schema changes

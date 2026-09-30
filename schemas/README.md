# CYCLO-NEXUS Shared Schemas

> **Owner:** ARCHITECT (locked after initial commit)  
> **Access:** ALL AGENTS — Read-Only

## Contents

| File | Format | Purpose |
|------|--------|---------|
| `telemetry_contract.py` | Pydantic v2 | Python source of truth for all cyclone data models |
| `geojson_spec.json` | JSON Schema (Draft-07) | RFC 7946 GeoJSON payload schema |
| `imd_scale.py` | Python module | Canonical IMD 7-tier enum, wind ranges, alert thresholds |
| `api_webhook_contract.md` | Markdown | HTTP webhook authentication and payload spec |

## Versioning Policy

1. All schemas use semantic versioning (`MAJOR.MINOR.PATCH`).
2. **PATCH**: Documentation fixes, comment changes — no agent impact.
3. **MINOR**: Additive fields with defaults — backward compatible.
4. **MAJOR**: Breaking changes (field removal, type change) — requires full RFC.

## Schema Modification RFC Process

1. Open an issue: `RFC: [description of proposed change]`
2. Document backward-compatibility impact.
3. All consuming agents must acknowledge the change.
4. Only the ARCHITECT merges schema changes to `main`.

## ⚠️ Inviolable Rule

**No agent may modify these files without completing the RFC process.**  
Agents must `import` / `require` types from this directory before writing any implementation code.

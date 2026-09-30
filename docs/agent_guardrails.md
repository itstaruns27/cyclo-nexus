# CYCLO-NEXUS Agent Guardrails

> See [.agents/rules/GEMINI.md](../.agents/rules/GEMINI.md) for the machine-readable version.
> See [AI_AGENT_SKILLS_DIRECTIVE.md](../AI_AGENT_SKILLS_DIRECTIVE.md) for the full skills constitution.

## Summary

1. **Schema-First**: Import types from `schemas/` before writing implementation.
2. **No Cross-Boundary Writes**: Only modify files in your designated directory.
3. **Additive-Only DB**: No DROP/TRUNCATE — use `ADD COLUMN IF NOT EXISTS`.
4. **Dependency Quarantine**: No shared requirements; Hostinger never gets PyTorch.
5. **No Shared Mutable State**: Communicate only via webhooks, MySQL, and REST API.
6. **RFC for Schema Changes**: File an issue, get all agents to acknowledge, ARCHITECT merges.

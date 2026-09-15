# Update deterministic modules

Low-level logic belongs in `adws/adw_modules/`; ADW scripts only sequence
phases and decide acceptance. The Copilot adapter owns SDK startup, runtime
preflight, create/resume, event subscription, capability permission handling,
idle completion, abort, cleanup, and runtime metadata. The orchestrator owns
the authoritative post-send repository write-policy check.

Keep the host-side contract:

- typed `AgentRequest`, `AgentCallbacks`, `AgentEvent`, and `AgentResult`;
- Pydantic envelope parsing and bounded same-session corrections;
- changed-path snapshot and rollback enforcement;
- centrally sanitized normalized events plus raw JSONL retention;
- SDK/runtime/CLI version metadata.

Run focused tests and lint after a change:

```bash
uv run pytest -q
uv run ruff check skills/sssf/templates/adws/adw_modules
```

Do not depend on private SDK process fields or invent a fallback CLI execution
path. Refresh the official [Python SDK
README](https://github.com/github/copilot-sdk/blob/main/python/README.md) when
public lifecycle behavior changes.

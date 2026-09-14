# Copilot-Native Software Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Pi worker harness with the official Python GitHub Copilot SDK while preserving SSSF's deterministic ADWs, typed handoffs, gates, write enforcement, traces, and acceptance semantics.

**Architecture:** Keep `agents.execute()` as the orchestration seam and place all Copilot lifecycle behavior behind a deep `agent_copilot.run(AgentRequest, AgentCallbacks) -> AgentResult` module. Move the distributable skill to a Copilot-first Agent Plugins 1.0 layout, add grounded `ai_docs/`, and verify the port through fake-SDK tests plus an opt-in authenticated smoke test.

**Tech Stack:** Python 3.11+, `uv`, `github-copilot-sdk==1.0.13`, Pydantic 2, PyYAML, pytest, pytest-asyncio, Ruff, Pyright, SQLite, Lychee, Just, GitHub Actions, Vue/Bun visualizer.

**Spec:** `docs/superpowers/specs/2026-09-14-copilot-software-factory-design.md`

## Global Constraints

- The runtime is Copilot-only; production code, config, and docs must not retain Pi or Claude Code harness paths.
- Pin `github-copilot-sdk==1.0.13` and use its bundled protocol-version-3 runtime until a separately reviewed compatibility update changes the pin.
- Use Python 3.11 or later.
- Preserve ADW phase chains, typed `EnvelopeBase` outputs, same-session corrections, gates, `writes` enforcement, SQLite table compatibility, and `run.finish(accepted=...)`.
- Use `mode="empty"`, caller-provided session IDs, explicit tool availability, explicit permission handling, and `session.abort()` after a phase deadline.
- Treat Copilot permissions and hooks as defense in depth; `permissions.enforce()` remains the repository write boundary.
- Keep credential-free tests deterministic. The authenticated smoke test is opt-in.
- Use primary sources in `ai_docs/`; every material claim has an adjacent official URL and `verified_on: 2026-09-14`.
- Do not stage or overwrite the unrelated `.gitignore` addition for `.aif-skills/`.
- Every implementation commit includes `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

---

## File Structure

The migration locks in these responsibilities:

```text
plugin.json
skills/sssf/
  SKILL.md                         # portable Agent Skill router and factory rules
  scripts/                         # installer/config/ADW generators
  references/                      # deep operational contracts
  cookbooks/                       # request-specific procedures
  templates/
    adws/adw_modules/
      agent_copilot.py             # SDK lifecycle, timeout, abort, resume, cleanup
      copilot_events.py            # pure Copilot event normalization and tool folding
      agents.py                    # prompts, typed corrections, gates, permissions, handoff
      data_types.py                # config and runtime interface models
      tracer.py                    # stable SQLite/JSONL persistence
    adws/adw_*.py                  # thin PEP 723 entry points with pinned SDK dependency
    sssf.config.yaml               # Copilot-native roster
    env.sample                     # Copilot authentication/runtime overrides
    justfile                       # generated repo run/observe/verify commands
  apps/visualizer/                 # adapter-neutral trace UI
ai_docs/                           # concise primary-source grounding
scripts/
  copilot_smoke.py                 # opt-in real-runtime verification
tests/
  conftest.py                      # template import path and common fixtures
  fakes/copilot_sdk.py             # deterministic fake client/session/events
  test_plugin_layout.py
  test_config.py
  test_copilot_events.py
  test_agent_copilot.py
  test_agents.py
  test_tracer.py
  test_install.py
  test_no_pi_runtime.py
pyproject.toml                     # repository development/test dependencies and tool config
uv.lock                            # reproducible development environment
justfile                           # repository verification feedback loop
lychee.toml                        # URL checker configuration
.github/workflows/verify.yml       # credential-free CI
```

---

### Task 1: Grounded AI Documentation and URL Feedback Loop

**Files:**
- Create: `ai_docs/README.md`
- Create: `ai_docs/software-factory.md`
- Create: `ai_docs/copilot-cli.md`
- Create: `ai_docs/copilot-python-sdk.md`
- Create: `ai_docs/copilot-sessions-events.md`
- Create: `ai_docs/copilot-tools-hooks-permissions.md`
- Create: `ai_docs/copilot-agents-skills-plugins-mcp.md`
- Create: `ai_docs/pi-capability-baseline.md`
- Create: `ai_docs/pi-to-copilot-migration-matrix.md`
- Create: `ai_docs/sssf-architecture.md`
- Create: `ai_docs/verification-playbook.md`
- Create: `lychee.toml`
- Create: `justfile`

**Interfaces:**
- Consumes: Approved design facts and primary-source URLs from the spec.
- Produces: `just docs-check`, a routed documentation corpus, and a source-of-truth migration matrix used by all later tasks.

- [ ] **Step 1: Write the documentation routing index**

Create `ai_docs/README.md` with this shape:

```markdown
# SSSF AI Documentation

verified_on: 2026-09-14

Read only the page needed for the current branch:

| Need | Read |
|---|---|
| Why this is a software factory | [software-factory.md](software-factory.md) |
| Copilot CLI commands and diagnostics | [copilot-cli.md](copilot-cli.md) |
| Python SDK lifecycle | [copilot-python-sdk.md](copilot-python-sdk.md) |
| Resume, events, idle, timeout, and abort | [copilot-sessions-events.md](copilot-sessions-events.md) |
| Tools, hooks, permissions, and containment | [copilot-tools-hooks-permissions.md](copilot-tools-hooks-permissions.md) |
| Agents, skills, plugins, and MCP | [copilot-agents-skills-plugins-mcp.md](copilot-agents-skills-plugins-mcp.md) |
| What Pi provided | [pi-capability-baseline.md](pi-capability-baseline.md) |
| Port decisions | [pi-to-copilot-migration-matrix.md](pi-to-copilot-migration-matrix.md) |
| Existing SSSF seams | [sssf-architecture.md](sssf-architecture.md) |
| Before/after verification | [verification-playbook.md](verification-playbook.md) |
```

- [ ] **Step 2: Write each distilled reference**

Each file begins with:

```markdown
# Page-specific title

verified_on: 2026-09-14
scope: A single sentence defining what this page covers and excludes.
```

Each claim links directly to GitHub Docs, `github/copilot-sdk`, `pi.dev`, `earendil-works/pi`, NIST, DoD, Agent Skills, or Agent Plugins. Record the persistence conflict, timeout-versus-abort distinction, early ephemeral-event risk, experimental fork/fleet status, and permissions-versus-containment distinction in the relevant pages.

- [ ] **Step 3: Add Lychee configuration**

Create `lychee.toml` from the `bossjones/boss-skills` pattern, but validate `ai_docs/` rather than excluding it:

```toml
verbose = "info"
no_progress = true
output = ".cache/lychee-report.md"
cache = false
max_redirects = 10
max_retries = 2
max_concurrency = 20
user_agent = "lychee/0.21.0"
timeout = 20
retry_wait_time = 2
accept = ["200", "401", "403", "405", "429"]
scheme = ["https", "http"]
require_https = false
method = "get"
fallback_extensions = ["md", "html"]
include_fragments = "anchor-only"
skip_missing = false
include_verbatim = false
exclude = [
  '^https?://localhost',
  '^https?://127\.0\.0\.1',
  '^https?://0\.0\.0\.0',
  '^file://',
  '^https?://.*\.local',
  '^https?://example\.(com|org)',
]
exclude_path = [
  "(^|/)node_modules/",
  "(^|/)\\.venv/",
  "(^|/)\\.git/",
  "(^|/)__pycache__/",
  "(^|/)\\.pytest_cache/",
  "(^|/)\\.cache/",
]
exclude_all_private = true
include_mail = false
```

- [ ] **Step 4: Add the initial repository Just feedback loop**

Create root `justfile`:

```just
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Validate every Markdown link, including ai_docs.
docs-check:
    @command -v lychee >/dev/null || { echo "install lychee: brew install lychee or cargo install lychee"; exit 1; }
    @mkdir -p .cache
    @GITHUB_TOKEN="$${GITHUB_TOKEN:-$$(gh auth token 2>/dev/null || true)}" \
      lychee --config lychee.toml '**/*.md'
```

- [ ] **Step 5: Run URL validation and fix every actionable failure**

Run:

```bash
just docs-check
```

Expected: exit 0 and `.cache/lychee-report.md` contains no unexcluded broken links. Use exclusions only for endpoints that return a verified non-checkable response; add a comment naming the endpoint behavior.

- [ ] **Step 6: Commit the grounded corpus**

```bash
git add ai_docs lychee.toml justfile
git commit -m "docs: add grounded Copilot port references" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Copilot Plugin Layout and Repository Test Harness

**Files:**
- Move: `.claude/skills/sssf/` -> `skills/sssf/`
- Create: `plugin.json`
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `tests/conftest.py`
- Create: `tests/test_plugin_layout.py`
- Modify: `skills/sssf/SKILL.md`

**Interfaces:**
- Consumes: Agent Plugins 1.0 and Agent Skills rules documented in Task 1.
- Produces: Stable source paths for all later tasks, `uv run pytest`, and a loadable Copilot-first plugin.

- [ ] **Step 1: Move the canonical skill**

Run:

```bash
mkdir -p skills
git mv .claude/skills/sssf skills/sssf
rmdir .claude/skills .claude 2>/dev/null || true
```

Do not create a second active `sssf` skill copy.

- [ ] **Step 2: Write failing plugin-layout tests**

Create `tests/test_plugin_layout.py`:

```python
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


def test_plugin_manifest_uses_agent_plugins_1():
    manifest = json.loads((ROOT / "plugin.json").read_text())
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "sssf"
    assert manifest["version"] == "1.0.0"


def test_canonical_skill_is_portable():
    metadata = _frontmatter(ROOT / "skills/sssf/SKILL.md")
    assert set(metadata) <= {
        "name", "description", "license", "compatibility", "metadata", "allowed-tools"
    }
    assert metadata["name"] == "sssf"
    assert not (ROOT / ".claude/skills/sssf").exists()
```

- [ ] **Step 3: Add repository development dependencies**

Create `pyproject.toml`:

```toml
[project]
name = "super-simple-software-factory"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = [
  "check-jsonschema>=0.33,<1",
  "github-copilot-sdk==1.0.13",
  "pydantic>=2.10,<3",
  "pyright>=1.1.400,<2",
  "pytest>=8.3,<9",
  "pytest-asyncio>=0.25,<1",
  "python-dotenv>=1.0,<2",
  "pyyaml>=6,<7",
  "rich>=13,<15",
  "ruff>=0.11,<1",
]

[tool.pytest.ini_options]
pythonpath = ["skills/sssf/templates/adws"]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
pythonVersion = "3.11"
include = ["skills/sssf/templates/adws/adw_modules", "scripts", "tests"]
```

Run:

```bash
uv lock
```

- [ ] **Step 4: Add plugin and portable skill metadata**

Create `plugin.json`:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "sssf",
  "version": "1.0.0",
  "description": "Install and operate deterministic agents-plus-code software factory workflows."
}
```

Replace `skills/sssf/SKILL.md` frontmatter with:

```yaml
---
name: sssf
description: Install and operate SSSF when creating, running, updating, or observing deterministic AI developer workflows and their agent roster.
compatibility: Requires Python 3.11+, uv, git, sqlite3, and GitHub Copilot authentication. Bun is optional for the visualizer.
metadata:
  author: bossjones
  version: "1.0.0"
---
```

- [ ] **Step 5: Add the common test import fixture**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def template_root(repo_root: Path) -> Path:
    return repo_root / "skills/sssf/templates"
```

- [ ] **Step 6: Run the focused tests and schema check**

Run:

```bash
uv run pytest tests/test_plugin_layout.py -q
uv run check-jsonschema \
  --schemafile https://agent-plugins.org/schemas/1.0.0/plugin.schema.json \
  plugin.json
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit the packaging seam**

```bash
git add plugin.json skills pyproject.toml uv.lock tests/conftest.py tests/test_plugin_layout.py
git commit -m "build: package SSSF as a Copilot plugin" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Copilot Runtime Contracts and Configuration

**Files:**
- Modify: `skills/sssf/templates/adws/adw_modules/data_types.py`
- Modify: `skills/sssf/templates/adws/adw_modules/agents.py`
- Modify: `skills/sssf/templates/sssf.config.yaml`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: Existing `EnvelopeBase`, `AgentCall`, `EventRecord`, and `UsageBreakdown`.
- Produces: `AgentRequest`, `AgentCallbacks`, `AgentEvent`, `AgentResult`, `RuntimeInfo`, `TimeoutConfig`, and Copilot-native `AgentConfig`.

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest
import yaml

from adw_modules import agents
from adw_modules.data_types import AgentConfig, SSSFConfig


def test_copilot_config_merges_defaults(tmp_path: Path):
    system = tmp_path / "system.md"
    user = tmp_path / "user.md"
    system.write_text("system")
    user.write_text("user")
    raw = {
        "defaults": {
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "context_tier": "default",
            "tools": ["view", "rg", "glob"],
            "timeouts": {"phase_seconds": 600, "tool_seconds": 120},
        },
        "agents": [{
            "name": "scout",
            "purpose": "Read only",
            "prompt_engineering": {"system": str(system), "user": str(user)},
            "writes": [],
        }],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))

    config = agents.load_config(str(path))
    scout = config.agents[0]

    assert scout.model == "gpt-5.4"
    assert scout.reasoning_effort == "high"
    assert scout.tools == ["view", "rg", "glob"]
    assert scout.timeouts.phase_seconds == 600


def test_removed_pi_fields_are_rejected():
    with pytest.raises(ValueError, match="coding_agent"):
        AgentConfig.model_validate({
            "name": "builder",
            "coding_agent": "pi",
            "purpose": "Build",
            "prompt_engineering": {"system": "system.md", "user": "user.md"},
        })


def test_default_config_is_copilot_only(repo_root: Path):
    config = SSSFConfig.model_validate(
        yaml.safe_load((repo_root / "skills/sssf/templates/sssf.config.yaml").read_text())
    )
    assert config.defaults.model
    assert all(not hasattr(agent, "coding_agent") for agent in config.agents)
```

- [ ] **Step 2: Run the tests to verify the old schema fails**

Run:

```bash
uv run pytest tests/test_config.py -q
```

Expected: failures for missing Copilot fields and acceptance of `coding_agent`.

- [ ] **Step 3: Replace Pi-specific config and runtime types**

In `data_types.py`, configure strict extra-field rejection and add:

```python
class TimeoutConfig(BaseModel):
    model_config = {"extra": "forbid"}

    phase_seconds: int = Field(default=1800, gt=0)
    tool_seconds: int = Field(default=300, gt=0)
    correction_seconds: int = Field(default=300, gt=0)


class AgentConfig(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    model: str = "gpt-5.4"
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] = "medium"
    context_tier: Literal["default", "long_context"] = "default"
    color: str = ""
    purpose: str = ""
    prompt_engineering: PromptEngineering
    tools: Optional[list[str]] = None
    skill_directories: list[str] = Field(default_factory=list)
    plugin_directories: list[str] = Field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    writes: Optional[list[str]] = None
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)


class AgentEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class AgentCallbacks(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    on_event: Optional[Callable[[AgentEvent], None]] = None


class AgentRequest(BaseModel):
    prompt: str
    system_prompt: str
    model: str
    reasoning_effort: str
    context_tier: str
    session_id: str
    resume: bool = False
    runtime_dir: str
    raw_output_path: str
    tools: Optional[list[str]] = None
    skill_directories: list[str] = Field(default_factory=list)
    plugin_directories: list[str] = Field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    timeout_seconds: int = 1800
    cwd: str = "."


class RuntimeInfo(BaseModel):
    sdk_version: str
    runtime_version: str
    protocol_version: str
    cli_version: str = ""


class AgentResult(BaseModel):
    text: str = ""
    session_id: str
    usage: UsageBreakdown = Field(default_factory=UsageBreakdown)
    context_tokens: int = 0
    context_window: int = 0
    runtime: Optional[RuntimeInfo] = None
```

Delete `PiRequest` and `PiResult`. Keep `UsageBreakdown`, but rewrite its docstrings and `add_turn()` input mapping to describe normalized Copilot usage rather than Pi fields.

- [ ] **Step 4: Update defaults merging**

In `agents.load_config()`, merge:

```python
for key in (
    "model", "reasoning_effort", "context_tier", "color", "tools",
    "skill_directories", "plugin_directories", "mcp_servers", "writes", "timeouts",
):
    if key in defaults:
        agent.setdefault(key, defaults[key])
```

Remove `coding_agent`, `thinking`, and `harness_engineering`.

- [ ] **Step 5: Rewrite the starter roster**

Use Copilot-native fields and built-in tool names:

```yaml
defaults:
  model: gpt-5.4
  reasoning_effort: medium
  context_tier: default
  tools: [view, rg, glob, bash, apply_patch]
  skill_directories: []
  plugin_directories: []
  mcp_servers: {}
  timeouts:
    phase_seconds: 1800
    tool_seconds: 300
    correction_seconds: 300
```

Remove `coding_agent`, provider prefixes, `harness_engineering`, and `subagent_*` tools from every agent.

- [ ] **Step 6: Run focused validation**

```bash
uv run pytest tests/test_config.py -q
uv run pyright skills/sssf/templates/adws/adw_modules/data_types.py
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit the contract**

```bash
git add skills/sssf/templates/adws/adw_modules/data_types.py \
  skills/sssf/templates/adws/adw_modules/agents.py \
  skills/sssf/templates/sssf.config.yaml tests/test_config.py
git commit -m "refactor: define Copilot runtime contracts" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Copilot Event Normalization

**Files:**
- Create: `skills/sssf/templates/adws/adw_modules/copilot_events.py`
- Create: `tests/test_copilot_events.py`

**Interfaces:**
- Consumes: Python SDK `SessionEvent`, `SessionEventType`, and typed event data.
- Produces: `CopilotEventNormalizer.observe(event) -> list[AgentEvent]`.

- [ ] **Step 1: Write event-normalization tests**

Use lightweight event objects so tests do not require a running runtime:

```python
from types import SimpleNamespace

from adw_modules.copilot_events import CopilotEventNormalizer


def event(event_type: str, **data):
    return SimpleNamespace(
        type=event_type,
        id=data.pop("id", "event-1"),
        agent_id=data.pop("agent_id", None),
        timestamp=data.pop("timestamp", "2026-09-14T12:00:00Z"),
        data=SimpleNamespace(**data),
    )


def test_tool_execution_is_folded_into_one_record():
    normalizer = CopilotEventNormalizer()
    assert normalizer.observe(event(
        "tool.execution_start",
        tool_call_id="call-1",
        tool_name="view",
        arguments={"path": "README.md"},
    )) == []

    records = normalizer.observe(event(
        "tool.execution_complete",
        tool_call_id="call-1",
        tool_name="view",
        result={"text": "contents"},
        success=True,
    ))

    assert len(records) == 1
    assert records[0].type == "tool_call"
    assert records[0].payload["tool_call_id"] == "call-1"
    assert records[0].payload["ok"] is True


def test_parent_final_message_wins_over_subagent_message():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(event("assistant.message", content="child", agent_id="agent-1"))
    normalizer.observe(event("assistant.message", content="parent"))
    assert normalizer.final_text == "parent"


def test_reasoning_events_are_not_normalized():
    normalizer = CopilotEventNormalizer()
    assert normalizer.observe(event("assistant.reasoning_delta", delta_content="secret")) == []
```

- [ ] **Step 2: Run the tests to verify the module is missing**

```bash
uv run pytest tests/test_copilot_events.py -q
```

Expected: import failure for `adw_modules.copilot_events`.

- [ ] **Step 3: Implement the pure normalizer**

Implement:

```python
class CopilotEventNormalizer:
    def __init__(self) -> None:
        self._open_tools: dict[str, dict[str, Any]] = {}
        self.final_text = ""
        self.context_tokens = 0
        self.context_window = 0
        self.usage = UsageBreakdown()

    def observe(self, event: Any) -> list[AgentEvent]:
        event_type = str(event.type)
        if event_type == "assistant.message" and event.agent_id is None:
            self.final_text = str(event.data.content or "")
            return []
        if event_type == "tool.execution_start":
            self._start_tool(event)
            return []
        if event_type == "tool.execution_complete":
            return [self._finish_tool(event)]
        if event_type == "session.usage_info":
            self._record_usage(event.data)
            return []
        if event_type in {"session.error", "tool.execution_error"}:
            return [AgentEvent(type="error", payload=self._safe_payload(event))]
        return []
```

Use `getattr()` helpers for SDK-version-tolerant field access. Clip argument and result strings at the existing 20,000-character limits. Never include reasoning-event payloads.

- [ ] **Step 4: Run focused tests and lint**

```bash
uv run pytest tests/test_copilot_events.py -q
uv run ruff check skills/sssf/templates/adws/adw_modules/copilot_events.py \
  tests/test_copilot_events.py
```

Expected: both commands exit 0.

- [ ] **Step 5: Commit event normalization**

```bash
git add skills/sssf/templates/adws/adw_modules/copilot_events.py tests/test_copilot_events.py
git commit -m "feat: normalize Copilot session events" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: SDK-Backed Copilot Runtime

**Files:**
- Create: `skills/sssf/templates/adws/adw_modules/agent_copilot.py`
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/copilot_sdk.py`
- Create: `tests/test_agent_copilot.py`

**Interfaces:**
- Consumes: `AgentRequest`, `AgentCallbacks`, `AgentResult`, `RuntimeInfo`, and `CopilotEventNormalizer`.
- Produces: `validate(config) -> RuntimeInfo` and `run(request, callbacks) -> AgentResult`.

- [ ] **Step 1: Create deterministic fake SDK objects**

Create fakes with the same methods used by production:

```python
class FakeSession:
    def __init__(self, session_id: str, events: list, result_text: str = "{}"):
        self.session_id = session_id
        self.events = events
        self.result_text = result_text
        self.handlers = []
        self.aborted = False
        self.disconnected = False

    def on(self, handler):
        self.handlers.append(handler)
        return lambda: self.handlers.remove(handler)

    async def send_and_wait(self, prompt: str, timeout: float | None = None):
        for event in self.events:
            for handler in list(self.handlers):
                handler(event)
        return SimpleNamespace(data=SimpleNamespace(content=self.result_text))

    async def abort(self):
        self.aborted = True

    async def disconnect(self):
        self.disconnected = True


class FakeClient:
    def __init__(self, *, create_session: FakeSession | None = None,
                 resume_session: FakeSession | None = None, **kwargs):
        self.created = create_session
        self.resumed = resume_session
        self.kwargs = kwargs
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def create_session(self, **kwargs):
        self.create_kwargs = kwargs
        return self.created

    async def resume_session(self, session_id: str, **kwargs):
        self.resume_id = session_id
        self.resume_kwargs = kwargs
        return self.resumed

    async def stop(self):
        self.stopped = True
```

- [ ] **Step 2: Write lifecycle tests**

Add tests named:

- `test_create_uses_empty_mode_explicit_tools_and_caller_session_id`
- `test_resume_reuses_session_id`
- `test_timeout_calls_abort_before_disconnect`
- `test_events_are_subscribed_before_send`
- `test_runtime_error_is_not_converted_to_success`
- `test_disconnect_and_client_stop_run_on_failure`
- `test_runtime_does_not_access_private_cli_process`

Assert constructor/session arguments:

```python
assert client.kwargs["mode"] == "empty"
assert client.kwargs["base_directory"] == request.runtime_dir
assert client.create_kwargs["session_id"] == request.session_id
assert client.create_kwargs["available_tools"] == request.tools
assert client.create_kwargs["reasoning_effort"] == request.reasoning_effort
assert client.create_kwargs["working_directory"] == request.cwd
```

- [ ] **Step 3: Run tests to verify the runtime module is missing**

```bash
uv run pytest tests/test_agent_copilot.py -q
```

Expected: import failure for `adw_modules.agent_copilot`.

- [ ] **Step 4: Implement runtime validation**

`validate()` checks:

```python
EXPECTED_SDK_VERSION = "1.0.13"
EXPECTED_PROTOCOL_VERSION = "3"


def validate(config: SSSFConfig) -> RuntimeInfo:
    installed = importlib.metadata.version("github-copilot-sdk")
    if installed != EXPECTED_SDK_VERSION:
        raise RuntimeError(
            f"github-copilot-sdk {installed} is installed; "
            f"SSSF requires {EXPECTED_SDK_VERSION}"
        )
    return asyncio.run(_validate_runtime(config, installed))


async def _validate_runtime(config: SSSFConfig, sdk_version: str) -> RuntimeInfo:
    client = CopilotClient(
        mode="empty",
        base_directory=str(Path(config.defaults.data_dir) / "copilot-runtime"),
    )
    await client.start()
    try:
        status = await client.get_status()
        if str(status.protocol_version) != EXPECTED_PROTOCOL_VERSION:
            raise RuntimeError(
                f"Copilot runtime protocol {status.protocol_version} is incompatible; "
                f"SSSF requires {EXPECTED_PROTOCOL_VERSION}"
            )
        return RuntimeInfo(
            sdk_version=sdk_version,
            runtime_version=status.version,
            protocol_version=str(status.protocol_version),
            cli_version=_cli_version(),
        )
    finally:
        await client.stop()
```

Use public `client.get_status()` for runtime and protocol metadata. Use
`copilot --version` only for diagnostic metadata, not to determine SDK runtime
compatibility.

- [ ] **Step 5: Implement asynchronous create/resume/send/abort**

The synchronous public function calls one async implementation:

```python
def run(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    return asyncio.run(_run(request, callbacks))
```

`_run()`:

```python
client = CopilotClient(
    mode="empty",
    base_directory=request.runtime_dir,
    working_directory=request.cwd,
)
await client.start()
status = await client.get_status()
session = None
normalizer = CopilotEventNormalizer()
try:
    session = await _create_or_resume(client, request, callbacks, normalizer)
    try:
        response = await session.send_and_wait(
            request.prompt,
            timeout=request.timeout_seconds,
        )
    except TimeoutError:
        await session.abort()
        raise
    text = normalizer.final_text or _response_text(response)
    return AgentResult(
        text=text,
        session_id=session.session_id,
        usage=normalizer.usage,
        context_tokens=normalizer.context_tokens,
        context_window=normalizer.context_window,
        runtime=RuntimeInfo(
            sdk_version=importlib.metadata.version("github-copilot-sdk"),
            runtime_version=status.version,
            protocol_version=str(status.protocol_version),
            cli_version=_cli_version(),
        ),
    )
finally:
    if session is not None:
        await session.disconnect()
    await client.stop()
```

Write every SDK event before normalization:

```python
raw_path = Path(request.raw_output_path)
raw_path.parent.mkdir(parents=True, exist_ok=True)


def handle_event(event: SessionEvent) -> None:
    payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else vars(event)
    with raw_path.open("a") as raw:
        raw.write(json.dumps(payload, default=str) + "\n")
    for normalized in normalizer.observe(event):
        if callbacks.on_event is not None:
            callbacks.on_event(normalized)
```

Create or resume explicitly; never fall back from a failed resume to create:

```python
options = {
    "model": request.model,
    "reasoning_effort": request.reasoning_effort,
    "context_tier": request.context_tier,
    "available_tools": request.tools,
    "system_message": {"mode": "append", "content": request.system_prompt},
    "working_directory": request.cwd,
    "streaming": True,
    "mcp_servers": request.mcp_servers,
    "skill_directories": request.skill_directories,
    "plugin_directories": request.plugin_directories,
    "on_permission_request": lambda _request, _invocation: PermissionDecisionApproveOnce(),
    "on_event": handle_event,
}
if request.resume:
    session = await client.resume_session(request.session_id, **options)
else:
    session = await client.create_session(session_id=request.session_id, **options)
```

`PermissionDecisionApproveOnce` applies only to tools already admitted by
`available_tools`; `permissions.enforce()` remains authoritative.

- [ ] **Step 6: Serialize access to each session**

Use an atomic exclusive create:

```python
lock_path = Path(request.runtime_dir) / "locks" / f"{request.session_id}.lock"
lock_path.parent.mkdir(parents=True, exist_ok=True)
try:
    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
except FileExistsError as error:
    raise RuntimeError(
        f"Copilot session {request.session_id!r} is already active; "
        "concurrent mutation is not allowed"
    ) from error
```

Release the lock in `finally`, including timeout and runtime-crash paths.

- [ ] **Step 7: Run focused validation**

```bash
uv run pytest tests/test_agent_copilot.py tests/test_copilot_events.py -q
uv run ruff check skills/sssf/templates/adws/adw_modules/agent_copilot.py tests/fakes tests/test_agent_copilot.py
uv run pyright skills/sssf/templates/adws/adw_modules/agent_copilot.py
```

Expected: all commands exit 0.

- [ ] **Step 8: Commit the Copilot runtime**

```bash
git add skills/sssf/templates/adws/adw_modules/agent_copilot.py \
  tests/fakes tests/test_agent_copilot.py
git commit -m "feat: execute agent phases through Copilot SDK" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Orchestration Integration and Same-Session Corrections

**Files:**
- Modify: `skills/sssf/templates/adws/adw_modules/agents.py`
- Create: `tests/test_agents.py`

**Interfaces:**
- Consumes: `agent_copilot.validate()`, `agent_copilot.run()`, and runtime contract types.
- Produces: Copilot-backed `agents.validate()` and `agents.execute()` with unchanged ADW call sites.

- [ ] **Step 1: Write orchestration tests**

Create fakes for `run`, `phase`, `tracer`, and console. Add tests named:

- `test_validate_calls_copilot_preflight_once`
- `test_execute_builds_copilot_request_from_agent_config`
- `test_invalid_json_retries_same_session`
- `test_gate_failure_retries_same_session`
- `test_permission_enforcement_runs_after_all_sends`
- `test_timeout_propagates_and_records_error`
- `test_runtime_versions_are_traced`

For same-session behavior:

```python
requests = []

def fake_run(request, callbacks):
    requests.append(request)
    text = "not-json" if len(requests) == 1 else valid_envelope_json
    return AgentResult(text=text, session_id=request.session_id)

assert [request.session_id for request in requests] == [
    requests[0].session_id,
    requests[0].session_id,
]
assert [request.resume for request in requests] == [False, True]
```

- [ ] **Step 2: Run focused tests to observe Pi coupling**

```bash
uv run pytest tests/test_agents.py -q
```

Expected: failures because `agents.py` imports `agent_pi` and constructs `PiRequest`.

- [ ] **Step 3: Replace the execution dependency**

Import:

```python
from . import agent_copilot, permissions, prompts
from .data_types import AgentCallbacks, AgentRequest, AgentResult
```

Build:

```python
request = AgentRequest(
    prompt=prompt_text,
    system_prompt=system_text,
    model=agent.model,
    reasoning_effort=agent.reasoning_effort,
    context_tier=agent.context_tier,
    session_id=session_id,
    resume=session_active,
    runtime_dir=str((agent_dir / "copilot").resolve()),
    raw_output_path=str((agent_dir / "raw_output.jsonl").resolve()),
    tools=agent.tools,
    skill_directories=agent.skill_directories,
    plugin_directories=agent.plugin_directories,
    mcp_servers=agent.mcp_servers,
    timeout_seconds=agent.timeouts.phase_seconds,
    cwd=str(run.repo_root),
)
```

Call:

```python
result = agent_copilot.run(
    request,
    AgentCallbacks(
        on_event=_event_forwarder(run, phase, agent.name),
    ),
)
session_active = True
```

Do not read `CopilotClient._cli_process` or synthesize an agent PID. The public
SDK does not expose the managed runtime PID. Existing process rows continue to
track the enclosing ADW process; `agent_start`, `agent_end`, and `error` events
provide logical runtime supervision.

- [ ] **Step 4: Preserve typed and gate corrections**

Initialize `session_active` from the matching `agent_map.json` entry. Keep
`_parse_with_retries()` and the gate loop above the runtime. The first new
session request sets `resume=False`; after its successful return, every
correction and later phase uses `resume=True` with the same `session_id`,
`runtime_dir`, model, and system prompt. A failed resume propagates and never
creates a replacement session.

- [ ] **Step 5: Rewrite validation**

`agents.validate()` verifies required names and prompt paths, then invokes one Copilot runtime preflight. It does not query a Pi model catalog. Model/reasoning compatibility that requires authentication is checked by the optional smoke test and surfaced by the SDK during session creation.

- [ ] **Step 6: Normalize trace payloads**

`agent_start` includes:

```python
{
    "model": agent.model,
    "reasoning_effort": agent.reasoning_effort,
    "context_tier": agent.context_tier,
    "session_id": session_id,
    "coding_agent": "copilot",
    "purpose": agent.purpose,
    "tools": agent.tools,
    "skill_directories": agent.skill_directories,
    "plugin_directories": agent.plugin_directories,
    "mcp_servers": sorted(agent.mcp_servers),
}
```

`agent_end` includes usage, context, SDK version, runtime version, protocol version, and CLI version.

- [ ] **Step 7: Run orchestration regression tests**

```bash
uv run pytest tests/test_agents.py tests/test_config.py tests/test_agent_copilot.py -q
uv run ruff check skills/sssf/templates/adws/adw_modules/agents.py tests/test_agents.py
```

Expected: both commands exit 0.

- [ ] **Step 8: Commit the orchestration switch**

```bash
git add skills/sssf/templates/adws/adw_modules/agents.py tests/test_agents.py
git commit -m "refactor: route SSSF agents through Copilot" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Trace and Visualizer Compatibility

**Files:**
- Modify: `skills/sssf/templates/adws/adw_modules/tracer.py`
- Modify: `skills/sssf/apps/visualizer/shared/types.ts`
- Modify: `skills/sssf/apps/visualizer/src/components/PhaseDetail.vue`
- Modify: `skills/sssf/apps/visualizer/src/components/SessionTrace.vue`
- Create: `tests/test_tracer.py`

**Interfaces:**
- Consumes: Normalized factory events and `RuntimeInfo`.
- Produces: Backward-readable SQLite rows and Copilot runtime metadata in the UI.

- [ ] **Step 1: Write trace compatibility tests**

Create a temporary tracer and assert:

```python
def test_agent_session_row_records_copilot_without_breaking_existing_schema(tmp_path):
    tracer = Tracer(tmp_path / "sssf.db", tmp_path / "events.jsonl")
    tracer.agent_session_row(
        "run-1",
        agent_config,
        "session-1",
        context_tokens=100,
        context_window=1000,
        runtime=RuntimeInfo(
            sdk_version="1.0.13",
            runtime_version="1.0.84",
            protocol_version="3",
            cli_version="1.0.84-5",
        ),
    )
    row = tracer.conn.execute(
        "select coding_agent, sdk_version, runtime_version, protocol_version "
        "from agent_sessions where adw_id='run-1'"
    ).fetchone()
    assert tuple(row) == ("copilot", "1.0.13", "1.0.84", "3")
```

Also initialize a database with the old `agent_sessions` schema and assert migrations add nullable runtime columns without losing rows.

- [ ] **Step 2: Add additive trace migrations**

Keep `coding_agent` for historical compatibility and always write `"copilot"` for new rows. Add nullable:

```sql
sdk_version TEXT
runtime_version TEXT
protocol_version TEXT
cli_version TEXT
```

Update the upsert so these fields refresh on later use.

- [ ] **Step 3: Update visualizer types and display**

Add nullable runtime metadata to `AgentSessionInfo`. Display it in `PhaseDetail.vue` under the existing agent configuration section:

```text
harness    Copilot
sdk        1.0.13
runtime    1.0.84
protocol   3
```

Keep old rows renderable when fields are null.

- [ ] **Step 4: Run Python and visualizer checks**

```bash
uv run pytest tests/test_tracer.py -q
cd skills/sssf/apps/visualizer
bun install --frozen-lockfile
bun run build
```

Expected: tests pass and Vite build exits 0.

- [ ] **Step 5: Commit observability compatibility**

```bash
git add skills/sssf/templates/adws/adw_modules/tracer.py \
  skills/sssf/apps/visualizer/shared/types.ts \
  skills/sssf/apps/visualizer/src/components/PhaseDetail.vue \
  skills/sssf/apps/visualizer/src/components/SessionTrace.vue tests/test_tracer.py
git commit -m "feat: trace Copilot runtime metadata" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Installer, Entry Points, and Pi Removal

**Files:**
- Delete: `skills/sssf/templates/adws/adw_modules/agent_pi.py`
- Delete: `skills/sssf/templates/adws/adw_modules/agent_cc.py`
- Delete: `skills/sssf/templates/harness_engineering/subagents.ts`
- Delete: `skills/sssf/templates/harness_engineering/themeMap.ts`
- Modify: `skills/sssf/scripts/install.py`
- Modify: `skills/sssf/templates/env.sample`
- Modify: `skills/sssf/templates/justfile`
- Modify: `skills/sssf/templates/adws/adw_*.py`
- Create: `tests/test_install.py`
- Create: `tests/test_no_pi_runtime.py`

**Interfaces:**
- Consumes: Copilot-only templates and pinned SDK dependency.
- Produces: Idempotent target-repository installation and no remaining production Pi runtime surface.

- [ ] **Step 1: Write installer tests**

Use `subprocess.run()` in a temporary Git repository:

```python
def test_install_stamps_copilot_factory(repo_root, tmp_path):
    result = subprocess.run(
        ["uv", "run", str(repo_root / "skills/sssf/scripts/install.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert (tmp_path / "adws/adw_modules/agent_copilot.py").is_file()
    assert not (tmp_path / "adws/adw_modules/agent_pi.py").exists()
    assert not (tmp_path / "adws/adw_data/harness_engineering").exists()
    assert "copilot" in (tmp_path / ".env.sample").read_text().lower()
    assert "just demo" in result.stdout


def test_second_install_skips_existing_files(repo_root, tmp_path):
    command = ["uv", "run", str(repo_root / "skills/sssf/scripts/install.py")]
    subprocess.run(command, cwd=tmp_path, check=True)
    target = tmp_path / "adws/adw_modules/agent_copilot.py"
    target.write_text("# local customization\n")

    result = subprocess.run(
        command, cwd=tmp_path, text=True, capture_output=True, check=True
    )

    assert target.read_text() == "# local customization\n"
    assert "skipped (already exist" in result.stdout


def test_force_install_overwrites_stamped_files(repo_root, tmp_path):
    command = ["uv", "run", str(repo_root / "skills/sssf/scripts/install.py")]
    subprocess.run(command, cwd=tmp_path, check=True)
    target = tmp_path / "adws/adw_modules/agent_copilot.py"
    target.write_text("# local customization\n")

    subprocess.run([*command, "--force"], cwd=tmp_path, check=True)

    assert target.read_text() != "# local customization\n"
```

- [ ] **Step 2: Write the Pi-removal guard**

Create `tests/test_no_pi_runtime.py`:

```python
from pathlib import Path

FORBIDDEN = (
    "agent_pi",
    "PiRequest",
    "PiResult",
    "PI_PATH",
    "PI_MODELS_PATH",
    "coding_agent: pi",
    "pi --mode",
)


def test_production_runtime_has_no_pi_coupling(repo_root: Path):
    roots = [
        repo_root / "skills/sssf/templates",
        repo_root / "skills/sssf/scripts",
        repo_root / "skills/sssf/SKILL.md",
        repo_root / "skills/sssf/references",
        repo_root / "skills/sssf/cookbooks",
        repo_root / "README.md",
    ]
    offenders = []
    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".md", ".yaml", ".yml", ".ts"}:
                continue
            text = path.read_text(errors="ignore")
            for needle in FORBIDDEN:
                if needle in text:
                    offenders.append(f"{path.relative_to(repo_root)}: {needle}")
    assert offenders == []
```

The historical `ai_docs/pi-*` pages and design/plan documents are outside this guard by design.

- [ ] **Step 3: Run tests to verify current Pi files fail**

```bash
uv run pytest tests/test_install.py tests/test_no_pi_runtime.py -q
```

Expected: failures list the Pi adapter, extension templates, installer path, environment sample, and docs.

- [ ] **Step 4: Remove Pi-only files and installer stamping**

Delete both old adapter modules and `templates/harness_engineering/`. Remove the harness-engineering stamp call from `install.py`. Update its docstring and output to say Copilot SDK/runtime.

- [ ] **Step 5: Pin the SDK in every ADW entry point**

In each `skills/sssf/templates/adws/adw_*.py` PEP 723 block, set:

```python
# dependencies = [
#   "github-copilot-sdk==1.0.13",
#   "pydantic",
#   "python-dotenv",
#   "pyyaml",
#   "rich",
# ]
```

Add a test that iterates all `adw_*.py` files and asserts the exact SDK pin appears once.

- [ ] **Step 6: Rewrite generated environment and Just guidance**

`env.sample` documents supported authentication precedence without containing credentials:

```dotenv
# Authenticate with `copilot login`, `gh auth login`, or one supported token.
# COPILOT_GITHUB_TOKEN=
# GH_TOKEN=
# GITHUB_TOKEN=

# Optional SDK/runtime overrides
# COPILOT_CLI_PATH=
# COPILOT_HOME=
# ENGINEER_NAME=
```

The generated `justfile` keeps workflow and observation recipes, changes the visualizer path to the installed app location, and adds:

```just
copilot-doctor:
    copilot --version
    uv run python -c "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
```

- [ ] **Step 7: Run installer and removal tests**

```bash
uv run pytest tests/test_install.py tests/test_no_pi_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit the breaking runtime migration**

```bash
git add -A skills/sssf/templates skills/sssf/scripts tests/test_install.py tests/test_no_pi_runtime.py
git commit -m "feat!: remove Pi and install Copilot runtime" \
  -m "BREAKING CHANGE: SSSF agent phases now require GitHub Copilot and no longer accept Pi configuration." \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: End-User Documentation and Operational References

**Files:**
- Modify: `README.md`
- Modify: `skills/sssf/SKILL.md`
- Modify: `skills/sssf/cookbooks/*.md`
- Modify: `skills/sssf/references/config.md`
- Modify: `skills/sssf/references/handoff.md`
- Modify: `skills/sssf/references/observability.md`

**Interfaces:**
- Consumes: Final Copilot config, runtime, installer, plugin layout, and `ai_docs/`.
- Produces: Copilot-first installation, migration, operation, and troubleshooting instructions.

- [ ] **Step 1: Rewrite installation instructions**

README quickstart uses:

```bash
copilot plugin install bossjones/super-simple-software-factory
copilot skill list
uv run skills/sssf/scripts/install.py
copilot login
just demo
just sessions
```

Document local development with `copilot --plugin-dir /path/to/super-simple-software-factory`. The installed CLI does not accept a local directory in `copilot plugin install`; `--plugin-dir` is the supported local validation path. Keep manual installation as a fallback and name Python 3.11+, `uv`, GitHub Copilot access, `sqlite3`, `just`, and optional Bun.

- [ ] **Step 2: Add an explicit breaking migration section**

List removed fields/files and the replacement:

| Removed | Replacement |
|---|---|
| `coding_agent: pi` | Copilot is the only runtime; remove the field |
| `thinking` | `reasoning_effort` |
| `harness_engineering` | `skill_directories`, `plugin_directories`, and `mcp_servers` |
| provider-qualified Pi model IDs | Copilot model IDs |
| `PI_PATH`, `PI_MODELS_PATH` | `COPILOT_CLI_PATH`, `COPILOT_HOME` |
| `agent_pi.py` and Pi extensions | `agent_copilot.py` and Copilot SDK configuration |

- [ ] **Step 3: Update operational contracts**

`config.md` documents every new field, default merging, tool names, timeout budgets, session invalidation on model change, and SDK/runtime preflight.

`handoff.md` describes Copilot session IDs and same-session corrections.

`observability.md` documents normalized Copilot events and runtime-version columns.

Cookbooks use `skills/sssf/...` paths and Copilot terminology.

- [ ] **Step 4: Verify no stale runtime guidance remains**

Run:

```bash
uv run pytest tests/test_no_pi_runtime.py -q
rg -n '\\.claude/skills/sssf|coding_agent|harness_engineering|PI_PATH|PI_MODELS_PATH' \
  README.md skills/sssf
```

Expected: pytest passes and `rg` has no matches.

- [ ] **Step 5: Validate docs and plugin loading**

```bash
just docs-check
uv run check-jsonschema \
  --schemafile https://agent-plugins.org/schemas/1.0.0/plugin.schema.json \
  plugin.json
copilot --no-auto-update --plugin-dir . plugin list --json
copilot --no-auto-update --plugin-dir . skill list --json
```

Expected: links and schema pass; `plugin list` shows `sssf` under external plugins and `skill list` contains an enabled `sssf` skill sourced from that plugin. These read-only commands do not modify user-level plugin state.

- [ ] **Step 6: Commit user-facing documentation**

```bash
git add README.md skills/sssf/SKILL.md skills/sssf/cookbooks skills/sssf/references
git commit -m "docs: document Copilot-native factory operation" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: Full Verification, Authenticated Smoke, Reviews, and PR

**Files:**
- Create: `scripts/copilot_smoke.py`
- Create: `.github/workflows/verify.yml`
- Modify: `justfile`
- Modify: `pyproject.toml`
- Modify: `README.md` only if verification evidence reveals a documented command mismatch

**Interfaces:**
- Consumes: Complete Copilot-only implementation.
- Produces: `just verify`, optional `just copilot-smoke`, independent review evidence, pushed branch, and an open PR.

- [ ] **Step 1: Add the authenticated smoke script**

`scripts/copilot_smoke.py`:

```python
async def main() -> int:
    with TemporaryDirectory(prefix="sssf-copilot-smoke-") as directory:
        repo = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "smoke@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "SSSF Smoke"], cwd=repo, check=True)
        (repo / "README.md").write_text("# Smoke\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

        request = AgentRequest(
            prompt='Return only {"status":"success","summary":"smoke","artifacts":[],"notes_for_next_agent":[]}',
            system_prompt="Follow the requested JSON contract.",
            model=os.environ.get("SSSF_SMOKE_MODEL", "gpt-5.4"),
            reasoning_effort="low",
            context_tier="default",
            session_id=f"sssf-smoke-{uuid.uuid4()}",
            resume=False,
            runtime_dir=str(repo / ".copilot-runtime"),
            raw_output_path=str(repo / "events.jsonl"),
            tools=["view"],
            timeout_seconds=300,
            cwd=str(repo),
        )
        result = agent_copilot.run(request, AgentCallbacks())
        GenericOutput.model_validate(agents._extract_json(result.text))
        return 0
```

The script prints versions and pass/fail status, never token values.

- [ ] **Step 2: Expand the repository Justfile**

Add:

```just
fmt:
    uv run ruff format .

fmt-check:
    uv run ruff format --check .

lint:
    uv run ruff check .

typecheck:
    uv run pyright

test:
    uv run pytest -q

plugin-check:
    uv run check-jsonschema --schemafile https://agent-plugins.org/schemas/1.0.0/plugin.schema.json plugin.json

visualizer-build:
    cd skills/sssf/apps/visualizer && bun install --frozen-lockfile && bun run build

verify: fmt-check lint typecheck test plugin-check docs-check visualizer-build

copilot-smoke:
    uv run python scripts/copilot_smoke.py
```

- [ ] **Step 3: Add credential-free CI**

Create `.github/workflows/verify.yml` with:

```yaml
name: verify
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - uses: extractions/setup-just@v3
      - uses: oven-sh/setup-bun@v2
      - uses: lycheeverse/lychee-action@v2
        with:
          args: --config lychee.toml '**/*.md'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - run: uv sync --locked --group dev
      - run: just fmt-check lint typecheck test plugin-check visualizer-build
```

The workflow does not run `copilot-smoke`.

- [ ] **Step 4: Run the complete credential-free suite**

```bash
just verify
git --no-pager diff --check -- \
  ':!.gitignore'
git status --short
```

Expected: `just verify` exits 0; only the known unrelated `.gitignore` modification remains outside staged implementation changes.

- [ ] **Step 5: Run the authenticated smoke test**

First verify:

```bash
copilot --version
gh auth status
```

Then:

```bash
just copilot-smoke
```

Expected: exit 0. If credentials or entitlements are unavailable, record the exact skipped reason in the PR instead of weakening the test.

- [ ] **Step 6: Run the requested independent review passes**

Dispatch two read-only subagents in parallel:

1. Documentation reviewer: verify every material `ai_docs/` claim, URL, version, and uncertainty against primary sources.
2. Runtime reviewer: inspect SDK lifecycle, resume, event normalization, timeout/abort, cleanup, typed corrections, permissions, traces, tests, and complete Pi removal.

Require severity, file/line evidence, and actionable fixes. Apply all material fixes and rerun:

```bash
just verify
just copilot-smoke
```

- [ ] **Step 7: Commit final verification infrastructure and review fixes**

```bash
git add scripts/copilot_smoke.py .github/workflows/verify.yml justfile pyproject.toml uv.lock
git add ai_docs skills tests README.md plugin.json lychee.toml
git commit -m "ci: verify the Copilot software factory" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

These explicit paths cover all planned review-fix locations and do not stage `.gitignore`.

- [ ] **Step 8: Inspect the final branch**

```bash
git status --short --branch
git --no-pager log --oneline --decorate main..HEAD
git --no-pager diff --stat main...HEAD
git --no-pager diff --check main...HEAD
```

Expected: implementation files are committed, `.gitignore` remains the only unrelated local modification, and the branch diff contains no whitespace errors.

- [ ] **Step 9: Push and open the PR**

```bash
git push -u origin feat/copilot-software-factory
gh pr create \
  --base main \
  --head feat/copilot-software-factory \
  --title "feat: port the software factory to GitHub Copilot" \
  --body-file /tmp/sssf-copilot-pr.md
```

The PR body records:

- SDK/runtime/CLI versions.
- Copilot-only breaking changes.
- Plugin and skill packaging.
- `ai_docs/` source-grounding approach.
- `just verify` result.
- Authenticated smoke result or exact skip reason.
- Independent documentation and runtime review outcomes.
- Known persistence, fork/fleet, headless-runtime, and hook-containment caveats.

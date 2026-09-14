# Copilot-Native Super Simple Software Factory

**Status:** Approved design  
**Date:** 2026-09-14  
**Scope:** Replace the Pi coding-agent harness with GitHub Copilot CLI's official Python SDK and make the repository Copilot-first.

## 1. Purpose

Super Simple Software Factory (SSSF) keeps deterministic workflow control in Python while bounded AI workers perform work that requires reading, judgment, or code generation. This port changes the worker harness from Pi to GitHub Copilot without moving sequencing, retries, gates, permissions, traceability, or final acceptance into prompts.

The port is intentionally Copilot-only. Pi configuration, runtime code, extensions, environment variables, and installation instructions are removed rather than retained as a second supported harness.

## 2. Grounded Design Facts

The design is based on primary sources verified on 2026-09-14:

- GitHub Copilot CLI supports non-interactive prompts, JSONL output, durable sessions, custom agents, skills, plugins, MCP servers, tool controls, and explicit permission flags. JSONL is a transport format; it does not enforce the semantic shape of an assistant response.
  - [Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
  - [Copilot CLI programmatic reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)
  - [Run Copilot CLI programmatically](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically)
- The official Python Copilot SDK controls a Copilot runtime over JSON-RPC and exposes session lifecycle, event streaming, tools, hooks, permissions, usage, resume, disconnect, and abort operations.
  - [Copilot SDK repository](https://github.com/github/copilot-sdk)
  - [Python SDK README](https://github.com/github/copilot-sdk/blob/main/python/README.md)
  - [Streaming events](https://github.com/github/copilot-sdk/blob/main/docs/features/streaming-events.md)
  - [Session persistence](https://github.com/github/copilot-sdk/blob/main/docs/features/session-persistence.md)
- The SDK's `send_and_wait()` timeout limits caller waiting but does not itself guarantee cancellation. The host must call `session.abort()` when a phase deadline expires.
  - [Python session implementation](https://github.com/github/copilot-sdk/blob/main/python/copilot/session.py)
- The SDK has no native guarantee that the final assistant text conforms to an application Pydantic model. SSSF must retain host-side parsing, validation, bounded correction turns, and gates.
- Copilot permissions, hooks, and tool filters are controls, not a complete repository containment boundary. SSSF's changed-path snapshot and rollback enforcement remains authoritative for the configured `writes` policy.
  - [Copilot hooks](https://docs.github.com/en/copilot/concepts/agents/hooks)
  - [Copilot CLI permissions](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/manage-permissions)
- GitHub Copilot and Claude Code support the open Agent Skills standard. Agent Plugins 1.0 provides a portable plugin core for skills and MCP configuration, with client-specific extensions outside that core.
  - [About Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
  - [Agent Skills specification](https://agentskills.io/specification)
  - [About Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins)
  - [Copilot plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
  - [Agent Plugins 1.0 specification](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md)
- A software factory is a delivery system of people, repeatable processes, automated toolchains, policy controls, evidence, feedback, and explicit approval boundaries. In an agentic factory, deterministic describes the control plane rather than model output.
  - [NIST NCCoE DevSecOps reference model](https://pages.nist.gov/nccoe-devsecops/notational-reference-model.html)
  - [NIST Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
  - [DoD Enterprise DevSecOps Reference Design](https://dodcio.defense.gov/Portals/0/Documents/Library/DoD-Enterprise-DevSecOps-Reference-Design-v1.0.pdf)

## 3. Goals

1. Run every SSSF agent phase through the official Python Copilot SDK.
2. Preserve existing ADW sequencing and phase semantics.
3. Preserve typed envelopes, same-session correction turns, gates, write enforcement, SQLite traces, JSONL traces, and final `run.finish()` acceptance.
4. Keep Copilot-specific complexity behind a small, testable runtime interface.
5. Make the repository installable and discoverable as a Copilot-first Agent Plugins 1.0 package with a standards-compliant Agent Skill.
6. Create concise `ai_docs/` references grounded in official documentation.
7. Provide credential-free deterministic tests plus an optional authenticated Copilot smoke test.
8. Validate all documentation URLs with Lychee through a repeatable `just` target and CI.
9. Deliver the port on a focused branch with conventional commits and a PR into `main`.

## 4. Non-Goals

- Supporting Pi after this migration.
- Maintaining a runtime abstraction for hypothetical future harnesses.
- Reimplementing Copilot SDK behavior through a Pi-shaped compatibility stream.
- Making Copilot fleet mode part of the core ADW execution path.
- Treating prompts, skills, hooks, or Copilot permissions as substitutes for deterministic gates and write enforcement.
- Requiring GitHub credentials for the normal unit and integration test suite.
- Automatically rewriting repositories generated by older SSSF releases.

## 5. Architecture

### 5.1 Control Plane

Deterministic Python remains the factory control plane:

```text
ADW script
  -> Run.phase()
  -> PhaseHandle.call()
  -> agents.execute()
  -> Copilot runtime module
  -> official Python Copilot SDK
  -> Copilot runtime and model
```

The ADW decides phase order, retry bounds, mechanical commands, gate outcomes, correction paths, and final acceptance. Copilot receives one bounded task at a time and returns evidence through the existing typed handoff contract.

### 5.2 Deep Runtime Module

The Copilot runtime is a deep module. Its orchestration-facing interface is small:

```python
def validate(config: CopilotRuntimeConfig) -> CopilotRuntimeInfo: ...

def run(
    request: AgentRequest,
    callbacks: AgentCallbacks,
) -> AgentResult: ...
```

The implementation owns:

- SDK client and runtime startup.
- Pinned SDK/runtime compatibility checks.
- Authentication preflight.
- `mode="empty"` session configuration.
- Session create or resume.
- Event subscription during create or resume so startup events are not missed.
- Explicit tool availability.
- Skills, plugin directories, and MCP configuration.
- Permission callbacks and lifecycle hooks.
- Prompt submission and idle detection.
- Raw event retention and normalized event production.
- Final assistant-message extraction.
- Usage and context metadata mapping.
- Deadline handling and explicit `session.abort()`.
- Disconnect without deleting resumable session state.
- SDK-managed runtime cleanup.

The Python SDK does not expose the managed runtime PID through a public
interface. SSSF must not depend on the private `_cli_process` field. The
`processes` table continues to track the killable ADW process; `agent_start`,
`agent_end`, and `error` events track the logical Copilot runtime lifecycle.

Callers do not depend on SDK event classes, JSON-RPC method names, CLI flags, or Copilot persistence layout.

### 5.3 Shared Runtime Types

Adapter-neutral names describe the factory's interface even though Copilot is the only implementation:

- `AgentRequest`
- `AgentCallbacks`
- `AgentEvent`
- `AgentResult`
- `AgentUsage`
- `CopilotRuntimeConfig`
- `CopilotRuntimeInfo`

These types replace Pi-specific request, result, usage, and tool-tracker types at the `agents.execute()` seam. They do not create a registry or unsupported multi-harness configuration.

### 5.4 Existing Orchestration Responsibilities

`agents.py` continues to own:

1. Agent roster lookup.
2. Prompt rendering.
3. Exact compiled-prompt persistence.
4. Stable phase session-ID lookup.
5. Runtime invocation.
6. Pydantic envelope extraction and validation.
7. Bounded same-session correction turns.
8. Gate execution and bounded gate corrections.
9. Changed-path permission enforcement.
10. Envelope and handoff persistence.
11. Factory-level trace events.

`runner.py`, ADW scripts, gates, prompts, handoff types, quality phases, and final acceptance do not gain Copilot-specific branches.

## 6. Session Model

`agent_map.json` remains the durable mapping from an SSSF agent name to a Copilot session UUID.

- The first call for an agent creates a session and stores its returned ID.
- Later phases and correction turns resume the same session.
- Resume failure is explicit and traceable; it does not silently create an unrelated session.
- One application-level lock protects each session ID from concurrent mutation.
- Disconnect preserves resumable state.
- Destructive session deletion is not part of normal phase cleanup.
- Fork and fleet RPCs remain outside the core path because they are experimental and unnecessary for current ADWs.

The implementation pins `github-copilot-sdk` and records SDK version, runtime version, protocol version, and detected CLI version in trace metadata. Compatibility tests run against those pinned artifacts.

## 7. Event and Completion Model

The runtime subscribes before work begins. Copilot events are normalized into the existing factory vocabulary:

- `agent_start`
- `tool_call`
- `handoff`
- `agent_end`
- `error`

Tool start, update, result, failure, and cancellation events are folded into one normalized tool-call record. Final completion uses the runtime's mechanical idle signal rather than a model-authored completion claim.

Raw Copilot event JSON is retained in the per-session runtime log for diagnosis. Normal SQLite traces exclude raw reasoning content and secrets. Persisted complete events can be replayed; ephemeral deltas are treated as live display data rather than authoritative state.

## 8. Typed Output and Correction

Existing `EnvelopeBase` subclasses remain the output contract. Every call site continues to pair:

1. A concrete Pydantic output type.
2. A matching JSON example in the agent prompt.
3. `output_type=` at the call site.

The runtime returns final assistant text. `agents.execute()` extracts and validates the JSON envelope. Invalid JSON, schema violations, and gate failures produce bounded correction turns in the same Copilot session. Each correction includes the concrete validation errors and requires a complete replacement envelope.

The system never:

- Treats transport JSONL as semantic output validation.
- Converts malformed output into an empty success object.
- Starts a fresh session for a correction.
- Retries indefinitely.

## 9. Tools, Permissions, and Containment

Each configured agent has:

- Copilot model.
- Reasoning effort.
- Context tier.
- Available tools.
- Skills.
- Optional plugin directories.
- Optional MCP servers.
- Repository `writes` patterns.
- Phase, tool, correction, and total timeout budgets.

Copilot receives the narrowest tool set needed for the phase. Permission callbacks and hooks deny operations outside the phase policy where possible. SSSF then independently snapshots repository state and enforces `writes` plus protected files after every call.

The write snapshot remains the final repository policy control because shell access and tool filters do not form a complete containment boundary. Authenticated production execution should run in an isolated worktree or container with restricted network and process limits.

Secrets are supplied through supported Copilot authentication mechanisms and are redacted from logs. The implementation does not copy credential values into prompts, traces, subprocess arguments, or generated configuration.

## 10. Failure Semantics

| Failure | Required behavior |
|---|---|
| Missing SDK/runtime | Fail validation before an agent phase starts |
| Unsupported SDK/runtime protocol | Fail validation with installed and required versions |
| Authentication failure | Fail validation or phase startup with actionable guidance |
| Session resume failure | Fail explicitly; preserve the stored session mapping for diagnosis |
| Malformed envelope | Send a bounded same-session correction |
| Gate violation | Record gate evidence and send a bounded same-session correction |
| Permission breach | Roll back unauthorized changes and fail the phase |
| Phase timeout | Call `session.abort()`, record terminal events, and fail the phase |
| Tool/MCP/hook failure | Preserve the native error and fail or correct according to phase policy |
| Runtime crash | Record the native runtime error and fail the phase |
| Trace persistence failure | Surface the error; do not report successful acceptance |

There is no automatic fallback from the SDK to `copilot -p`.

## 11. Configuration Migration

The generated `sssf.config.yaml` becomes Copilot-only.

Common agent fields:

```yaml
agents:
  planner:
    model: gpt-5.4
    reasoning_effort: high
    context_tier: default
    tools: [view, grep, glob]
    skill_directories: []
    plugin_directories: []
    mcp_servers: []
    writes:
      - specs/**
    timeouts:
      phase_seconds: 1800
      tool_seconds: 300
      correction_seconds: 300
```

The exact defaults must be verified against the pinned SDK and generated runtime during implementation. Configuration parsing rejects Pi fields with a migration-focused error:

- `coding_agent: pi`
- Pi provider names used only by the former harness
- `PI_PATH`
- `PI_MODELS_PATH`
- Pi extension paths
- Pi session-directory options

No hidden compatibility aliases keep Pi configuration working.

## 12. Plugin and Skill Packaging

The canonical distributable layout follows Agent Plugins 1.0:

```text
plugin.json
skills/
  sssf/
    SKILL.md
    scripts/
    references/
    cookbooks/
    templates/
    apps/
com.github.copilot/
  agents/
  commands/
  rules/
  hooks/
    hooks.json
```

Only Copilot-specific behavior belongs under `com.github.copilot/`. The deterministic factory runtime remains in the skill payload and generated target repository.

`SKILL.md` uses standard Agent Skills frontmatter:

- `name`
- `description`
- `license`, when selected for the repository
- `compatibility`
- `metadata`
- `allowed-tools` only if verified as safe and supported

Claude-only frontmatter such as `argument-hint` is removed. Installation and invocation docs use Copilot commands and avoid hard-coded `.claude/skills` paths.

The package must pass the Agent Plugins schema and be loadable from a local directory with Copilot CLI. Duplicate active copies of the `sssf` skill are avoided because skill precedence can silently shadow plugin-provided skills.

## 13. AI Documentation

`ai_docs/` is the agent-readable factual reference set:

```text
ai_docs/
  README.md
  software-factory.md
  copilot-cli.md
  copilot-python-sdk.md
  copilot-sessions-events.md
  copilot-tools-hooks-permissions.md
  copilot-agents-skills-plugins-mcp.md
  pi-capability-baseline.md
  pi-to-copilot-migration-matrix.md
  sssf-architecture.md
  verification-playbook.md
```

Each page contains:

- Scope.
- `verified_on: 2026-09-14`.
- Concise facts needed by an implementation or maintenance agent.
- Exact commands or interfaces only when verified.
- Primary-source links beside the claims they support.
- Known conflicts, experimental surfaces, and version-sensitive behavior.
- A pointer to the authoritative live documentation for refreshes.

The documents are distilled references, not copied documentation. `ai_docs/README.md` routes agents to the smallest relevant page.

## 14. URL Validation

The repository adds:

- `lychee.toml`, based on the conventions in [bossjones/boss-skills](https://github.com/bossjones/boss-skills).
- A fast `just docs-check` target for Markdown and URL validation.
- A `just verify` target that includes URL validation with the rest of the credential-free suite.
- CI that runs the same target.

Lychee configuration must:

- Check Markdown and supported text files.
- Validate HTTPS links.
- Retry transient failures.
- Use explicit exclusions only for documented endpoints that cannot be checked automatically.
- Fail on broken links after retries.
- Produce actionable output suitable for local and CI feedback.

## 15. Verification Strategy

### 15.1 Pre-Implementation Grounding

Before editing runtime code:

1. Pin the target SDK release and runtime protocol.
2. Capture installed `copilot --version` and `copilot --help`.
3. Verify Python SDK create, resume, event, idle, disconnect, and abort interfaces against official source.
4. Verify plugin and skill schemas.
5. Record documentation conflicts in `ai_docs/` rather than choosing a convenient interpretation.

### 15.2 Credential-Free Tests

Tests use fake SDK client, session, event, and runtime objects. Coverage includes:

- Runtime validation.
- Session creation and resume.
- Application-level session locks.
- Early event subscription.
- Event normalization.
- Tool-call folding.
- Final-message extraction.
- Usage mapping.
- Timeout followed by abort.
- Runtime crash and error propagation.
- Envelope parse corrections.
- Gate corrections.
- Same-session retry behavior.
- Permission rollback.
- SQLite and JSONL traces.
- Installer idempotency and force behavior.
- Plugin and skill schema validation.
- ADW acceptance behavior.
- Visualizer compatibility with normalized Copilot events.

### 15.3 Authenticated Smoke Test

An opt-in smoke target:

- Checks supported authentication without printing credentials.
- Starts the pinned runtime.
- Creates a session in a temporary fixture repository.
- Executes one read-only prompt.
- Executes one bounded write prompt.
- Verifies event capture, final envelope parsing, and write enforcement.
- Resumes the session for a correction turn.
- Cleans up the fixture without deleting persistent user sessions.

The smoke test is not required for default CI.

### 15.4 Full Local Verification

Before each implementation commit and before the PR:

1. Formatting.
2. Linting.
3. Static type checking.
4. Unit and integration tests.
5. Plugin schema validation.
6. Skill schema validation.
7. Installer smoke tests.
8. Generated-artifact drift check.
9. Lychee URL validation.
10. Git diff review.

Implementation is not complete until this loop is green.

## 16. Documentation and Code Review Passes

After the first complete implementation:

1. A documentation research reviewer checks every material `ai_docs/` claim, source link, version statement, and uncertainty against primary sources.
2. A runtime/code reviewer checks session lifecycle, abort behavior, permissions, trace compatibility, typed corrections, tests, and removal of Pi coupling.

Material findings are fixed. The full verification loop is rerun after fixes.

## 17. Migration and Compatibility

This is a breaking harness migration.

Preserved:

- ADW names and phase chains where behavior remains valid.
- Typed handoff envelopes.
- Gate contracts.
- Repository write policy.
- Trace tables and primary event names.
- Existing visualizer semantics.
- Final acceptance rules.

Removed:

- Pi executable discovery.
- Pi provider/model catalog resolution.
- Pi JSONL event parsing.
- Pi session directory handling.
- Pi environment variables.
- Pi extensions and `subagents.ts`.
- `coding_agent: pi`.
- Claude Code runtime stub configuration.

Existing generated repositories are not silently rewritten. Migration documentation identifies removed files and fields and provides an explicit update command or manual sequence. Old SQLite traces remain readable; schema additions are nullable and migration-safe.

## 18. Implementation Sequence

1. Create and validate `ai_docs/`.
2. Add Lychee configuration and `just` feedback targets.
3. Add fake Copilot SDK contract fixtures and failing tests.
4. Introduce shared runtime request/result/event types.
5. Implement the SDK-backed Copilot runtime module.
6. Switch `agents.py` validation and execution to Copilot.
7. Update session mapping, tracing, and visualizer compatibility.
8. Migrate configuration, installer templates, environment sample, and cookbooks.
9. Remove Pi and Claude-stub runtime code and Pi-only extensions.
10. Migrate to Agent Plugins 1.0 and standard Agent Skills packaging.
11. Update README and operational references.
12. Run credential-free and authenticated verification.
13. Run independent documentation and runtime review passes.
14. Fix findings and rerun full verification.
15. Create conventional commits, push the branch, and open the PR.

## 19. Git and PR Delivery

The implementation branch is `feat/copilot-software-factory` and targets `main` in `bossjones/super-simple-software-factory`.

Commits are grouped by coherent milestones and use conventional messages. Every commit includes the configured Copilot co-author trailer. Unrelated working-tree changes are not staged.

The PR description includes:

- Architecture rationale.
- Breaking changes.
- Pi removal summary.
- Copilot SDK/runtime versions.
- Plugin and skill packaging changes.
- `ai_docs/` grounding strategy.
- Verification commands and results.
- Authenticated smoke-test status.
- Known SDK/runtime documentation conflicts and experimental surfaces.

## 20. Acceptance Criteria

The port is accepted when all of the following are true:

1. No production runtime path imports, invokes, configures, or documents Pi.
2. Every ADW agent call executes through the official Python Copilot SDK.
3. Session create, resume, correction, timeout, abort, and disconnect behavior has deterministic tests.
4. Existing typed envelopes and gates operate unchanged from ADW call sites.
5. Repository write enforcement remains independent of Copilot tool permissions.
6. SQLite traces and the visualizer show normalized Copilot sessions and tool calls.
7. The repository installs as a Copilot Agent Plugins 1.0 package and Copilot discovers the `sssf` skill.
8. `ai_docs/` covers all research areas required for maintenance and cites valid primary sources.
9. The credential-free `just verify` target passes.
10. Lychee reports no unapproved broken links.
11. The optional authenticated smoke test either passes or is explicitly reported as not run because credentials are unavailable.
12. Two independent review passes have no unresolved material findings.
13. The feature branch is pushed and a PR into `main` is open with complete verification evidence.

## 21. Known Version-Sensitive Risks

- Official SDK documentation contains conflicting statements about default session persistence and caller-generated session IDs. Tests against the pinned runtime are authoritative for this release.
- SDK repository documentation describes general availability while Python package metadata may still label the package alpha. Pinning and compatibility tests are mandatory.
- Fleet and session fork surfaces are experimental and excluded from core execution.
- Runtime headless flags and external-runtime authentication behavior can differ between public CLI help and SDK implementation.
- Hook failures or timeouts may not provide a fail-closed containment boundary.
- CLI, SDK, and bundled runtime releases can drift. SSSF records and verifies all three versions rather than assuming compatibility.
- The public Python SDK does not expose its managed runtime PID. Runtime
  supervision uses SDK abort/stop operations while the existing process table
  tracks the enclosing ADW process.

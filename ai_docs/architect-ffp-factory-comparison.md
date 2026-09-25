# architect-ffp software-factory comparison

verified_on: 2026-09-25

## Scope and method

This compares the checked-out `architect-ffp` repository at
`/Users/malcolm/dev/adobe-ai-factory-summit/architect-ffp` with SSSF's
canonical package under `skills/sssf/`. Claims below are grounded in source
code, skill contracts, or tests. A skill/prompt contract is distinguished from
behavior enforced by code; passing a metadata check is not treated as proof
that the underlying artifact is valid.

## Existing SSSF baseline

SSSF already has a deterministic plan/build/test/review/document workflow,
bounded repair and review loops, a stale-test rerun after a code revision, and
acceptance that requires both successful phases and the workflow's acceptance
condition
([`adw_simple_sdlc.py`](../skills/sssf/templates/adws/adw_simple_sdlc.py):65-304;
[`runner.py`](../skills/sssf/templates/adws/adw_modules/runner.py):151-183).
It persists normalized phase, event, envelope, gate, and session evidence to
SQLite/JSONL and provides a visualizer
([`observability.md`](../skills/sssf/references/observability.md);
[`tracer.py`](../skills/sssf/templates/adws/adw_modules/tracer.py):19-81).
Agent tools, skills, plugins, MCP servers, and write limits are configurable
([`sssf.config.yaml`](../skills/sssf/templates/sssf.config.yaml):2-19).

The comparison therefore does **not** recommend adding basic planning,
review, test repair, tracing, or skill/MCP configuration. The opportunities
are narrower extensions to those existing seams.

## Distinctive architect-ffp capabilities

### 1. Adversarial plan review before implementation

In feature and plan modes, the `archffp` skill inserts an adversarial gate
after analysis and before the parity planner uses the plan; it also describes
adversarial review as a final ship-blocking gate across several modes
(`architect-ffp/skills/archffp/SKILL.md:1076-1123,1175-1176`). The plan
adversary writes a separate review artifact and, on `BLOCK`, causes the
orchestrator to revise the plan and rerun the adversary
(`architect-ffp/agents/archself-adversary.md:83-99`; coverage in
`architect-ffp/tests/test_orchestrator_gates.py:1878-1890`).

**Difference:** SSSF has a post-build reviewer and bounded builder revision
loop, but the standard simple SDLC chain has no adversarial review-and-revise
gate between planning and building
(`skills/sssf/templates/adws/adw_simple_sdlc.py:109-145,184-226`).

### 2. Explicit ship report and architecture-fit acceptance

The architect-ffp run-report builder supplies agent outcomes, visual evidence,
ownership, artifacts, and an optional PR URL to a structured validator
(`architect-ffp/src/scripts/orchestrator_gates.py:1241-1273`). Finish marked
as shipped is rejected unless the architecture-fit result is successful and
accepted (`.../orchestrator_gates.py:1535-1563`). Some artifact contents also
participate in specific ship-path checks (`.../orchestrator_gates.py:1613-1628`).

**Difference:** SSSF records detailed traces and has typed plan/build/review
envelopes, but its standard SDLC acceptance is test success plus reviewer
approval; it does not require a distinct architecture-fit result or emit a
similarly consolidated run/ship report as part of that chain
(`skills/sssf/templates/adws/adw_simple_sdlc.py:242-304`;
`skills/sssf/templates/adws/adw_modules/runner.py:151-183`).

### 3. Failure-targeted E2E reruns

The architect-ffp G3 classifier extracts failures, deduplicates affected spec
files, runs just that set together under load, and classifies the rerun
(`architect-ffp/src/e2e_manager/classifier.py:573-623`). Tests cover a repeated
failure that drops an inbox record and a clean run that does not rerun
(`architect-ffp/tests/e2e_manager/test_classifier_rerun.py:130-180`).

**Difference:** SSSF's simple SDLC reruns its configured test command after a
builder fix and after a successful review revision; the generic quality layer
does not itself classify failing specs and target only those for a diagnostic
rerun (`skills/sssf/templates/adws/adw_simple_sdlc.py:148-180,226-239`;
`skills/sssf/templates/adws/adw_modules/quality.py:153-207`).

### 4. Image-evidence metadata for visual stages—with a limitation

The architect-ffp report validator requires one visual-evidence row for a
successful image-requiring stage, checks stage/model/engine consistency, and
checks that the selected model is image-capable
(`architect-ffp/src/scripts/orchestrator_gates.py:1355-1370,1781-1817`).
Tests cover missing, orphaned, malformed, and mismatched evidence
(`architect-ffp/tests/test_orchestrator_gates.py:1494-1559,1586-1605`).

However, the separate persistence test verifies a prompt/recorder contract,
not that an image was actually captured or that its pixels prove correct
behavior (`architect-ffp/tests/test_artifact_persistence_contract.py:160-184`).
Likewise, report validation requires nonempty artifact strings and allows a
nullable PR URL, but the cited checks do not establish that artifact paths
exist or that a PR URL resolves (`.../orchestrator_gates.py:1831-1844`).
Treat this as a useful manifest/contract pattern, not as proof of visual
correctness.

## Improvement ideas for SSSF

| Priority | Idea | SSSF-shaped implementation | Tradeoff / acceptance signal |
|---|---|---|---|
| 1 | **Optional adversarial plan gate** | Add a configurable plan-review agent/envelope between `plan` and `build`; require cited blocking findings and bounded plan revision/re-review before implementation. Keep the existing post-build reviewer. | More model calls and latency. Measure plan defects caught before code, false blocks, and cost; leave it opt-in or mode-specific initially. |
| 2 | **Explicit ship/architecture result and portable run report** | Preserve the existing SQLite trace, but add a typed terminal report with completed/blocked stages, stop reason, acceptance evidence, artifact links, ownership, and optional PR URL. For repositories that need it, require a separate architecture-fit result before a `shipped` outcome. | Avoid duplicating trace data or making architecture review universal. Validate report shape and gate policy deterministically; do not imply that a path or URL is valid merely because it is a string. |
| 3 | **Targeted E2E failure diagnosis** | Add an optional test-failure classifier that extracts stable test/spec identifiers and reruns only failed cases as a separate diagnostic phase, with deduplication and persisted output. Keep the full configured suite as the acceptance gate. | Classification can be brittle and a passing subset is not a green full suite. Require a full-suite gate for acceptance; test repeated, flaky, and malformed failure reports. |
| 4 | **Verifiable visual-evidence workflow for browser tasks** | Where a target repo has browser tests, require deterministic capture/recording outputs plus a manifest linking the run, stage, browser/engine, and artifact; validate files exist and are readable before allowing visual-evidence acceptance. | More storage and browser setup. Start only for workflows that need UI evidence, and do not treat model capability metadata or a prompt instruction as proof that a screenshot was captured or is correct. |

## Recommendation

Start with **#1** as a small optional pre-build gate, then **#2** as an
operator-facing/CI report that composes existing trace evidence rather than
replacing it. Consider **#3** and **#4** only for repositories whose expensive
E2E/browser checks justify the extra classification and artifact lifecycle.
No issues have been created; the report is intended for review before any
implementation or GitHub issue creation.

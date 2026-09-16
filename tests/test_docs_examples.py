"""The docs/examples mocks must match the runtime they illustrate.

Every mock envelope is validated against the real output type in
adw_modules.data_types, every gate name against adw_modules.gates, and every
event against EventRecord. If a model gains a required field or a gate is
renamed, the examples fail here instead of drifting silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_args

import pytest
from adw_modules import data_types, gates
from adw_modules.data_types import (
    EnvelopeBase,
    EventRecord,
    GateCheck,
    PhaseKind,
    PhaseStatus,
    QualityResult,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs/examples"
RECORD_KEYS = {"agent_name", "purpose", "output_type", "attempt"}
ADW_ID = re.compile(r"^[0-9a-f]{8}$")
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)")

EXAMPLE_DIRS = sorted(p for p in EXAMPLES.iterdir() if p.is_dir())


def _mock_dir(example: Path) -> Path:
    mocks = [p for p in (example / "mock").iterdir() if p.is_dir()]
    assert len(mocks) == 1, f"{example.name}: expected exactly one mock/<adw_id>/ directory"
    assert ADW_ID.match(mocks[0].name), f"{example.name}: {mocks[0].name} is not an adw_id"
    return mocks[0]


def test_examples_index_links_every_example():
    text = (EXAMPLES / "README.md").read_text()
    for example in EXAMPLE_DIRS:
        assert f"({example.name}/request.md)" in text, f"README does not link {example.name}"


def test_examples_local_links_resolve():
    missing = []
    for source in EXAMPLES.rglob("*.md"):
        for target in LOCAL_LINK.findall(source.read_text()):
            if "://" in target:
                continue
            if not (source.parent / target).resolve().exists():
                missing.append(f"{source.relative_to(ROOT)} -> {target}")
    assert missing == []


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_example_has_request_and_mock(example: Path):
    request = example / "request.md"
    assert request.is_file()
    assert request.read_text().startswith("# "), "request.md starts with a title"
    mock = _mock_dir(example)
    assert (mock / "agent_map.json").is_file()
    assert (mock / "sessions.json").is_file()
    assert (mock / "gate_results.json").is_file()


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_mock_envelopes_validate_against_output_types(example: Path):
    mock = _mock_dir(example)
    envelopes = sorted(mock.glob("*/envelope.json"))
    assert envelopes, f"{example.name}: no <agent>/envelope.json"
    for path in envelopes:
        record = json.loads(path.read_text())
        assert RECORD_KEYS <= set(record), f"{path}: missing record keys"
        assert record["agent_name"] == path.parent.name
        output_type = getattr(data_types, record["output_type"])
        assert issubclass(output_type, EnvelopeBase)
        payload = {k: v for k, v in record.items() if k not in RECORD_KEYS}
        unknown = set(payload) - set(output_type.model_fields)
        assert not unknown, f"{path}: fields not on {output_type.__name__}: {sorted(unknown)}"
        output_type.model_validate(payload)


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_mock_agent_map_matches_envelopes(example: Path):
    mock = _mock_dir(example)
    agent_map = json.loads((mock / "agent_map.json").read_text())
    agents = {p.parent.name for p in mock.glob("*/envelope.json")}
    assert set(agent_map) == agents
    for entry in agent_map.values():
        assert set(entry) == {"session_id", "model", "runtime"}
        assert entry["runtime"] == "copilot"
        assert "/" not in entry["model"], "Copilot model IDs are unqualified"


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_mock_sessions_rows_are_well_formed(example: Path):
    mock = _mock_dir(example)
    rows = json.loads((mock / "sessions.json").read_text())
    session = rows["session"]
    assert session["adw_id"] == mock.name
    assert (ROOT / "skills/sssf/templates/adws" / f"{session['adw_name']}.py").is_file()
    agent_map = json.loads((mock / "agent_map.json").read_text())
    phases = rows["phases"]
    assert [p["seq"] for p in phases] == list(range(1, len(phases) + 1))
    for phase in phases:
        assert phase["kind"] in get_args(PhaseKind)
        assert phase["status"] in get_args(PhaseStatus)
        if phase["kind"] == "agent":
            assert phase["owner"] in agent_map, f"{phase['name']} owner not in agent_map"


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_mock_gate_results_name_real_gates(example: Path):
    mock = _mock_dir(example)
    phase_names = {p["name"] for p in json.loads((mock / "sessions.json").read_text())["phases"]}
    for row in json.loads((mock / "gate_results.json").read_text()):
        assert row["phase"] in phase_names
        assert callable(getattr(gates, row["gate"]))
        checks = [GateCheck.model_validate(c) for c in row["checks"]]
        violations = [f"{c.item}: {c.note or 'failed'}" for c in checks if not c.ok]
        assert row["violations"] == violations
        assert row["passed"] == (not violations)


@pytest.mark.parametrize("example", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_mock_events_and_quality_results_validate(example: Path):
    mock = _mock_dir(example)
    events = mock / "events.jsonl"
    if events.is_file():
        for line in events.read_text().splitlines():
            record = EventRecord.model_validate(json.loads(line))
            assert record.adw_id == mock.name
    quality = mock / "quality_result.json"
    if quality.is_file():
        QualityResult.model_validate(json.loads(quality.read_text()))

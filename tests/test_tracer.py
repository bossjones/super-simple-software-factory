from __future__ import annotations

import sqlite3
from pathlib import Path

from adw_modules.data_types import AgentConfig, EventRecord, PromptEngineering, RuntimeInfo
from adw_modules.tracer import Tracer


def agent_config() -> AgentConfig:
    return AgentConfig(
        name="builder",
        prompt_engineering=PromptEngineering(system="system.md", user="user.md"),
    )


def test_agent_session_row_records_copilot_runtime_metadata(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path / "sssf.db", tmp_path / "events.jsonl")

    tracer.session_start("run-1", "engineer")
    tracer.agent_session_row(
        "run-1",
        agent_config(),
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
        "select coding_agent, sdk_version, runtime_version, protocol_version, cli_version "
        "from agent_sessions where adw_id='run-1'"
    ).fetchone()
    assert tuple(row) == ("copilot", "1.0.13", "1.0.84", "3", "1.0.84-5")


def test_agent_session_row_refreshes_runtime_metadata_on_reuse(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path / "sssf.db", tmp_path / "events.jsonl")
    tracer.session_start("run-1", "engineer")
    tracer.agent_session_row(
        "run-1",
        agent_config(),
        "session-1",
        runtime=RuntimeInfo(
            sdk_version="old-sdk",
            runtime_version="old-runtime",
            protocol_version="2",
            cli_version="old-cli",
        ),
    )

    tracer.agent_session_row(
        "run-1",
        agent_config(),
        "session-2",
        runtime=RuntimeInfo(
            sdk_version="new-sdk",
            runtime_version="new-runtime",
            protocol_version="3",
            cli_version="new-cli",
        ),
    )

    row = tracer.conn.execute(
        "select session_id, sdk_version, runtime_version, protocol_version, cli_version "
        "from agent_sessions where adw_id='run-1'"
    ).fetchone()
    assert tuple(row) == ("session-2", "new-sdk", "new-runtime", "3", "new-cli")


def test_old_agent_sessions_rows_survive_runtime_column_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "sssf.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sessions (adw_id TEXT PRIMARY KEY);
        CREATE TABLE agent_sessions (
          adw_id TEXT,
          agent TEXT,
          coding_agent TEXT,
          model TEXT,
          session_id TEXT,
          created_at TEXT,
          last_used_at TEXT,
          PRIMARY KEY (adw_id, agent)
        );
        INSERT INTO sessions (adw_id) VALUES ('legacy-run');
        INSERT INTO agent_sessions (
          adw_id, agent, coding_agent, model, session_id, created_at, last_used_at
        ) VALUES (
          'legacy-run', 'builder', 'pi', 'legacy-model', 'legacy-session',
          '2026-09-14T00:00:00+00:00', '2026-09-14T00:00:01+00:00'
        );
        """
    )
    conn.close()

    tracer = Tracer(db_path, tmp_path / "events.jsonl")

    columns = {row[1] for row in tracer.conn.execute("PRAGMA table_info(agent_sessions)")}
    assert {"sdk_version", "runtime_version", "protocol_version", "cli_version"} <= columns
    row = tracer.conn.execute(
        "select coding_agent, model, session_id, sdk_version, runtime_version, "
        "protocol_version, cli_version from agent_sessions where adw_id='legacy-run'"
    ).fetchone()
    assert tuple(row) == (
        "pi",
        "legacy-model",
        "legacy-session",
        None,
        None,
        None,
        None,
    )


def test_reusing_legacy_agent_session_row_refreshes_copilot_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "sssf.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sessions (adw_id TEXT PRIMARY KEY);
        CREATE TABLE agent_sessions (
          adw_id TEXT,
          agent TEXT,
          coding_agent TEXT,
          model TEXT,
          session_id TEXT,
          created_at TEXT,
          last_used_at TEXT,
          PRIMARY KEY (adw_id, agent)
        );
        INSERT INTO sessions (adw_id) VALUES ('legacy-run');
        INSERT INTO agent_sessions (
          adw_id, agent, coding_agent, model, session_id, created_at, last_used_at
        ) VALUES (
          'legacy-run', 'builder', 'pi', 'legacy-model', 'legacy-session',
          '2026-09-14T00:00:00+00:00', '2026-09-14T00:00:01+00:00'
        );
        """
    )
    conn.close()

    tracer = Tracer(db_path, tmp_path / "events.jsonl")
    tracer.agent_session_row(
        "legacy-run",
        agent_config(),
        "copilot-session",
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
        "select coding_agent, model, session_id, context_tokens, context_window, "
        "sdk_version, runtime_version, protocol_version, cli_version "
        "from agent_sessions where adw_id='legacy-run'"
    ).fetchone()
    assert tuple(row) == (
        "copilot",
        "gpt-5.4",
        "copilot-session",
        100,
        1000,
        "1.0.13",
        "1.0.84",
        "3",
        "1.0.84-5",
    )


def test_tracer_redacts_credentials_from_jsonl_and_sqlite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configured_token = "github_pat_configured_secret_value"
    nested_secret = "database-password-value"
    monkeypatch.setenv("GITHUB_TOKEN", configured_token)
    tracer = Tracer(tmp_path / "sssf.db", tmp_path / "events.jsonl")

    tracer.event(
        EventRecord(
            adw_id="run-1",
            type="tool_call",
            payload={
                "args": {
                    "path": "README.md",
                    "token": configured_token,
                    "nested": {"password": nested_secret},
                },
                "result": f"Bearer {configured_token}",
            },
        )
    )

    jsonl = (tmp_path / "events.jsonl").read_text()
    sqlite_payload = tracer.conn.execute("SELECT payload_json FROM events").fetchone()[0]
    persisted = jsonl + sqlite_payload
    assert configured_token not in persisted
    assert nested_secret not in persisted
    assert "README.md" in persisted
    assert "[REDACTED]" in persisted

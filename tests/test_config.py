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

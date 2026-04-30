from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import phase2_crews  # noqa: E402
import phase3_holding  # noqa: E402


def test_phase2_allowlist_accepts_config_before_subcommand() -> None:
    command = "python scripts/tool_router.py --config config/projects.yaml run_holding --mode heartbeat"
    assert phase2_crews._is_allowlisted_tool_router_command(command) is True


def test_phase3_allowlist_accepts_config_before_subcommand() -> None:
    command = "python scripts/tool_router.py --config config/projects.yaml run_holding --mode heartbeat"
    assert phase3_holding._is_allowlisted_tool_router_command(command) is True


def test_phase2_build_llm_blocks_non_ollama_model() -> None:
    llm, warning = phase2_crews._build_llm(
        {
            "phase2": {
                "crewai": {
                    "ollama_model": "gpt-4o-mini",
                    "ollama_base_url": "http://127.0.0.1:11434",
                }
            }
        }
    )
    assert llm is None
    assert isinstance(warning, str)
    assert "blocked by R1" in warning


def test_phase3_build_llm_blocks_nonlocal_base_url() -> None:
    llm, warning = phase3_holding._build_llm(
        {
            "phase2": {"crewai": {"ollama_model": "ollama/llama3.2:latest"}},
            "phase3": {"ceo": {"ollama_model": "ollama/llama3.2:latest", "ollama_base_url": "https://api.openai.com"}},
        }
    )
    assert llm is None
    assert isinstance(warning, str)
    assert "blocked by R1" in warning

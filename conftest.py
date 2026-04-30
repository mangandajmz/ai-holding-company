from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath)).as_posix()
        name = item.name

        if path.endswith("mt5-agentic-desk/tests/test_mt5_connection.py") or path.endswith(
            "mt5-agentic-desk/tests/test_crewai_ollama.py"
        ):
            item.add_marker(pytest.mark.smoke)
            item.add_marker(pytest.mark.integration)
            continue

        if path.endswith("mt5-agentic-desk/tests/test_dashboard.py"):
            item.add_marker(pytest.mark.smoke)
            item.add_marker(pytest.mark.unit)
            continue

        item.add_marker(pytest.mark.unit)

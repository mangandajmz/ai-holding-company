"""Tests for Developer Tool scope gating and approval workflow."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import developer_tool  # noqa: E402


class TestScopeGating:
    """Test R8 scope gate enforcement."""

    def test_allowed_path_inside_ai_holding_company(self) -> None:
        assert developer_tool.is_path_allowed("scripts/test.py")
        assert developer_tool.is_path_allowed("crews/content_studio.yaml")
        assert developer_tool.is_path_allowed("config/targets.yaml")

    def test_disallowed_path_outside_ai_holding_company(self) -> None:
        assert not developer_tool.is_path_allowed("../../outside.py")
        assert not developer_tool.is_path_allowed("/etc/passwd")

    def test_protected_files_blocked(self) -> None:
        assert not developer_tool.is_path_allowed(".env")
        assert not developer_tool.is_path_allowed(".gitignore")
        assert not developer_tool.is_path_allowed("PLAN.md")


class TestCodeValidation:
    """Test code scope validation."""

    def test_valid_code_passes(self) -> None:
        result = developer_tool.validate_code_scope("print('hello')")
        assert result["ok"] is True
        assert result["safe_to_deploy"] is True

    def test_code_with_disallowed_path_fails(self) -> None:
        result = developer_tool.validate_code_scope('open("../../outside.txt")')
        assert result["ok"] is False
        assert len(result["violations"]) > 0

    def test_path_function_caught(self) -> None:
        result = developer_tool.validate_code_scope('Path("../../../etc/passwd")')
        assert result["ok"] is False


class TestApprovalWorkflow:
    """Test CEO approval workflow."""

    def test_submit_for_approval_returns_id(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", tmp_path / "pending.jsonl")
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr(developer_tool, "_DEFAULT_DEPLOY_FILE", tmp_path / "generated.py")

        result = developer_tool.submit_for_approval("test task", "print('test')")
        assert result["ok"] is True
        assert "approval_id" in result
        assert result["status"] == "PENDING_CEO_APPROVAL"

    def test_run_developer_tool_submit_action(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", tmp_path / "pending.jsonl")
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr(developer_tool, "_DEFAULT_DEPLOY_FILE", tmp_path / "generated.py")

        result = developer_tool.run_developer_tool({}, task="test task", action="submit")
        assert result["ok"] is True
        assert result["status"] == "PENDING_CEO_APPROVAL"

    def test_run_developer_tool_approve_action(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "ROOT", tmp_path)
        pending = tmp_path / "pending.jsonl"
        audit = tmp_path / "audit.jsonl"
        target = tmp_path / "generated.py"
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", pending)
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", audit)
        monkeypatch.setattr(developer_tool, "_DEFAULT_DEPLOY_FILE", target)
        monkeypatch.setattr(developer_tool, "_infer_target_file", lambda _task: target)

        sub = developer_tool.run_developer_tool({}, task="test task", action="submit")
        approval_id = sub["approval_id"]
        out = developer_tool.run_developer_tool({}, approval_id=approval_id, action="approve")
        assert out["ok"] is True
        assert out["status"] == "DEPLOYED"
        assert target.exists()

    def test_approve_rejected_syntax_does_not_write_target(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "ROOT", tmp_path)
        pending = tmp_path / "pending.jsonl"
        audit = tmp_path / "audit.jsonl"
        target = tmp_path / "generated.py"
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", pending)
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", audit)
        monkeypatch.setattr(developer_tool, "_DEFAULT_DEPLOY_FILE", target)
        monkeypatch.setattr(developer_tool, "_infer_target_file", lambda _task: target)

        sub = developer_tool.submit_for_approval("test task", "def broken(:\n    pass\n")
        out = developer_tool.run_developer_tool({}, approval_id=sub["approval_id"], action="approve")

        assert out["ok"] is False
        assert out["status"] == "REJECTED_SYNTAX"
        assert not target.exists()

    def test_run_developer_tool_deny_action(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", tmp_path / "pending.jsonl")
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr(developer_tool, "_DEFAULT_DEPLOY_FILE", tmp_path / "generated.py")

        sub = developer_tool.run_developer_tool({}, task="test task", action="submit")
        approval_id = sub["approval_id"]
        den = developer_tool.run_developer_tool({}, approval_id=approval_id, action="deny")
        assert den["ok"] is True
        assert den["status"] == "DENIED"


class TestDeveloperToolMainFunction:
    """Test main orchestration."""

    def test_status_action_returns_pending(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(developer_tool, "_PENDING_FILE", tmp_path / "pending.jsonl")
        monkeypatch.setattr(developer_tool, "_AUDIT_FILE", tmp_path / "audit.jsonl")
        result = developer_tool.run_developer_tool({}, action="status")
        assert result["ok"] is True
        assert "pending_count" in result

    def test_invalid_action_rejected(self) -> None:
        result = developer_tool.run_developer_tool({}, action="invalid_action")
        assert result["ok"] is False

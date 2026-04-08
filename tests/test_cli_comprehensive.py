"""Comprehensive tests for CLI module."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.cli import cmd_dashboard, cmd_projects, cmd_run, cmd_status, cmd_unregister, main
from lingflow_plus.project_manager import ProjectContext


class TestCmdStatus:
    def test_outputs_json(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.status.return_value = {"version": "0.1.0", "projects": []}
            cmd_status(MagicMock())
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out


class TestCmdProjects:
    def test_no_projects(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.list.return_value = []
            cmd_projects(MagicMock())
        captured = capsys.readouterr()
        assert "No projects" in captured.out

    def test_with_projects(self, capsys):
        ctx = ProjectContext(name="LingFlow", path="/tmp/lf", description="Main project")
        ctx.git_status = MagicMock(return_value={"branch": "master", "dirty_files": 0})
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.list.return_value = [ctx]
            cmd_projects(MagicMock())
        captured = capsys.readouterr()
        assert "LingFlow" in captured.out

    def test_with_session(self, capsys):
        ctx = ProjectContext(name="LF", path="/tmp/lf", terminal_session="sess-123")
        ctx.git_status = MagicMock(return_value={"branch": "main", "dirty_files": 2})
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.list.return_value = [ctx]
            cmd_projects(MagicMock())
        captured = capsys.readouterr()
        assert "sess-123" in captured.out


class TestCmdUnregister:
    def test_success(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.unregister.return_value = True
            cmd_unregister(MagicMock(name="TestProj"))
        captured = capsys.readouterr()
        assert "Unregistered" in captured.out

    def test_not_found(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.unregister.return_value = False
            args = MagicMock()
            args.name = "MissingProj"
            cmd_unregister(args)
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestCmdDashboard:
    def test_dashboard_output(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.dashboard.return_value = [
                {"name": "LingFlow", "git": {"branch": "main", "dirty_files": 0}, "valid": True},
                {"name": "Bad", "git": {"branch": "?", "dirty_files": 5}, "valid": False},
            ]
            instance.token_quota.get_status.return_value = {"window_used": 1000, "window_total": 5000000}
            cmd_dashboard(MagicMock())
        captured = capsys.readouterr()
        assert "LingFlow" in captured.out
        assert "Token" in captured.out


class TestCmdRun:
    def test_file_not_found(self, tmp_path):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            args = MagicMock()
            args.workflow = str(tmp_path / "nonexistent.yaml")
            with pytest.raises(SystemExit) as exc_info:
                cmd_run(args)
            assert exc_info.value.code == 1

    def test_successful_run(self, tmp_path, capsys):
        wf = tmp_path / "workflow.yaml"
        wf.write_text("tasks: []")
        r1 = MagicMock()
        r1.success = True
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.run_workflow_file.return_value = {"t1": r1}
            args = MagicMock()
            args.workflow = str(wf)
            cmd_run(args)
        captured = capsys.readouterr()
        assert "1 success" in captured.out
        assert "0 failed" in captured.out


class TestMainEntry:
    def test_main_with_argv(self, capsys):
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.list.return_value = []
            main(["projects"])
        captured = capsys.readouterr()
        assert "No projects" in captured.out

    def test_main_none_argv_shows_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0

"""LingFlow+ P2 tests: coordinator, project_manager session persistence, cli, scheduler."""
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.coordinator import LingFlowPlus
from lingflow_plus.project_manager import ProjectContext, ProjectManager
from lingflow_plus.quality_gate import QualityGate


@pytest.fixture
def tmp_projects(tmp_path):
    projects = {}
    for name in ["LingFlow", "LingClaude"]:
        p = tmp_path / name
        p.mkdir()
        (p / ".git").mkdir()
        (p / "README.md").write_text(f"# {name}")
        projects[name] = str(p)
    return projects


@pytest.fixture
def lf(tmp_path):
    return LingFlowPlus(state_dir=str(tmp_path / "state"))


# ── P2-1: Coordinator dynamic token estimation ──


class TestCoordinatorTokenEstimation:
    def test_estimate_with_context(self):
        task = MagicMock()
        task.context = {"target": "src/main.py", "query": "refactor this function"}
        est = LingFlowPlus._estimate_tokens(task)
        assert est >= 200
        assert est != 500

    def test_estimate_with_description_only(self):
        task = MagicMock(spec=[])
        task.description = "Run full test suite for the project"
        est = LingFlowPlus._estimate_tokens(task)
        assert est >= 200

    def test_estimate_fallback(self):
        task = MagicMock(spec=[])
        est = LingFlowPlus._estimate_tokens(task)
        assert est == 500

    def test_estimate_minimum(self):
        task = MagicMock()
        task.context = {"target": "a"}
        est = LingFlowPlus._estimate_tokens(task)
        assert est >= 200


# ── P2-2: ProjectManager terminal_session persistence ──


class TestSessionPersistence:
    def test_bind_session_roundtrip(self, tmp_projects, tmp_path):
        registry = str(tmp_path / "sess_test.json")
        pm1 = ProjectManager(registry_path=registry)
        pm1.register("LingFlow", tmp_projects["LingFlow"])
        pm1.bind_session("LingFlow", "session-abc-123")

        pm2 = ProjectManager(registry_path=registry)
        ctx = pm2.get("LingFlow")
        assert ctx is not None
        assert ctx.terminal_session == "session-abc-123"

    def test_no_session_roundtrip(self, tmp_projects, tmp_path):
        registry = str(tmp_path / "no_sess.json")
        pm1 = ProjectManager(registry_path=registry)
        pm1.register("LingFlow", tmp_projects["LingFlow"])

        pm2 = ProjectManager(registry_path=registry)
        ctx = pm2.get("LingFlow")
        assert ctx is not None
        assert ctx.terminal_session is None

    def test_session_in_status(self, tmp_projects, tmp_path):
        registry = str(tmp_path / "status_sess.json")
        pm = ProjectManager(registry_path=registry)
        pm.register("LingFlow", tmp_projects["LingFlow"])
        pm.bind_session("LingFlow", "s-456")
        status = pm.status("LingFlow")
        assert status["terminal_session"] == "s-456"

    def test_json_contains_terminal_session(self, tmp_projects, tmp_path):
        registry = str(tmp_path / "json_sess.json")
        pm = ProjectManager(registry_path=registry)
        pm.register("LingFlow", tmp_projects["LingFlow"])
        pm.bind_session("LingFlow", "session-xyz")

        with open(registry) as f:
            data = json.load(f)
        assert data["LingFlow"]["terminal_session"] == "session-xyz"


# ── Coordinator status and quality_check ──


class TestCoordinatorStatus:
    def test_status_structure(self, lf):
        s = lf.status()
        assert "version" in s
        assert "projects" in s
        assert "token_quota" in s
        assert "rate_limiter" in s
        assert "context_budget" in s
        assert "routes" in s

    def test_quality_check_clean(self, lf):
        report = lf.quality_check(["src/main.py", "tests/test_main.py"])
        assert report.passed is True

    def test_quality_check_dirty(self, lf):
        report = lf.quality_check([".env", "secret_key.pem"])
        assert report.passed is False
        assert len(report.critical_issues) > 0


# ── CLI tests ──


class TestCLI:
    def test_version(self, capsys):
        from lingflow_plus.cli import main
        main(["version"])
        captured = capsys.readouterr()
        assert "LingFlow+" in captured.out

    def test_register_and_unregister(self, tmp_path, capsys):
        from lingflow_plus.cli import main
        proj = tmp_path / "TestProj"
        proj.mkdir()
        (proj / ".git").mkdir()
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.project_manager.register.return_value = ProjectContext(
                name="TestProj", path=str(proj)
            )
            instance.project_manager.unregister.return_value = True
            main(["register", "TestProj", str(proj)])
            main(["unregister", "TestProj"])

    def test_no_command_shows_help(self, capsys):
        from lingflow_plus.cli import main
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0

    def test_review_command(self, capsys):
        from lingflow_plus.cli import main
        from lingflow_plus.quality_gate import QualityReport
        with patch("lingflow_plus.cli.LingFlowPlus") as MockLF:
            instance = MockLF.return_value
            instance.quality_check.return_value = QualityReport(
                score=85,
                passed=True,
                dimensions={"file_check": 85},
                critical_issues=[],
                warnings=[],
                summary="OK",
            )
            main(["review", "src/main.py"])
        captured = capsys.readouterr()
        assert "85" in captured.out


# ── Scheduler unit tests (no LingFlow dependency) ──


class TestSchedulerStatus:
    def test_group_by_project(self):
        from lingflow_plus.scheduler import MultiProjectScheduler
        with patch("lingflow_plus.scheduler.ProjectManager"):
            sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
            sched.project_manager = MagicMock()
            sched.coordinator = MagicMock()
            sched.max_projects_parallel = 3
            sched._statuses = {}
            sched._results = {}
            sched._progress_callbacks = []

        t1 = MagicMock()
        t1.project = "LingFlow"
        t2 = MagicMock()
        t2.project = "LingClaude"
        t3 = MagicMock()
        t3.project = "LingFlow"

        groups = sched._group_by_project([t1, t2, t3])
        assert len(groups) == 2
        assert len(groups["LingFlow"]) == 2
        assert len(groups["LingClaude"]) == 1

    def test_group_by_project_default(self):
        from lingflow_plus.scheduler import MultiProjectScheduler
        with patch("lingflow_plus.scheduler.ProjectManager"):
            sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
            sched.project_manager = MagicMock()
            sched.coordinator = MagicMock()
            sched.max_projects_parallel = 3
            sched._statuses = {}
            sched._results = {}
            sched._progress_callbacks = []

        t = MagicMock()
        t.project = None
        groups = sched._group_by_project([t])
        assert "default" in groups

    def test_get_status_empty(self):
        from lingflow_plus.scheduler import MultiProjectScheduler
        with patch("lingflow_plus.scheduler.ProjectManager"):
            sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
            sched.project_manager = MagicMock()
            sched.coordinator = MagicMock()
            sched.max_projects_parallel = 3
            sched._statuses = {}
            sched._results = {}
            sched._progress_callbacks = []

        status = sched.get_status()
        assert status["total_tasks"] == 0
        assert status["total_completed"] == 0

    def test_on_progress(self):
        from lingflow_plus.scheduler import MultiProjectScheduler
        with patch("lingflow_plus.scheduler.ProjectManager"):
            sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
            sched.project_manager = MagicMock()
            sched.coordinator = MagicMock()
            sched.max_projects_parallel = 3
            sched._statuses = {}
            sched._results = {}
            sched._progress_callbacks = []

        cb = MagicMock()
        sched.on_progress(cb)
        assert cb in sched._progress_callbacks

    def test_execute_async_empty(self):
        from lingflow_plus.scheduler import MultiProjectScheduler
        import asyncio
        with patch("lingflow_plus.scheduler.ProjectManager"):
            sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
            sched.project_manager = MagicMock()
            sched.coordinator = MagicMock()
            sched.max_projects_parallel = 3
            sched._statuses = {}
            sched._results = {}
            sched._progress_callbacks = []

        result = asyncio.run(sched.execute_async([]))
        assert result == {}


# ── ProjectContext edge cases ──


class TestProjectContextEdgeCases:
    def test_is_valid_nonexistent(self):
        ctx = ProjectContext(name="x", path="/nonexistent/path")
        assert ctx.is_valid() is False

    def test_is_valid_not_git(self, tmp_path):
        ctx = ProjectContext(name="x", path=str(tmp_path))
        assert ctx.is_valid() is False

    def test_is_valid_git_repo(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        ctx = ProjectContext(name="x", path=str(tmp_path))
        assert ctx.is_valid() is True

    def test_git_status_no_git(self, tmp_path):
        ctx = ProjectContext(name="x", path=str(tmp_path))
        status = ctx.git_status()
        assert "branch" in status

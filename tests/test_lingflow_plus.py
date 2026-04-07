"""LingFlow+ 测试套件"""
import subprocess
import tempfile

import pytest

from lingflow_plus.constraints import (
    ContextBudget,
    FileLock,
    RateLimiter,
    TokenQuotaManager,
)
from lingflow_plus.project_manager import ProjectContext, ProjectManager
from lingflow_plus.quality_gate import QualityGate
from lingflow_plus.tool_router import AgentTarget, ToolRouter


# ── Fixtures ──


@pytest.fixture
def tmp_projects(tmp_path):
    projects = {}
    for name in ["LingFlow", "LingClaude", "LingYi"]:
        p = tmp_path / name
        p.mkdir()
        (p / ".git").mkdir()
        (p / "README.md").write_text(f"# {name}")
        projects[name] = str(p)
    return projects


@pytest.fixture
def pm(tmp_projects, tmp_path):
    registry = str(tmp_path / "test_projects.json")
    manager = ProjectManager(registry_path=registry)
    for name, path in tmp_projects.items():
        manager.register(name, path, description=f"Test {name}")
    return manager


# ── ProjectManager ──


class TestProjectManager:
    def test_register_and_get(self, pm):
        ctx = pm.get("LingFlow")
        assert ctx is not None
        assert ctx.name == "LingFlow"
        assert "LingFlow" in ctx.path

    def test_list(self, pm):
        projects = pm.list()
        assert len(projects) == 3
        assert {p.name for p in projects} == {"LingFlow", "LingClaude", "LingYi"}

    def test_unregister(self, pm):
        assert pm.unregister("LingClaude") is True
        assert pm.get("LingClaude") is None
        assert len(pm.list()) == 2

    def test_persistence(self, tmp_projects, tmp_path):
        registry = str(tmp_path / "persist_test.json")
        pm1 = ProjectManager(registry_path=registry)
        pm1.register("LingFlow", tmp_projects["LingFlow"])
        pm2 = ProjectManager(registry_path=registry)
        assert pm2.get("LingFlow") is not None

    def test_git_status(self, pm, tmp_projects):
        p = tmp_projects["LingFlow"]
        subprocess.run(["git", "init"], cwd=p, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=p, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=p, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=p, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=p, capture_output=True)
        status = pm.status("LingFlow")
        assert status["git"]["valid"] is True
        assert status["git"]["branch"] in ("master", "main")

    def test_invalid_path(self, pm):
        with pytest.raises(ValueError):
            pm.register("bad", "/nonexistent/path")

    def test_dashboard(self, pm):
        dash = pm.dashboard()
        assert len(dash) == 3
        assert all("git" in d for d in dash)

    def test_bind_session(self, pm):
        pm.bind_session("LingFlow", "session-123")
        ctx = pm.get("LingFlow")
        assert ctx.terminal_session == "session-123"


# ── TokenQuotaManager ──


class TestTokenQuotaManager:
    def test_allocate_and_consume(self):
        qm = TokenQuotaManager(window_tokens=10000)
        qm.allocate("test", 5000)
        assert qm.consume("test", 1000) is True
        assert qm.consume("test", 5000) is False

    def test_no_budget(self):
        qm = TokenQuotaManager()
        assert qm.consume("unknown", 100) is False

    def test_status(self):
        qm = TokenQuotaManager(window_tokens=10000)
        qm.allocate("proj1", 5000)
        qm.consume("proj1", 1000)
        status = qm.get_status()
        assert status["window_used"] == 1000
        assert status["projects"]["proj1"]["remaining"] == 4000


# ── RateLimiter ──


class TestRateLimiter:
    def test_acquire(self):
        rl = RateLimiter(max_rpm=10, max_concurrent=5)
        wait = rl.acquire()
        assert wait == 0.0
        rl.release()

    def test_concurrent_limit(self):
        rl = RateLimiter(max_rpm=100, max_concurrent=1)
        rl.acquire()
        wait = rl.acquire()
        assert wait > 0
        rl.release()

    def test_backoff(self):
        rl = RateLimiter()
        rl.trigger_backoff(0.1)
        wait = rl.acquire()
        assert wait > 0

    def test_status(self):
        rl = RateLimiter(max_rpm=60, max_concurrent=5)
        status = rl.get_status()
        assert status["rpm_limit"] == 60
        assert status["max_concurrent"] == 5


# ── FileLock ──


class TestFileLock:
    def test_acquire_release(self, tmp_path):
        fl = FileLock(locks_dir=str(tmp_path / "locks"))
        assert fl.acquire("/tmp/test.py") is True
        fl.release("/tmp/test.py")

    def test_contention(self, tmp_path):
        fl = FileLock(locks_dir=str(tmp_path / "locks"))
        assert fl.acquire("/tmp/contention.py", timeout=1) is True
        fl2 = FileLock(locks_dir=str(tmp_path / "locks"))
        assert fl2.acquire("/tmp/contention.py", timeout=0.5) is False
        fl.release("/tmp/contention.py")


# ── ContextBudget ──


class TestContextBudget:
    def test_track_and_compress(self):
        cb = ContextBudget(default_limit=1000)
        cb.track("proj1", 800)
        assert cb.should_compress("proj1") is False
        cb.track("proj1", 100)
        assert cb.should_compress("proj1") is True

    def test_custom_limit(self):
        cb = ContextBudget()
        cb.set_limit("big", 50000)
        cb.track("big", 10000)
        assert cb.should_compress("big") is False

    def test_status(self):
        cb = ContextBudget(default_limit=1000)
        cb.track("proj1", 500)
        status = cb.get_status()
        assert "proj1" in status
        assert status["proj1"]["used"] == 500


# ── ToolRouter ──


class TestToolRouter:
    def test_exact_match(self):
        router = ToolRouter()
        rule = router.route("bash")
        assert rule is not None
        assert rule.target == AgentTarget.LINGXI

    def test_substring_match(self):
        router = ToolRouter()
        result = router.route_task("code_review_python")
        assert result["routed"] is True
        assert result["target"] == AgentTarget.LINGKE.value

    def test_no_match(self):
        router = ToolRouter()
        result = router.route_task("unknown_task_xyz")
        assert result["routed"] is False

    def test_list_routes(self):
        router = ToolRouter()
        routes = router.list_routes()
        assert len(routes) > 0

    def test_knowledge_search_routes_to_lingzhi_only(self):
        router = ToolRouter()
        rule = router.route("knowledge_search")
        assert rule is not None
        assert rule.target == AgentTarget.LINGZHI
        assert rule.priority == 10

    def test_short_keyword_rejected(self):
        router = ToolRouter()
        assert router.route("run") is None
        assert router.route("list") is None

    def test_substring_directional_only(self):
        router = ToolRouter()
        result = router.route_task("run_workflow_custom")
        assert result["routed"] is True
        assert result["target"] == AgentTarget.LINGTONG.value


# ── QualityGate ──


class TestQualityGate:
    def test_clean_files_pass(self):
        gate = QualityGate()
        report = gate.check_file_changes(["src/main.py", "tests/test_main.py"])
        assert report.passed is True

    def test_secret_file_blocks(self):
        gate = QualityGate()
        report = gate.check_file_changes([".env", "config.yaml"])
        assert len(report.critical_issues) > 0
        assert report.score < 100

    def test_error_result(self):
        from lingflow.core.types import Result
        gate = QualityGate()
        result = Result.fail("Review error")
        report = gate.check(result)
        assert report.passed is False

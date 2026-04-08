"""Comprehensive tests for quality_gate, constraints, and project_manager edge cases."""
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lingflow_plus.constraints import (
    ContextBudget,
    FileLock,
    RateLimiter,
    TokenBudget,
    TokenQuotaManager,
    _safe_lock_name,
)
from lingflow_plus.project_manager import ProjectContext, ProjectManager
from lingflow_plus.quality_gate import QualityGate, QualityReport


# ── QualityGate comprehensive ──


class TestQualityGateCheck:
    def test_check_success_result(self):
        from lingflow.core.types import Result

        gate = QualityGate()
        data = {"score": 85, "dimensions": {"code_quality": 80}, "critical_issues": [], "warnings": ["minor"]}
        result = Result.ok(data)
        report = gate.check(result)
        assert report.passed is True
        assert report.score == 85

    def test_check_error_result(self):
        from lingflow.core.types import Result

        gate = QualityGate()
        result = Result.fail("Review error")
        report = gate.check(result)
        assert report.passed is False
        assert report.score == 0
        assert "Review error" in report.critical_issues[0]

    def test_check_low_score_blocks(self):
        from lingflow.core.types import Result

        gate = QualityGate(min_score=70)
        data = {"score": 50, "dimensions": {}, "critical_issues": [], "warnings": []}
        result = Result.ok(data)
        report = gate.check(result)
        assert report.passed is False
        assert report.score == 50

    def test_check_critical_issue_blocks(self):
        from lingflow.core.types import Result

        gate = QualityGate(max_critical=0)
        data = {"score": 95, "dimensions": {}, "critical_issues": ["bug"], "warnings": []}
        result = Result.ok(data)
        report = gate.check(result)
        assert report.passed is False

    def test_check_with_none_data(self):
        from lingflow.core.types import Result

        gate = QualityGate()
        result = Result.ok(None)
        report = gate.check(result)
        assert report.score == 0


class TestQualityGateFileChanges:
    def test_empty_files_pass(self):
        gate = QualityGate()
        report = gate.check_file_changes([])
        assert report.passed is True
        assert report.score == 100

    def test_pyc_file_warning(self):
        gate = QualityGate()
        report = gate.check_file_changes(["src/__pycache__/module.pyc"])
        assert len(report.warnings) > 0
        assert report.score < 100

    def test_pyo_file_warning(self):
        gate = QualityGate()
        report = gate.check_file_changes(["src/module.pyo"])
        assert len(report.warnings) > 0

    def test_credential_file_blocks(self):
        gate = QualityGate()
        report = gate.check_file_changes(["credentials.json"])
        assert report.passed is False
        assert any("credential" in i for i in report.critical_issues)

    def test_secret_file_blocks(self):
        gate = QualityGate()
        report = gate.check_file_changes(["secret_config.yaml"])
        assert report.passed is False

    def test_no_test_warning_many_files(self):
        gate = QualityGate()
        files = ["src/main.py", "src/util.py", "src/helper.py", "src/extra.py"]
        report = gate.check_file_changes(files)
        assert any("No test" in w for w in report.warnings)

    def test_no_test_warning_few_files(self):
        gate = QualityGate()
        files = ["src/main.py"]
        report = gate.check_file_changes(files)
        assert not any("No test" in w for w in report.warnings)

    def test_custom_threshold(self):
        gate = QualityGate(min_score=50)
        report = gate.check_file_changes([".env"])
        assert report.score == 80
        assert report.passed is False

    def test_score_minimum_zero(self):
        gate = QualityGate(min_score=50)
        files = [f".env_{i}" for i in range(10)]
        report = gate.check_file_changes(files)
        assert report.score >= 0


class TestQualityReportToDict:
    def test_to_dict_fields(self):
        report = QualityReport(
            score=90,
            passed=True,
            dimensions={"code_quality": 90},
            critical_issues=[],
            warnings=["minor"],
            summary="Score: 90/100",
        )
        d = report.to_dict()
        assert d["score"] == 90
        assert d["passed"] is True
        assert d["dimensions"] == {"code_quality": 90}
        assert d["warnings"] == ["minor"]

    def test_to_dict_from_gate(self):
        gate = QualityGate()
        report = gate.check_file_changes(["src/main.py"])
        d = report.to_dict()
        assert "score" in d
        assert "passed" in d


# ── Constraints comprehensive ──


class TestTokenBudget:
    def test_remaining(self):
        b = TokenBudget(project="p", allocated=1000, used=300)
        assert b.remaining == 700

    def test_remaining_zero_allocated(self):
        b = TokenBudget(project="p", allocated=0, used=0)
        assert b.remaining == 0

    def test_usage_ratio(self):
        b = TokenBudget(project="p", allocated=1000, used=400)
        assert b.usage_ratio == 0.4

    def test_usage_ratio_zero_allocated(self):
        b = TokenBudget(project="p", allocated=0)
        assert b.usage_ratio == 0.0


class TestTokenQuotaManagerWindowReset:
    def test_window_reset(self):
        qm = TokenQuotaManager(window_tokens=10000, window_seconds=0)
        qm.allocate("p1", 5000)
        qm.consume("p1", 1000)
        assert qm._total_used == 1000
        qm._window_start = time.time() - 1
        qm.allocate("p2", 5000)
        assert qm._total_used == 0


class TestRateLimiterRpmLimit:
    def test_rpm_limit_hit(self):
        rl = RateLimiter(max_rpm=2, max_concurrent=100)
        rl.acquire()
        rl.acquire()
        wait = rl.acquire()
        assert wait > 0


class TestFileLockIsLocked:
    def test_is_locked_false_when_free(self, tmp_path):
        fl = FileLock(locks_dir=str(tmp_path / "locks"))
        assert fl.is_locked("/tmp/free_file.py") is False

    def test_is_locked_true_when_held(self, tmp_path):
        fl = FileLock(locks_dir=str(tmp_path / "locks"))
        fl.acquire("/tmp/locked_file.py")
        assert fl.is_locked("/tmp/locked_file.py") is True
        fl.release("/tmp/locked_file.py")

    def test_release_no_fd(self, tmp_path):
        fl = FileLock(locks_dir=str(tmp_path / "locks"))
        fl.release("/tmp/never_acquired.py")


class TestSafeLockName:
    def test_deterministic(self):
        name1 = _safe_lock_name("/tmp/test.py")
        name2 = _safe_lock_name("/tmp/test.py")
        assert name1 == name2

    def test_ends_with_lock(self):
        name = _safe_lock_name("/tmp/test.py")
        assert name.endswith(".lock")


class TestContextBudgetReset:
    def test_reset(self):
        cb = ContextBudget(default_limit=1000)
        cb.track("p1", 800)
        cb.reset("p1")
        assert cb.should_compress("p1") is False

    def test_get_limit_default(self):
        cb = ContextBudget(default_limit=5000)
        assert cb.get_limit("unknown") == 5000

    def test_get_limit_custom(self):
        cb = ContextBudget()
        cb.set_limit("big", 50000)
        assert cb.get_limit("big") == 50000

    def test_status_empty(self):
        cb = ContextBudget()
        assert cb.get_status() == {}

    def test_status_mixed_projects(self):
        cb = ContextBudget(default_limit=1000)
        cb.set_limit("p1", 2000)
        cb.track("p2", 500)
        status = cb.get_status()
        assert "p1" in status
        assert "p2" in status
        assert status["p1"]["limit"] == 2000
        assert status["p2"]["used"] == 500


# ── ProjectManager comprehensive ──


class TestProjectManagerStatus:
    def test_status_not_found(self, tmp_path):
        pm = ProjectManager(registry_path=str(tmp_path / "pm.json"))
        status = pm.status("nonexistent")
        assert "error" in status

    def test_status_found(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        (proj / ".git").mkdir()
        pm = ProjectManager(registry_path=str(tmp_path / "pm.json"))
        pm.register("myproj", str(proj), description="test")
        status = pm.status("myproj")
        assert status["name"] == "myproj"
        assert status["description"] == "test"
        assert "git" in status


class TestProjectManagerLoadError:
    def test_corrupt_json(self, tmp_path):
        reg = tmp_path / "bad.json"
        reg.write_text("not valid json{{{")
        pm = ProjectManager(registry_path=str(reg))
        assert pm.list() == []

    def test_missing_keys_json(self, tmp_path):
        reg = tmp_path / "missing.json"
        reg.write_text('{"p1": {"bad_key": "val"}}')
        pm = ProjectManager(registry_path=str(reg))
        assert pm.list() == []


class TestProjectContextGitStatus:
    def test_git_status_with_untracked(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "new_file.py").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
        ctx = ProjectContext(name="test", path=str(tmp_path))
        status = ctx.git_status()
        assert status["branch"] in ("master", "main")
        assert status["valid"] is True

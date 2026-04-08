"""Comprehensive tests for coordinator module."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.coordinator import LingFlowPlus


@pytest.fixture
def lf(tmp_path):
    return LingFlowPlus(state_dir=str(tmp_path / "state"))


class TestCoordinatorInit:
    def test_state_dir_created(self, tmp_path):
        state = tmp_path / "my_state"
        lf = LingFlowPlus(state_dir=str(state))
        assert state.is_dir()

    def test_default_subsystems(self, lf):
        assert lf.project_manager is not None
        assert lf.token_quota is not None
        assert lf.rate_limiter is not None
        assert lf.file_lock is not None
        assert lf.context_budget is not None
        assert lf.tool_router is not None
        assert lf.quality_gate is not None


class TestSchedulerLazy:
    def test_scheduler_none_initially(self, lf):
        assert lf._scheduler is None

    @patch("lingflow.coordination.coordinator.AgentCoordinator")
    @patch("lingflow_plus.coordinator.MultiProjectScheduler")
    def test_scheduler_lazy_init(self, mock_mps, mock_ac, lf):
        mock_ac.return_value = MagicMock()
        mock_mps.return_value = MagicMock()
        sched = lf.scheduler
        assert sched is not None
        assert lf._scheduler is not None

    @patch("lingflow.coordination.coordinator.AgentCoordinator")
    @patch("lingflow_plus.coordinator.MultiProjectScheduler")
    def test_scheduler_cached(self, mock_mps, mock_ac, lf):
        mock_ac.return_value = MagicMock()
        mock_mps.return_value = MagicMock()
        s1 = lf.scheduler
        s2 = lf.scheduler
        assert s1 is s2


class TestRunTasks:
    @patch("lingflow_plus.coordinator.time")
    def test_run_tasks_with_projects(self, mock_time, lf):
        mock_time.time.return_value = 0
        mock_sched = MagicMock()
        mock_sched.execute.return_value = {"t1": MagicMock(success=True)}
        lf._scheduler = mock_sched

        task = MagicMock()
        task.project = "LingFlow"
        task.context = {"target": "src/main.py"}

        results = lf.run_tasks([task])
        assert "t1" in results
        mock_sched.execute.assert_called_once()

    @patch("lingflow_plus.coordinator.time")
    def test_run_tasks_no_project(self, mock_time, lf):
        mock_time.time.return_value = 0
        mock_sched = MagicMock()
        mock_sched.execute.return_value = {}
        lf._scheduler = mock_sched

        task = MagicMock()
        task.project = ""
        results = lf.run_tasks([task])
        assert results == {}

    @patch("lingflow_plus.coordinator.time")
    def test_run_tasks_rate_limit_wait(self, mock_time, lf):
        mock_time.time.return_value = 0
        mock_time.sleep = MagicMock()
        mock_sched = MagicMock()
        mock_sched.execute.return_value = {}
        lf._scheduler = mock_sched
        lf.rate_limiter.acquire = MagicMock(return_value=0.5)
        lf.rate_limiter.release = MagicMock()

        task = MagicMock()
        task.project = ""
        lf.run_tasks([task])
        mock_time.sleep.assert_called_once_with(0.5)


class TestRunWorkflowFile:
    @patch("lingflow_plus.coordinator.MultiProjectScheduler")
    def test_run_workflow_file(self, mock_mps, lf):
        mock_mps.load_tasks_from_yaml.return_value = [MagicMock(project="p1")]
        mock_sched = MagicMock()
        mock_sched.execute.return_value = {"t1": MagicMock(success=True)}
        lf._scheduler = mock_sched

        with patch.object(lf, "run_tasks", return_value={"t1": MagicMock(success=True)}) as mock_rt:
            results = lf.run_workflow_file("test.yaml")
            mock_mps.load_tasks_from_yaml.assert_called_once_with("test.yaml")
            mock_rt.assert_called_once()


class TestSaveState:
    def test_save_state_creates_file(self, lf):
        lf._save_state()
        state_file = lf._state_dir / "state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert "timestamp" in data
        assert "projects_count" in data
        assert "token_status" in data

    def test_save_state_content(self, lf, tmp_path):
        proj = tmp_path / "state" / "proj"
        proj.mkdir()
        (proj / ".git").mkdir()
        lf.project_manager.register("test", str(proj))
        lf._save_state()
        data = json.loads((lf._state_dir / "state.json").read_text())
        assert data["projects_count"] == 1


class TestStatusSchedulerField:
    def test_status_no_scheduler(self, lf):
        s = lf.status()
        assert s["scheduler"] is None

    def test_status_with_scheduler(self, lf):
        mock_sched = MagicMock()
        mock_sched.get_status.return_value = {"projects": {}, "total_tasks": 0}
        lf._scheduler = mock_sched
        s = lf.status()
        assert s["scheduler"] is not None
        assert s["scheduler"]["total_tasks"] == 0

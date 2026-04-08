"""Comprehensive tests for scheduler module."""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.scheduler import (
    DEFAULT_MAX_PROJECTS_PARALLEL,
    MultiProjectScheduler,
    ProjectScheduleStatus,
)


class TestProjectScheduleStatus:
    def test_is_done_all_completed(self):
        s = ProjectScheduleStatus(project="p1", total=3, completed=3)
        assert s.is_done is True

    def test_is_done_all_failed(self):
        s = ProjectScheduleStatus(project="p1", total=2, failed=2)
        assert s.is_done is True

    def test_is_done_mixed(self):
        s = ProjectScheduleStatus(project="p1", total=3, completed=1, failed=1)
        assert s.is_done is False

    def test_is_done_zero_total(self):
        s = ProjectScheduleStatus(project="p1", total=0)
        assert s.is_done is True

    def test_to_dict_fields(self):
        s = ProjectScheduleStatus(
            project="test", total=5, completed=2, failed=1, running=1,
            start_time=100.0, end_time=200.0,
        )
        d = s.to_dict()
        assert d["project"] == "test"
        assert d["total"] == 5
        assert d["completed"] == 2
        assert d["failed"] == 1
        assert d["running"] == 1
        assert d["elapsed"] == 100.0
        assert d["is_done"] is False

    def test_to_dict_no_end_time_uses_current(self):
        s = ProjectScheduleStatus(project="p", total=1, start_time=time.time())
        d = s.to_dict()
        assert d["elapsed"] >= 0


def _make_scheduler():
    with patch("lingflow_plus.scheduler.ProjectManager"):
        sched = MultiProjectScheduler.__new__(MultiProjectScheduler)
        sched.project_manager = MagicMock()
        sched.coordinator = MagicMock()
        sched.max_projects_parallel = DEFAULT_MAX_PROJECTS_PARALLEL
        sched._statuses = {}
        sched._results = {}
        sched._progress_callbacks = []
    return sched


class TestMultiProjectSchedulerInit:
    @patch("lingflow.coordination.coordinator.AgentCoordinator")
    @patch("lingflow_plus.scheduler.ProjectManager")
    def test_default_init(self, mock_pm, mock_ac):
        sched = MultiProjectScheduler()
        assert sched.max_projects_parallel == DEFAULT_MAX_PROJECTS_PARALLEL
        assert sched._statuses == {}
        assert sched._results == {}
        assert sched._progress_callbacks == []

    @patch("lingflow.coordination.coordinator.AgentCoordinator")
    @patch("lingflow_plus.scheduler.ProjectManager")
    def test_custom_max_parallel(self, mock_pm, mock_ac):
        sched = MultiProjectScheduler(max_projects_parallel=5)
        assert sched.max_projects_parallel == 5


class TestNotifyProgress:
    def test_callback_called(self):
        sched = _make_scheduler()
        cb = MagicMock()
        sched.on_progress(cb)
        sched._notify_progress()
        cb.assert_called_once()
        call_arg = cb.call_args[0][0]
        assert "projects" in call_arg
        assert "total_tasks" in call_arg

    def test_callback_exception_handled(self):
        sched = _make_scheduler()
        cb = MagicMock(side_effect=RuntimeError("boom"))
        sched.on_progress(cb)
        sched._notify_progress()
        cb.assert_called_once()

    def test_multiple_callbacks(self):
        sched = _make_scheduler()
        cb1 = MagicMock()
        cb2 = MagicMock()
        sched.on_progress(cb1)
        sched.on_progress(cb2)
        sched._notify_progress()
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestGetStatus:
    def test_with_results(self):
        sched = _make_scheduler()
        r1 = MagicMock()
        r1.success = True
        r2 = MagicMock()
        r2.success = False
        sched._results = {"t1": r1, "t2": r2}
        status = sched.get_status()
        assert status["total_tasks"] == 2
        assert status["total_completed"] == 1
        assert status["total_failed"] == 1


class TestExecuteAsync:
    def test_empty_tasks(self):
        sched = _make_scheduler()
        result = asyncio.run(sched.execute_async([]))
        assert result == {}

    def test_group_by_project_with_project_field(self):
        sched = _make_scheduler()
        t1 = MagicMock()
        t1.project = "Alpha"
        t2 = MagicMock()
        t2.project = "Beta"
        t3 = MagicMock()
        t3.project = "Alpha"
        groups = sched._group_by_project([t1, t2, t3])
        assert set(groups.keys()) == {"Alpha", "Beta"}
        assert len(groups["Alpha"]) == 2

    def test_group_by_project_null_defaults(self):
        sched = _make_scheduler()
        t = MagicMock()
        t.project = None
        groups = sched._group_by_project([t])
        assert "default" in groups

    def test_execute_async_with_tasks(self):
        sched = _make_scheduler()
        t1 = MagicMock()
        t1.project = "TestProj"

        async def _fake_exec(pn, tasks, mp):
            return {"t1": MagicMock(success=True)}

        sched._execute_project = _fake_exec
        result = asyncio.run(sched.execute_async([t1]))
        assert "t1" in result

    def test_execute_async_exception_in_project(self):
        sched = _make_scheduler()
        t1 = MagicMock()
        t1.project = "FailProj"
        sched._execute_project = MagicMock(side_effect=RuntimeError("fail"))
        result = asyncio.run(sched.execute_async([t1]))
        assert result == {}


class TestLoadTasksFromYaml:
    def test_basic_yaml(self, tmp_path):
        yaml_file = tmp_path / "test_workflow.yaml"
        yaml_file.write_text("""
tasks:
  - task_id: t1
    project: LingFlow
    skill: code-review
    priority: high
    depends_on: []
    params:
      target: src/
  - task_id: t2
    project: LingClaude
    skill: test-runner
    priority: normal
""")
        with patch("lingflow.common.models.Task") as MockTask:
            MockTask.return_value = MagicMock()
            tasks = MultiProjectScheduler.load_tasks_from_yaml(str(yaml_file))
            assert MockTask.call_count == 2

    def test_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("tasks: []\n")
        tasks = MultiProjectScheduler.load_tasks_from_yaml(str(yaml_file))
        assert tasks == []

    def test_missing_tasks_key(self, tmp_path):
        yaml_file = tmp_path / "notasks.yaml"
        yaml_file.write_text("other: data\n")
        tasks = MultiProjectScheduler.load_tasks_from_yaml(str(yaml_file))
        assert tasks == []

    def test_priority_mapping(self, tmp_path):
        yaml_file = tmp_path / "priorities.yaml"
        yaml_file.write_text("""
tasks:
  - task_id: t1
    priority: critical
  - task_id: t2
    priority: low
  - task_id: t3
    priority: unknown_value
""")
        with patch("lingflow.common.models.Task") as MockTask, \
             patch("lingflow.common.models.TaskPriority") as MockPriority:
            MockPriority.CRITICAL = "critical"
            MockPriority.HIGH = "high"
            MockPriority.NORMAL = "normal"
            MockPriority.LOW = "low"
            MockTask.return_value = MagicMock()
            tasks = MultiProjectScheduler.load_tasks_from_yaml(str(yaml_file))
            assert MockTask.call_count == 3

    def test_defaults_applied(self, tmp_path):
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text("""
tasks:
  - task_id: t1
""")
        with patch("lingflow.common.models.Task") as MockTask:
            MockTask.return_value = MagicMock()
            MultiProjectScheduler.load_tasks_from_yaml(str(yaml_file))
            call_kwargs = MockTask.call_args[1]
            assert call_kwargs["task_id"] == "t1"
            assert call_kwargs["name"] == "t1"
            assert call_kwargs["description"] == ""
            assert call_kwargs["project"] == ""
            assert call_kwargs["working_dir"] == ""


class TestSchedulerStatusWithRealStatuses:
    def test_status_with_populated_projects(self):
        sched = _make_scheduler()
        sched._statuses["proj1"] = ProjectScheduleStatus(
            project="proj1", total=3, completed=2, failed=0, running=1,
        )
        status = sched.get_status()
        assert "proj1" in status["projects"]
        assert status["projects"]["proj1"]["total"] == 3

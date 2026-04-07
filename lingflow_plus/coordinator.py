"""协调器层

LingFlow+ 核心协调器，组合所有子系统：
- ProjectManager：项目注册与上下文
- MultiProjectScheduler：跨项目并行调度
- TokenQuotaManager：Token 配额
- RateLimiter：请求限速
- FileLock：文件互斥
- ContextBudget：上下文预算
- ToolRouter：工具路由
- QualityGate：质量门
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lingflow.common.models import Task, TaskResult
from lingflow import LingFlow

from lingflow_plus.constraints import (
    ContextBudget,
    FileLock,
    RateLimiter,
    TokenQuotaManager,
)
from lingflow_plus.project_manager import ProjectManager
from lingflow_plus.quality_gate import QualityGate, QualityReport
from lingflow_plus.scheduler import MultiProjectScheduler
from lingflow_plus.tool_router import AgentTarget, ToolRouter

logger = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".lingflow-plus"
STATE_FILE = STATE_DIR / "state.json"


class LingFlowPlus:
    """LingFlow+ 主协调器

    统一管理多项目并行工作流执行。
    """

    def __init__(self, state_dir: Optional[str] = None):
        self._state_dir = Path(state_dir) if state_dir else STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)

        self.project_manager = ProjectManager(
            registry_path=str(self._state_dir / "projects.json")
        )
        self.token_quota = TokenQuotaManager()
        self.rate_limiter = RateLimiter()
        self.file_lock = FileLock(locks_dir=str(self._state_dir / "locks"))
        self.context_budget = ContextBudget()
        self.tool_router = ToolRouter()
        self.quality_gate = QualityGate()

        self._scheduler: Optional[MultiProjectScheduler] = None
        self._lingflow = LingFlow()

    @property
    def scheduler(self) -> MultiProjectScheduler:
        """懒加载调度器（需要 coordinator）"""
        if self._scheduler is None:
            from lingflow.coordination.coordinator import AgentCoordinator
            coordinator = AgentCoordinator()
            self._scheduler = MultiProjectScheduler(
                project_manager=self.project_manager,
                coordinator=coordinator,
            )
        return self._scheduler

    def run_tasks(self, tasks: List[Task], max_parallel: int = 2) -> Dict[str, TaskResult]:
        """执行多项目任务"""
        for task in tasks:
            if task.project:
                self.context_budget.track(task.project, 500)
        results = self.scheduler.execute(tasks, max_parallel)
        self._save_state()
        return results

    def run_workflow_file(self, filepath: str) -> Dict[str, TaskResult]:
        """从 YAML 加载并执行跨项目工作流"""
        tasks = MultiProjectScheduler.load_tasks_from_yaml(filepath)
        return self.run_tasks(tasks)

    def status(self) -> Dict[str, Any]:
        """获取全局状态"""
        return {
            "version": "0.1.0",
            "projects": self.project_manager.dashboard(),
            "token_quota": self.token_quota.get_status(),
            "rate_limiter": self.rate_limiter.get_status(),
            "context_budget": self.context_budget.get_status(),
            "scheduler": self._scheduler.get_status() if self._scheduler else None,
            "routes": self.tool_router.list_routes(),
        }

    def quality_check(self, changed_files: List[str]) -> QualityReport:
        """执行质量门检查"""
        return self.quality_gate.check_file_changes(changed_files)

    def _save_state(self) -> None:
        """保存运行时状态"""
        state = {
            "timestamp": time.time(),
            "projects_count": len(self.project_manager.list()),
            "token_status": self.token_quota.get_status(),
        }
        try:
            with open(self._state_dir / "state.json", "w") as f:
                json.dump(state, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save state: {e}")

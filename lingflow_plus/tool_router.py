"""工具路由层

按任务类型路由到对应的灵字辈 Agent：
- bash/shell → 灵犀 (LingTermMCP)
- code/review/refactor → 灵克 (LingClaude)
- workflow/skill → 灵通 (LingFlow)

所有工具通过 MCP 协议访问，不做源码级 import。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentTarget(Enum):
    """目标 Agent"""
    LINGXI = "灵犀"
    LINGKE = "灵克"
    LINGTONG = "灵通"
    LINGYI = "灵依"
    LINGYOU = "灵极优"
    LOCAL = "本地"


@dataclass
class RouteRule:
    """路由规则"""
    pattern: str
    target: AgentTarget
    tool_name: str
    priority: int = 5


DEFAULT_RULES: List[RouteRule] = [
    RouteRule("bash", AgentTarget.LINGXI, "execute_command", 10),
    RouteRule("shell", AgentTarget.LINGXI, "execute_command", 10),
    RouteRule("terminal", AgentTarget.LINGXI, "create_session", 9),
    RouteRule("code_review", AgentTarget.LINGKE, "review_code", 9),
    RouteRule("code_refactor", AgentTarget.LINGKE, "refactor_code", 8),
    RouteRule("implement", AgentTarget.LINGKE, "implement", 8),
    RouteRule("code", AgentTarget.LINGKE, "query", 7),
    RouteRule("debug", AgentTarget.LINGKE, "query", 8),
    RouteRule("query", AgentTarget.LINGKE, "query", 7),
    RouteRule("workflow", AgentTarget.LINGTONG, "run_workflow", 10),
    RouteRule("skill", AgentTarget.LINGTONG, "execute_skill", 9),
    RouteRule("test", AgentTarget.LINGTONG, "execute_skill", 8),
    RouteRule("image", AgentTarget.LINGYI, "analyze_image", 8),
    RouteRule("screenshot", AgentTarget.LINGYI, "analyze_image", 8),
    RouteRule("optimize", AgentTarget.LINGYOU, "optimize", 7),
]


class ToolRouter:
    """工具路由器

    根据任务类型匹配路由规则，返回目标 Agent 和工具名。
    """

    def __init__(self, rules: Optional[List[RouteRule]] = None):
        self._rules = rules or DEFAULT_RULES

    def route(self, task_type: str) -> Optional[RouteRule]:
        """路由任务类型到目标 Agent

        精确匹配优先，然后按 priority 降序匹配子串。
        """
        exact = [r for r in self._rules if r.pattern == task_type]
        if exact:
            return max(exact, key=lambda r: r.priority)

        matches = [r for r in self._rules if r.pattern in task_type or task_type in r.pattern]
        if matches:
            return max(matches, key=lambda r: r.priority)

        return None

    def route_task(self, task_name: str, task_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """路由完整任务，返回路由结果"""
        rule = self.route(task_name)
        if not rule:
            return {
                "target": AgentTarget.LOCAL.value,
                "tool": task_name,
                "method": "direct",
                "routed": False,
            }
        return {
            "target": rule.target.value,
            "tool": rule.tool_name,
            "pattern": rule.pattern,
            "method": "mcp",
            "routed": True,
        }

    def list_routes(self) -> List[Dict[str, Any]]:
        """列出所有路由规则"""
        return [
            {"pattern": r.pattern, "target": r.target.value, "tool": r.tool_name, "priority": r.priority}
            for r in sorted(self._rules, key=lambda r: -r.priority)
        ]

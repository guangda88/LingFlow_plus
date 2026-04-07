from __future__ import annotations
"""工具路由层

按任务类型路由到对应的灵字辈 Agent，覆盖生态 10 个 MCP 服务器 99 个工具：
- 灵犀 (Ling-term-mcp): 终端命令、会话管理
- 灵克 (LingClaude): 代码读写、搜索、Git、分析、优化
- 灵通 (LingFlow): 工作流、技能、测试、监控、需求、文件操作
- 灵依 (LingYi): 备忘、日程、计划、项目巡逻、情报
- 灵通问道 (LingTongAsk): 情感分析、语音合成、内容生成
- 灵知 (zhineng-knowledge-system): 知识检索、问答、领域查询
- 灵信 (LingMessage): 消息总线、标注、签名
- 智桥 (zhineng-bridge): 跨平台通信

所有工具通过 MCP 协议访问，不做源码级 import。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentTarget(Enum):
    LINGXI = "灵犀"
    LINGKE = "灵克"
    LINGTONG = "灵通"
    LINGYI = "灵依"
    LINGTONGASK = "灵通问道"
    LINGZHI = "灵知"
    LINGMESSAGE = "灵信"
    ZHIBRIDGE = "智桥"
    LINGYOU = "灵极优"
    LOCAL = "本地"


@dataclass
class RouteRule:
    pattern: str
    target: AgentTarget
    tool_name: str
    priority: int = 5


DEFAULT_RULES: List[RouteRule] = [
    # ── 灵犀 (Ling-term-mcp): 终端 ──
    RouteRule("execute_command", AgentTarget.LINGXI, "execute_command", 10),
    RouteRule("bash", AgentTarget.LINGXI, "execute_command", 10),
    RouteRule("shell", AgentTarget.LINGXI, "execute_command", 10),
    RouteRule("sync_terminal", AgentTarget.LINGXI, "sync_terminal", 9),
    RouteRule("terminal", AgentTarget.LINGXI, "create_session", 9),
    RouteRule("list_sessions", AgentTarget.LINGXI, "list_sessions", 8),
    RouteRule("create_session", AgentTarget.LINGXI, "create_session", 8),
    RouteRule("destroy_session", AgentTarget.LINGXI, "destroy_session", 7),

    # ── 灵克 (LingClaude): 代码 ──
    RouteRule("read_file", AgentTarget.LINGKE, "read_file", 10),
    RouteRule("write_file", AgentTarget.LINGKE, "write_file", 10),
    RouteRule("edit_code", AgentTarget.LINGKE, "edit_code", 10),
    RouteRule("search_code", AgentTarget.LINGKE, "search_code", 9),
    RouteRule("run_bash", AgentTarget.LINGKE, "run_bash", 9),
    RouteRule("index_project", AgentTarget.LINGKE, "index_project", 8),
    RouteRule("list_functions", AgentTarget.LINGKE, "list_functions", 8),
    RouteRule("replace_function", AgentTarget.LINGKE, "replace_function", 8),
    RouteRule("git_status", AgentTarget.LINGKE, "git_status", 9),
    RouteRule("git_log", AgentTarget.LINGKE, "git_log", 9),
    RouteRule("git_diff", AgentTarget.LINGKE, "git_diff", 9),
    RouteRule("git_blame", AgentTarget.LINGKE, "git_blame", 9),
    RouteRule("evaluate_code", AgentTarget.LINGKE, "evaluate_code", 9),
    RouteRule("run_optimization", AgentTarget.LINGKE, "run_optimization", 8),
    RouteRule("get_advice", AgentTarget.LINGKE, "get_advice", 8),
    RouteRule("check_triggers", AgentTarget.LINGKE, "check_triggers", 7),
    RouteRule("glob", AgentTarget.LINGKE, "glob", 7),
    RouteRule("file_create", AgentTarget.LINGKE, "file_create", 8),
    RouteRule("file_insert", AgentTarget.LINGKE, "file_insert", 8),
    RouteRule("file_delete_lines", AgentTarget.LINGKE, "file_delete_lines", 8),
    RouteRule("file_undo", AgentTarget.LINGKE, "file_undo", 7),
    RouteRule("analyze_full", AgentTarget.LINGKE, "analyze_full", 9),
    RouteRule("session_list", AgentTarget.LINGKE, "session_list", 7),
    RouteRule("stt", AgentTarget.LINGKE, "stt", 8),
    RouteRule("check_and_optimize", AgentTarget.LINGKE, "check_and_optimize", 8),
    RouteRule("code_search", AgentTarget.LINGKE, "knowledge_search", 9),
    RouteRule("knowledge_search_code", AgentTarget.LINGKE, "knowledge_search", 8),
    RouteRule("code_review", AgentTarget.LINGKE, "evaluate_code", 9),
    RouteRule("code_refactor", AgentTarget.LINGKE, "replace_function", 8),
    RouteRule("implement", AgentTarget.LINGKE, "edit_code", 8),
    RouteRule("code", AgentTarget.LINGKE, "search_code", 7),
    RouteRule("debug", AgentTarget.LINGKE, "analyze_full", 8),
    RouteRule("query", AgentTarget.LINGKE, "search_code", 7),

    # ── 灵通 (LingFlow): 工作流 ──
    RouteRule("list_skills", AgentTarget.LINGTONG, "list_skills", 10),
    RouteRule("run_skill", AgentTarget.LINGTONG, "run_skill", 10),
    RouteRule("review_code", AgentTarget.LINGTONG, "review_code", 9),
    RouteRule("get_github_trends", AgentTarget.LINGTONG, "get_github_trends", 7),
    RouteRule("get_npm_trends", AgentTarget.LINGTONG, "get_npm_trends", 7),
    RouteRule("list_workflows", AgentTarget.LINGTONG, "list_workflows", 10),
    RouteRule("run_workflow", AgentTarget.LINGTONG, "run_workflow", 10),
    RouteRule("get_workflow_status", AgentTarget.LINGTONG, "get_workflow_status", 9),
    RouteRule("create_requirement", AgentTarget.LINGTONG, "create_requirement", 9),
    RouteRule("get_requirement", AgentTarget.LINGTONG, "get_requirement", 9),
    RouteRule("update_requirement", AgentTarget.LINGTONG, "update_requirement", 8),
    RouteRule("list_requirements", AgentTarget.LINGTONG, "list_requirements", 8),
    RouteRule("link_requirement_to_branch", AgentTarget.LINGTONG, "link_requirement_to_branch", 8),
    RouteRule("run_tests", AgentTarget.LINGTONG, "run_tests", 9),
    RouteRule("get_coverage", AgentTarget.LINGTONG, "get_coverage", 9),
    RouteRule("generate_test_report", AgentTarget.LINGTONG, "generate_test_report", 8),
    RouteRule("get_health_status", AgentTarget.LINGTONG, "get_health_status", 8),
    RouteRule("get_metrics", AgentTarget.LINGTONG, "get_metrics", 8),
    RouteRule("detect_anomaly", AgentTarget.LINGTONG, "detect_anomaly", 8),
    RouteRule("multiedit", AgentTarget.LINGTONG, "multiedit", 9),
    RouteRule("list_directory", AgentTarget.LINGTONG, "list_directory", 8),
    RouteRule("download_file", AgentTarget.LINGTONG, "download_file", 7),
    RouteRule("get_diagnostics", AgentTarget.LINGTONG, "get_diagnostics", 7),
    RouteRule("find_references", AgentTarget.LINGTONG, "find_references", 8),
    RouteRule("workflow", AgentTarget.LINGTONG, "run_workflow", 10),
    RouteRule("skill", AgentTarget.LINGTONG, "run_skill", 9),
    RouteRule("test", AgentTarget.LINGTONG, "run_tests", 8),
    RouteRule("requirement", AgentTarget.LINGTONG, "list_requirements", 7),
    RouteRule("coverage", AgentTarget.LINGTONG, "get_coverage", 8),
    RouteRule("health", AgentTarget.LINGTONG, "get_health_status", 8),
    RouteRule("anomaly", AgentTarget.LINGTONG, "detect_anomaly", 8),

    # ── 灵依 (LingYi): 备忘/日程/情报 ──
    RouteRule("add_memo", AgentTarget.LINGYI, "add_memo", 10),
    RouteRule("list_memos", AgentTarget.LINGYI, "list_memos", 10),
    RouteRule("add_schedule", AgentTarget.LINGYI, "add_schedule", 10),
    RouteRule("list_schedules", AgentTarget.LINGYI, "list_schedules", 9),
    RouteRule("add_plan", AgentTarget.LINGYI, "add_plan", 10),
    RouteRule("list_plans", AgentTarget.LINGYI, "list_plans", 9),
    RouteRule("show_project", AgentTarget.LINGYI, "show_project", 9),
    RouteRule("generate_report", AgentTarget.LINGYI, "generate_report", 9),
    RouteRule("patrol_project", AgentTarget.LINGYI, "patrol_project", 9),
    RouteRule("get_briefing", AgentTarget.LINGYI, "get_briefing", 9),
    RouteRule("digest_content", AgentTarget.LINGYI, "digest_content", 8),
    RouteRule("ask_lingzhi", AgentTarget.LINGYI, "ask_lingzhi", 8),
    RouteRule("image", AgentTarget.LINGYI, "digest_content", 8),
    RouteRule("screenshot", AgentTarget.LINGYI, "digest_content", 8),
    RouteRule("memo", AgentTarget.LINGYI, "list_memos", 8),
    RouteRule("schedule", AgentTarget.LINGYI, "list_schedules", 8),
    RouteRule("briefing", AgentTarget.LINGYI, "get_briefing", 9),
    RouteRule("patrol", AgentTarget.LINGYI, "patrol_project", 8),

    # ── 灵通问道 (LingTongAsk): 语音/内容 ──
    RouteRule("analyze_emotion", AgentTarget.LINGTONGASK, "analyze_emotion", 10),
    RouteRule("synthesize_speech", AgentTarget.LINGTONGASK, "synthesize_speech", 10),
    RouteRule("list_voices", AgentTarget.LINGTONGASK, "list_voices", 9),
    RouteRule("generate_topics", AgentTarget.LINGTONGASK, "generate_topics", 10),
    RouteRule("list_categories", AgentTarget.LINGTONGASK, "list_categories", 9),
    RouteRule("check_episode_quality", AgentTarget.LINGTONGASK, "check_episode_quality", 9),
    RouteRule("run_self_optimization", AgentTarget.LINGTONGASK, "run_self_optimization", 8),
    RouteRule("get_voice_registry", AgentTarget.LINGTONGASK, "get_voice_registry", 8),
    RouteRule("get_episode_list", AgentTarget.LINGTONGASK, "get_episode_list", 8),
    RouteRule("emotion", AgentTarget.LINGTONGASK, "analyze_emotion", 9),
    RouteRule("speech", AgentTarget.LINGTONGASK, "synthesize_speech", 9),
    RouteRule("voice", AgentTarget.LINGTONGASK, "list_voices", 8),
    RouteRule("topic", AgentTarget.LINGTONGASK, "generate_topics", 8),
    RouteRule("episode", AgentTarget.LINGTONGASK, "get_episode_list", 8),
    RouteRule("podcast", AgentTarget.LINGTONGASK, "generate_topics", 8),

    # ── 灵知 (zhineng-knowledge-system): 知识 ──
    RouteRule("knowledge_search", AgentTarget.LINGZHI, "knowledge_search", 10),
    RouteRule("ask_question", AgentTarget.LINGZHI, "ask_question", 10),
    RouteRule("domain_query", AgentTarget.LINGZHI, "domain_query", 9),
    RouteRule("optimization_status", AgentTarget.LINGZHI, "optimization_status", 7),
    RouteRule("submit_feedback", AgentTarget.LINGZHI, "submit_feedback", 8),
    RouteRule("generate_training_data", AgentTarget.LINGZHI, "generate_training_data", 8),
    RouteRule("safe_db_query", AgentTarget.LINGZHI, "safe_db_query", 9),
    RouteRule("submit_search_feedback", AgentTarget.LINGZHI, "submit_search_feedback", 7),
    RouteRule("get_search_feedback", AgentTarget.LINGZHI, "get_search_feedback", 7),
    RouteRule("system_stats", AgentTarget.LINGZHI, "system_stats", 7),
    RouteRule("list_knowledge_categories", AgentTarget.LINGZHI, "list_categories", 10),
    RouteRule("知识", AgentTarget.LINGZHI, "knowledge_search", 9),
    RouteRule("搜索知识", AgentTarget.LINGZHI, "knowledge_search", 10),
    RouteRule("问答", AgentTarget.LINGZHI, "ask_question", 9),
    RouteRule("数据库查询", AgentTarget.LINGZHI, "safe_db_query", 8),

    # ── 灵信 (LingMessage): 消息 ──
    RouteRule("open_thread", AgentTarget.LINGMESSAGE, "open_thread", 10),
    RouteRule("post_reply", AgentTarget.LINGMESSAGE, "post_reply", 10),
    RouteRule("poll_messages", AgentTarget.LINGMESSAGE, "poll_messages", 9),
    RouteRule("ack_message", AgentTarget.LINGMESSAGE, "ack_message", 8),
    RouteRule("get_stats", AgentTarget.LINGMESSAGE, "get_stats", 8),
    RouteRule("detect_anomalies", AgentTarget.LINGMESSAGE, "detect_anomalies", 9),
    RouteRule("annotate_messages", AgentTarget.LINGMESSAGE, "annotate_messages", 9),
    RouteRule("annotation_report", AgentTarget.LINGMESSAGE, "annotation_report", 8),
    RouteRule("sign", AgentTarget.LINGMESSAGE, "sign", 9),
    RouteRule("verify", AgentTarget.LINGMESSAGE, "verify", 9),
    RouteRule("annotate_verified", AgentTarget.LINGMESSAGE, "annotate_verified", 8),
    RouteRule("message", AgentTarget.LINGMESSAGE, "poll_messages", 8),
    RouteRule("discussion", AgentTarget.LINGMESSAGE, "open_thread", 8),
    RouteRule("annotate", AgentTarget.LINGMESSAGE, "annotate_messages", 8),

    # ── 智桥 (zhineng-bridge): 跨平台通信 ──
    RouteRule("hello_world", AgentTarget.ZHIBRIDGE, "hello_world", 5),
    RouteRule("bridge", AgentTarget.ZHIBRIDGE, "hello_world", 5),

    # ── 灵极优 (LingMinOpt): 优化 ──
    RouteRule("optimize", AgentTarget.LINGYOU, "optimize", 7),
]


class ToolRouter:
    """工具路由器

    根据任务类型匹配路由规则，返回目标 Agent 和工具名。
    精确匹配优先，然后按 priority 降序匹配子串。
    """

    def __init__(self, rules: Optional[List[RouteRule]] = None):
        self._rules = rules or DEFAULT_RULES

    def route(self, task_type: str) -> Optional[RouteRule]:
        """根据任务类型匹配路由规则，返回优先级最高的 RouteRule

        匹配策略：精确匹配优先，其次子串包含匹配，均按 priority 降序选择。

        Args:
            task_type: 任务类型关键字，如 "git_status"、"workflow"、"知识"

        Returns:
            匹配的 RouteRule，无匹配时返回 None
        """
        exact = [r for r in self._rules if r.pattern == task_type]
        if exact:
            return max(exact, key=lambda r: r.priority)

        MIN_LEN = 4
        if len(task_type) >= MIN_LEN:
            matches = [r for r in self._rules if len(r.pattern) >= MIN_LEN and r.pattern in task_type]
        else:
            matches = []
        if matches:
            return max(matches, key=lambda r: r.priority)

        return None

    def route_task(self, task_name: str, task_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """将任务名路由为目标 Agent 和工具的完整描述

        Args:
            task_name: 任务名称或关键字
            task_context: 额外上下文（预留，当前未使用）

        Returns:
            包含 target、tool、method、routed 字段的字典
        """
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
        """列出所有路由规则，按优先级降序排列

        Returns:
            包含 pattern、target、tool、priority 的字典列表
        """
        return [
            {"pattern": r.pattern, "target": r.target.value, "tool": r.tool_name, "priority": r.priority}
            for r in sorted(self._rules, key=lambda r: -r.priority)
        ]

    def route_by_tool_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """按 MCP 工具名查找路由目标（最高优先级生效）

        Args:
            tool_name: MCP 工具名称，如 "git_status"

        Returns:
            包含 target、tool、server_key 的字典，无匹配时返回 None
        """
        exact = [r for r in self._rules if r.tool_name == tool_name]
        if exact:
            best = max(exact, key=lambda r: r.priority)
            return {"target": best.target.value, "tool": best.tool_name, "server_key": best.target.name.lower()}
        return None

    def get_tools_for_agent(self, target: AgentTarget) -> List[str]:
        """获取指定 Agent 拥有的去重工具列表

        Args:
            target: 目标 Agent 枚举值

        Returns:
            该 Agent 下的工具名列表（已去重，保留定义顺序）
        """
        seen = set()
        result = []
        for r in self._rules:
            if r.target == target and r.tool_name not in seen:
                seen.add(r.tool_name)
                result.append(r.tool_name)
        return result

    def get_agents_summary(self) -> List[Dict[str, Any]]:
        """汇总所有 Agent 的工具数和规则数

        Returns:
            包含 target、tool_count、rule_count 的字典列表
        """
        agents: Dict[AgentTarget, Dict[str, Any]] = {}
        for r in self._rules:
            if r.target not in agents:
                agents[r.target] = {"target": r.target.value, "tools": set(), "rules": 0}
            agents[r.target]["tools"].add(r.tool_name)
            agents[r.target]["rules"] += 1
        return [
            {"target": v["target"], "tool_count": len(v["tools"]), "rule_count": v["rules"]}
            for v in agents.values()
        ]

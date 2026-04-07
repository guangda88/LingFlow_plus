from __future__ import annotations
"""MCP 服务器注册表

灵字辈生态 10 个 MCP 服务器的连接配置。
每个 AgentTarget 对应一个 MCP 服务器（或服务器组）。
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Transport(str, Enum):
    STDIO = "stdio"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable_http"


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    agent_id: str
    transport: Transport
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    working_dir: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)


MCP_SERVERS: Dict[str, MCPServerConfig] = {
    "lingtong": MCPServerConfig(
        name="灵通",
        agent_id="lingflow",
        transport=Transport.STDIO,
        command="lingflow-mcp",
        args=[],
        working_dir=str(Path.home() / "LingFlow" / "mcp_server"),
        tools=[
            "list_skills", "run_skill", "review_code",
            "get_github_trends", "get_npm_trends",
            "list_workflows", "run_workflow", "get_workflow_status",
            "create_requirement", "get_requirement", "update_requirement",
            "list_requirements", "link_requirement_to_branch",
            "run_tests", "get_coverage", "generate_test_report",
            "get_health_status", "get_metrics", "detect_anomaly",
            "multiedit", "list_directory", "download_file",
            "get_diagnostics", "find_references",
        ],
    ),
    "lingke": MCPServerConfig(
        name="灵克",
        agent_id="lingclaude",
        transport=Transport.STDIO,
        command="lingclaude-mcp",
        args=[],
        tools=[
            "read_file", "write_file", "edit_code", "search_code",
            "run_bash", "index_project", "list_functions",
            "replace_function", "git_status", "git_log", "git_diff",
            "git_blame", "evaluate_code", "run_optimization",
            "get_advice", "check_triggers", "glob",
            "file_create", "file_insert", "file_delete_lines",
            "file_undo", "analyze_full", "knowledge_search",
            "session_list", "stt", "check_and_optimize",
        ],
    ),
    "lingyi": MCPServerConfig(
        name="灵依",
        agent_id="lingyi",
        transport=Transport.STDIO,
        command="lingyi-mcp",
        args=[],
        tools=[
            "add_memo", "list_memos", "add_schedule", "list_schedules",
            "add_plan", "list_plans", "show_project",
            "generate_report", "patrol_project", "get_briefing",
            "digest_content", "ask_lingzhi",
            "today_schedule", "week_schedule", "smart_remind",
            "done_plan", "week_plans", "plan_stats",
            "list_projects", "save_session", "last_session",
            "search_knowledge", "speak", "synthesize_to_file",
            "transcribe", "council_scan", "council_health",
        ],
    ),
    "lingtongask": MCPServerConfig(
        name="灵通问道",
        agent_id="lingtongask",
        transport=Transport.STDIO,
        command="python",
        args=["-m", "mcp_server"],
        working_dir=str(Path.home() / "lingtongask"),
        tools=[
            "analyze_emotion", "synthesize_speech", "list_voices",
            "generate_topics", "list_categories",
            "check_episode_quality", "run_self_optimization",
            "get_voice_registry", "get_episode_list",
        ],
    ),
    "lingzhi": MCPServerConfig(
        name="灵知",
        agent_id="lingzhi",
        transport=Transport.STDIO,
        command="python",
        args=["-m", "mcp_servers.zhineng_server"],
        working_dir=str(Path.home() / "zhineng-knowledge-system"),
        tools=[
            "knowledge_search", "ask_question", "domain_query",
            "optimization_status", "submit_feedback",
            "generate_training_data", "safe_db_query",
            "submit_search_feedback", "get_search_feedback",
            "list_categories", "system_stats",
        ],
    ),
    "lingmessage_annotate": MCPServerConfig(
        name="灵信标注",
        agent_id="lingmessage",
        transport=Transport.STDIO,
        command="fastmcp",
        args=["run", str(Path.home() / "LingMessage" / "mcp_servers" / "annotate_server.py")],
        tools=["detect_anomalies", "annotate_messages", "annotation_report"],
    ),
    "lingmessage_bus": MCPServerConfig(
        name="灵信消息总线",
        agent_id="lingmessage",
        transport=Transport.STDIO,
        command="fastmcp",
        args=["run", str(Path.home() / "LingMessage" / "mcp_servers" / "lingbus_server.py")],
        tools=["open_thread", "post_reply", "poll_messages", "ack_message", "get_stats"],
    ),
    "lingmessage_signing": MCPServerConfig(
        name="灵信签名",
        agent_id="lingmessage",
        transport=Transport.STDIO,
        command="fastmcp",
        args=["run", str(Path.home() / "LingMessage" / "mcp_servers" / "signing_server.py")],
        tools=["sign", "verify", "annotate_verified"],
    ),
    "lingxi": MCPServerConfig(
        name="灵犀",
        agent_id="lingxi",
        transport=Transport.STDIO,
        command="node",
        args=[str(Path.home() / "Ling-term-mcp" / "dist" / "cli.js")],
        tools=[
            "execute_command", "sync_terminal",
            "list_sessions", "create_session", "destroy_session",
        ],
    ),
    "zhibridge": MCPServerConfig(
        name="智桥",
        agent_id="zhibridge",
        transport=Transport.STDIO,
        command="npx",
        args=["tsx", "src/index.ts"],
        working_dir=str(Path.home() / "zhineng-bridge" / "mcp-server"),
        tools=["hello_world"],
    ),
    "lingyang": MCPServerConfig(
        name="灵扬",
        agent_id="lingyang",
        transport=Transport.STDIO,
        command="python",
        args=["-m", "src.mcp_server"],
        working_dir=str(Path.home() / "LingYang"),
        tools=[
            "collect_metrics", "latest_metrics", "metrics_history",
            "format_report", "growth_report", "format_growth",
            "cleanup_old_metrics",
            "add_contact", "list_contacts", "get_contact",
            "find_contacts", "update_contact", "delete_contact",
            "contacts_summary",
        ],
    ),
    "lingresearch": MCPServerConfig(
        name="灵妍",
        agent_id="lingresearch",
        transport=Transport.STDIO,
        command="python",
        args=[str(Path.home() / "lingresearch" / "mcp_server.py")],
        tools=[
            "add_intel", "from_identity_test", "from_hallucination_event",
            "from_test_result", "from_experiment", "from_agent_behavior",
            "list_intel", "clear_intel", "intel_summary",
            "record_assertion", "score_counterfactual",
            "get_baseline", "get_consistency",
            "generate_digest", "generate_digest_markdown", "relay_intel",
        ],
    ),
}


def get_server_config(key: str) -> Optional[MCPServerConfig]:
    """按 key 获取单个 MCP 服务器配置

    Args:
        key: 服务器标识，如 "lingtong"、"lingke"

    Returns:
        MCPServerConfig 实例，不存在时返回 None
    """
    return MCP_SERVERS.get(key)


def get_all_server_configs() -> Dict[str, MCPServerConfig]:
    """获取全部 MCP 服务器配置的副本

    Returns:
        key → MCPServerConfig 的字典
    """
    return dict(MCP_SERVERS)


def find_server_for_tool(tool_name: str) -> Optional[tuple]:
    """查找提供指定工具的 MCP 服务器

    Args:
        tool_name: 工具名称，如 "run_workflow"

    Returns:
        (key, MCPServerConfig) 元组，未找到时返回 None
    """
    for key, config in MCP_SERVERS.items():
        if tool_name in config.tools:
            return (key, config)
    return None


def get_tools_by_agent_group() -> Dict[str, List[str]]:
    """按 agent_id 分组汇总所有工具名

    Returns:
        agent_id → 工具名列表的字典
    """
    groups: Dict[str, List[str]] = {}
    for config in MCP_SERVERS.values():
        aid = config.agent_id
        if aid not in groups:
            groups[aid] = []
        groups[aid].extend(config.tools)
    return groups


def get_server_stats() -> Dict[str, Any]:
    """统计 MCP 服务器和工具的总体信息

    Returns:
        包含 total_servers、total_tools、by_agent、transports 的字典
    """
    total_tools = sum(len(c.tools) for c in MCP_SERVERS.values())
    by_agent: Dict[str, int] = {}
    for config in MCP_SERVERS.values():
        by_agent[config.name] = by_agent.get(config.name, 0) + len(config.tools)
    return {
        "total_servers": len(MCP_SERVERS),
        "total_tools": total_tools,
        "by_agent": by_agent,
        "transports": {c.name: c.transport.value for c in MCP_SERVERS.values()},
    }

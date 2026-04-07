"""LingFlow+ MCP 注册测试套件 — 验证 10 个 MCP 服务器 99 个工具的完整注册"""
import pytest

from lingflow_plus.tool_router import AgentTarget, RouteRule, ToolRouter, DEFAULT_RULES
from lingflow_plus.mcp_registry import (
    MCP_SERVERS,
    MCPServerConfig,
    Transport,
    get_server_config,
    get_all_server_configs,
    find_server_for_tool,
    get_tools_by_agent_group,
    get_server_stats,
)


# ── AgentTarget 枚举 ──


class TestAgentTarget:
    def test_all_twelve_agents_exist(self):
        expected = {"灵犀", "灵克", "灵通", "灵依", "灵通问道", "灵知", "灵信", "智桥", "灵极优", "灵扬", "灵妍", "本地"}
        actual = {a.value for a in AgentTarget}
        assert actual == expected

    def test_new_agents_present(self):
        assert AgentTarget.LINGTONGASK.value == "灵通问道"
        assert AgentTarget.LINGZHI.value == "灵知"
        assert AgentTarget.LINGMESSAGE.value == "灵信"
        assert AgentTarget.ZHIBRIDGE.value == "智桥"

    def test_legacy_agents_still_work(self):
        assert AgentTarget.LINGXI.value == "灵犀"
        assert AgentTarget.LINGKE.value == "灵克"
        assert AgentTarget.LINGTONG.value == "灵通"
        assert AgentTarget.LINGYI.value == "灵依"
        assert AgentTarget.LINGYOU.value == "灵极优"
        assert AgentTarget.LOCAL.value == "本地"


# ── 路由规则覆盖度 ──


class TestDefaultRulesCoverage:
    def test_total_rules_count(self):
        assert len(DEFAULT_RULES) >= 99

    def test_every_agent_has_rules(self):
        agents_with_rules = {r.target for r in DEFAULT_RULES}
        assert AgentTarget.LINGXI in agents_with_rules
        assert AgentTarget.LINGKE in agents_with_rules
        assert AgentTarget.LINGTONG in agents_with_rules
        assert AgentTarget.LINGYI in agents_with_rules
        assert AgentTarget.LINGTONGASK in agents_with_rules
        assert AgentTarget.LINGZHI in agents_with_rules
        assert AgentTarget.LINGMESSAGE in agents_with_rules
        assert AgentTarget.ZHIBRIDGE in agents_with_rules

    def test_unique_tool_names_count(self):
        unique_tools = {r.tool_name for r in DEFAULT_RULES}
        assert len(unique_tools) >= 60

    def test_no_duplicate_exact_patterns_same_target(self):
        seen = {}
        for r in DEFAULT_RULES:
            key = (r.pattern, r.target)
            assert key not in seen, f"Duplicate rule: {key}"
            seen[key] = r


class TestPortablePaths:
    def test_working_dirs_use_pathlib_resolution(self):
        from pathlib import Path
        home = str(Path.home())
        for key, config in MCP_SERVERS.items():
            if config.working_dir:
                assert config.working_dir.startswith(home), \
                    f"{key} working_dir not under Path.home(): {config.working_dir}"

    def test_lingtong_working_dir_portable(self):
        from pathlib import Path
        config = get_server_config("lingtong")
        assert config.working_dir == str(Path.home() / "LingFlow" / "mcp_server")

    def test_lingtongask_working_dir_portable(self):
        from pathlib import Path
        config = get_server_config("lingtongask")
        assert config.working_dir == str(Path.home() / "lingtongask")

    def test_lingzhi_working_dir_portable(self):
        from pathlib import Path
        config = get_server_config("lingzhi")
        assert config.working_dir == str(Path.home() / "zhineng-knowledge-system")

    def test_zhibridge_working_dir_portable(self):
        from pathlib import Path
        config = get_server_config("zhibridge")
        assert config.working_dir == str(Path.home() / "zhineng-bridge" / "mcp-server")


class TestCollisionDisambiguation:
    def test_knowledge_search_routes_to_lingzhi(self):
        router = ToolRouter()
        result = router.route_task("knowledge_search")
        assert result["routed"] is True
        assert result["target"] == "灵知"

    def test_code_search_routes_to_lingke(self):
        router = ToolRouter()
        result = router.route_task("code_search")
        assert result["routed"] is True
        assert result["target"] == "灵克"
        assert result["tool"] == "knowledge_search"

    def test_knowledge_search_code_routes_to_lingke(self):
        router = ToolRouter()
        result = router.route_task("knowledge_search_code")
        assert result["routed"] is True
        assert result["target"] == "灵克"
        assert result["tool"] == "knowledge_search"

    def test_list_categories_routes_to_lingtongask(self):
        router = ToolRouter()
        result = router.route_task("list_categories")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"

    def test_list_knowledge_categories_routes_to_lingzhi(self):
        router = ToolRouter()
        result = router.route_task("list_knowledge_categories")
        assert result["routed"] is True
        assert result["target"] == "灵知"
        assert result["tool"] == "list_categories"

    def test_route_by_tool_name_knowledge_search_highest_priority(self):
        router = ToolRouter()
        result = router.route_by_tool_name("knowledge_search")
        assert result is not None
        assert result["target"] == "灵知"


class TestDocstrings:
    def test_tool_router_methods_have_docstrings(self):
        router = ToolRouter()
        for method_name in ["route", "route_task", "list_routes", "route_by_tool_name", "get_tools_for_agent", "get_agents_summary"]:
            method = getattr(router, method_name)
            assert method.__doc__ is not None, f"ToolRouter.{method_name} missing docstring"
            assert len(method.__doc__.strip()) > 10, f"ToolRouter.{method_name} docstring too short"

    def test_mcp_registry_functions_have_docstrings(self):
        funcs = {
            "get_server_config": get_server_config,
            "get_all_server_configs": get_all_server_configs,
            "find_server_for_tool": find_server_for_tool,
            "get_tools_by_agent_group": get_tools_by_agent_group,
            "get_server_stats": get_server_stats,
        }
        for name, func in funcs.items():
            assert func.__doc__ is not None, f"{name} missing docstring"
            assert len(func.__doc__.strip()) > 10, f"{name} docstring too short"


# ── 灵犀 (Ling-term-mcp) 路由 ──
    def test_execute_command(self):
        router = ToolRouter()
        rule = router.route("execute_command")
        assert rule is not None
        assert rule.target == AgentTarget.LINGXI
        assert rule.tool_name == "execute_command"

    def test_bash(self):
        router = ToolRouter()
        rule = router.route("bash")
        assert rule is not None
        assert rule.target == AgentTarget.LINGXI

    def test_shell(self):
        router = ToolRouter()
        rule = router.route("shell")
        assert rule is not None
        assert rule.target == AgentTarget.LINGXI

    def test_create_session(self):
        router = ToolRouter()
        rule = router.route("create_session")
        assert rule is not None
        assert rule.target == AgentTarget.LINGXI

    def test_sync_terminal(self):
        router = ToolRouter()
        result = router.route_task("sync_terminal")
        assert result["routed"] is True
        assert result["target"] == "灵犀"


# ── 灵克 (LingClaude) 路由 ──


class TestLingKeRouting:
    def test_read_file(self):
        router = ToolRouter()
        result = router.route_task("read_file")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_write_file(self):
        router = ToolRouter()
        result = router.route_task("write_file")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_edit_code(self):
        router = ToolRouter()
        result = router.route_task("edit_code")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_search_code(self):
        router = ToolRouter()
        result = router.route_task("search_code")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_git_operations(self):
        router = ToolRouter()
        for tool in ["git_status", "git_log", "git_diff", "git_blame"]:
            result = router.route_task(tool)
            assert result["routed"] is True, f"{tool} not routed"
            assert result["target"] == "灵克", f"{tool} routed to {result['target']}"

    def test_analyze_full(self):
        router = ToolRouter()
        result = router.route_task("analyze_full")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_code_review_keyword(self):
        router = ToolRouter()
        result = router.route_task("code_review")
        assert result["routed"] is True
        assert result["target"] == "灵克"

    def test_stt(self):
        router = ToolRouter()
        result = router.route_task("stt")
        assert result["routed"] is True
        assert result["target"] == "灵克"


# ── 灵通 (LingFlow) 路由 ──


class TestLingTongRouting:
    def test_workflow(self):
        router = ToolRouter()
        result = router.route_task("workflow")
        assert result["routed"] is True
        assert result["target"] == "灵通"
        assert result["tool"] == "run_workflow"

    def test_skill(self):
        router = ToolRouter()
        result = router.route_task("skill")
        assert result["routed"] is True
        assert result["target"] == "灵通"
        assert result["tool"] == "run_skill"

    def test_run_tests(self):
        router = ToolRouter()
        result = router.route_task("run_tests")
        assert result["routed"] is True
        assert result["target"] == "灵通"

    def test_list_skills(self):
        router = ToolRouter()
        result = router.route_task("list_skills")
        assert result["routed"] is True
        assert result["target"] == "灵通"

    def test_multiedit(self):
        router = ToolRouter()
        result = router.route_task("multiedit")
        assert result["routed"] is True
        assert result["target"] == "灵通"

    def test_requirement(self):
        router = ToolRouter()
        result = router.route_task("requirement")
        assert result["routed"] is True
        assert result["target"] == "灵通"

    def test_coverage(self):
        router = ToolRouter()
        result = router.route_task("coverage")
        assert result["routed"] is True
        assert result["target"] == "灵通"

    def test_health(self):
        router = ToolRouter()
        result = router.route_task("health")
        assert result["routed"] is True
        assert result["target"] == "灵通"


# ── 灵依 (LingYi) 路由 ──


class TestLingYiRouting:
    def test_memo(self):
        router = ToolRouter()
        result = router.route_task("memo")
        assert result["routed"] is True
        assert result["target"] == "灵依"

    def test_schedule(self):
        router = ToolRouter()
        result = router.route_task("schedule")
        assert result["routed"] is True
        assert result["target"] == "灵依"

    def test_briefing(self):
        router = ToolRouter()
        result = router.route_task("briefing")
        assert result["routed"] is True
        assert result["target"] == "灵依"

    def test_patrol(self):
        router = ToolRouter()
        result = router.route_task("patrol")
        assert result["routed"] is True
        assert result["target"] == "灵依"

    def test_add_memo_exact(self):
        router = ToolRouter()
        result = router.route_task("add_memo")
        assert result["routed"] is True
        assert result["target"] == "灵依"
        assert result["tool"] == "add_memo"


# ── 灵通问道 (LingTongAsk) 路由 ──


class TestLingTongAskRouting:
    def test_emotion(self):
        router = ToolRouter()
        result = router.route_task("emotion")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"

    def test_speech(self):
        router = ToolRouter()
        result = router.route_task("speech")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"

    def test_voice(self):
        router = ToolRouter()
        result = router.route_task("voice")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"

    def test_podcast(self):
        router = ToolRouter()
        result = router.route_task("podcast")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"

    def test_synthesize_speech_exact(self):
        router = ToolRouter()
        result = router.route_task("synthesize_speech")
        assert result["routed"] is True
        assert result["target"] == "灵通问道"
        assert result["tool"] == "synthesize_speech"


# ── 灵知 (LingZhi) 路由 ──


class TestLingZhiRouting:
    def test_knowledge_search(self):
        router = ToolRouter()
        result = router.route_task("knowledge_search")
        assert result["routed"] is True
        assert result["target"] == "灵知"

    def test_ask_question(self):
        router = ToolRouter()
        result = router.route_task("ask_question")
        assert result["routed"] is True
        assert result["target"] == "灵知"

    def test_safe_db_query(self):
        router = ToolRouter()
        result = router.route_task("safe_db_query")
        assert result["routed"] is True
        assert result["target"] == "灵知"

    def test_chinese_keyword(self):
        router = ToolRouter()
        result = router.route_task("知识")
        assert result["routed"] is True
        assert result["target"] == "灵知"


# ── 灵信 (LingMessage) 路由 ──


class TestLingMessageRouting:
    def test_open_thread(self):
        router = ToolRouter()
        result = router.route_task("open_thread")
        assert result["routed"] is True
        assert result["target"] == "灵信"

    def test_message(self):
        router = ToolRouter()
        result = router.route_task("message")
        assert result["routed"] is True
        assert result["target"] == "灵信"

    def test_discussion(self):
        router = ToolRouter()
        result = router.route_task("discussion")
        assert result["routed"] is True
        assert result["target"] == "灵信"

    def test_sign(self):
        router = ToolRouter()
        result = router.route_task("sign")
        assert result["routed"] is True
        assert result["target"] == "灵信"

    def test_annotate(self):
        router = ToolRouter()
        result = router.route_task("annotate")
        assert result["routed"] is True
        assert result["target"] == "灵信"


# ── ToolRouter 新方法 ──


class TestToolRouterNewMethods:
    def test_route_by_tool_name(self):
        router = ToolRouter()
        result = router.route_by_tool_name("git_status")
        assert result is not None
        assert result["target"] == "灵克"
        assert result["tool"] == "git_status"

    def test_route_by_tool_name_unknown(self):
        router = ToolRouter()
        result = router.route_by_tool_name("nonexistent_tool_xyz")
        assert result is None

    def test_get_tools_for_agent(self):
        router = ToolRouter()
        tools = router.get_tools_for_agent(AgentTarget.LINGTONG)
        assert "run_workflow" in tools
        assert "run_skill" in tools
        assert "list_skills" in tools
        assert len(tools) >= 20

    def test_get_tools_for_agent_lingxi(self):
        router = ToolRouter()
        tools = router.get_tools_for_agent(AgentTarget.LINGXI)
        assert "execute_command" in tools
        assert "sync_terminal" in tools
        assert len(tools) >= 5

    def test_get_agents_summary(self):
        router = ToolRouter()
        summary = router.get_agents_summary()
        assert len(summary) >= 8
        agent_names = {s["target"] for s in summary}
        assert "灵犀" in agent_names
        assert "灵通" in agent_names
        assert "灵克" in agent_names

    def test_list_routes_ordered_by_priority(self):
        router = ToolRouter()
        routes = router.list_routes()
        assert len(routes) >= 99
        for i in range(len(routes) - 1):
            assert routes[i]["priority"] >= routes[i + 1]["priority"]


# ── MCP Registry ──


class TestMCPRegistry:
    def test_twelve_servers_registered(self):
        assert len(MCP_SERVERS) == 12

    def test_all_transport_types(self):
        transports = {c.transport for c in MCP_SERVERS.values()}
        assert Transport.STDIO in transports

    def test_lingtong_config(self):
        config = get_server_config("lingtong")
        assert config is not None
        assert config.name == "灵通"
        assert config.agent_id == "lingflow"
        assert config.command == "lingflow-mcp"
        assert len(config.tools) == 24

    def test_lingke_config(self):
        config = get_server_config("lingke")
        assert config is not None
        assert config.name == "灵克"
        assert len(config.tools) == 26

    def test_lingyi_config(self):
        config = get_server_config("lingyi")
        assert config is not None
        assert len(config.tools) == 27

    def test_lingtongask_config(self):
        config = get_server_config("lingtongask")
        assert config is not None
        assert config.name == "灵通问道"
        assert config.command == "python"
        assert config.working_dir is not None
        assert "lingtongask" in config.working_dir
        assert len(config.tools) == 9

    def test_lingzhi_config(self):
        config = get_server_config("lingzhi")
        assert config is not None
        assert config.name == "灵知"
        assert len(config.tools) == 11

    def test_lingmessage_servers(self):
        annotate = get_server_config("lingmessage_annotate")
        bus = get_server_config("lingmessage_bus")
        signing = get_server_config("lingmessage_signing")
        assert annotate is not None
        assert bus is not None
        assert signing is not None
        assert len(annotate.tools) == 3
        assert len(bus.tools) == 5
        assert len(signing.tools) == 3

    def test_lingxi_config(self):
        config = get_server_config("lingxi")
        assert config is not None
        assert config.command == "node"
        assert len(config.tools) == 5

    def test_zhibridge_config(self):
        config = get_server_config("zhibridge")
        assert config is not None
        assert len(config.tools) == 1

    def test_get_all_server_configs(self):
        configs = get_all_server_configs()
        assert len(configs) == 12

    def test_find_server_for_tool(self):
        result = find_server_for_tool("run_workflow")
        assert result is not None
        key, config = result
        assert config.name == "灵通"

    def test_find_server_for_tool_unknown(self):
        result = find_server_for_tool("nonexistent_tool")
        assert result is None

    def test_get_tools_by_agent_group(self):
        groups = get_tools_by_agent_group()
        assert "lingflow" in groups
        assert "lingclaude" in groups
        assert "lingmessage" in groups
        assert len(groups["lingmessage"]) == 11  # 3+5+3

    def test_get_server_stats(self):
        stats = get_server_stats()
        assert stats["total_servers"] == 12
        assert stats["total_tools"] >= 140
        assert "灵通" in stats["by_agent"]
        assert "灵克" in stats["by_agent"]

    def test_all_servers_have_command(self):
        for key, config in MCP_SERVERS.items():
            assert config.command is not None, f"{key} has no command"

    def test_all_tools_nonempty(self):
        for key, config in MCP_SERVERS.items():
            assert len(config.tools) > 0, f"{key} has no tools"

    def test_no_tool_overlap_within_agent(self):
        for key, config in MCP_SERVERS.items():
            assert len(config.tools) == len(set(config.tools)), f"{key} has duplicate tools"


# ── 集成：路由器 + 注册表一致性 ──


class TestRouterRegistryConsistency:
    def test_all_mcp_tools_have_route(self):
        router = ToolRouter()
        routed_tools = {r.tool_name for r in DEFAULT_RULES}
        for key, config in MCP_SERVERS.items():
            for tool in config.tools:
                assert tool in routed_tools, f"Tool '{tool}' from {key} has no route"

    def test_all_agents_in_enum(self):
        from lingflow_plus.mcp_registry import MCP_SERVERS
        for key, config in MCP_SERVERS.items():
            assert any(a.name.lower() == config.agent_id or a.value == config.name for a in AgentTarget), \
                f"No AgentTarget for {key} ({config.name}, agent_id={config.agent_id})"


# ── Cross-Registration Integrity Tests ──


class TestCrossRegistrationIntegrity:
    """Validate cross-registration: every MCP server entry point must exist on disk,
    all tool counts must match source-of-truth, no duplicate tools across servers."""

    def test_all_server_paths_exist(self):
        """Every MCPServerConfig with working_dir or args pointing to files must resolve."""
        from pathlib import Path

        for key, config in MCP_SERVERS.items():
            if config.working_dir:
                assert Path(config.working_dir).exists(), f"{key}: working_dir {config.working_dir} not found"
            for arg in config.args:
                if arg.endswith(".py") or arg.endswith(".js") or arg.endswith(".ts"):
                    if arg.startswith("/"):
                        assert Path(arg).exists(), f"{key}: arg path {arg} not found"

    def test_no_duplicate_tools_across_servers(self):
        """Tool names shared across servers are allowed only if resolved by router priority."""
        tool_to_servers: dict = {}
        for key, config in MCP_SERVERS.items():
            for tool in config.tools:
                if tool not in tool_to_servers:
                    tool_to_servers[tool] = []
                tool_to_servers[tool].append(key)
        collisions = {t: keys for t, keys in tool_to_servers.items() if len(keys) > 1}
        known_accepted = {"knowledge_search", "list_categories"}
        unresolved = {t: keys for t, keys in collisions.items() if t not in known_accepted}
        assert unresolved == {}, f"Unresolved tool collisions: {unresolved}"

    def test_lingyang_registered(self):
        config = get_server_config("lingyang")
        assert config is not None
        assert config.name == "灵扬"
        assert len(config.tools) == 14
        assert "collect_metrics" in config.tools
        assert "add_contact" in config.tools

    def test_lingresearch_registered(self):
        config = get_server_config("lingresearch")
        assert config is not None
        assert config.name == "灵妍"
        assert len(config.tools) == 16
        assert "add_intel" in config.tools
        assert "generate_digest" in config.tools

    def test_lingyi_all_27_tools_registered(self):
        config = get_server_config("lingyi")
        assert len(config.tools) == 27
        expected_new = [
            "today_schedule", "week_schedule", "smart_remind",
            "done_plan", "week_plans", "plan_stats",
            "list_projects", "save_session", "last_session",
            "search_knowledge", "speak", "synthesize_to_file",
            "transcribe", "council_scan", "council_health",
        ]
        for tool in expected_new:
            assert tool in config.tools, f"Missing tool: {tool}"

    def test_no_hardcoded_home_in_source(self):
        """Source code of mcp_registry.py must not contain hardcoded /home/ai/ paths."""
        from pathlib import Path
        source = (Path(__file__).parent.parent / "lingflow_plus" / "mcp_registry.py").read_text()
        assert '"/home/ai/' not in source, "Hardcoded /home/ai/ path found in mcp_registry.py source"
        assert "'/home/ai/" not in source, "Hardcoded /home/ai/ path found in mcp_registry.py source"

    def test_total_tool_count_matches_registry(self):
        """Sum of all server tools must match get_server_stats."""
        stats = get_server_stats()
        manual_count = sum(len(c.tools) for c in MCP_SERVERS.values())
        assert stats["total_tools"] == manual_count

    def test_router_all_new_agent_tools_routable(self):
        """Every tool in lingyang and lingresearch must have an exact-match route."""
        router = ToolRouter()
        for key in ("lingyang", "lingresearch"):
            config = get_server_config(key)
            assert config is not None
            for tool in config.tools:
                rule = router.route(tool)
                assert rule is not None, f"Tool '{tool}' from {key} has no route"
                assert rule.tool_name == tool, f"Tool '{tool}' routed to wrong tool: {rule.tool_name}"


class TestCrossRegistrationRouting:
    """End-to-end routing tests for cross-registered tools."""

    def test_route_metric_to_lingyang(self):
        router = ToolRouter()
        rule = router.route("collect_metrics")
        assert rule is not None
        assert rule.target == AgentTarget.LINGYANG

    def test_route_intel_to_lingresearch(self):
        router = ToolRouter()
        rule = router.route("add_intel")
        assert rule is not None
        assert rule.target == AgentTarget.LINGRESEARCH

    def test_route_schedule_to_lingyi(self):
        router = ToolRouter()
        rule = router.route("today_schedule")
        assert rule is not None
        assert rule.target == AgentTarget.LINGYI

    def test_route_contact_to_lingyang(self):
        router = ToolRouter()
        rule = router.route("add_contact")
        assert rule is not None
        assert rule.target == AgentTarget.LINGYANG

    def test_route_digest_to_lingresearch(self):
        router = ToolRouter()
        rule = router.route("generate_digest")
        assert rule is not None
        assert rule.target == AgentTarget.LINGRESEARCH

    def test_alias_metric_routes(self):
        router = ToolRouter()
        rule = router.route("metric")
        assert rule is not None
        assert rule.target == AgentTarget.LINGYANG

    def test_alias_research_routes(self):
        router = ToolRouter()
        rule = router.route("research")
        assert rule is not None
        assert rule.target == AgentTarget.LINGRESEARCH

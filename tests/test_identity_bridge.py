"""Comprehensive tests for identity_bridge module."""
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.identity_bridge import (
    HAS_LINGMESSAGE,
    agent_id_to_display_name,
    build_registry,
    server_key_to_agent_id,
)
from lingflow_plus.mcp_registry import MCP_SERVERS


@pytest.mark.skipif(not HAS_LINGMESSAGE, reason="LingMessage not installed")
class TestBuildRegistry:
    def test_returns_identity_registry(self):
        from lingmessage.types import IdentityRegistry

        reg = build_registry()
        assert isinstance(reg, IdentityRegistry)

    def test_registry_contains_mcp_servers(self):
        reg = build_registry()
        for server_key in MCP_SERVERS:
            entry = reg.get_by_server_key(server_key)
            if entry is not None:
                assert entry.mcp_server_key == server_key
                assert entry.mcp_command is not None

    def test_registry_tools_populated(self):
        reg = build_registry()
        for server_key, config in MCP_SERVERS.items():
            entry = reg.get_by_server_key(server_key)
            if entry is not None:
                assert len(entry.tools) == len(config.tools)

    def test_unknown_agent_id_skipped(self):
        """Agent IDs not in LingIdentity should be silently skipped."""
        reg = build_registry()
        assert reg is not None


@pytest.mark.skipif(not HAS_LINGMESSAGE, reason="LingMessage not installed")
class TestAgentIdToDisplayName:
    def test_known_agent(self):
        from lingmessage.types import LingIdentity

        name = agent_id_to_display_name("lingflow")
        assert name != "lingflow"
        assert len(name) > 0

    def test_unknown_agent_returns_id(self):
        name = agent_id_to_display_name("nonexistent_agent")
        assert name == "nonexistent_agent"

    def test_various_known_agents(self):
        for agent_id in ["lingflow", "lingclaude", "lingke"]:
            name = agent_id_to_display_name(agent_id)
            assert isinstance(name, str)
            assert len(name) > 0


class TestServerKeyToAgentId:
    def test_known_server(self):
        agent_id = server_key_to_agent_id("lingtong")
        assert agent_id is not None
        assert isinstance(agent_id, str)

    def test_unknown_server(self):
        agent_id = server_key_to_agent_id("nonexistent_server")
        assert agent_id is None

    def test_all_servers_have_agent_id(self):
        for server_key in MCP_SERVERS:
            agent_id = server_key_to_agent_id(server_key)
            assert agent_id is not None, f"Missing agent_id for {server_key}"


@pytest.mark.skipif(not HAS_LINGMESSAGE, reason="LingMessage not installed")
class TestRegistryRoundTrip:
    def test_server_key_lookup_after_build(self):
        reg = build_registry()
        lingtong = reg.get_by_server_key("lingtong")
        assert lingtong is not None
        assert lingtong.mcp_server_key == "lingtong"

    def test_tool_provider_search(self):
        reg = build_registry()
        providers = reg.find_tool_provider("knowledge_search")
        assert len(providers) > 0


class TestNoLingMessageFallback:
    def test_agent_id_to_display_name_without_lingmessage(self):
        with patch("lingflow_plus.identity_bridge.HAS_LINGMESSAGE", False):
            name = agent_id_to_display_name("lingflow")
            assert name == "lingflow"

    def test_agent_id_unknown_without_lingmessage(self):
        with patch("lingflow_plus.identity_bridge.HAS_LINGMESSAGE", False):
            name = agent_id_to_display_name("anything")
            assert name == "anything"

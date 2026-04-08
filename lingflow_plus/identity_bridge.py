"""Identity Bridge — aligns LingFlow+ with LingMessage's IdentityRegistry.

This module provides a bridge between LingFlow+'s internal identity systems
(AgentTarget, mcp_registry agent_id) and LingMessage's canonical IdentityRegistry.

Usage:
    from lingflow_plus.identity_bridge import build_registry

    registry = build_registry()
    entry = registry.get_by_server_key("lingtong")
    providers = registry.find_tool_provider("knowledge_search")
"""

from __future__ import annotations

from lingflow_plus.mcp_registry import MCP_SERVERS

try:
    from lingmessage.types import (
        IdentityEntry,
        IdentityRegistry,
        LingIdentity,
        SourceType,
    )
    HAS_LINGMESSAGE = True
except ImportError:
    HAS_LINGMESSAGE = False


def build_registry() -> IdentityRegistry:
    """Build IdentityRegistry by merging LingMessage defaults with MCP registry.

    LingMessage provides the canonical identity definitions (LingIdentity enum,
    display names). LingFlow+'s mcp_registry provides server configuration
    (command, args, tools). This function merges both sources.

    Returns:
        IdentityRegistry with entries from both sources
    """
    reg = IdentityRegistry.default()

    for server_key, config in MCP_SERVERS.items():
        try:
            identity = LingIdentity(config.agent_id)
        except ValueError:
            continue

        existing = reg.get(identity)
        if existing:
            from lingmessage.types import _now_iso
            merged = IdentityEntry(
                identity=identity,
                display_name=existing.display_name,
                mcp_server_key=server_key,
                mcp_command=config.command or "",
                mcp_args=tuple(config.args),
                working_dir=config.working_dir or "",
                tools=tuple(config.tools),
                source_type=existing.source_type,
                process_status=existing.process_status,
                last_heartbeat=existing.last_heartbeat,
            )
            reg.register(merged)

    return reg


def agent_id_to_display_name(agent_id: str) -> str:
    """Convert mcp_registry agent_id to Chinese display name.

    Args:
        agent_id: e.g. "lingflow", "lingclaude"

    Returns:
        Display name e.g. "灵通", "灵克", or agent_id if unknown
    """
    if HAS_LINGMESSAGE:
        try:
            identity = LingIdentity(agent_id)
            from lingmessage.types import _IDENTITY_NAMES
            return _IDENTITY_NAMES.get(identity, agent_id)
        except ValueError:
            return agent_id
    return agent_id


def server_key_to_agent_id(server_key: str) -> str | None:
    """Convert mcp_registry server_key to LingIdentity value.

    Args:
        server_key: e.g. "lingtong", "lingke"

    Returns:
        agent_id / LingIdentity value, or None if not found
    """
    config = MCP_SERVERS.get(server_key)
    return config.agent_id if config else None

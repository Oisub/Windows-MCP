import os


def is_debug() -> bool:
    """Return True if debug mode is enabled via the WINDOWS_MCP_DEBUG environment variable."""
    return os.getenv("WINDOWS_MCP_DEBUG", "false").lower() in ("1", "true", "yes", "on")


def control_gate_enabled() -> bool:
    """Fork change: the desktop-control gate is opt-in (WINDOWS_MCP_CONTROL=on).

    Upstream always runs it: input hooks, the AI indicator overlay and a
    user-takeover lease. With a person chatting with the agent at the same
    machine, every keystroke blocks all tools for 10 s, and an indicator
    health hiccup fails the server closed (CONTROL_UNAVAILABLE).
    """
    return os.getenv("WINDOWS_MCP_CONTROL", "off").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    )


def esc_takeover_enabled() -> bool:
    """Fork addition: reclaim control only on Esc (WINDOWS_MCP_ESC_TAKEOVER=on).

    Default off keeps upstream behaviour, where any physical mouse movement or
    key press reclaims control from the agent. With a person sharing the machine
    with the agent, incidental trackpad contact then seizes control constantly;
    enabling this makes Esc the only reclaim signal (the Ctrl+Alt+Shift+Backspace
    emergency chord and every fail-open path still apply).
    """
    return os.getenv("WINDOWS_MCP_ESC_TAKEOVER", "off").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    )


def enable_debug() -> None:
    """Enable debug mode by setting the WINDOWS_MCP_DEBUG environment variable."""
    os.environ["WINDOWS_MCP_DEBUG"] = "true"

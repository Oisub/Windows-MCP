"""WINDOWS_MCP_CONTROL actually gates the desktop-control machinery.

Fork change. Upstream always runs input hooks, the overlay and the takeover
lease; this fork makes them opt-in. These tests pin that the flag is wired end
to end: off means no subscribe, no overlay/controller start and no tool gate;
on means all three run.
"""

import pytest


class _FakeController:
    def __init__(self):
        self.listeners = []
        self.started = False
        self.stopped = False
        self.health_probe = None
        self.state = "ready"
        self.generation = 1
        self.esc_takeover = False
        self.mouse_takeover_units = 0
        self.mouse_takeover_pixels = 0
        self._thread = None

    def subscribe(self, callback):
        self.listeners.append(callback)

    def status(self):
        return {"state": self.state, "generation": self.generation, "wait_seconds": 0.0}

    def set_health_probe(self, probe):
        self.health_probe = probe

    def start(self):
        self.started = True
        self.state = "user"

    def stop(self):
        self.stopped = True
        self.state = "unavailable"


def _patch_build(monkeypatch, overlay_calls):
    from windows_mcp import __main__ as wm
    from windows_mcp.desktop import control as control_module, control_overlay
    from windows_mcp.desktop import service as desktop_service
    from windows_mcp import tools as tool_registry

    controller = _FakeController()
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "false")
    monkeypatch.setattr(wm, "_mcp", None)
    monkeypatch.setattr(control_module, "get_controller", lambda: controller)
    monkeypatch.setattr(tool_registry, "register_all", lambda *a, **k: None)
    monkeypatch.setattr(wm, "_start_watchdog", lambda desktop: None)
    monkeypatch.setattr(
        desktop_service, "Desktop", type("D", (), {"get_screen_size": lambda self: (100, 100)})
    )
    monkeypatch.setattr(control_overlay, "start", lambda: overlay_calls.append("start"))
    monkeypatch.setattr(control_overlay, "stop", lambda: overlay_calls.append("stop"))
    return wm, controller


def _has_control_gate(mcp) -> bool:
    from windows_mcp.tools.control_notifications import ControlToolGate

    return any(isinstance(m, ControlToolGate) for m in mcp.middleware)


@pytest.mark.asyncio
async def test_control_off_skips_all_machinery(monkeypatch):
    overlay_calls: list[str] = []
    wm, controller = _patch_build(monkeypatch, overlay_calls)
    monkeypatch.delenv("WINDOWS_MCP_CONTROL", raising=False)  # default off

    mcp = wm._build_mcp()
    assert controller.listeners == []  # no state subscription
    assert not _has_control_gate(mcp)  # tools are not ownership-gated
    async with mcp._lifespan(mcp):
        assert controller.started is False
        assert overlay_calls == []
    assert controller.stopped is False


@pytest.mark.asyncio
async def test_control_on_runs_machinery(monkeypatch):
    overlay_calls: list[str] = []
    wm, controller = _patch_build(monkeypatch, overlay_calls)
    monkeypatch.setenv("WINDOWS_MCP_CONTROL", "on")
    monkeypatch.setenv("WINDOWS_MCP_ESC_TAKEOVER", "on")

    mcp = wm._build_mcp()
    assert len(controller.listeners) == 1  # subscribed to state changes
    assert _has_control_gate(mcp)  # tool calls are ownership-gated
    async with mcp._lifespan(mcp):
        assert controller.started is True
        assert controller.health_probe is not None
        assert controller.esc_takeover is True  # env applied in the on path
        assert "start" in overlay_calls
    assert controller.stopped is True
    assert "stop" in overlay_calls

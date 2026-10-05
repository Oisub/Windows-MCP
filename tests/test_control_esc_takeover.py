"""esc_takeover mode: only Esc (and the emergency chord) reclaims control.

Fork addition. In this mode a person can share the machine with the agent
without stray trackpad contact or typing seizing control; only a deliberate
Esc hands control back.
"""

import ctypes

from windows_mcp.desktop import control


def armed_ai_controller(esc_takeover: bool) -> tuple[control.ControlCoordinator, int]:
    """Return a controller in the armed, suppressing AI state plus its lease token."""
    owner = control.ControlCoordinator(esc_takeover=esc_takeover)
    with owner._lock:
        owner._set_locked("ready")
    owner.set_health_probe(lambda: True)
    owner.subscribe(
        lambda status: owner.arm_visible(status["generation"]) if status["state"] == "ai" else None
    )
    token = owner.begin_call("Type")
    owner.checkpoint(token)
    assert owner._suppress
    return owner, token


def test_mouse_movement_does_not_reclaim_or_pause(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=True)

    data = control._MouseHookData()
    data.flags = 0
    # A physical move is swallowed while suppressed, but must not pause the agent.
    assert owner._physical_mouse(0, 0x200, ctypes.addressof(data)) == 1
    assert owner._fast_pending is False

    owner._handle(owner._events.get_nowait())
    assert owner.status()["state"] == "ai"


def test_mouse_movement_still_pauses_without_esc_mode(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=False)

    data = control._MouseHookData()
    data.flags = 0
    assert owner._physical_mouse(0, 0x200, ctypes.addressof(data)) == 1
    assert owner._fast_pending is True  # upstream behaviour unchanged


def test_ordinary_key_does_not_reclaim(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=True)

    event = control._KeyHookData()
    event.vkCode = 0x41  # 'A'
    event.flags = 0
    assert owner._physical_key(0, 0x100, ctypes.addressof(event)) == 1  # swallowed

    owner._handle(owner._events.get_nowait())
    assert owner.status()["state"] == "ai"


def test_escape_reclaims_control_and_passes_through(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=True)

    event = control._KeyHookData()
    event.vkCode = 0x1B  # VK_ESCAPE
    event.flags = 0
    # Esc is passed through (not consumed) so the focused app still sees it.
    assert owner._physical_key(0, 0x100, ctypes.addressof(event)) == 7
    assert owner._fast_takeover is True
    assert not owner._suppress

    owner._handle(owner._events.get_nowait())
    assert owner.status()["state"] == "user"


def test_escape_is_inert_when_agent_not_in_control(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner = control.ControlCoordinator(esc_takeover=True)
    with owner._lock:
        owner._set_locked("ready")

    event = control._KeyHookData()
    event.vkCode = 0x1B
    event.flags = 0
    # No AI lease to reclaim: Esc is an ordinary pass-through key, no takeover.
    assert owner._physical_key(0, 0x100, ctypes.addressof(event)) == 7
    assert owner._fast_takeover is False
    assert owner._events.get_nowait() == ("key",)


def test_escape_ignored_in_default_mode(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=False)

    event = control._KeyHookData()
    event.vkCode = 0x1B
    event.flags = 0
    # Default mode has no special Esc path; it is swallowed like any key.
    assert owner._physical_key(0, 0x100, ctypes.addressof(event)) == 1
    assert owner._fast_takeover is False


def test_emergency_chord_still_reclaims_in_esc_mode(monkeypatch):
    monkeypatch.setattr(control._user32, "CallNextHookEx", lambda *args: 7)
    owner, _ = armed_ai_controller(esc_takeover=True)

    for vk in (0x10, 0x11, 0x12):  # Shift, Ctrl, Alt held.
        event = control._KeyHookData()
        event.vkCode = vk
        event.flags = 0
        owner._physical_key(0, 0x100, ctypes.addressof(event))
    chord = control._KeyHookData()
    chord.vkCode = 0x08  # Backspace completes the chord.
    chord.flags = 0
    assert owner._physical_key(0, 0x100, ctypes.addressof(chord)) == 1  # consumed
    assert owner._fast_takeover is True

    while not owner._events.empty():
        owner._handle(owner._events.get_nowait())
    assert owner.status()["state"] == "user"

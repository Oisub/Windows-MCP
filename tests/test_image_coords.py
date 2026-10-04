"""Fork addition: image-space coordinates (coords='image').

The screenshot the agent sees is often downscaled and, for region/display
captures, does not start at screen (0, 0). image_to_screen must apply both the
per-axis ratio and the capture origin.
"""

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import ScreenshotGeometry
from windows_mcp.tools.input import _to_screen


def _desktop(geometry: ScreenshotGeometry | None) -> Desktop:
    desktop = Desktop.__new__(Desktop)  # skip __init__: no UIA needed for the mapping
    desktop.last_capture = geometry
    return desktop


def test_full_desktop_downscaled() -> None:
    # 3072x1920 screen shown as 1728x1080
    d = _desktop(ScreenshotGeometry(0, 0, 1728, 1080, 3072 / 1728, 1920 / 1080))
    assert d.image_to_screen([864, 540]) == [1536, 960]
    assert d.image_to_screen([0, 0]) == [0, 0]


def test_region_capture_adds_origin() -> None:
    # region [1000, 500, 1800, 1000] shown at full size: image (0,0) is screen (1000,500)
    d = _desktop(ScreenshotGeometry(1000, 500, 800, 500, 1.0, 1.0))
    assert d.image_to_screen([10, 20]) == [1010, 520]


def test_negative_virtual_origin() -> None:
    # a monitor left of the primary puts the virtual desktop origin at negative x
    d = _desktop(ScreenshotGeometry(-1920, 0, 1920, 540, 2.0, 2.0))
    assert d.image_to_screen([960, 270]) == [0, 540]


def test_requires_a_screenshot() -> None:
    with pytest.raises(ValueError, match="screenshot first"):
        _desktop(None).image_to_screen([1, 1])


def test_rejects_points_outside_the_image() -> None:
    d = _desktop(ScreenshotGeometry(0, 0, 100, 100, 1.0, 1.0))
    with pytest.raises(ValueError, match="outside the last screenshot"):
        d.image_to_screen([101, 5])


def test_to_screen_passthrough_and_mapping() -> None:
    d = _desktop(ScreenshotGeometry(100, 100, 50, 50, 2.0, 2.0))
    assert _to_screen(d, [7, 8], "screen") == [7, 8]
    assert _to_screen(d, [10, 10], "image") == [120, 120]
    assert _to_screen(d, ["10", "10"], "image") == [120, 120]
    with pytest.raises(ValueError, match="coords must be"):
        _to_screen(d, [1, 1], "pixels")

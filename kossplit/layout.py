"""Placement maths for dialogs and menus, kept free of Kivy so it can be unit tested.

All values are window pixels measured from the bottom, like Kivy coordinates.
"""

from __future__ import annotations


def dialog_frame(
    window_height: float,
    safe_top: float,
    safe_bottom: float,
    keyboard: float,
    gap: float,
    min_free: float,
    max_ratio: float = 0.88,
) -> tuple[float, float]:
    """Height and center y of a dialog that stays between the top bar and the bottom bar or keyboard.

    The keyboard covers the navigation bar, so the bottom edge is whichever reaches higher.
    """
    top_gap = safe_top + gap
    bottom_gap = max(safe_bottom, keyboard) + gap
    free = max(min_free, window_height - top_gap - bottom_gap)
    height = min(window_height * max_ratio, free)
    return height, bottom_gap + free / 2


def dropdown_frame(
    anchor_bottom: float,
    anchor_top: float,
    wanted: float,
    low: float,
    high: float,
    min_height: float,
) -> tuple[float, float]:
    """Height and bottom y of a menu attached to a widget, kept between low and high.

    Opens below the widget when it fits, otherwise above. When neither side fits, the
    roomier side is used and the menu is shortened so its list scrolls.
    """
    below = anchor_bottom - low
    above = high - anchor_top
    if below >= wanted:
        return wanted, anchor_bottom - wanted
    if above >= wanted:
        return wanted, anchor_top
    if below >= above:
        height = max(min_height, below)
        return height, anchor_bottom - height
    return max(min_height, above), anchor_top

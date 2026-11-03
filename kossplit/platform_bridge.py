"""Small wrappers for Android intents with desktop fallbacks."""

from __future__ import annotations

import webbrowser

from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.utils import platform

IS_ANDROID = platform == "android"


def copy_text(text: str) -> None:
    Clipboard.copy(text)


def _android_views():
    """The Kivy activity, its decor view, and the on-screen rectangle of the app surface."""
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    decor = activity.getWindow().getDecorView()
    content = activity.findViewById(autoclass("android.R$id").content)
    rect = autoclass("android.graphics.Rect")()
    content.getGlobalVisibleRect(rect)
    return activity, decor, rect


def _resource_bar_sizes(activity) -> tuple[int, int]:
    """Status bar and navigation bar heights declared by the system theme, in pixels."""
    resources = activity.getResources()

    def dimen(name: str) -> int:
        ident = resources.getIdentifier(name, "dimen", "android")
        return resources.getDimensionPixelSize(ident) if ident > 0 else 0

    return dimen("status_bar_height"), dimen("navigation_bar_height")


def fallback_bar_sizes() -> tuple[int, int]:
    """Conservative padding for when the real overlap cannot be measured.

    Extra empty space is safer than letting the clock, battery, or navigation buttons
    cover the app, so this assumes the bars overlap the app surface.
    """
    if not IS_ANDROID:
        return 0, 0
    try:
        from jnius import autoclass

        top, bottom = _resource_bar_sizes(autoclass("org.kivy.android.PythonActivity").mActivity)
    except Exception:
        top = bottom = 0
    return top or int(dp(24)), bottom or int(dp(48))


def system_bar_overlap() -> tuple[int, int] | None:
    """Pixels of the app surface hidden under the status bar (top) and navigation bar (bottom).

    Apps targeting Android 15 are drawn edge to edge, behind the system bars. The overlap is
    measured against where the content view really sits, so devices that still reserve space
    for the bars report zero instead of getting double padding.

    Returns None while Android has not laid out the window yet, so the caller can retry.
    """
    if not IS_ANDROID:
        return 0, 0
    try:
        activity, decor, rect = _android_views()
        insets = decor.getRootWindowInsets()
        if insets is None or decor.getHeight() <= 0 or rect.height() <= 0:
            return None  # Window not attached or laid out yet
    except Exception:
        return fallback_bar_sizes()
    try:
        from jnius import autoclass

        types = autoclass("android.view.WindowInsets$Type")
        bars = insets.getInsets(types.systemBars() | types.displayCutout())
        top, bottom = bars.top, bars.bottom
    except Exception:  # Android 10 and older
        try:
            top, bottom = insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetBottom()
        except Exception:
            top, bottom = _resource_bar_sizes(activity)
    screen_bottom = decor.getHeight() - bottom
    return max(0, top - rect.top), max(0, rect.bottom - screen_bottom)


def keyboard_overlap() -> int:
    """Pixels of the app surface currently hidden under the on-screen keyboard.

    Kivy's own keyboard_height is always 0 on the SDL2 Android bootstrap, so it is measured
    here. When Android already shrank the app above the keyboard, this reports zero.
    """
    if not IS_ANDROID:
        return 0
    try:
        _activity, decor, rect = _android_views()
        insets = decor.getRootWindowInsets()
        if insets is None or decor.getHeight() <= 0:
            return 0
        try:
            from jnius import autoclass

            keyboard = insets.getInsets(autoclass("android.view.WindowInsets$Type").ime()).bottom
        except Exception:  # Android 10 and older: the keyboard shrinks the visible frame
            from jnius import autoclass

            frame = autoclass("android.graphics.Rect")()
            decor.getWindowVisibleDisplayFrame(frame)
            keyboard = decor.getHeight() - frame.bottom
        if keyboard <= 0:
            return 0
        return max(0, rect.bottom - (decor.getHeight() - keyboard))
    except Exception:
        return 0


def open_url(url: str) -> bool:
    if not IS_ANDROID:
        return webbrowser.open(url)
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
    try:
        PythonActivity.mActivity.startActivity(intent)
        return True
    except Exception:
        return False


def open_app(package: str) -> bool:
    """Open an installed app by package, or its Play Store page when missing.

    Uses an explicit launcher intent so Android 11 package visibility rules do
    not require a <queries> manifest entry.
    """
    if not IS_ANDROID:
        return False
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    intent = Intent(Intent.ACTION_MAIN)
    intent.addCategory(Intent.CATEGORY_LAUNCHER)
    intent.setPackage(package)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    try:
        PythonActivity.mActivity.startActivity(intent)
        return True
    except Exception:
        return open_url(f"market://details?id={package}") or open_url(
            f"https://play.google.com/store/apps/details?id={package}"
        )

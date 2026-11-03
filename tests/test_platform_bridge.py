"""Android measurements, checked against a fake pyjnius that imitates real devices."""

import sys
import types

import pytest

from kivy.metrics import dp

from kossplit import platform_bridge

SCREEN = 2400


class Rect:
    def __init__(self):
        self.top = self.bottom = 0

    def height(self):
        return self.bottom - self.top


class Device:
    """A phone: screen height, where Kivy's surface sits, and what the system reports."""

    def __init__(
        self,
        content=(0, SCREEN),
        bars=(96, 63),
        keyboard=0,
        laid_out=True,
        modern=True,
        legacy_insets=True,
        visible_bottom=None,
    ):
        self.content = content
        self.bars = bars
        self.keyboard = keyboard
        self.laid_out = laid_out
        self.modern = modern
        self.legacy_insets = legacy_insets
        self.visible_bottom = visible_bottom

    def autoclass(self, name):
        device = self
        if name == "org.kivy.android.PythonActivity":
            return types.SimpleNamespace(mActivity=Activity(device))
        if name == "android.R$id":
            return types.SimpleNamespace(content=1)
        if name == "android.graphics.Rect":
            return Rect
        if name == "android.view.WindowInsets$Type":
            if not device.modern:
                raise Exception("Class not found on Android 10")
            return types.SimpleNamespace(systemBars=lambda: 1, displayCutout=lambda: 2, ime=lambda: 4)
        raise AssertionError(f"unexpected class {name}")


class Insets:
    def __init__(self, device):
        self.device = device

    def getInsets(self, mask):
        if mask == 4:
            return types.SimpleNamespace(top=0, bottom=self.device.keyboard)
        top, bottom = self.device.bars
        return types.SimpleNamespace(top=top, bottom=bottom)

    def getSystemWindowInsetTop(self):
        if not self.device.legacy_insets:
            raise Exception("not available")
        return self.device.bars[0]

    def getSystemWindowInsetBottom(self):
        if not self.device.legacy_insets:
            raise Exception("not available")
        return self.device.bars[1]


class Decor:
    def __init__(self, device):
        self.device = device

    def getRootWindowInsets(self):
        return Insets(self.device) if self.device.laid_out else None

    def getHeight(self):
        return SCREEN if self.device.laid_out else 0

    def getWindowVisibleDisplayFrame(self, rect):
        rect.top, rect.bottom = 0, self.device.visible_bottom


class Content:
    def __init__(self, device):
        self.device = device

    def getGlobalVisibleRect(self, rect):
        rect.top, rect.bottom = self.device.content if self.device.laid_out else (0, 0)


class Resources:
    sizes = {"status_bar_height": 84, "navigation_bar_height": 126}

    def getIdentifier(self, name, kind, package):
        return list(self.sizes).index(name) + 1

    def getDimensionPixelSize(self, ident):
        return list(self.sizes.values())[ident - 1]


class Activity:
    def __init__(self, device):
        self.device = device

    def getWindow(self):
        return types.SimpleNamespace(getDecorView=lambda: Decor(self.device))

    def findViewById(self, _ident):
        return Content(self.device)

    def getResources(self):
        return Resources()


@pytest.fixture
def phone(monkeypatch):
    def install(device):
        monkeypatch.setitem(sys.modules, "jnius", types.SimpleNamespace(autoclass=device.autoclass))
        monkeypatch.setattr(platform_bridge, "IS_ANDROID", True)
        return device

    return install


def test_desktop_has_no_bars_or_keyboard(monkeypatch):
    monkeypatch.setattr(platform_bridge, "IS_ANDROID", False)
    assert platform_bridge.system_bar_overlap() == (0, 0)
    assert platform_bridge.keyboard_overlap() == 0


def test_android15_edge_to_edge_pads_status_and_navigation_bars(phone):
    phone(Device(content=(0, SCREEN), bars=(96, 63)))
    assert platform_bridge.system_bar_overlap() == (96, 63)


def test_older_phone_that_reserves_bar_space_gets_no_double_padding(phone):
    phone(Device(content=(96, SCREEN - 63), bars=(96, 63)))
    assert platform_bridge.system_bar_overlap() == (0, 0)


def test_window_not_laid_out_yet_asks_caller_to_retry(phone):
    phone(Device(laid_out=False))
    assert platform_bridge.system_bar_overlap() is None


def test_android10_uses_legacy_insets(phone):
    phone(Device(content=(0, SCREEN), bars=(72, 144), modern=False))
    assert platform_bridge.system_bar_overlap() == (72, 144)


def test_falls_back_to_theme_bar_sizes_when_insets_fail(phone):
    phone(Device(content=(0, SCREEN), modern=False, legacy_insets=False))
    assert platform_bridge.system_bar_overlap() == (84, 126)


def test_unreachable_activity_uses_conservative_padding(phone):
    device = phone(Device())
    device.autoclass = lambda name: (_ for _ in ()).throw(Exception("no activity"))
    sys.modules["jnius"].autoclass = device.autoclass
    assert platform_bridge.system_bar_overlap() == (int(dp(24)), int(dp(48)))


def test_keyboard_overlap_on_edge_to_edge_screen(phone):
    phone(Device(content=(0, SCREEN), keyboard=900))
    assert platform_bridge.keyboard_overlap() == 900


def test_keyboard_hidden_reports_zero(phone):
    phone(Device(content=(0, SCREEN), keyboard=0))
    assert platform_bridge.keyboard_overlap() == 0


def test_keyboard_reports_zero_when_android_already_shrank_the_app(phone):
    phone(Device(content=(0, SCREEN - 900), keyboard=900))
    assert platform_bridge.keyboard_overlap() == 0


def test_android10_keyboard_from_visible_frame(phone):
    phone(Device(content=(0, SCREEN), modern=False, visible_bottom=SCREEN - 900))
    assert platform_bridge.keyboard_overlap() == 900


def test_android10_navigation_bar_alone_is_not_a_keyboard(phone):
    phone(Device(content=(0, SCREEN - 63), modern=False, visible_bottom=SCREEN - 63))
    assert platform_bridge.keyboard_overlap() == 0

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import BoxShadow, Color, InstructionGroup, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.core.text import Label as CoreLabel
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from kossplit.calculator import (
    custom_amount_split,
    equal_split,
    itemized_split,
    percentage_split,
    simplify_debts,
)
from kossplit.database import Database
from kossplit.file_saver import clean_filename, copy_to_folder, mime_type, report_filename
from kossplit.labels import CATEGORIES, METHOD_LABELS, MONTH_NAMES, guess_category
from kossplit.layout import dialog_frame, dropdown_frame
from kossplit.money import parse_amount, reformat_typed_amount, rupiah
from kossplit.payments import (
    PROVIDER_NAMES,
    format_payment_info,
    parse_payment_info,
    payment_reminder,
    whatsapp_url,
)
from kossplit.platform_bridge import (
    IS_ANDROID,
    copy_text,
    fallback_bar_sizes,
    keyboard_overlap,
    open_app,
    open_url,
    system_bar_overlap,
)
from kossplit.receipt_parser import (
    ReceiptDraft,
    ReceiptItem,
    parse_receipt,
)
from kossplit.receipt_scanner import ReceiptScanner


# Dark blue neumorphism. Every surface shares NIGHT; a cool rim light and deep shadow create depth.
NIGHT = (0.106, 0.149, 0.220, 1)
TEXT = (0.910, 0.933, 0.969, 1)
MUTED = (0.576, 0.639, 0.741, 1)
AZURE = (0.184, 0.486, 0.965, 1)
SKY = (0.486, 0.722, 1, 1)
EMBER = (1, 0.541, 0.478, 1)
MINT = (0.373, 0.827, 0.643, 1)
WHITE = (1, 1, 1, 1)
WELL = (0.086, 0.125, 0.192, 1)
GLOW = (0.188, 0.259, 0.388, 0.6)
SHADE = (0.020, 0.035, 0.067, 0.75)
AZURE_SHADE = (0.010, 0.030, 0.080, 0.7)
AZURE_GLOW = (0.55, 0.75, 1, 0.35)

# Bottom navigation, left to right. The order also decides the slide direction.
NAV_TABS = (
    ("Ringkas", "dashboard"),
    ("Tagihan", "bills"),
    ("Catatan", "expenses"),
    ("Anggota", "members"),
)
TAB_ORDER = [name for _, name in NAV_TABS]


def amount(text: str) -> int:
    """Whole Rupiah from any Indonesian format: 48.000, 48.000,00, IDR 48.000, or 48k."""
    return parse_amount(text)


class Neu:
    """Paints a raised, inset, or flat night-blue shape beneath any widget."""

    neu_mode = "raised"
    neu_fill = NIGHT
    neu_radius = dp(16)
    neu_depth = dp(5)

    def neu_setup(self, mode=None, fill=None, radius=None, depth=None):
        self.neu_mode = mode or self.neu_mode
        self.neu_fill = fill or self.neu_fill
        self.neu_radius = self.neu_radius if radius is None else radius
        self.neu_depth = self.neu_depth if depth is None else depth
        self._neu = InstructionGroup()
        # Index 0 keeps Kivy's own canvas.before items, such as the TextInput cursor, on top.
        self.canvas.before.insert(0, self._neu)
        self.bind(pos=self.neu_paint, size=self.neu_paint)
        self.neu_paint()

    def neu_current_mode(self) -> str:
        return self.neu_mode

    def _neu_shadow(self, color, offset, blur, corners, inset):
        self._neu.add(Color(*color))
        self._neu.add(
            BoxShadow(
                pos=self.pos,
                size=self.size,
                offset=offset,
                blur_radius=blur,
                border_radius=corners,
                inset=inset,
            )
        )

    def neu_paint(self, *_):
        group = self._neu
        group.clear()
        mode = self.neu_current_mode()
        radius = max(0, min(self.neu_radius, self.width / 2, self.height / 2))
        corners = (radius, radius, radius, radius)
        accent = self.neu_fill == AZURE
        shade = AZURE_SHADE if accent else SHADE
        depth = self.neu_depth
        if mode == "raised":
            self._neu_shadow(shade, (depth, -depth), depth * 2.6, corners, False)
            self._neu_shadow(GLOW, (-depth, depth), depth * 2.6, corners, False)
        group.add(Color(*self.neu_fill))
        group.add(RoundedRectangle(pos=self.pos, size=self.size, radius=[radius]))
        if mode == "inset":
            inner = depth * 0.7
            self._neu_shadow(shade, (inner, -inner), depth * 1.6, corners, True)
            self._neu_shadow(AZURE_GLOW if accent else GLOW, (-inner, inner), depth * 1.6, corners, True)


class Surface(Neu, BoxLayout):
    def __init__(self, mode="raised", fill=NIGHT, radius=dp(18), depth=dp(6), **kwargs):
        kwargs.pop("background", None)
        super().__init__(**kwargs)
        self.neu_setup(mode=mode, fill=fill, radius=radius, depth=depth)


class TapSurface(ButtonBehavior, Surface):
    """A surface that reacts to touch, used for tappable debt slips."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(state=self.neu_paint)

    def neu_current_mode(self) -> str:
        return "raised" if self.state == "down" else self.neu_mode


class NeuButton(Neu, Button):
    """Raised by default, pressed into the surface while touched."""

    def __init__(self, primary=False, quiet=False, mode="raised", selected=False, **kwargs):
        height = kwargs.pop("height", dp(50))
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = WHITE if primary else (SKY if selected else TEXT)
        self.font_size = sp(12 if quiet else 13)
        self.bold = True
        self.size_hint_y = None
        self.height = height
        self.neu_setup(
            mode="inset" if selected else mode,
            fill=AZURE if primary else NIGHT,
            radius=dp(14 if quiet else 16),
            depth=dp(4),
        )
        self.bind(state=self.neu_paint)

    def neu_current_mode(self) -> str:
        return "inset" if self.state == "down" else self.neu_mode


InkButton = NeuButton


def chevron_points(cx: float, cy: float, up: bool = False) -> list[float]:
    half, rise = dp(5), dp(2.6)
    if up:
        return [cx - half, cy - rise, cx, cy + rise, cx + half, cy - rise]
    return [cx - half, cy + rise, cx, cy - rise, cx + half, cy + rise]


class Chevron(Widget):
    """A stroked chevron that flips up when its menu is open."""

    def __init__(self, up: bool = False, color=MUTED, **kwargs):
        super().__init__(**kwargs)
        self.up = up
        self.tint = color
        self.bind(pos=self.draw, size=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self.tint)
            Line(
                points=chevron_points(self.center_x, self.center_y, self.up),
                width=dp(1.4),
                cap="round",
                joint="round",
            )


class NeuDropDown(Neu, DropDown):
    """Raised night-blue panel that floats below a spinner."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_height = dp(260)
        self.bar_width = dp(3)
        self.bar_color = (*SKY[:3], 0.5)
        self.container.padding = [dp(6), dp(6)]
        self.container.spacing = dp(4)
        self.neu_setup(mode="raised", radius=dp(18), depth=dp(5))

    def _reposition(self, *largs):
        # Kivy places the menu anywhere inside the window; keep it clear of the
        # status bar, navigation bar, and keyboard as well.
        super()._reposition(*largs)
        widget = self.attach_to
        if not self._win or not widget or not widget.get_parent_window():
            return
        app = App.get_running_app()
        wanted = self.container.minimum_height
        if self.max_height is not None:
            wanted = min(self.max_height, wanted)
        self.height, self.y = dropdown_frame(
            anchor_bottom=widget.to_window(*widget.pos)[1],
            anchor_top=widget.to_window(widget.right, widget.top)[1],
            wanted=wanted,
            low=max(app.safe_bottom, app.keyboard_inset) + dp(8),
            high=self._win.height - app.safe_top - dp(8),
            min_height=dp(88),
        )


class NeuOption(Neu, SpinnerOption):
    """Menu row: flat at rest, pressed in while touched or when it is the chosen value."""

    def __init__(self, **kwargs):
        self.selected = False
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT
        self.font_size = sp(13)
        self.height = dp(44)
        self.halign = "left"
        self.valign = "middle"
        self.shorten = True
        self.padding = [dp(14), 0, dp(40), 0]
        self.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.neu_setup(mode="flat", fill=NIGHT, radius=dp(12), depth=dp(3))
        self.bind(state=self.neu_paint)

    def mark(self, selected: bool):
        self.selected = selected
        self.color = SKY if selected else TEXT
        self.bold = selected
        self.neu_paint()

    def neu_current_mode(self) -> str:
        return "inset" if self.state == "down" or self.selected else "flat"

    def neu_paint(self, *_):
        super().neu_paint()
        if self.selected:
            x, y = self.right - dp(24), self.center_y
            self._neu.add(Color(*SKY))
            self._neu.add(
                Line(
                    points=[x - dp(5), y, x - dp(1.5), y - dp(3.5), x + dp(5), y + dp(4)],
                    width=dp(1.5),
                    cap="round",
                    joint="round",
                )
            )


class NeuSpinner(Neu, Spinner):
    """Dropdown trigger with a small field label, the chosen value, and a chevron well."""

    def __init__(self, label: str = "", placeholder: str = "", **kwargs):
        kwargs.setdefault("option_cls", NeuOption)
        kwargs.setdefault("dropdown_cls", NeuDropDown)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(58))
        if placeholder and not kwargs.get("text"):
            kwargs["text"] = placeholder
        self.placeholder = placeholder
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.font_size = sp(14)
        self.halign = "left"
        self.valign = "bottom" if label else "middle"
        self.shorten = True
        self.padding = [dp(16), dp(8), dp(60), dp(10) if label else 0]
        self.kicker = Label(
            text=label.upper(),
            font_size=sp(9),
            bold=True,
            color=MUTED,
            halign="left",
            valign="middle",
            size_hint=(None, None),
        )
        if label:
            self.add_widget(self.kicker)
        self.neu_setup(mode="raised", radius=dp(16), depth=dp(4))
        self.bind(
            size=self._layout,
            pos=self._layout,
            text=self._tint,
            state=self.neu_paint,
            is_open=self._on_open,
        )
        self._layout()
        self._tint()

    def _layout(self, *_):
        self.text_size = self.size
        self.kicker.size = (max(0, self.width - dp(76)), dp(16))
        self.kicker.text_size = self.kicker.size
        self.kicker.pos = (self.x + dp(16), self.top - dp(25))

    def _tint(self, *_):
        self.color = MUTED if self.text == self.placeholder else TEXT

    def _on_open(self, *_):
        self.kicker.color = SKY if self.is_open else MUTED
        if self.is_open:
            for option in self._dropdown.container.children:
                if isinstance(option, NeuOption):
                    option.mark(option.text == self.text)
        self.neu_paint()

    def neu_current_mode(self) -> str:
        return "inset" if self.state == "down" or self.is_open else "raised"

    def neu_paint(self, *_):
        super().neu_paint()
        opened = getattr(self, "is_open", False)
        size = dp(40)
        x, y = self.right - dp(8) - size, self.center_y - size / 2
        self._neu.add(Color(*(NIGHT if opened else WELL)))
        self._neu.add(RoundedRectangle(pos=(x, y), size=(size, size), radius=[dp(12)]))
        self._neu.add(Color(*(SKY if opened else MUTED)))
        self._neu.add(
            Line(
                points=chevron_points(x + size / 2, y + size / 2, opened),
                width=dp(1.4),
                cap="round",
                joint="round",
            )
        )


class NeuField(Neu, TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.neu_setup(mode="inset", radius=dp(14), depth=dp(4))


class NeuBar(Neu, Widget):
    """Inset track with a raised green fill for category totals."""

    def __init__(self, ratio: float, **kwargs):
        self.ratio = max(0.1, min(1.0, ratio))
        super().__init__(**kwargs)
        self.neu_setup(mode="inset", radius=dp(6), depth=dp(2))

    def neu_paint(self, *_):
        super().neu_paint()
        inset = dp(2)
        height = max(0, self.height - inset * 2)
        width = max(height, (self.width - inset * 2) * self.ratio)
        self._neu.add(Color(*MINT))
        self._neu.add(
            RoundedRectangle(
                pos=(self.x + inset, self.y + inset), size=(width, height), radius=[height / 2]
            )
        )


def text_label(
    text: str,
    size: int = 14,
    color=TEXT,
    bold: bool = False,
    height: int | None = None,
    halign: str = "left",
    wrap: bool = False,
    markup: bool = False,
) -> Label:
    # Single-line labels are shortened; wrap=True lets messages break across lines.
    label = Label(
        text=text,
        color=color,
        font_size=sp(size),
        bold=bold,
        halign=halign,
        valign="middle",
        size_hint_y=None,
        height=dp(height or 28),
        shorten=not wrap,
        shorten_from="right",
        markup=markup,
    )
    label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
    return label


def fit_one_line(label: Label, max_size: int, min_size: int) -> Label:
    """Shrink a heading until it fits one line on narrow phones instead of ending in '...'."""

    def fit(*_):
        if label.width <= 1:
            return
        probe = CoreLabel(font_size=sp(max_size), bold=label.bold)
        text_width, _ = probe.get_extents(label.text)
        available = label.width - dp(2)
        if text_width <= available:
            label.font_size = sp(max_size)
        else:
            label.font_size = max(sp(min_size), sp(max_size) * available / text_width)

    label.bind(width=fit, text=fit)
    return label


def track_keyboard(widget: TextInput) -> TextInput:
    """Report focus changes so the app can measure the keyboard and keep the field visible."""

    def changed(instance, focused):
        app = App.get_running_app()
        if app is not None and hasattr(app, "on_field_focus"):
            app.on_field_focus(instance, focused)

    widget.bind(focus=changed)
    return widget


def field(hint: str, multiline: bool = False, height: int = 48) -> TextInput:
    return track_keyboard(NeuField(
        hint_text=hint,
        multiline=multiline,
        size_hint_y=None,
        height=dp(height),
        padding=[dp(16), dp(14)],
        foreground_color=TEXT,
        hint_text_color=(0.576, 0.639, 0.741, 0.8),
        cursor_color=SKY,
        font_size=sp(14),
    ))


class MoneyInput(TextInput):
    """Digits-only input that keeps Indonesian thousand dots while typing: 1500000 -> 1.500.000."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._reformat_soon = Clock.create_trigger(self._reformat, 0)
        self.bind(text=lambda *_: self._reformat_soon(), focus=self._on_focus_change)

    def insert_text(self, substring, from_undo=False):
        if not from_undo and not substring.isdigit():
            # Pasted receipt text such as "IDR 48.000,00" or "48k" becomes whole Rupiah digits.
            try:
                substring = str(parse_amount(substring)) if substring.strip() else ""
            except ValueError:
                substring = re.sub(r"\D", "", substring)
        return super().insert_text(substring, from_undo=from_undo)

    def _reformat(self, *_):
        formatted, index = reformat_typed_amount(self.text, self.cursor_index())
        if formatted == self.text:
            return
        self.text = formatted
        self.cursor = self.get_cursor_from_index(index)

    def _on_focus_change(self, _instance, focused):
        if focused:
            # Select the whole amount on tap so a new number replaces it immediately.
            Clock.schedule_once(lambda *_: self.select_all() if self.focus else None, 0.1)
        else:
            self.scroll_x = 0


class MoneyField(Neu, BoxLayout):
    """Inset Rupiah well: 'Rp' prefix, the editable amount, and a fixed ',00' suffix."""

    text = StringProperty("")

    def __init__(self, hint: str = "0", height: int = 48, **kwargs):
        super().__init__(size_hint_y=None, height=dp(height), padding=[dp(16), 0, dp(14), 0], **kwargs)
        self.add_widget(
            Label(text="Rp", color=MUTED, font_size=sp(13), size_hint_x=None, width=dp(26))
        )
        self.input = MoneyInput(
            hint_text=hint,
            multiline=False,
            input_type="number",
            write_tab=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            padding=[dp(2), dp(14), dp(2), dp(14)],
            foreground_color=TEXT,
            hint_text_color=(0.576, 0.639, 0.741, 0.8),
            cursor_color=SKY,
            font_size=sp(15),
        )
        track_keyboard(self.input)
        self.add_widget(self.input)
        self.add_widget(
            Label(text=",00", color=MUTED, font_size=sp(13), size_hint_x=None, width=dp(30))
        )
        self.input.bind(text=self._from_input)
        self.bind(text=self._to_input)
        self.neu_setup(mode="inset", radius=dp(14), depth=dp(4))

    def _from_input(self, _instance, value):
        if self.text != value:
            self.text = value

    def _to_input(self, _instance, value):
        if self.input.text != value:
            self.input.text = value


def money_field(hint: str = "0", height: int = 48) -> MoneyField:
    return MoneyField(hint=hint, height=height)


class FormModal(ModalView):
    title = StringProperty("")

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.92, None)
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0.01, 0.02, 0.05, 0.6)
        self.auto_dismiss = False
        self.panel = Surface(
            orientation="vertical", padding=dp(20), spacing=dp(12), radius=dp(28), depth=dp(8)
        )
        header = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        header.add_widget(text_label(title, 22, bold=True, height=42))
        close = NeuButton(text="Tutup", quiet=True, size_hint_x=None, width=dp(80), height=dp(40))
        close.bind(on_release=lambda *_: self.dismiss())
        header.add_widget(close)
        self.panel.add_widget(header)
        # Inner padding gives raised shadows room before the ScrollView clips them.
        self.body = GridLayout(cols=1, spacing=dp(14), padding=[dp(8), dp(8)], size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter("height"))
        self.scroll = ScrollView()
        self.scroll.add_widget(self.body)
        self.panel.add_widget(self.scroll)
        self.add_widget(self.panel)
        self._center_y = None

    def on_pre_open(self):
        self._watch(True)
        self._relayout()

    def open(self, *args, **kwargs):
        super().open(*args, **kwargs)
        # ModalView centers itself in the whole window on open; move it into the free area.
        self._align_center()

    def on_dismiss(self):
        self._watch(False)

    def _watch(self, active: bool):
        app = App.get_running_app()
        bind = app.fbind if active else app.funbind
        for name in ("safe_top", "safe_bottom", "keyboard_inset"):
            bind(name, self._relayout)
        bind("focused_field", self._reveal_focus)
        (Window.fbind if active else Window.funbind)("size", self._relayout)

    def _relayout(self, *_):
        """Fit the dialog between the status bar and the navigation bar or keyboard."""
        app = App.get_running_app()
        self.height, self._center_y = dialog_frame(
            Window.height,
            app.safe_top,
            app.safe_bottom,
            app.keyboard_inset,
            gap=dp(16),
            min_free=dp(160),
        )
        self._align_center()
        if app.keyboard_inset:
            self._reveal_focus()

    def _align_center(self, *_):
        if getattr(self, "_is_open", False):
            self.center = (Window.center_x, self._center_y or Window.center_y)

    def _reveal_focus(self, *_):
        target = App.get_running_app().focused_field
        if target is None:
            return
        parent = target.parent
        while parent is not None and parent is not self.body:
            parent = getattr(parent, "parent", None)
        if parent is self.body:
            # Wait for the dialog to finish resizing, then scroll the field into view.
            Clock.schedule_once(lambda *_: self.scroll.scroll_to(target, padding=24), 0.15)

    def add_field(self, widget):
        self.body.add_widget(widget)
        return widget

    def message(self, value: str, error: bool = True):
        self.status.text = value
        self.status.color = EMBER if error else MINT


class AppScreen(Screen):
    page_title = ""
    page_kicker = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = BoxLayout(orientation="vertical")
        self.add_widget(self.root_layout)
        app = App.get_running_app()
        app.bind(safe_top=self.apply_safe_area, safe_bottom=self.apply_safe_area)
        self.apply_safe_area()
        self.build_header()
        self.scroll = ScrollView(do_scroll_x=False)
        self.content = GridLayout(
            cols=1,
            spacing=dp(16),
            padding=[dp(20), dp(14), dp(20), dp(28)],
            size_hint_y=None,
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.root_layout.add_widget(self.scroll)
        self.build_nav()

    def apply_safe_area(self, *_):
        app = App.get_running_app()
        self.root_layout.padding = [0, app.safe_top, 0, app.safe_bottom]

    def build_header(self):
        header = BoxLayout(
            orientation="vertical",
            padding=[dp(20), dp(12), dp(20), dp(8)],
            size_hint_y=None,
            height=dp(82),
        )
        header.add_widget(text_label(self.page_kicker.upper(), 10, SKY, True, 20))
        header.add_widget(fit_one_line(text_label(self.page_title, 27, TEXT, True, 42), 27, 18))
        self.root_layout.add_widget(header)

    def build_nav(self):
        holder = BoxLayout(padding=[dp(16), dp(6), dp(16), dp(14)], size_hint_y=None, height=dp(84))
        nav = Surface(padding=dp(6), spacing=dp(4), radius=dp(22), depth=dp(6))
        for title, screen_name in NAV_TABS:
            button = NeuButton(
                text=title,
                mode="flat",
                selected=screen_name == self.name,
                height=dp(52),
            )
            button.bind(on_release=lambda _, name=screen_name: self.go(name))
            nav.add_widget(button)
        holder.add_widget(nav)
        self.root_layout.add_widget(holder)

    def go(self, screen_name: str):
        if screen_name == self.manager.current:
            return
        # Slide toward the tapped tab: tabs to the right push left, tabs to the left push right.
        forward = TAB_ORDER.index(screen_name) > TAB_ORDER.index(self.manager.current)
        self.manager.transition.direction = "left" if forward else "right"
        self.manager.current = screen_name

    def clear(self):
        self.content.clear_widgets()

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        pass


class DashboardScreen(AppScreen):
    page_title = "Uang kos, tanpa tebak-tebakan"
    page_kicker = "Ringkasan bulan ini"

    def refresh(self):
        self.clear()
        app = App.get_running_app()
        summary = app.db.month_summary()
        balance = summary["income"] - summary["expense"]

        hero = Surface(
            orientation="vertical",
            padding=dp(20),
            spacing=dp(6),
            size_hint_y=None,
            height=dp(176),
            radius=dp(24),
            depth=dp(7),
        )
        hero.add_widget(text_label("SISA ARUS KAS", 10, MUTED, True, 20))
        hero.add_widget(text_label(rupiah(balance), 32, TEXT, True, 50))
        chips = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        for label, value, color in (
            ("Masuk", summary["income"], MINT),
            ("Keluar", summary["expense"], EMBER),
        ):
            chip = Surface(
                mode="inset",
                orientation="vertical",
                padding=[dp(12), dp(6)],
                radius=dp(14),
                depth=dp(4),
            )
            chip.add_widget(text_label(label, 10, MUTED, height=18))
            chip.add_widget(text_label(rupiah(value), 13, color, True, 22))
            chips.add_widget(chip)
        hero.add_widget(chips)
        self.content.add_widget(hero)

        actions = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(14))
        scan = NeuButton(text="Pindai struk", primary=True)
        scan.bind(on_release=lambda *_: app.open_scan())
        add_expense = NeuButton(text="Catat transaksi")
        add_expense.bind(on_release=lambda *_: app.open_transaction())
        actions.add_widget(scan)
        actions.add_widget(add_expense)
        self.content.add_widget(actions)

        self.content.add_widget(text_label("ALIRAN UTANG", 10, MUTED, True, 28))
        names = {int(row["id"]): row["name"] for row in app.db.members()}
        transfers = simplify_debts(app.db.balances())
        count = max(1, len(transfers))
        debt_sheet = Surface(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
            size_hint_y=None,
            height=dp(24 + 52 * count + 10 * (count - 1)),
        )
        if not transfers:
            debt_sheet.add_widget(
                text_label("Semua beres. Belum ada utang aktif.", 14, MUTED, height=52)
            )
        for debtor, creditor, value in transfers:
            slip = TapSurface(
                mode="inset",
                padding=[dp(16), 0],
                size_hint_y=None,
                height=dp(52),
                radius=dp(14),
                depth=dp(4),
            )
            slip.bind(
                on_release=lambda _, d=debtor, c=creditor, v=value: app.open_payment(d, c, v)
            )
            slip.add_widget(text_label(f"{names[debtor]}  →  {names[creditor]}", 14, bold=True, height=52))
            slip.add_widget(text_label(rupiah(value), 14, EMBER, True, 52, halign="right"))
            debt_sheet.add_widget(slip)
        self.content.add_widget(debt_sheet)
        if transfers:
            self.content.add_widget(
                text_label("Ketuk slip untuk membayar lewat bank atau mengingatkan.", 11, MUTED, height=20)
            )

        self.content.add_widget(text_label("POLA PENGELUARAN", 10, MUTED, True, 28))
        categories = app.db.category_summary()
        category_sheet = Surface(
            orientation="vertical",
            padding=[dp(16), dp(10)],
            size_hint_y=None,
            height=dp(max(68, 20 + 44 * len(categories))),
        )
        if not categories:
            category_sheet.add_widget(
                text_label("Belum ada transaksi bulan ini.", 14, MUTED, height=48)
            )
        peak = max((int(row["total"]) for row in categories), default=1)
        for item in categories:
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            row.add_widget(text_label(item["category"], 13, bold=True, height=44))
            track = AnchorLayout(anchor_y="center")
            track.add_widget(NeuBar(int(item["total"]) / peak, size_hint_y=None, height=dp(12)))
            row.add_widget(track)
            row.add_widget(text_label(rupiah(item["total"]), 12, MUTED, height=44, halign="right"))
            category_sheet.add_widget(row)
        self.content.add_widget(category_sheet)

        export_actions = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(14))
        xlsx = NeuButton(text="Ekspor Excel")
        pdf = NeuButton(text="Ekspor PDF")
        xlsx.bind(on_release=lambda *_: app.export("xlsx"))
        pdf.bind(on_release=lambda *_: app.export("pdf"))
        export_actions.add_widget(xlsx)
        export_actions.add_widget(pdf)
        self.content.add_widget(export_actions)


class BillsScreen(AppScreen):
    page_title = "Siapa pesan apa"
    page_kicker = "Tagihan patungan"

    def refresh(self):
        self.clear()
        app = App.get_running_app()
        actions = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(14))
        scan = NeuButton(text="Pindai struk", primary=True)
        scan.bind(on_release=lambda *_: app.open_scan())
        manual = NeuButton(text="Tambah manual")
        manual.bind(on_release=lambda *_: app.open_bill())
        actions.add_widget(scan)
        actions.add_widget(manual)
        self.content.add_widget(actions)
        bills = app.db.recent_bills()
        if not bills:
            self.content.add_widget(
                text_label("Belum ada tagihan. Mulai dari belanja bersama pertama.", 14, MUTED, 72)
            )
        for bill in bills:
            card = Surface(
                orientation="vertical",
                padding=[dp(16), dp(10)],
                size_hint_y=None,
                height=dp(94),
            )
            top = BoxLayout(size_hint_y=None, height=dp(42))
            top.add_widget(text_label(bill["title"], 16, bold=True, height=42))
            top.add_widget(text_label(rupiah(bill["grand_total"]), 15, TEXT, True, 42, halign="right"))
            card.add_widget(top)
            method = METHOD_LABELS.get(bill["method"], bill["method"])
            card.add_widget(
                text_label(
                    f"{bill['bill_date']}  ·  dibayar {bill['payer_name']}  ·  {method}",
                    11,
                    MUTED,
                    height=30,
                )
            )
            self.content.add_widget(card)


class ExpensesScreen(AppScreen):
    """Every calendar month with records is its own menu; the running month comes first."""

    page_title = "Jejak setiap rupiah"
    page_kicker = "Catatan per bulan"

    def __init__(self, **kwargs):
        self.expanded: dict[str, bool] = {}
        super().__init__(**kwargs)

    def refresh(self):
        self.clear()
        app = App.get_running_app()
        today = date.today()
        current = today.strftime("%Y-%m")
        button = NeuButton(text="Catat pemasukan atau pengeluaran", primary=True)
        button.bind(on_release=lambda *_: app.open_transaction())
        self.content.add_widget(button)
        self.content.add_widget(
            text_label(
                f"[color=5fd3a4][b]Terdeteksi otomatis[/b][/color]  ·  "
                f"{today.day} {MONTH_NAMES[today.month - 1]} {today.year}",
                11,
                MUTED,
                height=20,
                markup=True,
            )
        )
        year = None
        for summary in app.db.period_summaries(today):
            if summary["period"][:4] != year:
                year = summary["period"][:4]
                self.content.add_widget(text_label(f"TAHUN {year}", 10, MUTED, True, 28))
            self.content.add_widget(self.month_menu(app, summary, current))

    def is_open(self, period: str, current: str) -> bool:
        return self.expanded.get(period, period == current)

    def toggle(self, period: str, current: str):
        self.expanded[period] = not self.is_open(period, current)
        self.refresh()

    def month_menu(self, app, summary: dict, current: str) -> Surface:
        period = summary["period"]
        opened = self.is_open(period, current)
        card = Surface(
            orientation="vertical",
            padding=[dp(16), dp(12), dp(16), dp(16)],
            spacing=dp(12),
            size_hint_y=None,
            radius=dp(22),
            depth=dp(6),
        )
        card.bind(minimum_height=card.setter("height"))

        header = TapSurface(
            mode="flat", size_hint_y=None, height=dp(48), spacing=dp(10), radius=dp(14), depth=dp(3)
        )
        header.bind(on_release=lambda *_: self.toggle(period, current))
        titles = BoxLayout(orientation="vertical")
        badge = "   [size=9sp][color=7cb8ff][b]BULAN INI[/b][/color][/size]" if period == current else ""
        titles.add_widget(
            text_label(
                f"{MONTH_NAMES[int(period[5:7]) - 1]}{badge}", 18, TEXT, True, 26, markup=True
            )
        )
        net = summary["income"] - summary["expense"]
        count = summary["income_count"] + summary["expense_count"]
        titles.add_widget(text_label(f"{count} catatan  ·  sisa {rupiah(net)}", 11, MUTED, height=20))
        header.add_widget(titles)
        well = Surface(
            mode="inset" if opened else "raised",
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={"center_y": 0.5},
            radius=dp(20),
            depth=dp(3),
        )
        well.add_widget(Chevron(up=opened, color=SKY if opened else MUTED))
        header.add_widget(well)
        card.add_widget(header)

        stats = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(12))
        for label, number, total, color, sign in (
            ("pengeluaran", summary["expense_count"], summary["expense"], EMBER, "-"),
            ("pemasukan", summary["income_count"], summary["income"], MINT, "+"),
        ):
            chip = Surface(
                mode="inset", orientation="vertical", padding=[dp(12), dp(6)], radius=dp(14), depth=dp(4)
            )
            chip.add_widget(
                text_label(
                    f"[size=17sp][b][color=e8eef7]{number}[/color][/b][/size]  {label}",
                    12,
                    MUTED,
                    height=26,
                    markup=True,
                )
            )
            chip.add_widget(
                text_label(f"{sign if number else ''}{rupiah(total)}", 13, color, True, 22)
            )
            stats.add_widget(chip)
        card.add_widget(stats)

        if opened:
            rows = app.db.transactions_for_period(period)
            if not rows:
                card.add_widget(
                    text_label(
                        "Belum ada catatan di bulan ini. Catatan bulan lalu tetap tersimpan di bawah.",
                        13,
                        MUTED,
                        height=44,
                        wrap=True,
                    )
                )
            for transaction in rows:
                card.add_widget(self.transaction_row(transaction))
        return card

    @staticmethod
    def transaction_row(transaction) -> Surface:
        row = Surface(
            mode="inset",
            orientation="horizontal",
            padding=[dp(14), dp(8)],
            spacing=dp(10),
            size_hint_y=None,
            height=dp(64),
            radius=dp(14),
            depth=dp(4),
        )
        day = transaction["transaction_date"]
        stamp = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(32))
        stamp.add_widget(text_label(day[8:10], 15, TEXT, True, 26, halign="center"))
        stamp.add_widget(
            text_label(MONTH_NAMES[int(day[5:7]) - 1][:3].upper(), 9, MUTED, True, 16, halign="center")
        )
        row.add_widget(stamp)
        copy = BoxLayout(orientation="vertical")
        copy.add_widget(text_label(transaction["description"], 13, bold=True, height=26))
        copy.add_widget(
            text_label(f"{transaction['member_name']}  ·  {transaction['category']}", 10, MUTED, height=20)
        )
        row.add_widget(copy)
        expense = transaction["kind"] == "expense"
        value = text_label(
            f"{'-' if expense else '+'}{rupiah(transaction['amount'])}",
            13,
            EMBER if expense else MINT,
            True,
            48,
            halign="right",
        )
        value.size_hint_x = None
        value.width = dp(104)
        row.add_widget(value)
        return row


class MembersScreen(AppScreen):
    page_title = "Orang di balik patungan"
    page_kicker = "Anggota kos"

    def refresh(self):
        self.clear()
        app = App.get_running_app()
        button = NeuButton(text="Tambah anggota", primary=True)
        button.bind(on_release=lambda *_: app.open_member())
        self.content.add_widget(button)
        members = app.db.members()
        if not members:
            self.content.add_widget(text_label("Tambahkan dirimu sebagai pemilik catatan.", 14, MUTED, 72))
        for member in members:
            card = Surface(
                orientation="horizontal",
                padding=[dp(16), dp(10)],
                spacing=dp(14),
                size_hint_y=None,
                height=dp(80),
            )
            avatar = Surface(
                mode="inset",
                size_hint=(None, None),
                size=(dp(44), dp(44)),
                pos_hint={"center_y": 0.5},
                radius=dp(22),
                depth=dp(4),
            )
            avatar.add_widget(
                text_label(member["name"][:1].upper(), 15, SKY, True, 44, halign="center")
            )
            card.add_widget(avatar)
            info = BoxLayout(orientation="vertical")
            owner = "  ·  Saya" if member["is_owner"] else ""
            info.add_widget(text_label(f"{member['name']}{owner}", 15, bold=True))
            info.add_widget(
                text_label(member["payment_info"] or "Info pembayaran belum diisi", 11, MUTED)
            )
            card.add_widget(info)
            card.add_widget(
                text_label(
                    f"Budget\n{rupiah(member['monthly_budget'])}",
                    11,
                    MUTED,
                    height=60,
                    halign="right",
                    wrap=True,
                )
            )
            self.content.add_widget(card)


class KosSplitApp(App):
    title = "KosSplit"
    # Pixels hidden behind the Android status bar and navigation bar.
    safe_top = NumericProperty(0)
    safe_bottom = NumericProperty(0)
    # Pixels hidden behind the on-screen keyboard, and the text field that has focus.
    keyboard_inset = NumericProperty(0)
    focused_field = ObjectProperty(None, allownone=True)
    _safe_area_retries = 0
    _keyboard_watch = None

    def build(self):
        Window.clearcolor = NIGHT
        data_dir = Path(self.user_data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(data_dir / "kossplit.db")
        # Export locations: Android's save screen, or the last folder used on a computer.
        self.document_saver = None
        self.export_folder_file = data_dir / "export_folder.txt"
        self.db.activate_current_period()
        self.seen_day = date.today()
        # Poll the device clock so a new day or month appears while the app stays open.
        Clock.schedule_interval(self.watch_calendar, 30)
        self.scan_modal = None
        self.scanner = ReceiptScanner(self._on_receipt_text, self._on_scan_error)
        manager = ScreenManager(transition=SlideTransition(duration=0.25))
        manager.add_widget(DashboardScreen(name="dashboard"))
        manager.add_widget(BillsScreen(name="bills"))
        manager.add_widget(ExpensesScreen(name="expenses"))
        manager.add_widget(MembersScreen(name="members"))
        return manager

    def on_start(self):
        # Insets are only known once Android has laid out the window, so check again shortly after.
        Clock.schedule_once(self.update_safe_area, 0)
        Clock.schedule_once(self.update_safe_area, 0.8)
        Window.bind(size=lambda *_: Clock.schedule_once(self.update_safe_area, 0.3))

    def update_safe_area(self, *_):
        measured = system_bar_overlap()
        if measured is None:
            # Android has not laid out the window yet; look again shortly.
            self._safe_area_retries += 1
            if self._safe_area_retries <= 10:
                Clock.schedule_once(self.update_safe_area, 0.3)
            else:
                self.safe_top, self.safe_bottom = fallback_bar_sizes()
            return
        self._safe_area_retries = 0
        self.safe_top, self.safe_bottom = measured

    def on_field_focus(self, widget, focused: bool):
        if focused:
            self.focused_field = widget
            if IS_ANDROID and self._keyboard_watch is None:
                # The keyboard slides in over a few frames, so poll its height while typing.
                self._keyboard_watch = Clock.schedule_interval(self.update_keyboard_inset, 0.2)
        elif self.focused_field is widget:
            self.focused_field = None
            # Focus often hops straight to the next field; only stop if nothing took it.
            Clock.schedule_once(self._stop_keyboard_watch, 0.4)

    def update_keyboard_inset(self, *_):
        inset = keyboard_overlap()
        if inset != self.keyboard_inset:
            self.keyboard_inset = inset

    def _stop_keyboard_watch(self, *_):
        if self.focused_field is not None:
            return
        if self._keyboard_watch is not None:
            self._keyboard_watch.cancel()
            self._keyboard_watch = None
        self.keyboard_inset = 0

    def watch_calendar(self, *_):
        today = date.today()
        if today == self.seen_day:
            return
        self.seen_day = today
        self.db.activate_current_period(today)
        if self.root:
            self.root.current_screen.refresh()

    def on_resume(self):
        self.watch_calendar()
        Clock.schedule_once(self.update_safe_area, 0.3)
        return True

    def on_stop(self):
        self.db.close()

    def refresh_current(self):
        self.root.current_screen.refresh()

    def open_member(self):
        modal = FormModal("Anggota baru")
        name = modal.add_field(field("Nama panggilan"))
        phone = modal.add_field(field("Nomor WhatsApp"))
        provider = modal.add_field(
            NeuSpinner(
                label="Bank atau e-wallet",
                placeholder="Pilih bank atau e-wallet",
                values=(*PROVIDER_NAMES, "Lainnya"),
            )
        )
        account = modal.add_field(field("Nomor rekening atau nomor e-wallet"))
        budget = modal.add_field(money_field("Budget bulanan, contoh 1.500.000"))
        owner_spinner = NeuSpinner(
            label="Peran",
            text="Anggota kos",
            values=("Anggota kos", "Saya / pemilik catatan"),
        )
        modal.add_field(owner_spinner)
        modal.status = modal.add_field(text_label("", 12, EMBER, height=28, wrap=True))
        save = NeuButton(text="Simpan anggota", primary=True)

        def submit(*_):
            try:
                if not name.text.strip():
                    raise ValueError("Nama wajib diisi")
                label = "" if provider.text.startswith("Pilih") or provider.text == "Lainnya" else provider.text
                self.db.add_member(
                    name.text,
                    phone.text,
                    format_payment_info(label, account.text, name.text),
                    amount(budget.text),
                    owner_spinner.text.startswith("Saya"),
                )
                modal.dismiss()
                self.refresh_current()
            except ValueError as error:
                modal.message(str(error))

        save.bind(on_release=submit)
        modal.add_field(save)
        modal.open()

    def open_transaction(self):
        members = self.db.members()
        if not members:
            self.notice("Tambahkan anggota terlebih dahulu.")
            return
        modal = FormModal("Catat transaksi")
        member_names = [row["name"] for row in members]
        member = modal.add_field(
            NeuSpinner(label="Anggota", text=member_names[0], values=member_names)
        )
        kind = modal.add_field(
            NeuSpinner(label="Jenis", text="Pengeluaran", values=("Pengeluaran", "Pemasukan"))
        )
        category = modal.add_field(
            NeuSpinner(label="Kategori", text=CATEGORIES[0], values=CATEGORIES)
        )
        description = modal.add_field(field("Keterangan"))
        value = modal.add_field(money_field("Nominal Rupiah"))
        modal.status = modal.add_field(text_label("", 12, EMBER, height=28, wrap=True))
        save = NeuButton(text="Simpan transaksi", primary=True)

        def submit(*_):
            try:
                nominal = amount(value.text)
                if not description.text.strip() or nominal <= 0:
                    raise ValueError("Keterangan dan nominal wajib diisi")
                member_id = next(row["id"] for row in members if row["name"] == member.text)
                self.db.add_transaction(
                    member_id,
                    "expense" if kind.text == "Pengeluaran" else "income",
                    category.text,
                    description.text,
                    nominal,
                )
                modal.dismiss()
                self.refresh_current()
            except ValueError as error:
                modal.message(str(error))

        save.bind(on_release=submit)
        modal.add_field(save)
        modal.open()

    def open_bill(self, draft: ReceiptDraft | None = None):
        members = self.db.members()
        if len(members) < 2:
            self.notice("Tambahkan minimal dua anggota untuk membuat tagihan.")
            return
        modal = FormModal("Tagihan dari struk" if draft else "Tagihan baru")
        names = [row["name"] for row in members]
        ids = {row["name"].lower(): int(row["id"]) for row in members}
        title = modal.add_field(field("Judul, contoh Token listrik"))
        payer = modal.add_field(
            NeuSpinner(label="Dibayar oleh", text=names[0], values=names)
        )
        method = modal.add_field(
            NeuSpinner(
                label="Metode bagi",
                text="Bagi rata",
                values=("Bagi rata", "Nominal kustom", "Persentase", "Per item"),
            )
        )
        subtotal = modal.add_field(money_field("Subtotal"))
        tax = modal.add_field(money_field("Pajak, layanan, dan ongkir"))
        discount = modal.add_field(money_field("Diskon"))
        detail = modal.add_field(
            field(
                "Detail pembagian. Contoh:\nAyu=60000, Bima=40000\natau per item: Nasi|20000|Ayu+Bima",
                multiline=True,
                height=116,
            )
        )
        modal.add_field(
            text_label(
                "Bagi rata memakai semua anggota. Untuk metode lain, tulis nama sesuai daftar anggota.",
                11,
                MUTED,
                height=48,
                wrap=True,
            )
        )
        modal.status = modal.add_field(text_label("", 12, EMBER, height=36, wrap=True))
        save = NeuButton(text="Hitung dan simpan", primary=True)

        if draft:
            # Every item starts shared by everyone; the user edits names per line.
            everyone = "+".join(names)
            sub, fees, cut = draft.bill_values()
            title.text = draft.merchant or "Struk belanja"
            method.text = "Per item"
            subtotal.text = str(sub)
            tax.text = str(fees)
            discount.text = str(cut)
            detail.text = "\n".join(f"{item.name}|{item.price}|{everyone}" for item in draft.items)
            modal.message(
                f"Total struk {rupiah(sub + fees - cut)}. Ubah nama di akhir setiap baris sesuai pemesan.",
                error=False,
            )

        def key_values(raw: str, decimal=False):
            result = {}
            for pair in raw.replace("\n", ",").split(","):
                if not pair.strip():
                    continue
                name, raw_value = pair.split("=", 1)
                member_id = ids[name.strip().lower()]
                result[member_id] = Decimal(raw_value.strip()) if decimal else amount(raw_value)
            return result

        def submit(*_):
            try:
                sub = amount(subtotal.text)
                extra = amount(tax.text)
                cut = amount(discount.text)
                total = sub + extra - cut
                if not title.text.strip() or sub <= 0 or total < 0:
                    raise ValueError("Judul dan subtotal wajib diisi")
                if method.text == "Bagi rata":
                    shares = equal_split(total, list(ids.values()))
                    method_key = "equal"
                elif method.text == "Nominal kustom":
                    shares = custom_amount_split(total, key_values(detail.text))
                    method_key = "custom_amount"
                elif method.text == "Persentase":
                    shares = percentage_split(total, key_values(detail.text, decimal=True))
                    method_key = "percentage"
                else:
                    items = []
                    for line in detail.text.splitlines():
                        if not line.strip():
                            continue
                        item_name, raw_price, raw_names = line.split("|", 2)
                        assigned = [ids[name.strip().lower()] for name in raw_names.split("+")]
                        items.append((item_name.strip(), amount(raw_price), assigned))
                    shares = itemized_split(items, extra, cut)
                    if sum(price for _, price, _ in items) != sub:
                        raise ValueError("Jumlah harga item harus sama dengan subtotal")
                    method_key = "itemized"
                payer_id = ids[payer.text.lower()]
                self.db.add_bill(
                    title.text, payer_id, method_key, sub, extra, cut, shares, detail.text
                )
                modal.dismiss()
                self.refresh_current()
            except (ValueError, KeyError) as error:
                modal.message(f"Periksa pembagian: {error}")

        save.bind(on_release=submit)
        modal.add_field(save)
        modal.open()

    # Receipt scanning -------------------------------------------------------

    def open_scan(self):
        try:
            self._open_scan_modal()
        except Exception as error:
            from kivy.logger import Logger

            Logger.exception("KosSplit: popup pindai struk gagal dibuat")
            self.scan_modal = None
            self.notice(
                f"Menu pindai struk tidak dapat dibuka: {error}",
                "Pemindai tidak tersedia",
            )

    def _open_scan_modal(self):
        modal = FormModal("Pindai struk")
        self.scan_modal = modal
        modal.add_field(
            text_label(
                "Foto struk dibaca langsung di ponsel. Tidak ada gambar yang dikirim ke server.",
                12,
                MUTED,
                height=44,
                wrap=True,
            )
        )
        if IS_ANDROID:
            camera = modal.add_field(NeuButton(text="Buka kamera pemindai", primary=True))
            camera.bind(on_release=lambda *_: self._start_scan(modal, self.scanner.scan_camera))
            gallery = modal.add_field(NeuButton(text="Pilih foto dari galeri"))
            gallery.bind(on_release=lambda *_: self._start_scan(modal, self.scanner.pick_gallery))
        else:
            picker = modal.add_field(NeuButton(text="Pilih file gambar struk", primary=True))
            picker.bind(on_release=lambda *_: self.pick_image_file(modal))
        modal.add_field(text_label("ATAU TEMPEL TEKS STRUK", 10, MUTED, True, 28))
        pasted = modal.add_field(
            field("Tempel teks struk di sini, satu baris per item", multiline=True, height=140)
        )
        read = modal.add_field(NeuButton(text="Baca teks"))
        read.bind(on_release=lambda *_: self._on_receipt_text(pasted.text))
        modal.status = modal.add_field(text_label("", 12, EMBER, height=48, wrap=True))
        modal.open()

    def _start_scan(self, modal: FormModal, action):
        modal.message("Membuka pemindai...", error=False)
        try:
            action()
        except Exception as error:
            # Last-resort guard: an exception escaping a Kivy button callback can
            # terminate the Android process instead of showing an error.
            from kivy.logger import Logger

            Logger.exception("KosSplit: aksi pindai struk gagal")
            modal.message(
                f"Pemindai tidak dapat dibuka: {error}. "
                "Pilih foto dari galeri atau tempel teks struk."
            )

    def pick_image_file(self, parent: FormModal):
        chooser_modal = FormModal("Pilih gambar")
        chooser = FileChooserListView(
            path=str(Path.home()),
            filters=["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"],
            size_hint_y=None,
            height=dp(360),
        )
        chooser_modal.add_field(chooser)
        use = chooser_modal.add_field(NeuButton(text="Baca gambar ini", primary=True))

        def choose(*_):
            if chooser.selection:
                chooser_modal.dismiss()
                parent.message("Membaca struk...", error=False)
                self.scanner.read_file(chooser.selection[0])

        use.bind(on_release=choose)
        chooser_modal.open()

    def _on_scan_error(self, message: str):
        if self.scan_modal:
            self.scan_modal.message(message)
        else:
            self.notice(message)

    def _on_receipt_text(self, text: str):
        if not text.strip():
            self._on_scan_error("Belum ada teks struk untuk dibaca.")
            return
        if self.scan_modal:
            self.scan_modal.dismiss()
            self.scan_modal = None
        self.open_receipt_review(parse_receipt(text))

    def open_receipt_review(self, draft: ReceiptDraft):
        modal = FormModal("Periksa hasil")
        modal.add_field(text_label("NAMA TEMPAT", 10, MUTED, True, 22))
        merchant = modal.add_field(field("Nama toko atau restoran"))
        merchant.text = draft.merchant

        # Every item gets its own card so each price is fully visible and editable.
        item_heading = modal.add_field(text_label("", 10, MUTED, True, 22))
        item_list = GridLayout(cols=1, spacing=dp(14), size_hint_y=None)
        item_list.bind(minimum_height=item_list.setter("height"))
        modal.add_field(item_list)
        add_item = modal.add_field(NeuButton(text="+ Tambah item"))
        rows: list[tuple[Widget, TextInput, MoneyField]] = []

        modal.add_field(text_label("PAJAK, LAYANAN, ONGKIR", 10, MUTED, True, 22))
        fees = modal.add_field(money_field("0"))
        fees.text = str(draft.tax_service)
        modal.add_field(text_label("DISKON", 10, MUTED, True, 22))
        cut = modal.add_field(money_field("0"))
        cut.text = str(draft.discount)
        modal.add_field(text_label("TOTAL DI STRUK", 10, MUTED, True, 22))
        total = modal.add_field(money_field("0"))
        total.text = str(draft.total)
        summary = modal.add_field(text_label("", 12, MUTED, height=52, wrap=True))
        modal.status = modal.add_field(text_label("\n".join(draft.notes), 12, EMBER, height=48, wrap=True))

        def read_items() -> list[ReceiptItem]:
            parsed = []
            for _card, name_input, price_input in rows:
                name = name_input.text.strip()
                price = amount(price_input.text)
                if not name and not price:
                    continue
                if not name:
                    raise ValueError(f"Isi nama item untuk harga {rupiah(price)}")
                if price <= 0:
                    raise ValueError(f"Harga {name} masih Rp0")
                parsed.append(ReceiptItem(name=name, price=price))
            return parsed

        def rebuild() -> ReceiptDraft:
            parsed = read_items()
            return ReceiptDraft(
                merchant=merchant.text.strip(),
                items=parsed,
                subtotal=sum(item.price for item in parsed),
                tax_service=amount(fees.text),
                discount=amount(cut.text),
                total=amount(total.text),
            )

        def refresh_summary(*_):
            item_heading.text = f"ITEM DAN HARGA ({len(rows)})"
            try:
                current = rebuild()
                matches = current.total in (0, current.computed_total)
                summary.text = (
                    f"Item {rupiah(current.subtotal)} + biaya {rupiah(current.tax_service)}"
                    f" - diskon {rupiah(current.discount)} = {rupiah(current.computed_total)}"
                )
                summary.color = MINT if matches else EMBER
            except ValueError as error:
                summary.text = str(error)
                summary.color = EMBER

        def add_item_row(name: str = "", price: int = 0, focus: bool = False):
            card = Surface(
                orientation="vertical",
                padding=dp(12),
                spacing=dp(10),
                size_hint_y=None,
                height=dp(12 + 48 + 10 + 48 + 12),
                radius=dp(18),
                depth=dp(4),
            )
            # Name and the remove button share the top row so the price gets the full card width.
            name_row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(48))
            name_input = field("Nama item")
            name_input.text = name
            remove = NeuButton(text="Hapus", quiet=True, size_hint_x=None, width=dp(72), height=dp(48))
            name_row.add_widget(name_input)
            name_row.add_widget(remove)
            price_input = money_field("Harga")
            price_input.text = str(price) if price else ""
            card.add_widget(name_row)
            card.add_widget(price_input)
            entry = (card, name_input, price_input)
            rows.append(entry)
            item_list.add_widget(card)
            name_input.bind(text=refresh_summary)
            price_input.bind(text=refresh_summary)

            def remove_row(*_):
                rows.remove(entry)
                item_list.remove_widget(card)
                refresh_summary()

            remove.bind(on_release=remove_row)
            if focus:
                Clock.schedule_once(lambda *_: setattr(name_input, "focus", True), 0.1)

        for item in draft.items:
            add_item_row(item.name, item.price)
        add_item.bind(on_release=lambda *_: (add_item_row(focus=True), refresh_summary()))

        for widget in (fees, cut, total):
            widget.bind(text=refresh_summary)
        refresh_summary()

        modal.add_field(text_label("MAU DIAPAKAN STRUK INI?", 10, MUTED, True, 22))
        choices = modal.add_field(BoxLayout(spacing=dp(12), size_hint_y=None, height=dp(50)))
        split = NeuButton(text="Bagi tagihan", primary=True)
        record = NeuButton(text="Catat pengeluaran")
        choices.add_widget(split)
        choices.add_widget(record)
        modal.add_field(
            text_label(
                "Bagi tagihan untuk patungan. Catat pengeluaran jika dibayar sendiri.",
                11,
                MUTED,
                height=36,
                wrap=True,
            )
        )

        def split_bill(*_):
            try:
                current = rebuild()
                if not current.items:
                    raise ValueError("Tambahkan minimal satu item")
                modal.dismiss()
                self.open_bill(current)
            except ValueError as error:
                modal.message(str(error))

        def record_expense(*_):
            try:
                current = rebuild()
                if (current.total or current.computed_total) <= 0:
                    raise ValueError("Total struk masih Rp0")
                modal.dismiss()
                self.open_receipt_record(current)
            except ValueError as error:
                modal.message(str(error))

        split.bind(on_release=split_bill)
        record.bind(on_release=record_expense)
        modal.open()

    def open_receipt_record(self, draft: ReceiptDraft):
        """Save a scanned receipt straight to Catatan as one expense."""
        members = self.db.members()
        if not members:
            self.notice("Tambahkan anggota terlebih dahulu.")
            return
        # The printed total wins; fall back to the item sum when OCR missed it.
        nominal = draft.total or draft.computed_total
        guessed = guess_category(draft.merchant, [item.name for item in draft.items])
        modal = FormModal("Catat dari struk")
        modal.add_field(text_label("TOTAL", 10, MUTED, True, 20))
        modal.add_field(text_label(rupiah(nominal), 28, EMBER, True, 44))
        category = modal.add_field(NeuSpinner(label="Kategori", text=guessed, values=CATEGORIES))
        modal.add_field(
            text_label(
                "Kategori dipilih otomatis dari nama toko dan item. Ganti jika kurang tepat.",
                11,
                MUTED,
                height=36,
                wrap=True,
            )
        )
        names = [row["name"] for row in members]
        member = modal.add_field(NeuSpinner(label="Dibayar oleh", text=names[0], values=names))
        description = modal.add_field(field("Keterangan"))
        description.text = draft.merchant or "Belanja dari struk"
        value = modal.add_field(money_field("Nominal Rupiah"))
        value.text = str(nominal)
        modal.status = modal.add_field(text_label("", 12, EMBER, height=28, wrap=True))
        save = modal.add_field(NeuButton(text="Simpan ke catatan", primary=True))

        def submit(*_):
            try:
                total = amount(value.text)
                if not description.text.strip() or total <= 0:
                    raise ValueError("Keterangan dan nominal wajib diisi")
                member_id = next(row["id"] for row in members if row["name"] == member.text)
                self.db.add_transaction(member_id, "expense", category.text, description.text, total)
            except ValueError as error:
                modal.message(str(error))
                return
            modal.dismiss()
            # Show the new entry right away in this month's list.
            screen = self.root.current_screen
            if screen.name == "expenses":
                screen.refresh()
            else:
                screen.go("expenses")

        save.bind(on_release=submit)
        modal.open()

    # Bank and e-wallet handoff ---------------------------------------------

    def open_payment(self, debtor_id: int, creditor_id: int, value: int):
        debtor = self.db.member(debtor_id)
        creditor = self.db.member(creditor_id)
        target = parse_payment_info(creditor["payment_info"])
        modal = FormModal(f"Bayar ke {creditor['name']}")

        card = Surface(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(4),
            size_hint_y=None,
            height=dp(150),
            radius=dp(22),
        )
        card.add_widget(text_label(f"{debtor['name'].upper()} MEMBAYAR", 10, MUTED, True, 20))
        card.add_widget(text_label(rupiah(value), 30, EMBER, True, 46))
        account = Surface(mode="inset", orientation="vertical", padding=[dp(14), dp(6)], radius=dp(14), depth=dp(4))
        account.add_widget(text_label(target.label, 11, SKY, True, 20))
        account.add_widget(
            text_label(target.account_number or "Info pembayaran belum diisi", 15, TEXT, True, 24)
        )
        card.add_widget(account)
        modal.add_field(card)
        modal.status = modal.add_field(text_label("", 12, MINT, height=40, wrap=True))

        if target.account_number:
            app_label = target.provider.label if target.provider else "aplikasi bank"
            pay = modal.add_field(NeuButton(text=f"Salin nomor dan buka {app_label}", primary=True))

            def pay_now(*_):
                copy_text(target.account_number)
                opened = bool(target.provider) and open_app(target.provider.package)
                if opened:
                    modal.message(
                        f"Nomor disalin. Tempel di {app_label} dan transfer {rupiah(value)}.",
                        error=False,
                    )
                else:
                    modal.message(
                        "Nomor disalin. Buka aplikasi bank secara manual untuk transfer.", error=False
                    )

            pay.bind(on_release=pay_now)

        if debtor["phone"]:
            remind = modal.add_field(NeuButton(text=f"Ingatkan {debtor['name']} via WhatsApp"))
            message = payment_reminder(debtor["name"], creditor["name"], value, target)
            remind.bind(on_release=lambda *_: open_url(whatsapp_url(debtor["phone"], message)))

        settle = modal.add_field(NeuButton(text="Tandai sudah lunas"))

        def mark_paid(*_):
            self.db.add_settlement(debtor_id, creditor_id, value)
            modal.dismiss()
            self.refresh_current()

        settle.bind(on_release=mark_paid)
        modal.add_field(
            text_label(
                "KosSplit tidak masuk ke akun bank. Transfer tetap dikonfirmasi di aplikasi resmi bank.",
                11,
                MUTED,
                height=44,
                wrap=True,
            )
        )
        modal.open()

    def notice(self, message: str, title: str = "Belum bisa dilanjutkan", action=None):
        modal = FormModal(title)
        modal.add_field(text_label(message, 14, MUTED, height=96, wrap=True))
        if action:
            label, callback = action
            extra = NeuButton(text=label, primary=True)
            extra.bind(on_release=lambda *_: (modal.dismiss(), callback()))
            modal.add_field(extra)
        button = NeuButton(text="Mengerti", primary=not action)
        button.bind(on_release=lambda *_: modal.dismiss())
        modal.add_field(button)
        modal.open()

    def export(self, extension: str):
        # Build the report in private storage first, so a failure never leaves an empty file
        # in the location the user picks.
        draft = Path(self.user_data_dir) / "exports" / report_filename(extension)
        try:
            # Imported on demand: fpdf2 and openpyxl are heavy and must never block app startup.
            from kossplit.exporter import export_excel, export_pdf

            draft.parent.mkdir(parents=True, exist_ok=True)
            bills = self.db.recent_bills(1000)
            transactions = self.db.all_transactions(5000)
            if extension == "xlsx":
                export_excel(draft, bills, transactions)
            else:
                export_pdf(draft, bills, transactions)
        except Exception as error:  # A locked file or an unsupported PDF character must not close the app.
            self.notice(f"Laporan gagal dibuat: {error}", "Ekspor gagal")
            return
        if IS_ANDROID:
            self.save_on_android(draft, extension)
        else:
            self.choose_export_folder(draft, extension)

    def save_on_android(self, draft: Path, extension: str):
        """Open Android's save screen so the user picks the folder and file name."""
        try:
            if self.document_saver is None:
                from kossplit.file_saver import AndroidDocumentSaver

                self.document_saver = AndroidDocumentSaver()
            data = draft.read_bytes()
        except Exception as error:
            self.notice(f"Pemilih lokasi tidak tersedia: {error}", "Ekspor gagal")
            return
        finally:
            draft.unlink(missing_ok=True)
        mime = mime_type(extension)

        def saved(name: str, uri):
            self.notice(
                f"Laporan tersimpan sebagai:\n{name}",
                "Laporan tersimpan",
                ("Buka file", lambda: self.open_saved_report(uri, mime)),
            )

        self.document_saver.save(
            data,
            draft.name,
            mime,
            on_saved=saved,
            on_cancel=lambda: None,
            on_error=lambda message: self.notice(message, "Ekspor gagal"),
        )

    def open_saved_report(self, uri, mime: str):
        if not self.document_saver.open(uri, mime):
            self.notice(
                "Belum ada aplikasi untuk membuka file ini. Pasang Google Sheets, Excel, atau pembaca PDF.",
                "File tidak bisa dibuka",
            )

    def default_export_folder(self) -> Path:
        remembered = self.export_folder_file.read_text().strip() if self.export_folder_file.is_file() else ""
        if remembered and Path(remembered).is_dir():
            return Path(remembered)
        downloads = Path.home() / "Downloads"
        return downloads if downloads.is_dir() else Path.home()

    def choose_export_folder(self, draft: Path, extension: str):
        """Computer: pick a folder and file name inside the app, then copy the report there."""
        modal = FormModal("Simpan laporan")
        modal.add_field(text_label("NAMA FILE", 10, MUTED, True, 22))
        name = modal.add_field(field("Nama file"))
        name.text = draft.name
        modal.add_field(text_label("SIMPAN DI FOLDER", 10, MUTED, True, 22))
        folder_label = modal.add_field(text_label("", 12, SKY, height=40, wrap=True))
        chooser = modal.add_field(
            FileChooserListView(
                path=str(self.default_export_folder()),
                dirselect=True,
                # No file matches, so only folders are listed.
                filters=[lambda _folder, _name: False],
                size_hint_y=None,
                height=dp(300),
            )
        )
        modal.add_field(
            text_label(
                "Ketuk dua kali untuk masuk ke folder. Ketuk sekali untuk memilihnya.",
                11,
                MUTED,
                height=32,
                wrap=True,
            )
        )
        modal.status = modal.add_field(text_label("", 12, EMBER, height=40, wrap=True))
        save = modal.add_field(NeuButton(text="Simpan di folder ini", primary=True))
        overwrite = {"confirmed": None}

        def target_folder() -> Path:
            chosen = [path for path in chooser.selection if Path(path).is_dir()]
            return Path(chosen[0]) if chosen else Path(chooser.path)

        def show_folder(*_):
            folder_label.text = str(target_folder())
            overwrite["confirmed"] = None

        chooser.bind(path=show_folder, selection=show_folder)
        name.bind(text=lambda *_: overwrite.update(confirmed=None))
        show_folder()

        def submit(*_):
            try:
                filename = clean_filename(name.text, extension)
                folder = target_folder()
                destination = folder / filename
                if destination.exists() and overwrite["confirmed"] != destination:
                    overwrite["confirmed"] = destination
                    modal.message(f"{filename} sudah ada. Ketuk Simpan sekali lagi untuk menimpanya.")
                    return
                saved = copy_to_folder(draft, folder, filename)
                self.export_folder_file.write_text(str(folder))
            except (OSError, ValueError) as error:
                modal.message(f"Laporan gagal disimpan: {error}")
                return
            modal.dismiss()
            self.notice(
                f"Laporan tersimpan di:\n{saved}",
                "Laporan tersimpan",
                ("Buka file", lambda: open_url(saved.as_uri())),
            )

        save.bind(on_release=submit)
        modal.bind(on_dismiss=lambda *_: draft.unlink(missing_ok=True))
        modal.open()


if __name__ == "__main__":
    KosSplitApp().run()

from kossplit.layout import dialog_frame, dropdown_frame

WINDOW = 2400
STATUS, NAV, KEYBOARD = 96, 63, 900
GAP, MIN_FREE = 16, 160


def test_dialog_stays_between_status_bar_and_navigation_bar():
    height, center = dialog_frame(WINDOW, STATUS, NAV, 0, GAP, MIN_FREE)
    bottom, top = center - height / 2, center + height / 2
    assert bottom >= NAV + GAP
    assert top <= WINDOW - STATUS - GAP


def test_dialog_moves_above_keyboard():
    height, center = dialog_frame(WINDOW, STATUS, NAV, KEYBOARD, GAP, MIN_FREE)
    bottom, top = center - height / 2, center + height / 2
    assert bottom >= KEYBOARD + GAP
    assert top <= WINDOW - STATUS - GAP
    assert height == WINDOW - STATUS - KEYBOARD - 2 * GAP


def test_dialog_without_bars_keeps_original_size_limit():
    height, center = dialog_frame(WINDOW, 0, 0, 0, GAP, MIN_FREE)
    assert height == WINDOW * 0.88
    assert center == WINDOW / 2


def test_dropdown_opens_below_when_it_fits():
    assert dropdown_frame(1500, 1558, 260, NAV + 8, WINDOW - STATUS - 8, 88) == (260, 1240)


def test_dropdown_flips_above_instead_of_covering_navigation_bar():
    # Spinner sits just above the navigation bar: 200 px below it is not enough room.
    height, y = dropdown_frame(271, 329, 260, NAV + 8, WINDOW - STATUS - 8, 88)
    assert (height, y) == (260, 329)


def test_dropdown_never_goes_under_keyboard():
    low = KEYBOARD + 8
    height, y = dropdown_frame(1000, 1058, 260, low, WINDOW - STATUS - 8, 88)
    assert y >= low


def test_dropdown_shrinks_to_roomier_side_when_neither_fits():
    low, high = 100, 600
    height, y = dropdown_frame(400, 458, 500, low, high, 88)
    assert (height, y) == (300, 100)
    assert y >= low

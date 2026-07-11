from ui_scroll import _scroll_amount


class _WheelEvent:
    def __init__(self, *, delta=0, num=None):
        self.delta = delta
        self.num = num


def test_scroll_amount_windows_delta():
    assert _scroll_amount(_WheelEvent(delta=120)) == -1
    assert _scroll_amount(_WheelEvent(delta=-120)) == 1


def test_scroll_amount_linux_buttons():
    assert _scroll_amount(_WheelEvent(delta=0, num=4)) == -1
    assert _scroll_amount(_WheelEvent(delta=0, num=5)) == 1

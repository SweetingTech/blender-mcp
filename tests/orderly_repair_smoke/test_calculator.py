from calculator import clamp


def test_clamp_in_range():
    assert clamp(5, 0, 10) == 5


def test_clamp_below_range():
    assert clamp(-1, 0, 10) == 0


def test_clamp_above_range():
    assert clamp(11, 0, 10) == 10

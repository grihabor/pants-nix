from .lib import Version


def test_version_order():
    assert Version(1, 19, 0, "") > Version(1, 19, 0, "rc0")

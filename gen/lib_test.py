from .lib import Version


def test_from_tag():
    assert Version.from_tag("release_2.19.0.dev1") == Version(major=2, minor=19, micro=0, dev=1)
    assert Version.from_tag("release_2.19.0rc2") == Version(major=2, minor=19, micro=0, rc=2)
    assert Version.from_tag("release_2.19.0a3") == Version(major=2, minor=19, micro=0, a=3)
    assert Version.from_tag("release_2.19.0") == Version(major=2, minor=19, micro=0)


def test_version_order():
    assert Version(major=2, minor=19, micro=0, dev=100) < Version(major=2, minor=19, micro=0, a=0)
    assert Version(major=2, minor=19, micro=0, a=100) < Version(major=2, minor=19, micro=0, rc=0)
    assert Version(major=2, minor=19, micro=0, rc=100) < Version(major=2, minor=19, micro=0)


def test_version_format():
    assert "2.19.0.dev1" == str(Version(major=2, minor=19, micro=0, dev=1))
    assert "2.19.0rc2" == str(Version(major=2, minor=19, micro=0, rc=2))
    assert "2.19.0a3" == str(Version(major=2, minor=19, micro=0, a=3))
    assert "2.19.0" == str(Version(major=2, minor=19, micro=0))

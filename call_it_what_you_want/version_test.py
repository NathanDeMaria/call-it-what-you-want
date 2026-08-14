from .version import __version__


def test_version_is_populated() -> None:
    assert __version__

import re


def test_valid_version():
    from beocijies.version import __version__

    assert re.search(r"^\d+\.\d+\.\d+(-(rc\d+|dev))?$", __version__)


def test_imports():
    import beocijies.version
    from beocijies import __version__

    assert beocijies.version.__version__ == __version__

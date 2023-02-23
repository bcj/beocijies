"""
To install:

    python setup.py install
"""
from pathlib import Path

from setuptools import setup

from beocijies.version import __version__

DIRECTORY = Path(__file__).parent
REQUIREMENTS = DIRECTORY / "requirements"


def read_requirements(path: Path) -> list[str]:
    with path.open("r") as stream:
        return [line for line in stream.read().splitlines() if line]


setup(
    name="beocijies",
    description=("A beocijies site generator"),
    long_description=(DIRECTORY / "README.md").read_text("utf-8"),
    version=__version__,
    author="bcj",
    license=None,
    packages=("beocijies",),
    entry_points={"console_scripts": ("beocijies = beocijies.cli:main",)},
    install_requires=read_requirements(REQUIREMENTS / "install.txt"),
    tests_require=read_requirements(REQUIREMENTS / "tests.txt"),
    classifiers=(
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Utilities",
        "Typing :: Typed",
    ),
)

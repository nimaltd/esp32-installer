"""Shared fixtures: a throwaway library repository and a throwaway ESP-IDF project."""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

SRC = Path(__file__).resolve().parent.parent / "src"

# The package is the src folder itself, so it is loaded under its own name
# rather than found on sys.path, and before any test imports it.
if "esp32_installer" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "esp32_installer", SRC / "__init__.py", submodule_search_locations=[str(SRC)]
    )
    _package = importlib.util.module_from_spec(_spec)
    sys.modules["esp32_installer"] = _package
    _spec.loader.exec_module(_package)

from esp32_installer.core import cli, download  # noqa: E402

CMAKELISTS = """cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(app)
"""

MAIN_CMAKELISTS = """idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS ".")
"""


@pytest.fixture(autouse=True)
def no_idf(monkeypatch):
    """No ESP-IDF on the machine unless a test says so: IDF_PATH is unset."""
    monkeypatch.delenv("IDF_PATH", raising=False)


@pytest.fixture
def library(tmp_path):
    """
    Build a library repository on disk and return its path.

    Every argument has a working default, so a test states only the part it
    cares about. Anything in extra goes into installer.yml as it is.
    """

    def build(name="demo", headers=("src/demo.h",), sources=("src/demo.c",), esp32=None,
              requires=None, defines=None, layout="flat", extra=None, files=None, root=None):
        root = Path(root) if root else tmp_path / name
        root.mkdir(parents=True, exist_ok=True)

        written = {header: f"/**\n * @version 1.2.0\n */\nint {name}_answer(void);\n" for header in headers}
        written.update({source: "int answer(void) { return 42; }\n" for source in sources})
        written.update(files or {})

        for relative, text in written.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        data = {
            "name": name,
            "description": "A library for the tests",
            "repository": f"https://github.com/someone/{name}",
            "install": {"layout": layout},
            "files": {"headers": list(headers), "sources": list(sources)},
        }

        if defines:
            data["install"]["defines"] = list(defines)

        if requires is not None:
            data["requires"] = requires

        if esp32 is not None:
            data["esp32"] = esp32

        data.update(extra or {})
        (root / "installer.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        return root

    return build


@pytest.fixture
def project(tmp_path):
    """An ESP-IDF project on disk: CMakeLists.txt, main/, and any other files given."""

    def build(cmakelists=CMAKELISTS, main=MAIN_CMAKELISTS, defaults=None, sdkconfig=None,
              files=None, crlf=False, root=None):
        root = Path(root) if root else tmp_path / "app"
        root.mkdir(parents=True, exist_ok=True)
        written = {"CMakeLists.txt": cmakelists, "main/main.c": "void app_main(void) { }\n"}

        if main is not None:
            written["main/CMakeLists.txt"] = main

        if defaults is not None:
            written["sdkconfig.defaults"] = defaults

        if sdkconfig is not None:
            written["sdkconfig"] = sdkconfig

        written.update(files or {})

        for relative, text in written.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = text.replace("\n", "\r\n") if crlf else text
            path.write_bytes(data.encode("utf-8"))

        return root

    return build


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if a test that should stay offline goes online."""

    def refuse(*args, **kwargs):
        raise AssertionError("tried to use the network")

    monkeypatch.setattr(download, "fetch", refuse)


@pytest.fixture
def nobody(monkeypatch):
    """Nobody at the keyboard: every question takes its default."""
    monkeypatch.setattr(cli, "_answer", lambda prompt: None)


@pytest.fixture
def answers(monkeypatch):
    """Answer the questions with these, in order, and keep the questions asked."""
    asked = []

    def give(*replies):
        queue = list(replies)

        def answer(prompt):
            asked.append(prompt)
            return queue.pop(0) if queue else None

        monkeypatch.setattr(cli, "_answer", answer)

        return asked

    return give


def read(path):
    """A file's bytes as text, line endings untouched."""
    return Path(path).read_bytes().decode("utf-8")

"""
Taking a library out of an ESP-IDF project.

Installed and then uninstalled, the project's own files are back to the byte
they were, and the component files are gone.
"""

import pytest
from conftest import read

from esp32_installer.core import cli


def _install(*args):
    assert cli.main([str(arg) for arg in args]) == 0


def _uninstall(*args):
    return cli.main(["--uninstall"] + [str(arg) for arg in args])


FILES = ("CMakeLists.txt", "sdkconfig.defaults", "main/CMakeLists.txt")


MINIMAL = ('cmake_minimum_required(VERSION 3.22)\ninclude($ENV{IDF_PATH}/tools/cmake/project.cmake)\n'
           'idf_build_set_property(MINIMAL_BUILD ON)\nproject(app)\n')
CMAKELISTS = 'cmake_minimum_required(VERSION 3.16)\n\ninclude($ENV{IDF_PATH}/tools/cmake/project.cmake)\nproject(app)\n'


@pytest.mark.parametrize("crlf", [False, True])
@pytest.mark.parametrize("folder", ["components/demo", "libs/demo"])
@pytest.mark.parametrize("cmakelists, main", [
    (CMAKELISTS, 'idf_component_register(SRCS "main.c" PRIV_REQUIRES esp_timer)\n'),
    (MINIMAL, 'idf_component_register(SRCS "main.c"\n                    INCLUDE_DIRS ".")\n'),
])
def test_the_project_is_back_as_it_was(library, project, nobody, no_network, crlf, folder, cmakelists, main,
                                       capsys):
    root = project(defaults="CONFIG_A=y\n", cmakelists=cmakelists, main=main, crlf=crlf)
    before = {name: read(root / name) for name in FILES}
    lib = library(requires={"kconfig": ["FREERTOS_HZ=1000"]}, esp32={"settings": [
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"}]})

    _install(lib, "--project", root, "--dir", folder)
    assert {name: read(root / name) for name in FILES} != before

    assert _uninstall("demo", "--project", root) == 0

    assert {name: read(root / name) for name in FILES} == before
    assert not (root / folder).exists()

    out = capsys.readouterr().out
    assert "Removed demo from sdkconfig.defaults." in out
    assert "Removed demo from the components main requires." in out


def test_one_of_two_libraries_comes_out(library, project, nobody, no_network, tmp_path):
    root = project(main='idf_component_register(SRCS "main.c" PRIV_REQUIRES esp_timer)\n')
    first = library(name="first", headers=("first.h",), sources=("first.c",), root=tmp_path / "src" / "first",
                    requires={"kconfig": ["A"]})
    second = library(name="second", headers=("second.h",), sources=("second.c",), root=tmp_path / "src" / "second",
                     requires={"kconfig": ["B"]})
    _install(second, "--project", root)
    only_second = {name: read(root / name) for name in FILES}
    _install(first, "--project", root)

    assert _uninstall("first", "--project", root) == 0

    assert {name: read(root / name) for name in FILES} == only_second
    assert (root / "components" / "second" / "CMakeLists.txt").is_file()


def test_a_setting_the_user_set_is_named(library, project, nobody, no_network, capsys):
    root = project()
    lib = library(esp32={"settings": [{"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"}]})
    _install(lib, "--project", root)
    (root / "sdkconfig.defaults").write_bytes(b"CONFIG_DEMO_SIZE=16\n")

    assert _uninstall("demo", "--project", root) == 0

    out = capsys.readouterr().out
    assert "sdkconfig.defaults still sets what came with demo" in out
    assert "CONFIG_DEMO_SIZE=16" in out
    assert read(root / "sdkconfig.defaults") == "CONFIG_DEMO_SIZE=16\n"


def test_the_users_cmake_lines_are_saved(library, project, nobody, no_network, capsys):
    root = project()
    _install(library(), "--project", root)
    path = root / "components" / "demo" / "CMakeLists.txt"
    path.write_text(read(path).replace("# USER CODE BEGIN DEMO_CMAKE\n", "# USER CODE BEGIN DEMO_CMAKE\nmine()\n"),
                    encoding="utf-8")

    assert _uninstall("demo", "--project", root) == 0

    saved = list((root / "components" / "demo").glob("CMakeLists.txt.*.bak"))
    assert len(saved) == 1 and "mine()" in read(saved[0])
    assert "Your lines in its CMakeLists.txt are saved" in capsys.readouterr().out

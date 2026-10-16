"""The whole command, from the command line to the files it leaves, and what it checks first."""

import json

import pytest
from conftest import read

from esp32_installer import __version__
from esp32_installer.core import cli, manifest, target
from esp32_installer.core.target import INFO, OK, WARN


def _install(*args):
    return cli.main([str(arg) for arg in args])


# ----------------------------------------------------------------------------
# The command
# ----------------------------------------------------------------------------


def test_the_version_is_the_packages(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])

    assert capsys.readouterr().out.strip() == f"esp32-installer {__version__}"


def test_the_help_names_an_esp_idf_project_and_offers_no_ide(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    out = capsys.readouterr().out
    assert "ESP-IDF project" in out
    assert "--ide" not in out


def test_nothing_to_install_says_how(capsys):
    assert cli.main([]) == 2
    assert "esp32-installer owner/example" in capsys.readouterr().err


# ----------------------------------------------------------------------------
# A whole install
# ----------------------------------------------------------------------------


def test_a_library_becomes_a_component(library, project, nobody, no_network, capsys):
    lib = library(layout="mirror", requires={"kconfig": ["FREERTOS_HZ=1000"]}, esp32={"requires": ["esp_timer"]})
    root = project()

    assert _install(lib, "--project", root) == 0

    folder = root / "components" / "demo"
    assert (folder / "src" / "demo.h").is_file()
    assert "esp_timer" in read(folder / "CMakeLists.txt")
    assert "CONFIG_FREERTOS_HZ=1000" in read(root / "sdkconfig.defaults")
    assert "EXTRA_COMPONENT_DIRS" not in read(root / "CMakeLists.txt")

    record = json.loads(read(root / ".esp32-installer.json"))
    assert record["libraries"]["demo"]["folder"] == "components/demo"

    out = capsys.readouterr().out
    assert '#include "demo.h"' in out


def test_a_second_install_changes_nothing(library, project, nobody, no_network):
    lib = library(requires={"kconfig": ["FREERTOS_HZ=1000"]})
    root = project(main='idf_component_register(SRCS "main.c" PRIV_REQUIRES esp_timer)\n')
    _install(lib, "--project", root)
    files = ["CMakeLists.txt", "sdkconfig.defaults", "main/CMakeLists.txt", "components/demo/CMakeLists.txt"]
    first = {name: read(root / name) for name in files}

    assert _install(lib, "--project", root) == 0

    assert {name: read(root / name) for name in files} == first


def test_a_dependency_is_required_by_its_folders_name(library, project, nobody, no_network, tmp_path):
    root = project()
    osal = library(name="osal", headers=("osal.h",), sources=(), root=tmp_path / "libs" / "osal")
    lib = library(requires={"libraries": ["osal"]}, esp32={"requires": ["esp_timer"]})

    assert _install(osal, "--project", root, "--dir", "components/osal_lib") == 0
    assert _install(lib, "--project", root) == 0

    text = read(root / "components" / "demo" / "CMakeLists.txt")
    assert "REQUIRES\n        esp_timer\n        osal_lib\n)" in text


def test_a_folder_outside_components_is_added_to_the_project(library, project, nobody, no_network):
    root = project()

    assert _install(library(), "--project", root, "--dir", "libs/demo") == 0

    assert '"${CMAKE_CURRENT_SOURCE_DIR}/libs/demo"' in read(root / "CMakeLists.txt")
    assert (root / "libs" / "demo" / "CMakeLists.txt").is_file()


def test_the_folder_offered_is_in_components(library, project, answers, no_network):
    asked = answers("")
    root = project()

    assert _install(library(), "--project", root) == 0

    assert "[components/demo]" in asked[0]


# ----------------------------------------------------------------------------
# What is checked before the library goes in
# ----------------------------------------------------------------------------


def _check(library, root, **kwargs):
    return target.current.check(manifest.load(library(**kwargs)), root)


def test_no_project_is_one_warning(library, tmp_path):
    found = _check(library, tmp_path)

    assert [f.level for f in found] == [WARN]
    assert "include(.../project.cmake)" in found[0].message


def test_a_name_esp_idf_has_already_is_warned_about(library, project, tmp_path, monkeypatch):
    idf = tmp_path / "idf"
    (idf / "components" / "demo").mkdir(parents=True)
    monkeypatch.setenv("IDF_PATH", str(idf))

    found = _check(library, project())

    assert found[0].level == WARN
    assert "ESP-IDF has a component called demo" in found[0].message
    assert "components/demo_lib" in found[0].hint


def test_each_symbol_is_said_once_for_what_it_is(library, project):
    root = project(defaults="CONFIG_A=y\nCONFIG_B=1\n", sdkconfig="CONFIG_C=n\nCONFIG_D=y\n")

    found = _check(library, root, requires={"kconfig": ["A", "B=2", "C", "D", "E"],
                                            "peripherals": [{"type": "i2c", "note": "400 kHz"}]})
    said = [(f.level, f.message) for f in found]

    assert said == [
        (WARN, "sdkconfig.defaults already sets CONFIG_A=y, so the block has it commented out"),
        (WARN, "sdkconfig.defaults sets CONFIG_B=1, and demo needs 2. The block has it commented out"),
        (WARN, "sdkconfig has CONFIG_C=n, and demo needs y"),
        (INFO, "CONFIG_D=y goes into sdkconfig.defaults"),
        (INFO, "CONFIG_E=y goes into sdkconfig.defaults"),
        (INFO, "Needs I2C, 400 kHz"),
    ]


def test_a_symbol_already_in_the_block_is_ok(library, project, nobody, no_network):
    lib = library(requires={"kconfig": ["A"]})
    root = project()
    _install(lib, "--project", root)

    found = target.current.check(manifest.load(lib), root)

    assert [(f.level, f.message) for f in found] == [(OK, "CONFIG_A=y is in sdkconfig.defaults")]


def test_a_project_naming_its_own_defaults_is_warned(library, project):
    cmakelists = 'set(SDKCONFIG_DEFAULTS "my.defaults")\ninclude($ENV{IDF_PATH}/tools/cmake/project.cmake)\n'

    found = _check(library, project(cmakelists=cmakelists), requires={"kconfig": ["A"]})

    assert "SDKCONFIG_DEFAULTS" in found[0].message

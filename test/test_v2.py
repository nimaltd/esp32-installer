"""
What 2.0.0 brings to an ESP-IDF project: groups of CMake lines in the
component and in the project's CMakeLists.txt, each between markers of its own,
and files of the project's own made once.
"""

from pathlib import Path

import pytest
from conftest import CMAKELISTS, read

from esp32_installer.core import cli, manifest
from esp32_installer.core.manifest import ManifestError

MODERN = {"esp32_installer": "2.0.0"}


def _lib(library, groups, root=None, options=None, extra=None):
    more = dict(extra or {})

    if options:
        more["options"] = options

    return library(name="demo", requires=MODERN, esp32={"cmake": groups}, extra=more, root=root)


def _install(source, root, *more):
    return cli.main([str(source), "--project", str(root), "--dir", "components/demo", *more])


GROUPS = [
    {"label": "opts", "lines": ["target_compile_options(${COMPONENT_LIB} PRIVATE -Wall)"]},
    {"label": "dirs", "where": "before-project", "lines": ['list(APPEND EXTRA_COMPONENT_DIRS "extra")']},
    {"label": "report", "where": "after-project", "lines": ['message(STATUS "demo is in")']},
]


def test_each_group_lands_in_its_place(library, project, nobody, no_network):
    root = project()

    assert _install(_lib(library, GROUPS), root) == 0

    text = read(root / "CMakeLists.txt")
    component = read(root / "components" / "demo" / "CMakeLists.txt")
    assert text.index("demo/dirs >>>") < text.index("include($ENV{IDF_PATH}") < text.index("demo/report >>>")
    assert ("# >>> esp32-installer: demo/opts >>>\n"
            "# From demo's installer.yml, and written again on every install.\n"
            "target_compile_options(${COMPONENT_LIB} PRIVATE -Wall)\n"
            "# <<< esp32-installer: demo/opts <<<\n") in component
    assert "demo/dirs" not in component


def test_a_changed_block_is_reported_as_updated(library, project, nobody, no_network, tmp_path, capsys):
    root = project()
    _install(_lib(library, GROUPS, root=tmp_path / "v1"), root)
    assert "Added demo to CMakeLists.txt." in capsys.readouterr().out
    changed = [dict(GROUPS[1], lines=['list(APPEND EXTRA_COMPONENT_DIRS "more")'])]

    _install(_lib(library, changed, root=tmp_path / "v2"), root)

    assert "Updated demo in CMakeLists.txt." in capsys.readouterr().out


def test_installing_again_changes_nothing(library, project, nobody, no_network):
    root = project()
    source = _lib(library, GROUPS)
    _install(source, root)
    before = read(root / "CMakeLists.txt")
    backups = sorted(p.name for p in root.rglob("*.bak"))

    _install(source, root)

    assert read(root / "CMakeLists.txt") == before
    assert sorted(p.name for p in root.rglob("*.bak")) == backups


def test_changing_moving_and_dropping_groups(library, project, nobody, no_network, tmp_path):
    root = project()
    _install(_lib(library, GROUPS, root=tmp_path / "v1"), root)
    changed = [
        {"label": "dirs", "where": "after-project", "lines": ['list(APPEND EXTRA_COMPONENT_DIRS "extra")']},
    ]

    _install(_lib(library, changed, root=tmp_path / "v2"), root)

    text = read(root / "CMakeLists.txt")
    assert text.index("include($ENV{IDF_PATH}") < text.index("demo/dirs >>>")
    assert "demo/report" not in text


def test_an_options_groups_come_and_go_with_it(library, project, nobody, no_network):
    root = project()
    options = {"x": {"description": "x", "esp32": {"cmake": [
        {"label": "xtra", "where": "after-project", "lines": ["x()"]}]}}}
    source = _lib(library, [], options=options)

    _install(source, root, "--with", "x")
    assert "demo/xtra >>>" in read(root / "CMakeLists.txt")

    _install(source, root, "--without", "x")
    assert "demo/xtra" not in read(root / "CMakeLists.txt")


def test_uninstall_takes_every_group_out(library, project, nobody, no_network):
    root = project()
    _install(_lib(library, GROUPS), root)

    assert cli.main(["--uninstall", "demo", "--project", str(root)]) == 0

    assert read(root / "CMakeLists.txt") == CMAKELISTS


def test_two_groups_with_one_label_are_refused(library):
    groups = [{"label": "a", "lines": ["a()"]}, {"label": "a", "where": "after-project", "lines": ["b()"]}]

    with pytest.raises(ManifestError, match="two groups labelled a"):
        manifest.load(_lib(library, groups))


def test_the_plain_list_from_before_is_written_as_it_always_was(library, project, nobody, no_network):
    root = project()

    _install(library(name="demo", esp32={"cmake": ["target_compile_options(${COMPONENT_LIB} PRIVATE -O2)"]}),
             root)

    component = read(root / "components" / "demo" / "CMakeLists.txt")
    assert "# From demo's installer.yml.\ntarget_compile_options(${COMPONENT_LIB} PRIVATE -O2)\n" in component
    assert ">>>" not in component


def test_a_project_from_1_x_updates_without_a_change(library, project, nobody, no_network):
    root = project(defaults="CONFIG_X=y\n")
    source = library(name="demo", requires={"kconfig": ["FREERTOS_HZ=1000"]})
    _install(source, root)
    files = {name: read(root / name) for name in ("CMakeLists.txt", "sdkconfig.defaults", "main/CMakeLists.txt")}

    _install(source, root)

    assert {name: read(root / name) for name in files} == files


def test_once_files_land_in_the_project_and_a_managed_one_is_refused(library, project, nobody, no_network, capsys):
    root = project()
    once = {"once": [{"from": "project/VERSION"}]}
    source = library(name="demo", requires=MODERN, extra=once, files={"project/VERSION": "1.0.0\n"})

    assert _install(source, root) == 0
    assert (root / "VERSION").read_text() == "1.0.0\n"

    for to in ("sdkconfig.defaults", "main/CMakeLists.txt", "sdkconfig"):
        bad = library(name="bad", requires=MODERN, extra={"once": [{"from": "project/VERSION", "to": to}]},
                      files={"project/VERSION": "1.0.0\n"}, root=Path(root).parent / f"bad-{to.replace('/', '-')}")

        assert cli.main([str(bad), "--project", str(root), "--dir", "components/bad"]) == 2

    assert "edits or reads as the project's own" in capsys.readouterr().err

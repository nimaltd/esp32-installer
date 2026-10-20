"""
What 2.1.0 brings to an ESP-IDF project: {library} in a group of CMake lines
names the folder the library was installed in, wherever --dir put it.
"""

from conftest import read

from esp32_installer.core import cli

ROOTED = {"esp32_installer": "2.1.0"}

GROUPS = [
    {"label": "dirs", "where": "before-project", "lines": ['list(APPEND EXTRA_COMPONENT_DIRS "{library}/extra")']},
    {"label": "opts", "lines": ['message(STATUS "{library}")']},
]


def _install(source, root, *more):
    return cli.main([str(source), "--project", str(root), "--dir", "libs/demo", *more])


def test_library_is_where_dir_put_it_and_the_components_folder(library, project, nobody, no_network):
    root = project()

    assert _install(library(name="demo", requires=ROOTED, esp32={"cmake": GROUPS}), root) == 0

    assert ('list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/libs/demo/extra")'
            in read(root / "CMakeLists.txt"))
    assert 'message(STATUS "${COMPONENT_DIR}")' in read(root / "libs" / "demo" / "CMakeLists.txt")


def test_before_2_1_0_library_is_left_as_it_was_written(library, project, nobody, no_network):
    root = project()

    assert _install(library(name="demo", requires={"esp32_installer": "2.0.0"}, esp32={"cmake": GROUPS}), root) == 0

    assert 'list(APPEND EXTRA_COMPONENT_DIRS "{library}/extra")' in read(root / "CMakeLists.txt")



def test_the_lines_go_under_the_places_they_go(library, project, nobody, no_network):
    root = project()
    placed = {"before-project": ['list(APPEND EXTRA_COMPONENT_DIRS "{library}/extra")'],
              "component": ['message(STATUS "{library}")']}

    assert _install(library(name="demo", requires=ROOTED, esp32={"cmake": placed}), root) == 0

    text = read(root / "CMakeLists.txt")
    assert "# >>> esp32-installer: demo/before-project >>>" in text
    assert '"${CMAKE_CURRENT_SOURCE_DIR}/libs/demo/extra"' in text
    assert 'message(STATUS "${COMPONENT_DIR}")' in read(root / "libs" / "demo" / "CMakeLists.txt")

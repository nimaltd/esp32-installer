"""The project's own files: CMakeLists.txt, sdkconfig.defaults and main/CMakeLists.txt."""

import pytest
from conftest import read

from esp32_installer import project as prj
from esp32_installer.core import manifest
from esp32_installer.core.target import ALREADY, CHANGED, MANUAL


def _loaded(library, **kwargs):
    return manifest.load(library(**kwargs))


# ----------------------------------------------------------------------------
# CMakeLists.txt
# ----------------------------------------------------------------------------


def test_a_project_is_known_by_its_include_of_project_cmake(project, tmp_path):
    assert prj.find_project(project()) is not None

    other = tmp_path / "other"
    other.mkdir()
    (other / "CMakeLists.txt").write_text("# include($ENV{IDF_PATH}/tools/cmake/project.cmake)\n", encoding="utf-8")

    assert prj.find_project(other) is None


def test_a_library_in_components_needs_no_cmake_block(project, library):
    root = project()
    before = read(root / "CMakeLists.txt")

    outcome = prj.integrate_cmake(root, _loaded(library), root / "components" / "demo")

    assert outcome is None
    assert read(root / "CMakeLists.txt") == before


@pytest.mark.parametrize("crlf", [False, True])
def test_a_library_elsewhere_is_added_above_include(project, library, crlf):
    root = project(crlf=crlf)
    newline = "\r\n" if crlf else "\n"

    outcome = prj.integrate_cmake(root, _loaded(library), root / "libs" / "demo")
    text = read(root / "CMakeLists.txt")

    assert outcome.status == CHANGED
    expected = ('list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/libs/demo")' + newline
                + "# <<< esp32-installer: demo <<<" + newline + newline + "include($ENV{IDF_PATH}")
    assert expected in text
    assert text.count("\r\n") == (text.count("\n") if crlf else 0)

    again = prj.integrate_cmake(root, _loaded(library), root / "libs" / "demo")
    assert again.status == ALREADY


def test_a_block_below_include_moves_above_it(project, library):
    late = ("include($ENV{IDF_PATH}/tools/cmake/project.cmake)\n# >>> esp32-installer: demo >>>\n"
            "STALE_LINE\n# <<< esp32-installer: demo <<<\nproject(app)\n")
    root = project(cmakelists=late)

    prj.integrate_cmake(root, _loaded(library), root / "libs" / "demo")
    text = read(root / "CMakeLists.txt")

    assert text.index("EXTRA_COMPONENT_DIRS") < text.index("include(")
    assert "STALE_LINE" not in text
    assert text.count(">>> esp32-installer: demo") == 1


def test_a_library_moved_into_components_loses_its_block(project, library):
    root = project()
    before = read(root / "CMakeLists.txt")
    prj.integrate_cmake(root, _loaded(library), root / "libs" / "demo")

    outcome = prj.integrate_cmake(root, _loaded(library), root / "components" / "demo")

    assert outcome.status == CHANGED
    assert read(root / "CMakeLists.txt") == before


def test_a_half_written_block_is_left_for_the_user(project, library):
    root = project(cmakelists="# >>> esp32-installer: demo >>>\ninclude($ENV{IDF_PATH}/tools/cmake/project.cmake)\n")

    outcome = prj.integrate_cmake(root, _loaded(library), root / "libs" / "demo")

    assert outcome.status == MANUAL
    assert "half written" in outcome.message


def test_with_no_project_the_lines_are_given_to_add_by_hand(library, tmp_path):
    outcome = prj.integrate_cmake(tmp_path, _loaded(library), tmp_path / "libs" / "demo")

    assert outcome.status == MANUAL
    assert any("EXTRA_COMPONENT_DIRS" in step for step in outcome.steps)


# ----------------------------------------------------------------------------
# sdkconfig.defaults
# ----------------------------------------------------------------------------


def test_a_library_that_needs_no_symbol_adds_no_block(project, library):
    root = project()

    assert prj.integrate_defaults(root, _loaded(library)) is None
    assert not (root / "sdkconfig.defaults").exists()


def test_the_symbols_go_at_the_end_after_a_blank_line(project, library):
    root = project(defaults="CONFIG_LOG_DEFAULT_LEVEL_INFO=y\n")

    outcome = prj.integrate_defaults(root, _loaded(library, requires={"kconfig": ["FREERTOS_HZ=1000"]}))

    assert outcome.status == CHANGED
    assert read(root / "sdkconfig.defaults") == (
        "CONFIG_LOG_DEFAULT_LEVEL_INFO=y\n\n# >>> esp32-installer: demo >>>\n"
        "# Added by esp32-installer, and written again on every install, so set\n"
        "# demo's symbols below this block rather than in it.\n"
        "CONFIG_FREERTOS_HZ=1000\n# <<< esp32-installer: demo <<<\n"
    )


def test_a_symbol_the_user_sets_is_left_commented(project, library):
    root = project(defaults="CONFIG_FREERTOS_HZ=100\n# CONFIG_X is not set\n")
    loaded = _loaded(library, requires={"kconfig": ["FREERTOS_HZ=1000", "X"]})

    prj.integrate_defaults(root, loaded)
    text = read(root / "sdkconfig.defaults")

    assert "# CONFIG_FREERTOS_HZ=1000  (left out: sdkconfig.defaults sets CONFIG_FREERTOS_HZ=100)" in text
    assert "# CONFIG_X=y  (left out: sdkconfig.defaults sets CONFIG_X=n)" in text


def test_a_value_sdkconfig_holds_is_named_for_menuconfig(project, library):
    root = project(sdkconfig="CONFIG_FREERTOS_HZ=100\nCONFIG_OTHER=y\n")

    outcome = prj.integrate_defaults(root, _loaded(library, requires={"kconfig": ["FREERTOS_HZ=1000", "OTHER"]}))

    assert outcome.steps == ["sdkconfig has CONFIG_FREERTOS_HZ=100, which is what ESP-IDF builds with. "
                             "Set it to 1000 in idf.py menuconfig."]


def test_the_block_of_a_library_that_needs_nothing_now_comes_out(project, library):
    root = project(defaults="CONFIG_A=y\n")
    prj.integrate_defaults(root, _loaded(library, requires={"kconfig": ["B"]}))

    outcome = prj.integrate_defaults(root, _loaded(library, root=library().parent / "again"))

    assert outcome.status == CHANGED
    assert read(root / "sdkconfig.defaults") == "CONFIG_A=y\n"


def test_crlf_is_kept_in_sdkconfig_defaults(project, library):
    root = project(defaults="CONFIG_A=y\n", crlf=True)

    prj.integrate_defaults(root, _loaded(library, requires={"kconfig": ["B"]}))
    text = read(root / "sdkconfig.defaults")

    assert "\n" not in text.replace("\r\n", "")


# ----------------------------------------------------------------------------
# main/CMakeLists.txt
# ----------------------------------------------------------------------------


def test_main_with_no_list_of_its_own_is_left_alone(project):
    root = project()
    before = read(root / "main" / "CMakeLists.txt")

    assert prj.integrate_main(root, "demo") is None
    assert read(root / "main" / "CMakeLists.txt") == before


@pytest.mark.parametrize("main, expected", [
    ('idf_component_register(SRCS "main.c" PRIV_REQUIRES esp_timer)\n',
     'idf_component_register(SRCS "main.c" PRIV_REQUIRES demo esp_timer)\n'),
    ('idf_component_register(SRCS "main.c" REQUIRES driver)\n',
     'idf_component_register(SRCS "main.c" REQUIRES demo driver)\n'),
    ('idf_component_register(SRCS "main.c"\n    REQUIRES driver\n    PRIV_REQUIRES nvs_flash)\n',
     'idf_component_register(SRCS "main.c"\n    REQUIRES driver\n    PRIV_REQUIRES demo nvs_flash)\n'),
    ('idf_component_register(SRCS "main.c" PRIV_REQUIRES)\n',
     'idf_component_register(SRCS "main.c" PRIV_REQUIRES demo)\n'),
])
def test_main_with_a_list_gets_the_component(project, main, expected):
    root = project(main=main)

    outcome = prj.integrate_main(root, "demo")

    assert outcome.status == CHANGED
    assert read(root / "main" / "CMakeLists.txt") == expected
    assert prj.integrate_main(root, "demo").status == ALREADY


def test_a_word_in_a_comment_or_a_string_is_not_a_keyword(project):
    main = ('idf_component_register(SRCS "REQUIRES.c" # REQUIRES nothing\n'
            '    INCLUDE_DIRS "$<IF:1,(a),b>")\n')
    root = project(main=main)

    assert prj.integrate_main(root, "demo") is None


def test_a_name_already_listed_in_quotes_is_not_added_again(project):
    root = project(main='idf_component_register(SRCS "main.c" PRIV_REQUIRES "demo")\n')

    assert prj.integrate_main(root, "demo").status == ALREADY


def test_main_that_cannot_be_read_is_left_with_steps(project):
    root = project(main="idf_component_register(SRCS main.c\n")

    outcome = prj.integrate_main(root, "demo")

    assert outcome.status == MANUAL
    assert "demo" in outcome.steps[0]


def test_the_component_comes_out_of_main_again(project):
    root = project(main='idf_component_register(SRCS "main.c"\n    PRIV_REQUIRES\n        demo\n        esp_timer\n'
                        '    REQUIRES demo)\n')

    outcome = prj.unrequire_main(root, "demo")

    assert outcome.status == CHANGED
    assert read(root / "main" / "CMakeLists.txt") == (
        'idf_component_register(SRCS "main.c"\n    PRIV_REQUIRES\n        esp_timer\n    REQUIRES)\n'
    )
    assert prj.unrequire_main(root, "demo") is None


def test_a_parenthesis_inside_an_argument_does_not_close_the_call(project):
    root = project(main='idf_component_register(SRCS "main.c" INCLUDE_DIRS $<IF:1,(a),b>\n'
                        '    PRIV_REQUIRES esp_timer)\n')

    outcome = prj.integrate_main(root, "demo")

    assert outcome.status == CHANGED
    assert "PRIV_REQUIRES demo esp_timer)" in read(root / "main" / "CMakeLists.txt")

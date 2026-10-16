"""The component's own files: CMakeLists.txt and Kconfig, written from installer.yml."""

from conftest import read

from esp32_installer import component
from esp32_installer.core import manifest
from esp32_installer.core.target import ALREADY, CHANGED


def _loaded(library, **kwargs):
    return manifest.load(library(**kwargs))


def test_the_component_lists_its_sources_includes_and_requires(library):
    loaded = _loaded(library, layout="mirror", esp32={"requires": ["esp_timer"]})
    text = component.cmakelists(loaded, ["esp_timer", "osal"])

    assert text.startswith(component.MARK)
    assert 'SRCS\n        "src/demo.c"\n' in text
    assert 'INCLUDE_DIRS\n        "src"\n' in text
    assert "REQUIRES\n        esp_timer\n        osal\n)" in text
    assert "# USER CODE BEGIN DEMO_CMAKE\n# USER CODE END DEMO_CMAKE\n" in text


def test_a_library_of_headers_only_has_no_srcs_and_interface_defines(library):
    loaded = _loaded(library, sources=(), defines=["DEMO_FAST", "DEMO_N=2"])
    text = component.cmakelists(loaded, [])

    assert "SRCS" not in text
    assert "REQUIRES" not in text
    assert "target_compile_definitions(${COMPONENT_LIB} INTERFACE\n    DEMO_FAST\n    DEMO_N=2\n)" in text
    assert "target_compile_options(${COMPONENT_LIB} INTERFACE -O2)" in text


def test_a_library_with_sources_gives_its_defines_to_every_user(library):
    text = component.cmakelists(_loaded(library, defines=["DEMO_FAST"]), [])

    assert "target_compile_definitions(${COMPONENT_LIB} PUBLIC\n    DEMO_FAST\n)" in text


def test_a_file_at_the_top_is_found_from_the_component(library):
    text = component.cmakelists(_loaded(library, headers=("demo.h",), sources=("demo.c",)), [])

    assert 'INCLUDE_DIRS\n        "."\n' in text
    assert 'SRCS\n        "demo.c"\n' in text


def test_an_odd_file_name_stays_one_argument():
    # Such a name cannot even be made on Windows, so it is quoted on its own.
    assert component.cmake_quote('src/a "b";$c.c') == '"src/a \\"b\\"\\;\\$c.c"'


def test_cmake_lines_from_installer_yml_go_after_the_registration(library):
    loaded = _loaded(library, esp32={"cmake": ["target_link_libraries(${COMPONENT_LIB} PRIVATE m)"]})
    text = component.cmakelists(loaded, [])

    assert text.index(")\n") < text.index("target_link_libraries(${COMPONENT_LIB} PRIVATE m)")
    assert text.index("PRIVATE m)") < text.index("USER CODE BEGIN")


def test_no_settings_means_no_kconfig(library):
    assert component.kconfig(_loaded(library)) is None


def test_the_kconfig_is_a_menu_of_the_settings(library):
    loaded = _loaded(library, esp32={"settings": [
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "range": [1, 64], "prompt": 'Size "in" bytes',
         "help": "How big.\n\nIn bytes."},
        {"name": "DEMO_MASK", "type": "hex", "default": "0x10", "range": ["0x0", "0xFF"], "prompt": "Mask"},
    ]})
    text = component.kconfig(loaded)

    assert text.startswith(component.MARK)
    assert 'menu "demo: A library for the tests"' in text
    assert '    config DEMO_SIZE\n        int "Size \\"in\\" bytes"\n        default 8\n        range 1 64\n' in text
    assert "        help\n            How big.\n\n            In bytes.\n" in text
    assert "        range 0x0 0xff\n" in text
    assert text.endswith("endmenu\n")


def test_both_files_are_written_then_left_alone(library, tmp_path):
    loaded = _loaded(library, esp32={"settings": [{"name": "DEMO_N", "type": "int", "default": 1, "prompt": "N"}]})
    folder = tmp_path / "components" / "demo"
    folder.mkdir(parents=True)

    first = component.write(loaded, folder, [])
    second = component.write(loaded, folder, [])

    assert first.status == CHANGED
    assert "wrote CMakeLists.txt, Kconfig" in first.message
    assert second.status == ALREADY
    assert (folder / "Kconfig").is_file()


def test_a_kconfig_for_settings_that_went_is_removed(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    with_settings = _loaded(library, esp32={"settings": [{"name": "DEMO_N", "type": "int", "default": 1, "prompt": "N"}]})
    component.write(with_settings, folder, [])

    outcome = component.write(_loaded(library, root=tmp_path / "again"), folder, [])

    assert not (folder / "Kconfig").exists()
    assert "removed its Kconfig" in outcome.message


def test_a_kconfig_of_the_librarys_own_is_never_removed(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "Kconfig").write_text("menu \"mine\"\nendmenu\n", encoding="utf-8")

    component.write(_loaded(library), folder, [])

    assert (folder / "Kconfig").read_text(encoding="utf-8") == "menu \"mine\"\nendmenu\n"


def test_the_users_lines_are_carried_into_the_new_file(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    loaded = _loaded(library)
    component.write(loaded, folder, [])
    path = folder / "CMakeLists.txt"
    path.write_text(read(path).replace("# USER CODE BEGIN DEMO_CMAKE\n",
                                       "# USER CODE BEGIN DEMO_CMAKE\nmessage(STATUS mine)\n"), encoding="utf-8")

    outcome = component.write(loaded, folder, ["esp_timer"])

    assert "message(STATUS mine)" in read(path)
    assert "esp_timer" in read(path)
    assert "Kept your USER CODE DEMO_CMAKE" in " ".join(outcome.steps)


def test_broken_markers_put_the_old_file_aside(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    loaded = _loaded(library)
    component.write(loaded, folder, [])
    path = folder / "CMakeLists.txt"
    path.write_text(read(path).replace("# USER CODE END DEMO_CMAKE\n", "mine\n"), encoding="utf-8")

    outcome = component.write(loaded, folder, ["esp_timer"])

    assert outcome.backup is not None and "mine" in read(outcome.backup)
    assert "# USER CODE END DEMO_CMAKE" in read(path)


def test_a_library_with_its_own_cmakelists_is_left_alone(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "CMakeLists.txt").write_bytes(b"idf_component_register(SRCS mine.c)\n")

    outcome = component.write(_loaded(library), folder, [])

    assert outcome.status == ALREADY
    assert read(folder / "CMakeLists.txt") == "idf_component_register(SRCS mine.c)\n"
    assert not (folder / "Kconfig").exists()


def test_remove_takes_only_what_write_made(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    loaded = _loaded(library, esp32={"settings": [{"name": "DEMO_N", "type": "int", "default": 1, "prompt": "N"}]})
    component.write(loaded, folder, [])
    assert component.symbols(folder) == ["DEMO_N"]

    assert component.remove(folder) is None
    assert not (folder / "CMakeLists.txt").exists()
    assert not (folder / "Kconfig").exists()


def test_remove_keeps_a_copy_of_the_users_lines(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    component.write(_loaded(library), folder, [])
    path = folder / "CMakeLists.txt"
    path.write_text(read(path).replace("# USER CODE BEGIN DEMO_CMAKE\n",
                                       "# USER CODE BEGIN DEMO_CMAKE\nmine()\n"), encoding="utf-8")

    saved = component.remove(folder)

    assert saved is not None and "mine()" in read(saved)
    assert not path.exists()


def test_remove_leaves_a_kconfig_of_the_librarys_own(library, tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    component.write(_loaded(library), folder, [])
    (folder / "Kconfig").write_bytes(b'menu "mine"\n    config MINE\n        bool "Mine"\nendmenu\n')

    assert component.symbols(folder) == []

    component.remove(folder)

    assert not (folder / "CMakeLists.txt").exists()
    assert (folder / "Kconfig").is_file()

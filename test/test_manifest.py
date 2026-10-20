"""The ESP-IDF part of installer.yml: what it accepts, and what it refuses before anything is written."""

import pytest

from esp32_installer.core import manifest
from esp32_installer.core.manifest import ManifestError


def _load(library, **kwargs):
    return manifest.load(library(**kwargs))


def test_a_library_with_no_esp32_part_has_nothing_extra(library):
    loaded = _load(library)

    assert loaded.esp32.requires == []
    assert loaded.esp32.settings == []
    assert loaded.esp32.cmake == []
    assert loaded.requires.kconfig == []


def test_requires_kconfig_takes_a_symbol_or_a_value(library):
    loaded = _load(library, requires={"kconfig": ["FREERTOS_HZ=1000", "CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD", 'X="text"']})

    assert [r.line for r in loaded.requires.kconfig] == [
        "CONFIG_FREERTOS_HZ=1000",
        "CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD=y",
        'CONFIG_X="text"',
    ]


@pytest.mark.parametrize("bad", ["lower", "A B", "X=two words", "X=y\nCONFIG_Y=y", 'X="un"closed"'])
def test_requires_kconfig_refuses_what_cannot_be_written_safely(library, bad):
    with pytest.raises(ManifestError, match="requires.kconfig"):
        _load(library, requires={"kconfig": [bad]})


def test_esp32_requires_lists_idf_components_once(library):
    loaded = _load(library, esp32={"requires": ["esp_timer", "esp-tls", "esp_timer"]})

    assert loaded.esp32.requires == ["esp_timer", "esp-tls"]


@pytest.mark.parametrize("bad", ["esp timer", "a;b", "${X}", '"q"'])
def test_esp32_requires_refuses_what_is_not_a_component_name(library, bad):
    with pytest.raises(ManifestError, match="esp32.requires"):
        _load(library, esp32={"requires": [bad]})


def test_esp32_requires_is_a_list(library):
    with pytest.raises(ManifestError, match="esp32.requires is a list"):
        _load(library, esp32={"requires": "esp_timer"})


def test_settings_of_every_type(library):
    loaded = _load(library, esp32={"settings": [
        {"name": "DEMO_ON", "type": "bool", "default": True, "prompt": "On"},
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "range": [1, 64], "prompt": "Size"},
        {"name": "DEMO_MASK", "type": "hex", "default": "0x0F", "prompt": "Mask"},
        {"name": "DEMO_TEXT", "type": "string", "default": 'say "hi"', "prompt": "Text"},
    ]})

    assert [s.line for s in loaded.esp32.settings] == [
        "CONFIG_DEMO_ON=y",
        "CONFIG_DEMO_SIZE=8",
        "CONFIG_DEMO_MASK=0xf",
        'CONFIG_DEMO_TEXT="say \\"hi\\""',
    ]


@pytest.mark.parametrize("setting, message", [
    ({"name": "DEMO_X", "type": "float", "default": 1}, "type"),
    ({"name": "DEMO_X", "type": "int"}, "no default"),
    ({"name": "DEMO_X", "type": "int", "default": 99, "range": [1, 10]}, "outside its range"),
    ({"name": "DEMO_X", "type": "int", "default": 5, "range": [10, 1]}, "starts above"),
    ({"name": "DEMO_X", "type": "bool", "default": "maybe"}, "true or false"),
    ({"name": "DEMO_X", "type": "string", "default": "two\nlines"}, "one line"),
    ({"name": "DEMO_X", "type": "bool", "default": True, "range": [0, 1]}, "only an int or a hex"),
    ({"name": "lower", "type": "int", "default": 1}, "capitals"),
])
def test_a_setting_that_cannot_build_is_refused(library, setting, message):
    with pytest.raises(ManifestError, match=message):
        _load(library, esp32={"settings": [setting]})


def test_a_setting_named_twice_is_refused(library):
    twice = {"name": "DEMO_X", "type": "int", "default": 1}

    with pytest.raises(ManifestError, match="more than once"):
        _load(library, esp32={"settings": [twice, dict(twice)]})


def test_cmake_lines_are_kept_one_per_line(library):
    loaded = _load(library, esp32={"cmake": ["  target_compile_options(${COMPONENT_LIB} PRIVATE -O2)  ", ""]})

    # The form from before 2.0.0: one group, in the component, written as it always was.
    assert [(g.label, g.where, g.lines, g.legacy) for g in loaded.esp32.cmake] == [
        ("cmake", "component", ["target_compile_options(${COMPONENT_LIB} PRIVATE -O2)"], True)]


def test_a_cmake_line_that_runs_onto_another_is_refused(library):
    with pytest.raises(ManifestError, match="runs onto another"):
        _load(library, esp32={"cmake": ["one\ntwo"]})


def test_a_setting_without_the_prefix_or_a_prompt_is_warned_about(library, capsys):
    loaded = _load(library, esp32={"settings": [{"name": "OTHER", "type": "int", "default": 1}]})

    from esp32_installer.core import target

    found = target.current.warnings(loaded)
    assert any("does not start with DEMO_" in line for line in found)
    assert any("has no prompt" in line for line in found)


def test_the_oldest_installer_is_read_from_esp32_installer(library):
    with pytest.raises(ManifestError, match="esp32-installer"):
        _load(library, requires={"esp32_installer": "99.0.0"})

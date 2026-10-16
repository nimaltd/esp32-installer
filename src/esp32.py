"""
What esp32-installer adds to the shared core: what an ESP-IDF project is.

The core does everything a library needs whatever it is installed into. This
says the rest for ESP-IDF: the part of installer.yml only ESP-IDF reads, the
checks against the project's sdkconfig, and the integration, which makes the
library a component of the project (component.py) and adds what it needs to
the project's own files (project.py).
"""

import os
import re
from pathlib import Path

from . import component, project
from .core import installer
from .core.manifest import ManifestError
from .core.target import CHANGED, INFO, MANUAL, OK, WARN, Finding, Outcome, Target

# A Kconfig symbol as ESP-IDF writes them, without CONFIG_ in front.
SYMBOL = re.compile(r"^[A-Z0-9_]+$")

# A value a required symbol may be given in sdkconfig.defaults: y or n, a
# number, a hex number, or a string in quotes. Written into the file as it
# stands, so nothing else gets through.
VALUE = re.compile(r'^(?:y|n|-?[0-9]+|0x[0-9A-Fa-f]+|"[^"\\\n]*")$')

# An ESP-IDF component's name, as it lands unquoted in REQUIRES: esp_timer,
# esp_driver_i2c, esp-tls.
COMPONENT = re.compile(r"^[A-Za-z0-9_.+-]+$")

# What a setting can be, as Kconfig names its types.
TYPES = ("bool", "int", "hex", "string")

_INT = re.compile(r"^-?[0-9]+$")
_HEX = re.compile(r"^0x[0-9A-Fa-f]+$")

symbol_of = component.symbol_of


def _symbol(text, where):
    """A symbol written in installer.yml, without CONFIG_ in front, or ManifestError."""
    found = str(text).strip()

    if found.startswith("CONFIG_"):
        found = found[len("CONFIG_"):]

    if not SYMBOL.match(found):
        raise ManifestError(
            f"{where} has {text!r}. Write a Kconfig symbol in capitals, digits and _, "
            "such as FREERTOS_HZ or CONFIG_FREERTOS_HZ."
        )

    return found


class Requirement:
    """A symbol the project has to have, and the value it needs: CONFIG_FREERTOS_HZ=1000."""

    def __init__(self, text):
        name, _, value = str(text).partition("=")
        self.symbol = _symbol(name, "requires.kconfig")
        self.value = value.strip() or "y"

        if not VALUE.match(self.value):
            raise ManifestError(
                f"requires.kconfig has {text!r}. Give a symbol, which is set to y, or "
                'SYMBOL=value, with y, n, a number, 0x and a hex number, or "text".'
            )

    @property
    def line(self):
        """The line in sdkconfig.defaults."""
        return f"CONFIG_{self.symbol}={self.value}"

    def __repr__(self):
        return f"Requirement({self.line})"


class Peripheral:
    """Hardware the library uses, for the user to give it in their code or menuconfig."""

    def __init__(self, data):
        data = data if isinstance(data, dict) else {"type": data}
        self.type = str(data.get("type", "")).lower()
        self.count = int(data.get("count", 1))
        self.note = str(data.get("note", "") or "")

    def describe(self):
        many = f" x{self.count}" if self.count > 1 else ""
        detail = f", {self.note}" if self.note else ""

        return f"{self.type.upper()}{many}{detail}"


class Setting:
    """
    One setting of the library, a Kconfig symbol the user sets in menuconfig.

    Written into the component's Kconfig, so the C code reads it as
    CONFIG_<name> from sdkconfig.h. Everything is checked here, since all of
    it is written into a file Kconfig reads, and the manifest comes over the
    network.
    """

    def __init__(self, data):
        if not isinstance(data, dict):
            raise ManifestError("esp32.settings holds one entry per setting, each with a name and a type.")

        self.name = _symbol(data.get("name", ""), "esp32.settings")
        where = f"esp32.settings {self.name}"
        self.type = str(data.get("type", "")).lower()

        if self.type not in TYPES:
            raise ManifestError(f"{where} has type {data.get('type')!r}. Use one of: {', '.join(TYPES)}.")

        self.prompt_given = bool(data.get("prompt"))
        self.prompt = component.one_line(data.get("prompt") or self.name)
        self.help = [line.rstrip() for line in str(data.get("help") or "").strip().splitlines()]
        self.range = self._range(data.get("range"), where)

        if "default" not in data or data["default"] is None:
            raise ManifestError(f"{where} has no default. Every setting needs one, so it builds as it is.")

        self.default = self._value(data["default"], where)

    def _number(self, value, where):
        """An int or hex value as a number, for comparing with the range."""
        text = str(value).strip()

        if isinstance(value, bool) or not (_INT.match(text) or _HEX.match(text)):
            raise ManifestError(f"{where}: {value!r} is not a number.")

        return int(text, 0)

    def _range(self, value, where):
        """The smallest and largest the setting may be, or None."""
        if value is None:
            return None

        if self.type not in ("int", "hex"):
            raise ManifestError(f"{where} has a range, which only an int or a hex setting can have.")

        if not isinstance(value, list) or len(value) != 2:
            raise ManifestError(f"{where}: write the range as [smallest, largest].")

        low, high = (self._number(item, where) for item in value)

        if low > high:
            raise ManifestError(f"{where}: the range starts above where it ends.")

        return (low, high)

    def _value(self, value, where):
        """The default as Kconfig writes it."""
        if self.type == "bool":
            if value is True or str(value).lower() in ("y", "yes", "true"):
                return "y"

            if value is False or str(value).lower() in ("n", "no", "false"):
                return "n"

            raise ManifestError(f"{where}: the default of a bool is true or false, not {value!r}.")

        if self.type == "string":
            text = str(value)

            if "\n" in text:
                raise ManifestError(f"{where}: the default is one line of text.")

            return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

        number = self._number(value, where)

        if self.range and not (self.range[0] <= number <= self.range[1]):
            raise ManifestError(f"{where}: the default {value} is outside its range.")

        return self.format(number)

    def format(self, number):
        """A number written the way this setting's type writes it."""
        return hex(number) if self.type == "hex" else str(number)

    @property
    def line(self):
        """The setting at its default, as a line of sdkconfig."""
        return f"CONFIG_{self.name}={self.default}"

    def __repr__(self):
        return f"Setting({self.line})"


class Esp32Part:
    """The esp32 section of installer.yml, with what it leaves out filled in."""

    def __init__(self, data):
        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise ManifestError("esp32 should hold requires, cmake and settings.")

        # The ESP-IDF components the library's code uses, such as esp_timer.
        # They go into REQUIRES of its component, which is how ESP-IDF puts
        # their headers on the library's include path.
        requires = data.get("requires") or []

        if not isinstance(requires, list):
            raise ManifestError("esp32.requires is a list of ESP-IDF components, such as [esp_timer].")

        self.requires = []

        for entry in requires:
            name = str(entry).strip()

            if not COMPONENT.match(name):
                raise ManifestError(
                    f"esp32.requires has {entry!r}. Write an ESP-IDF component by its name, "
                    "such as esp_timer or esp_driver_i2c."
                )

            if name not in self.requires:
                self.requires.append(name)

        settings = data.get("settings") or []

        if not isinstance(settings, list):
            raise ManifestError("esp32.settings is a list, one entry per setting.")

        self.settings = [Setting(entry) for entry in settings]
        names = [setting.name for setting in self.settings]
        twice = sorted({name for name in names if names.count(name) > 1})

        if twice:
            raise ManifestError(f"esp32.settings has {', '.join(twice)} more than once.")

        # Lines of CMake the library needs beyond its files, written as they
        # stand into its component's CMakeLists.txt, after
        # idf_component_register(), where ${COMPONENT_LIB} is its library.
        cmake = data.get("cmake") or []

        if not isinstance(cmake, list) or not all(isinstance(line, str) for line in cmake):
            raise ManifestError("esp32.cmake is a list of lines of CMake, each in quotes when it holds a colon.")

        if any("\n" in line or "\r" in line for line in cmake):
            raise ManifestError("esp32.cmake has a line that runs onto another. Give each line on its own.")

        self.cmake = [line.strip() for line in cmake if line.strip()]


def idf_components(name):
    """
    The folder of ESP-IDF's own component of this name, when there is one.

    Read from IDF_PATH, which ESP-IDF's own shell sets. A project component of
    the same name takes the place of ESP-IDF's in the build.
    """
    idf = os.environ.get("IDF_PATH")

    if not idf:
        return None

    path = Path(idf) / "components" / name

    return path if path.is_dir() else None


class Esp32(Target):
    """An ESP-IDF project: CMakeLists.txt with include(project.cmake), main, and sdkconfig."""

    name = "esp32-installer"
    record_name = ".esp32-installer.json"
    project = "ESP-IDF project"
    requires_key = "esp32_installer"
    no_project = "No ESP-IDF project was recognised here, so nothing was registered."
    no_project_hint = "Run this from your project's folder, the one holding CMakeLists.txt and main/."

    def __init__(self, version):
        self.version = version

    def default_folder(self, library):
        """Libraries go into the project's components folder, where ESP-IDF finds them."""
        return f"{project.COMPONENTS}/{library.name}"

    def read_manifest(self, manifest, data):
        manifest.esp32 = Esp32Part(data.get("esp32"))

    def read_requirements(self, requirements, data):
        """The ESP-IDF part of requires: Kconfig symbols, and hardware."""
        kconfig = data.get("kconfig") or []

        if not isinstance(kconfig, list):
            raise ManifestError("requires.kconfig is a list of symbols, such as [FREERTOS_HZ=1000].")

        requirements.kconfig = [Requirement(entry) for entry in kconfig]
        requirements.peripherals = [Peripheral(entry) for entry in (data.get("peripherals") or [])]

    def requirements_empty(self, requirements):
        return not (requirements.kconfig or requirements.peripherals)

    def warnings(self, manifest):
        part = getattr(manifest, "esp32", None)
        prefix = symbol_of(manifest.name)
        found = []

        for setting in (part.settings if part else []):
            if not setting.name.startswith(prefix + "_"):
                found.append(f"esp32.settings {setting.name} does not start with {prefix}_, "
                             "so it may be taken by another component")

            if not setting.prompt_given:
                found.append(f"esp32.settings {setting.name} has no prompt, so menuconfig shows only its name")

        return found

    def _folder(self, library, project_root):
        """The library's folder: the one it is in already, or the one it is offered."""
        recorded = installer.installed_libraries(project_root).get(library.name)

        if isinstance(recorded, dict) and isinstance(recorded.get("folder"), str):
            return recorded["folder"]

        return self.default_folder(library)

    def check(self, library, project_root):
        """What the project is missing for this library. Never stops an install."""
        findings = []

        if project.find_project(project_root) is None:
            findings.append(Finding(
                WARN, "No CMakeLists.txt with include(.../project.cmake) here",
                "Run this from your ESP-IDF project's folder, or give it with --project.",
            ))

            return findings

        name = component.component_name(self._folder(library, project_root))
        own = idf_components(name)

        if own is not None:
            findings.append(Finding(
                WARN, f"ESP-IDF has a component called {name}, and this one would take its place",
                f"Install it into a folder of another name, such as --dir components/{name}_lib.",
            ))

        if library.requires.kconfig and project.names_its_defaults(project_root):
            findings.append(Finding(
                WARN, "This project sets SDKCONFIG_DEFAULTS, so ESP-IDF may not read sdkconfig.defaults",
                f"Keep {project.DEFAULTS} in that list, or set the lines below in one of yours.",
            ))

        taken = project.user_defaults(project_root, library.name)
        ours = project.in_block(project_root, library.name)
        have = project.configured(project_root)

        for symbol, value, line in project.wanted(library):
            if symbol in taken and taken[symbol] == value:
                findings.append(Finding(
                    WARN, f"{project.DEFAULTS} already sets {line}, so the block has it commented out",
                    "Your line is the one used. Nothing to do.",
                ))
            elif symbol in taken:
                findings.append(Finding(
                    WARN, f"{project.DEFAULTS} sets CONFIG_{symbol}={taken[symbol]}, and {library.name} "
                    f"needs {value}. The block has it commented out",
                    "Your line is the one used. Change it if the library is to work.",
                ))
            elif symbol in have and have[symbol] != value:
                findings.append(Finding(
                    WARN, f"sdkconfig has CONFIG_{symbol}={have[symbol]}, and {library.name} needs {value}",
                    "sdkconfig is what ESP-IDF builds with. Set it in idf.py menuconfig.",
                ))
            elif ours.get(symbol) == value:
                findings.append(Finding(OK, f"{line} is in {project.DEFAULTS}"))
            else:
                findings.append(Finding(INFO, f"{line} goes into {project.DEFAULTS}"))

        for peripheral in library.requires.peripherals:
            findings.append(Finding(INFO, f"Needs {peripheral.describe()}",
                                    "Set it up in your code, or in idf.py menuconfig."))

        return findings

    def requires_of(self, library, project_root):
        """
        Every component the library's component needs: ESP-IDF's own from
        installer.yml, then the libraries it depends on, by the names their
        folders give them, as the record has them.
        """
        recorded = installer.installed_libraries(project_root)
        names = list(library.esp32.requires)

        for dependency in library.dependencies:
            entry = recorded.get(dependency.name)
            folder = entry.get("folder") if isinstance(entry, dict) else None
            name = component.component_name(folder) if isinstance(folder, str) else dependency.name

            if name not in names:
                names.append(name)

        return names

    def integrate(self, project_root, library, destination, only=None, dropped=(),
                  dropped_defines=()):
        """
        Make the library a component of the project, and give it what it needs.

        dropped and dropped_defines need nothing here: the component's files
        are written again from the new manifest on every install, so a file or
        a define that has gone is simply no longer in them.
        """
        outcomes = [component.write(library, destination, self.requires_of(library, project_root))]
        outcomes.extend(project.integrate(project_root, library, destination))

        return outcomes

    def uninstall(self, project_root, library):
        """
        Take the library out of the project's files, and delete the component
        files this wrote into its folder.
        """
        destination = library.destination
        defined = component.symbols(destination) if destination is not None else []
        name = component.component_name(destination) if destination is not None else None
        outcomes = project.uninstall(project_root, library.name, name)

        if destination is not None:
            saved = component.remove(destination)

            if saved is not None:
                outcomes.append(Outcome(
                    component.NAME, CHANGED,
                    f"Your lines in its CMakeLists.txt are saved, in {saved.name}.",
                    backup=saved,
                ))

        # A setting the user set in sdkconfig.defaults names a symbol that is
        # gone now. ESP-IDF only warns about it, but the line is the user's,
        # so it is named rather than taken out.
        lines = project.leftover(project_root, defined)

        if lines:
            outcomes.append(Outcome(
                project.DEFAULTS, MANUAL,
                f"{project.DEFAULTS} still sets what came with {library.name}, which ESP-IDF no "
                "longer knows. Take these lines out:",
                lines,
            ))

        return outcomes

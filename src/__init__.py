"""
Install embedded C libraries into an ESP-IDF project.

Installed with pip, it is the esp32-installer command. It takes a library from
GitHub, from a downloaded zip, or from a folder, and makes it a component of
the project: its own CMakeLists.txt and Kconfig, the ESP-IDF components it
uses, and the settings it needs in sdkconfig.defaults.

The work that is the same for any project is the shared core, in core/, from
github.com/nimaltd/core-installer. What an ESP-IDF project is, is in esp32.py.

See https://github.com/nimaltd/esp32-installer
"""

__version__ = "2.1.0"

# Before anything of the core is used: it asks the target for every answer
# that depends on the kind of project.
from .core import target as _target  # noqa: E402
from .esp32 import Esp32  # noqa: E402

_target.use(Esp32(__version__))

from .core.installer import InstallError, Result, install_in_place, install_to  # noqa: E402
from .core.manifest import Manifest, ManifestError, load  # noqa: E402

__all__ = [
    "InstallError",
    "Manifest",
    "ManifestError",
    "Result",
    "install_in_place",
    "install_to",
    "load",
    "main",
]


def main(argv=None):
    """Run the command line interface. Imported lazily to keep start-up cheap."""
    from .cli import main as _main

    return _main(argv=argv)

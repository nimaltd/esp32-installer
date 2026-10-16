"""
The project's own files: CMakeLists.txt, sdkconfig.defaults, and main's CMakeLists.txt.

Each is touched only when the library needs it, and each edit is one the user
can see and undo:

    CMakeLists.txt       a block that adds the library's folder to
                         EXTRA_COMPONENT_DIRS, above include(project.cmake),
                         only for a library outside the components folder,
                         which ESP-IDF finds by itself
    sdkconfig.defaults   a block with the Kconfig symbols the library needs,
                         only when it needs any
    main/CMakeLists.txt  the library's name in main's REQUIRES, only when main
                         lists its own. Without a list of its own, main uses
                         every component of the build, this one too

All of them are the user's, so the rules of every edit here hold: a copy is
taken before anything changes, a file this cannot read safely is left alone
with the lines to add by hand, a second install adds nothing twice, and the
file's own line endings are kept.

What the user set in sdkconfig.defaults outside the block is theirs. A symbol
they set is not set again in the block, whatever value they gave it, since the
line read last would win and quietly undo their choice. And sdkconfig itself,
which ESP-IDF writes and reads before sdkconfig.defaults, is never edited: a
value it holds already is named, for the user to change in menuconfig.
"""

import os
import re
from pathlib import Path

from .component import cmake_quote, component_name
from .core.files import backup
from .core.target import ALREADY, CHANGED, MANUAL, Outcome

CMAKELISTS = "CMakeLists.txt"
DEFAULTS = "sdkconfig.defaults"
SDKCONFIG = "sdkconfig"
MAIN = "main/CMakeLists.txt"
COMPONENTS = "components"

MARK_OPEN = "# >>> esp32-installer: {name} >>>"
MARK_CLOSE = "# <<< esp32-installer: {name} <<<"

# The line an ESP-IDF project's CMakeLists.txt is built around. CMake commands
# ignore case, and only a line that starts with it counts, so a commented out
# one does not.
PROJECT_CMAKE = re.compile(r"^[ \t]*include[ \t]*\([^)\n]*tools/cmake/project\.cmake", re.MULTILINE | re.IGNORECASE)

# A project that names its own defaults files, in place of sdkconfig.defaults.
NAMES_DEFAULTS = re.compile(r"^[ \t]*set[ \t]*\([ \t]*SDKCONFIG_DEFAULTS\b", re.MULTILINE | re.IGNORECASE)

# CONFIG_FOO=y, and the form menuconfig writes for a symbol switched off. A
# file written on Windows ends its lines in CRLF, and $ stops only before the
# line feed, so the carriage return is allowed for, never taken into a value.
ASSIGNED = re.compile(r"^[ \t]*CONFIG_([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*?)[ \t\r]*$", re.MULTILINE)
NOT_SET = re.compile(r"^[ \t]*#[ \t]*CONFIG_([A-Za-z0-9_]+) is not set[ \t\r]*$", re.MULTILINE)


def read(path):
    """The file's text, with its line endings exactly as they are on disk."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    """Write the text back with its line endings untouched."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def line_ending(text):
    """The line ending the file already uses, line feed for a new one."""
    return "\r\n" if "\r\n" in text else "\n"


def _text(path):
    """A file's text, empty when it is missing or unreadable."""
    try:
        return read(path)
    except (OSError, UnicodeDecodeError):
        return ""


def find_project(project_root):
    """The project's CMakeLists.txt, when it is an ESP-IDF project."""
    path = Path(project_root) / CMAKELISTS

    return path if PROJECT_CMAKE.search(_text(path)) else None


def names_its_defaults(project_root):
    """Whether the project's CMakeLists.txt sets SDKCONFIG_DEFAULTS itself."""
    return bool(NAMES_DEFAULTS.search(_text(Path(project_root) / CMAKELISTS)))


def in_components(destination, project_root):
    """Whether the library's folder sits right in the components folder, where ESP-IDF looks."""
    try:
        return Path(destination).resolve().parent == (Path(project_root) / COMPONENTS).resolve()
    except OSError:
        return False


def block_span(text, name):
    """
    Where this library's block is: (start, end), None when it has none, or
    False when only its first marker is there.
    """
    open_mark = MARK_OPEN.format(name=name)
    close_mark = MARK_CLOSE.format(name=name)

    if open_mark not in text:
        return None

    start = text.index(open_mark)

    if close_mark not in text[start:]:
        return False

    return start, text.index(close_mark, start) + len(close_mark)


def _outside(text, name):
    """The text without this library's block."""
    span = block_span(text, name)

    return text[:span[0]] + text[span[1]:] if span else text


def assigned(text):
    """Every symbol a Kconfig file sets: {symbol: value}, n for one it switches off."""
    found = {}

    for symbol in NOT_SET.findall(text):
        found.setdefault(symbol, "n")

    for symbol, value in ASSIGNED.findall(text):
        found.setdefault(symbol, value)

    return found


def user_defaults(project_root, name):
    """Every symbol sdkconfig.defaults sets outside this library's block: {symbol: value}."""
    return assigned(_outside(_text(Path(project_root) / DEFAULTS), name))


def in_block(project_root, name):
    """The symbols this library's own block in sdkconfig.defaults sets, and their values."""
    text = _text(Path(project_root) / DEFAULTS)
    span = block_span(text, name)

    return dict(ASSIGNED.findall(text[span[0]:span[1]])) if span else {}


def configured(project_root):
    """What sdkconfig, the configuration ESP-IDF builds with, sets: {symbol: value}."""
    return assigned(_text(Path(project_root) / SDKCONFIG))


def relative(path, root):
    """A forward slash path from root to path, None on another drive."""
    try:
        return Path(os.path.relpath(Path(path).resolve(), Path(root).resolve())).as_posix()
    except ValueError:
        return None


def _write_block(path, label, text, updated, what):
    """Back the file up and write it. Returns an Outcome."""
    if updated == text:
        return Outcome(label, ALREADY, f"{label} already has {what}.")

    saved = backup(path) if path.exists() else None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, updated)
    except OSError as error:
        return Outcome(label, MANUAL, f"Could not write {label}: {error}", backup=saved)

    return Outcome(label, CHANGED, f"Added {what} to {label}.", backup=saved)


def _half_written(label, name, block):
    return Outcome(
        label, MANUAL,
        f"{label} has a half written esp32-installer block for {name}. Fix it by hand first.",
        block.splitlines(),
    )


def _cut(text, span, newline):
    """
    The text with a block taken out, with the line it stood on and the one
    blank line that came with it: below it in CMakeLists.txt, or above it at
    the end of sdkconfig.defaults.
    """
    start, end = span

    if text.startswith(newline, end):
        end += len(newline)

    if text.startswith(newline, end):
        end += len(newline)
    elif end == len(text) and text[:start].endswith(newline + newline):
        start -= len(newline)

    return text[:start] + text[end:]


def _cut_block(path, label, name):
    """Take this library's block out of one file. Returns an Outcome, ALREADY when it has none."""
    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    span = block_span(text, name)

    if span is None:
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    if span is False:
        return Outcome(label, MANUAL, f"{label} has a half written esp32-installer block for {name}. "
                       "Take it out by hand.")

    saved = backup(path)
    write(path, _cut(text, span, line_ending(text)))

    return Outcome(label, CHANGED, f"Removed {name} from {label}.", backup=saved)


# CMakeLists.txt

def _folder_path(destination, project_root):
    """The library's folder as CMake reads it, from the project's folder."""
    folder = relative(destination, project_root)

    if folder is None:
        return cmake_quote(Path(destination).resolve().as_posix())

    return '"${CMAKE_CURRENT_SOURCE_DIR}/' + cmake_quote(folder)[1:]


def cmake_block(library, destination, project_root, newline="\n"):
    """The lines this tool owns in the project's CMakeLists.txt."""
    lines = [
        MARK_OPEN.format(name=library.name),
        f"# Added by esp32-installer, since {library.name} is not in the components folder,",
        "# where ESP-IDF looks by itself. Delete this block to drop it from the build.",
        f"list(APPEND EXTRA_COMPONENT_DIRS {_folder_path(destination, project_root)})",
        MARK_CLOSE.format(name=library.name),
    ]

    return newline.join(lines)


def integrate_cmake(project_root, library, destination):
    """
    Add a library outside the components folder to EXTRA_COMPONENT_DIRS, or
    take out the block of one that has moved into it. Returns an Outcome, or
    None when there is nothing to say.
    """
    path = find_project(project_root)
    name = library.name
    wanted = not in_components(destination, project_root)

    if path is None:
        if not wanted:
            return None

        return Outcome(
            CMAKELISTS, MANUAL,
            "No ESP-IDF project CMakeLists.txt here, so the library was not added to the build.",
            ["Add this to your project's CMakeLists.txt, above include(.../project.cmake):"]
            + cmake_block(library, destination, project_root).splitlines(),
        )

    text = read(path)
    newline = line_ending(text)
    span = block_span(text, name)

    if not wanted:
        # In the components folder now, where ESP-IDF finds it, so a block
        # from when it was elsewhere would only add it a second time.
        return _cut_block(path, CMAKELISTS, name) if span is not None else None

    block = cmake_block(library, destination, project_root, newline)

    if span is False:
        return _half_written(CMAKELISTS, name, block)

    rest = text

    if span is not None:
        start, end = span

        # Where it is, when that is above include(project.cmake).
        if start < PROJECT_CMAKE.search(text).start():
            return _write_block(path, CMAKELISTS, text, text[:start] + block + text[end:], name)

        # Below it the list does nothing, since ESP-IDF has looked for
        # components by then. It comes out, and goes above.
        if text.startswith(newline, end):
            end += len(newline)

        rest = text[:start] + text[end:]

    # Right above include(project.cmake), with a blank line between, and
    # nothing added above it, so an uninstall gives the file back as it was.
    first = PROJECT_CMAKE.search(rest).start()
    updated = rest[:first] + block + newline + newline + rest[first:]

    return _write_block(path, CMAKELISTS, text, updated, name)


# sdkconfig.defaults

def wanted(library):
    """Every line the library asks for in sdkconfig.defaults: (symbol, value, line)."""
    return [(requirement.symbol, requirement.value, requirement.line) for requirement in library.requires.kconfig]


def defaults_block(library, project_root, newline="\n"):
    """
    The lines this tool owns in sdkconfig.defaults.

    A symbol the user sets already is written too, commented out with what
    they set, so the block shows what the library asked for and why it is not
    set here.
    """
    taken = user_defaults(project_root, library.name)
    body = []

    for symbol, _value, line in wanted(library):
        if symbol in taken:
            body.append(f"# {line}  (left out: {DEFAULTS} sets CONFIG_{symbol}={taken[symbol]})")
        else:
            body.append(line)

    lines = [
        MARK_OPEN.format(name=library.name),
        "# Added by esp32-installer, and written again on every install, so set",
        f"# {library.name}'s symbols below this block rather than in it.",
    ]
    lines.extend(body)
    lines.append(MARK_CLOSE.format(name=library.name))

    return newline.join(lines)


def integrate_defaults(project_root, library):
    """
    Set the symbols the library needs in sdkconfig.defaults, created when it
    is not there. A library that needs none has no block, and one an earlier
    version left is taken out. Returns an Outcome, or None.
    """
    path = Path(project_root) / DEFAULTS

    if not wanted(library):
        return _cut_block(path, DEFAULTS, library.name) if block_span(_text(path), library.name) else None

    try:
        text = read(path) if path.exists() else ""
    except (OSError, UnicodeDecodeError) as error:
        return Outcome(DEFAULTS, MANUAL, f"Could not read {DEFAULTS}: {error}",
                       defaults_block(library, project_root).splitlines())

    newline = line_ending(text)
    block = defaults_block(library, project_root, newline)
    span = block_span(text, library.name)

    if span is False:
        return _half_written(DEFAULTS, library.name, block)

    if span is not None:
        updated = text[:span[0]] + block + text[span[1]:]
    else:
        # At the end, after a blank line when the file has anything in it.
        head = text.rstrip("\r\n")
        updated = (head + newline + newline if head else "") + block + newline

    outcome = _write_block(path, DEFAULTS, text, updated, library.name)
    outcome.steps += stale(library, project_root)

    return outcome


def stale(library, project_root):
    """
    Sentences for the symbols sdkconfig holds at another value than the
    library needs. ESP-IDF reads sdkconfig.defaults only for a symbol sdkconfig
    does not have yet, so sdkconfig's value is the one built with.
    """
    have = configured(project_root)
    taken = user_defaults(project_root, library.name)

    return [
        f"sdkconfig has CONFIG_{symbol}={have[symbol]}, which is what ESP-IDF builds with. "
        f"Set it to {value} in idf.py menuconfig."
        for symbol, value, _line in wanted(library)
        if symbol in have and have[symbol] != value and symbol not in taken
    ]


# main/CMakeLists.txt

# The arguments of idf_component_register() that take a list. A word that is
# one of these starts a new list.
KEYWORDS = {
    "SRCS", "SRC_DIRS", "EXCLUDE_SRCS", "INCLUDE_DIRS", "PRIV_INCLUDE_DIRS", "LDFRAGMENTS",
    "REQUIRES", "PRIV_REQUIRES", "REQUIRED_IDF_TARGETS", "EMBED_FILES", "EMBED_TXTFILES",
    "KCONFIG", "KCONFIG_PROJBUILD", "WHOLE_ARCHIVE",
}

_REGISTER = re.compile(r"\bidf_component_register[ \t]*\(", re.IGNORECASE)


def _words(text, start):
    """
    The arguments of the call whose opening parenthesis ends at start:
    [(word, first, last)], and where its closing parenthesis is.

    Read the way CMake reads them: a comment runs from # to the end of the
    line, a quoted argument is one word whatever it holds, and a parenthesis
    inside an argument, such as one of a generator expression, does not close
    the call. Raises ValueError for a call that never closes.
    """
    words = []
    depth = 0
    index = start

    while index < len(text):
        char = text[index]

        if char == "#":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue

        if char in " \t\r\n":
            index += 1
            continue

        if char == ")" and depth == 0:
            return words, index

        first = index

        if char == '"':
            index += 1

            while index < len(text) and text[index] != '"':
                index += 2 if text[index] == "\\" else 1

            index += 1
        else:
            while index < len(text) and text[index] not in " \t\r\n#\"" and not (text[index] == ")" and depth == 0):
                if text[index] == "(":
                    depth += 1
                elif text[index] == ")":
                    depth -= 1

                index += 1

        words.append((text[first:index], first, index))

    raise ValueError("idf_component_register() is never closed")


def _lists(text):
    """
    main's REQUIRES and PRIV_REQUIRES, as {keyword: (keyword's end, [(word, first, last)])},
    or None when main/CMakeLists.txt has no idf_component_register() it can read.
    """
    found = _REGISTER.search(text)

    if found is None:
        return None

    try:
        words, _close = _words(text, found.end())
    except ValueError:
        return None

    lists = {}
    current = None

    for word, first, last in words:
        if word in KEYWORDS:
            current = word if word in ("REQUIRES", "PRIV_REQUIRES") else None

            if current is not None and current not in lists:
                lists[current] = (last, [])

            continue

        if current is not None:
            lists[current][1].append((word, first, last))

    return lists


def integrate_main(project_root, name):
    """
    Add the component to main's REQUIRES, when main lists its own. Returns an
    Outcome, or None when main needs nothing: without a list of its own, main
    uses every component of the build by itself.
    """
    path = Path(project_root) / MAIN

    if not path.is_file():
        return None

    try:
        text = read(path)
    except (OSError, UnicodeDecodeError) as error:
        return Outcome(MAIN, MANUAL, f"Could not read {MAIN}: {error}",
                       [f"Add {name} to PRIV_REQUIRES of idf_component_register() in {MAIN}."])

    lists = _lists(text)

    if lists is None:
        return Outcome(MAIN, MANUAL, f"{MAIN} has no idf_component_register() this could read.",
                       [f"If main lists REQUIRES or PRIV_REQUIRES, add {name} to them."])

    if not lists:
        return None

    if any(word.strip('"') == name for _end, items in lists.values() for word, _first, _last in items):
        return Outcome(MAIN, ALREADY, f"{MAIN} already requires {name}.")

    # Main's own use, so PRIV_REQUIRES when it has one, as ESP-IDF suggests
    # for a component nothing else builds on.
    keyword = "PRIV_REQUIRES" if "PRIV_REQUIRES" in lists else "REQUIRES"
    end = lists[keyword][0]
    outcome = _write_block(path, MAIN, text, text[:end] + " " + name + text[end:], name)

    if outcome.status == CHANGED:
        outcome.message = f"Added {name} to {keyword} in {MAIN}, since main lists the components it uses."

    return outcome


def _without(text, first, last):
    """The text with one word taken out: its whole line when it stood alone on one."""
    start = text.rfind("\n", 0, first) + 1
    end = text.find("\n", last)
    end = len(text) if end < 0 else end
    line_end = end + 1 if end < len(text) else end

    if not text[start:first].strip() and not text[last:end].strip():
        return text[:start] + text[line_end:]

    while first > 0 and text[first - 1] in " \t":
        first -= 1

    return text[:first] + text[last:]


def unrequire_main(project_root, name):
    """Take the component out of main's REQUIRES and PRIV_REQUIRES. An Outcome, or None."""
    path = Path(project_root) / MAIN

    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return None

    lists = _lists(text) or {}
    found = sorted(((first, last) for _end, items in lists.values()
                    for word, first, last in items if word.strip('"') == name), reverse=True)

    if not found:
        return None

    updated = text

    for first, last in found:
        updated = _without(updated, first, last)

    saved = backup(path)
    write(path, updated)

    return Outcome(MAIN, CHANGED, f"Removed {name} from the components main requires.", backup=saved)


# The whole project

def integrate(project_root, library, destination):
    """Every edit the library needs. Returns a list of Outcome."""
    outcomes = [integrate_cmake(project_root, library, destination)]

    if find_project(project_root) is not None:
        outcomes.append(integrate_defaults(project_root, library))
        outcomes.append(integrate_main(project_root, component_name(destination)))

    return [outcome for outcome in outcomes if outcome is not None]


def uninstall(project_root, name, component):
    """Take this library out of the project's files. A list of Outcome."""
    root = Path(project_root)
    outcomes = []

    for relative_path in (CMAKELISTS, DEFAULTS):
        path = root / relative_path

        if path.is_file() and block_span(_text(path), name) is not None:
            outcomes.append(_cut_block(path, relative_path, name))

    if component is not None:
        outcomes.append(unrequire_main(project_root, component))

    return [outcome for outcome in outcomes if outcome is not None]


def leftover(project_root, symbols):
    """The lines of sdkconfig.defaults that still set one of symbols, once the block is out."""
    wanted_symbols = set(symbols)
    text = _text(Path(project_root) / DEFAULTS)

    return [
        line.strip() for line in text.splitlines()
        if (ASSIGNED.match(line) and ASSIGNED.match(line).group(1) in wanted_symbols)
        or (NOT_SET.match(line) and NOT_SET.match(line).group(1) in wanted_symbols)
    ]

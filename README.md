# esp32-installer

Installs embedded C libraries into an ESP-IDF project, for any ESP32 chip.

A library written for any project has no idea what an ESP-IDF component is. This copies it into your project's `components` folder and makes it a component: its own `CMakeLists.txt`, the ESP-IDF components it uses, its settings in menuconfig, and the symbols it needs in `sdkconfig.defaults`. Then `idf.py build` picks it up like any other component.

It works with any library that has an `installer.yml` at the root of its repository. I wrote it for my own [NimaLTD](https://github.com/nimaltd) libraries, and they all have one, but nothing in it is tied to them: add an `installer.yml` to yours, as shown [below](#for-someone-writing-a-library), and it installs the same way. The same file serves [stm32-installer](https://github.com/nimaltd/stm32-installer), [zephyr-installer](https://github.com/nimaltd/zephyr-installer), [arduino-installer](https://github.com/nimaltd/arduino-installer) and [pio-installer](https://github.com/nimaltd/pio-installer), so one library can be installed into an ESP-IDF project, an STM32 project, a Zephyr application, an Arduino sketch and a PlatformIO project alike.

Every command below uses `owner/example`, the library's GitHub owner and name, such as `nimaltd/ee24`. Put the real ones in its place.

---

## Installing a library

Install the installer once. This needs internet:

```bash
pip install esp32-installer
```

Then, from your project's folder, the one holding `CMakeLists.txt` and `main/`, install a library by its GitHub owner and name. To see it work first, take [esp32-installer-example](https://github.com/nimaltd/esp32-installer-example), a library made for trying the installer on:

```bash
esp32-installer nimaltd/esp32-installer-example
```

It builds for any ESP32 chip, with its settings in menuconfig. Its README walks through an install, a setting changed, an option, and an uninstall. Any other library goes in the same way, as `esp32-installer owner/example`.

Then build as always:

```bash
idf.py build
```

To update it later, `pip install --upgrade esp32-installer`. To remove it, `pip uninstall esp32-installer`.

When a newer esp32-installer is out, the last line of a run says so, with that command. It asks PyPI at most once a day, waits no more than two seconds for an answer, and says nothing when there is none. `--no-update-check` turns it off, and so does `INSTALLER_NO_UPDATE_CHECK` set to anything. On a build server, where `CI` is set, it is off already.

It runs from any shell, ESP-IDF's own included: it needs Python and nothing of ESP-IDF's. On Windows, if `esp32-installer` is not found after installing, pip put it in a folder that is not on your PATH. `python -m esp32_installer owner/example` runs the same thing.

### Every command

Each command with `owner/example` standing for the library. An update is the install again. Every option is explained under [Options](#options).

| To | Run |
|---|---|
| Install the installer | `pip install esp32-installer` |
| Update the installer | `pip install --upgrade esp32-installer` |
| Remove the installer | `pip uninstall esp32-installer` |
| See which version you have | `esp32-installer --version` |
| See every option | `esp32-installer --help` |
| Install a library from GitHub | `esp32-installer owner/example` |
| Install one release of it, a branch or a commit | `esp32-installer owner/example@v2.0.0` |
| Install it by its GitHub address | `esp32-installer https://github.com/owner/example` |
| Install it from a downloaded zip | `esp32-installer D:/Downloads/example-main.zip` |
| Install it from a folder on disk | `esp32-installer D:/Downloads/example-main` |
| Install several at once, such as a library and the zip of one it needs | `esp32-installer D:/Downloads/example-main.zip D:/Downloads/osal-main.zip` |
| Install into a folder you choose, without the question | `esp32-installer owner/example --dir libs/example` |
| Install into a project you are not running from | `esp32-installer owner/example --project D:/work/app` |
| Take an option of the library without the question | `esp32-installer owner/example --with littlefs` |
| Leave an option out, or take it out of a library already installed | `esp32-installer owner/example --without littlefs` |
| Run a step of the library without the question | `esp32-installer owner/example --run make-key` |
| Leave a step unrun, without the question | `esp32-installer owner/example --no-run make-key` |
| Answer every question with the answer offered, and run every step, for a script | `esp32-installer owner/example --yes` |
| Install from a private repository | `esp32-installer owner/example --key github_pat_...` |
| Leave out the check for a newer installer | `esp32-installer owner/example --no-update-check` |
| Update a library | `esp32-installer owner/example` |
| Uninstall a library | `esp32-installer --uninstall example` |
| Uninstall several, in any order | `esp32-installer --uninstall osal example` |
| Run it when `esp32-installer` is not found | `python -m esp32_installer owner/example` |

### What happens

Take `example`, installed into a project called `app`:

```
app/
  CMakeLists.txt           not touched, for a library in components/ that
                           adds no lines of its own here
  sdkconfig.defaults       one block added, with the symbols the library needs
  main/
    CMakeLists.txt         example added to PRIV_REQUIRES, when main lists its own
                           or the project builds only what main names
  components/example/
    example.h              the library's files, as its installer.yml lists them
    example.c
    CMakeLists.txt         written by the installer: idf_component_register()
    Kconfig                written by the installer: the library's settings
```

ESP-IDF builds every folder of `components/` that has a `CMakeLists.txt` calling `idf_component_register()`, so the installer writes one, from the library's `installer.yml`:

```cmake
idf_component_register(
    SRCS
        "example.c"
    INCLUDE_DIRS
        "."
    REQUIRES
        esp_timer
)
```

`REQUIRES` names the ESP-IDF components the library uses, and the libraries it needs, so their headers are on its include path.

The component is named after its folder, `example`. A component of the project takes the place of one of ESP-IDF's with the same name, so a library called `log` would replace ESP-IDF's own logging. When ESP-IDF is set up in the shell you run from, so `IDF_PATH` is set, the installer checks for that before anything is written, and says to install it into a folder of another name:

```
Requirements
  check   ESP-IDF has a component called log, and this one would take its place
          Install it into a folder of another name, such as --dir components/log_lib.
```

### main

`main` is special in ESP-IDF: as long as its `idf_component_register()` lists no `REQUIRES` or `PRIV_REQUIRES` of its own, it uses every component of the project by itself, and nothing in it changes. Once it lists its own, it sees only those, so the installer adds the library to them:

```cmake
idf_component_register(SRCS "main.c"
                       PRIV_REQUIRES example esp_timer)
```

Into `PRIV_REQUIRES` when main has one, otherwise `REQUIRES`.

A project that builds only what `main` names leaves out every other component, so there `main` gets a list even when it had none. ESP-IDF's own examples are built that way, `hello_world` and `blink` among them, with `idf_build_set_property(MINIMAL_BUILD ON)` in the project's `CMakeLists.txt`, and `set(COMPONENTS ...)` does the same:

```cmake
idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS "." PRIV_REQUIRES example)
```

Without it, `#include "example.h"` in main would not be found. A component of your own that uses the library lists it the same way, by its folder's name.

### sdkconfig.defaults

The Kconfig symbols the library needs go into a block at the end of `sdkconfig.defaults`, created when the project has none:

```
# >>> esp32-installer: example >>>
# Added by esp32-installer, and written again on every install, so set
# example's symbols below this block rather than in it.
CONFIG_FREERTOS_HZ=1000
# <<< esp32-installer: example <<<
```

A library that needs no symbol gets no block. A symbol you already set yourself, on or off, is not set again, since the line read last would quietly undo your choice. It is still written in the block, commented out, with the line that set it:

```
# CONFIG_FREERTOS_HZ=1000  (left out: sdkconfig.defaults sets CONFIG_FREERTOS_HZ=100)
```

ESP-IDF reads `sdkconfig.defaults` only for a symbol your `sdkconfig` does not have yet, and `sdkconfig` is what it builds with. So the installer also reads your `sdkconfig`, and names every symbol it holds at another value:

```
Requirements
  check   sdkconfig has CONFIG_FREERTOS_HZ=100, and example needs 1000
          sdkconfig is what ESP-IDF builds with. Set it in idf.py menuconfig.
```

Set it in `idf.py menuconfig`, or delete `sdkconfig` to start again from `sdkconfig.defaults`. The installer never edits `sdkconfig` itself: ESP-IDF writes that file, and it is yours.

Every file is copied aside before it changes, as `sdkconfig.defaults.20261016-190827.bak` and the like, and the files keep their own line endings. Installing twice changes nothing the second time.

### Settings

A library's settings are Kconfig symbols, in `idf.py menuconfig` under the library's name, from the `Kconfig` the installer wrote into its component. Set one there, or in `sdkconfig.defaults` for a fresh `sdkconfig`:

```
CONFIG_EXAMPLE_PERIOD_MS=250
```

The C code reads it as `CONFIG_EXAMPLE_PERIOD_MS`, from `sdkconfig.h`.

### A folder outside components

Pressed Enter at the folder question, a library goes into `components/<name>`, where ESP-IDF finds it by itself. Anywhere else, given with `--dir` or typed as the answer, ESP-IDF has to be told, so a block goes into your project's `CMakeLists.txt`, above `include(project.cmake)`, which is when ESP-IDF looks:

```cmake
cmake_minimum_required(VERSION 3.16)

# >>> esp32-installer: example >>>
# Added by esp32-installer, since example is not in the components folder,
# where ESP-IDF looks by itself. Delete this block to drop it from the build.
list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/libs/example")
# <<< esp32-installer: example <<<

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(app)
```

### Lines a library adds to your CMakeLists.txt

A library can need lines of CMake in your project's `CMakeLists.txt`, and then it says so in its `installer.yml`: above `include(project.cmake)`, for what ESP-IDF reads as the project starts, or at the end of the file, for what needs the project's own targets. Each group goes between two lines that name it:

```cmake
# >>> esp32-installer: example/defaults >>>
# From example's installer.yml, and written again on every install.
list(APPEND SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_SOURCE_DIR}/example.defaults")
# <<< esp32-installer: example/defaults <<<
```

Every block is written again on every install, so put your own lines outside them. An edit made inside one is noticed on the next install, and the file as it was is in the `.bak`.

### Files that become yours

A library can bring files that belong to your project rather than to the library, such as a `version.txt`, which ESP-IDF reads the project's version from, or a file of settings: a start, made for you to change. Each is created in your project's folder only when it is not there:

```
Files
  written components/example/example.h
  created version.txt  yours from now on
```

From then on it is yours. An update never writes over it, and says so with `kept version.txt  yours`. An uninstall leaves it where it is, with `kept version.txt  yours, not removed`. A library can never put such a file over one the installer manages or reads, `CMakeLists.txt`, `main/CMakeLists.txt`, `sdkconfig` and `sdkconfig.defaults`, nor outside your project's folder.

### Steps a library runs

A library can need something made that no file can carry, such as a key, made fresh for each product. It names a step for that, and once its files are in, the installer shows you exactly what will run, and asks:

```
Run
  make-key     Make the product's key, product.key
               python scripts/make_key.py product.key
               Run it? [Y/n]:
```

Enter runs it, in your project's folder. A Python script runs with the same Python as the installer, so it works the same on every computer. `n` leaves it, and the output says how to run it later. In a script, where nobody can answer, it is not run.

Nothing in a library's `installer.yml` can skip the question. Only you can: `--run make-key` runs that step without asking, `--no-run make-key` leaves it, and `--yes` runs every step and takes the offered answer to every other question, for a script or a build server.

A step that makes a file can name it, and when that file is already in your project the step is skipped without a question, so a second install never makes a second key. A step that names no file and ran before is not asked about again either, until the library changes what it runs. When a step fails, what was installed stays installed, and the installer ends with exit code 1, so a script notices.

### What you see

A first install from GitHub, into a project whose `main` lists its own components:

```
Fetching owner/example ...

example 1.2.0
Driver for the X chip
driver / storage

Requirements
  note    CONFIG_FREERTOS_HZ=1000 goes into sdkconfig.defaults
  note    Needs I2C, 400 kHz
          Set it up in your code, or in idf.py menuconfig.

Folder to install example into [components/example]:

Files
  written components/example/example.h
  written components/example/example.c

Project
  updated ESP-IDF component  The component example: wrote CMakeLists.txt, Kconfig.
  updated sdkconfig.defaults  Added example to sdkconfig.defaults.
          backup: sdkconfig.defaults.20261016-190827.bak
  updated main/CMakeLists.txt  Added example to PRIV_REQUIRES in main/CMakeLists.txt, since main lists the components it uses.
          backup: CMakeLists.txt.20261016-190827.bak

Done. #include "example.h" and you are away.
```

The hardware a library uses is yours to set up, which the installer names but does not do.

### What to install

The argument can be any of these, and you can give several at once:

| You have | You type |
|---|---|
| Nothing yet, and internet | `esp32-installer owner/example` |
| One release of it, a branch, or a commit | `esp32-installer owner/example@v2.0.0` |
| The library's GitHub address | `esp32-installer https://github.com/owner/example` |
| The zip from GitHub's **Download ZIP** | `esp32-installer D:/Downloads/example-main.zip` |
| That zip unpacked, anywhere on disk | `esp32-installer D:/Downloads/example-main` |
| The library's folder, already inside your project | `esp32-installer components/example` |

A bare name with no owner, like `example`, is a NimaLTD library, `nimaltd/example` on GitHub, unless a folder of that name exists where you run it, in which case the folder is used. A path that does not exist is reported as missing rather than looked up on GitHub.

From GitHub, a library comes from its repository's default branch, the one GitHub shows first, whatever the repository calls it. After an `@`, a tag, a branch or a commit takes exactly that instead, and so does a GitHub address ending in `/tree/v2.0.0`. Every file comes from one commit, even when the branch moves on while they download, and the record keeps that commit, so you can always tell what you built with.

### Options

| Option | What it does |
|---|---|
| `--dir libs/example` | The folder of your project to install into, for one library. Asked for when not given, with `components/<name>` as the answer if you just press Enter, or the folder it is already in |
| `--project D:/work/app` | Your project's folder, when you are not running from it |
| `--ref v2.0.0` | A tag, a branch or a commit to take from GitHub, the same as `owner/example@v2.0.0`. When not given, the repository's default branch |
| `--key github_pat_...` | A GitHub token, for a library in a private repository. See [A private repository](#a-private-repository) |
| `--uninstall example` | Take the library out of the project. See [Uninstalling a library](#uninstalling-a-library) |
| `--with littlefs` | Take this part of the library without being asked. Give it once for each part |
| `--without littlefs` | Leave this part out, or take it out of a library already installed |
| `--run make-key` | Run this step of the library without being asked. Give it once for each step. See [Steps a library runs](#steps-a-library-runs) |
| `--no-run make-key` | Leave this step unrun, without being asked |
| `--yes` | Take the answer each question offers, without asking, and run every step. For a script or a build server |
| `--no-update-check` | Do not ask PyPI whether a newer esp32-installer is out |
| `--version` | Show which version of the installer you have, and do nothing else |

### Updating a library

Run the same command again. Every file of the library is replaced, so an update updates, and the component's `CMakeLists.txt` and `Kconfig` are written again from the new `installer.yml`, so a source file the new version adds is built without you editing anything. A file that did not change is left alone, so the build does not configure again for nothing.

What you wrote between `USER CODE BEGIN` and `USER CODE END` in a library's file is kept. Outside those lines, the next install replaces it, and when that would lose something of yours the file is saved beside it first, as a `.bak`.

The record of what is installed, and where, is `.esp32-installer.json` in your project's folder. For each library it also keeps where it came from, down to the commit, the blocks written into your files, and the steps that ran. Keep it in version control with the rest.

### Uninstalling a library

```bash
esp32-installer --uninstall example
```

From your project's folder, or with `--project`. Its block goes from `sdkconfig.defaults`, and its blocks from `CMakeLists.txt` when it has any, its name goes from main's `REQUIRES` and `PRIV_REQUIRES`, and a list left with nothing in it goes too, the files the installer wrote go from its component, and then the library's own files. Installed and then uninstalled, your project's files are back to the byte they were, except the [files that became yours](#files-that-become-yours), which stay.

What was yours is saved before it goes, as a `.bak` beside it: any file of the library you wrote in between its `USER CODE` lines or changed by hand. A file you put in the library's folder yourself is left where it is, and the folder with it.

A setting you set yourself in `sdkconfig.defaults` is your line, and it stays. The symbol it sets went with the library, though, so the installer names every such line, for you to take out:

```
  manual  sdkconfig.defaults  sdkconfig.defaults still sets what came with example, which ESP-IDF no longer knows. Take these lines out:
          CONFIG_EXAMPLE_PERIOD_MS=250
```

Your `sdkconfig` still has the library's settings too. ESP-IDF drops a symbol it no longer knows the next time it writes `sdkconfig`, so there is nothing to do there.

A library another one needs stays, and the installer says which needs it. Name them all, in any order, and each goes after what needs it: `esp32-installer --uninstall osal ee24`. When the library you took out brought another with it that nothing left needs, the last line names it, with the command that takes it out too.

### A library that needs another

You install only the one you want, and what it needs goes in first, each as a component of its own, and the one that needs it lists it in its `REQUIRES`. It comes from the release the library names for it, or else from its default branch. One already in the project at a version that will do is left alone. Everything is fetched before anything is installed, so when a library cannot be had, your project is left as it was.

### Without internet

On a machine that has internet, `pip download esp32-installer` saves one file, the installer, which needs nothing else. Download the library too, from the green **Code** button, **Download ZIP**. Then, on the machine with no internet:

```bash
pip install esp32_installer-1.0.0-py3-none-any.whl
esp32-installer D:/Downloads/example-main.zip
```

If the library needs another, give that zip on the same line. Behind a proxy, set `HTTPS_PROXY` to its address.

### A private repository

A library in a private repository installs the same way, given a GitHub token that can read it. Make one once:

1. Open [github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens) and click **Generate new token**.
2. Give it a name and an expiry. Under **Resource owner**, pick the account or the organisation that owns the repository.
3. Under **Repository access**, choose **Only select repositories** and pick the library's repository.
4. Under **Permissions**, set **Contents** to **Read-only**:
   - Older layout: open **Repository permissions** and change **Contents** from **No access** to **Read-only**.
   - Newer layout: click **+ Add permissions**, tick **Contents**, then set its access to **Read-only**.

   **Metadata** comes with it by itself. Contents is the one that matters: without it the token can see the repository but not read a file of it.
5. Click **Generate token**, and copy it. GitHub shows it only once.

Then give it with `--key`:

```bash
esp32-installer owner/example --key github_pat_...
```

Or put it in `GITHUB_TOKEN` once, and install by name as usual. That keeps it out of your shell's history, where `--key` leaves it:

**Windows, PowerShell:**

```powershell
$env:GITHUB_TOKEN = "github_pat_..."
esp32-installer owner/example
```

**Windows, Command Prompt:**

```bat
set GITHUB_TOKEN=github_pat_...
esp32-installer owner/example
```

**Linux and macOS:**

```bash
export GITHUB_TOKEN=github_pat_...
esp32-installer owner/example
```

`--key` comes first when both are there. `GH_TOKEN` works as well, and if you use the `gh` command, `gh auth token` prints the token you are signed in with. Whichever way it comes, the token is sent to GitHub and nowhere else.

When the token cannot read the library, the installer says which of these it is:

- **It can see the repository, but cannot read its files.** The token has no Contents permission, only Metadata. Edit the token, and its value stays the same, so the command you ran keeps working: open the tokens page, click the token's name, click **Edit**, set Contents to **Read-only** as in step 4, and click **Update** at the bottom of the page. Then run the same command again.
- **It cannot see the repository.** The repository is not in the token's Repository access. Edit the token as above and add it.
- **GitHub did not accept the token.** It has expired, been revoked, or was copied with a character missing. Make a new one.

A repository of an organisation can need one more step: an organisation that asks for fine-grained tokens to be approved shows the token nothing of its repositories until an owner of the organisation approves it, under its settings, **Personal access tokens**, **Pending requests**.

---

## For someone writing a library

Put an `installer.yml` at the root of the repository. Any library can have one, whoever wrote it, and the one file serves esp32-installer and the other installers alike: each reads its own keys and leaves the others' alone.

Every key esp32-installer reads is below, each with what it does. Only `name` and `files` are required; leave out what your library does not need. For a working one to copy, see [esp32-installer-example](https://github.com/nimaltd/esp32-installer-example).

```yaml
name: example                      # the library's name, its component and its folder
description: Driver for the X chip # one line, shown while installing and in menuconfig
repository: https://github.com/owner/example  # where it comes from
license: Apache-2.0                # the licence's SPDX name
version: 1.0.0                     # only when the first header has no @version tag

kind: driver                       # driver, middleware, rtos, protocol, filesystem,
                                   # utility or bsp
category: storage                  # sensor, storage, display, communication, wireless,
                                   # rtos, timing, power, input, math or system
provides: []                       # what it gives other libraries: [rtos] for an RTOS

requires:
  esp32_installer: 2.0.0           # the oldest esp32-installer that reads this file
  libraries:                       # other libraries, installed first when missing
    - osal >= 1.0.0                # no owner means nimaltd; >= the oldest that will do
    - owner/lib                    # anyone else's, as owner/name
    - owner/lib@v1.2.0             # a tag, branch or commit, not its default branch
    - source: owner/other@v2.9.3   # a repository with no installer.yml of its own,
      manifest: manifests/other.yml  # with one this library carries for it
      minimum: 2.9.0               # the oldest version that will do
  kconfig:                         # symbols it needs, set in sdkconfig.defaults
    - FREERTOS_HZ=1000             # SYMBOL=value: y, n, a number, 0x.. or "text"
    - SPI_MASTER_IN_IRAM           # a symbol alone is set to y
  peripherals:                     # hardware it uses, named to the user
    - type: i2c                    # what it is
      count: 1                     # how many
      note: 400 kHz                # how to set it up

install:
  layout: mirror                   # mirror keeps the repository's folders,
                                   # flat (the default) puts every file at the top
  include_dirs: [src]              # include folders, only when the guess is wrong
  defines:                         # given to the library and every component using it,
    - EXAMPLE_FAST                 # NAME or NAME=value

files:
  headers:                         # .h files; the first is the one to #include
    - src/example.h
    - src/port/*.h                 # a wildcard, matched the way a shell would
  sources:                         # .c files, the component's SRCS
    - src/example.c
    - from: src/port/spi.c         # a file that goes somewhere of its own,
      to: port/spi.c               # whatever the layout says

options:                           # parts the user chooses at install
  littlefs:                        # the name typed after --with
    description: LittleFS file system on the flash  # the question asked
    libraries:                     # libraries this part needs, installed first
      - littlefs >= 2.11.0
    files:                         # its files, written like files above
      sources:
        - src/example_lfs.c

extras:                            # copied as they are, never compiled
  - LICENSE.md                     # LICENSE.md and NOTICE are the default,
  - NOTICE                         # so leave this out if that is all
  - README.md

once:                              # the project's own files: made when missing,
                                   # then the user's, never replaced or removed
  - from: project/version.txt      # the file in the repository, to the project's folder
  - from: config/example.defaults  # to: its place in the project, when not its name
    to: example.defaults

run:                               # steps run once the files are in, each asked about first
  - label: make-key                # the name typed after --run
    description: Make the product's key, product.key  # shown with the question
    script: scripts/make_key.py    # Python, run with the installer's own Python,
    args: [product.key]            # or command: [program, arguments], with no shell
    unless: product.key            # skipped when this file is in the project already

esp32:                             # read by esp32-installer only
  requires:                        # ESP-IDF components the code uses: its REQUIRES
    - esp_timer
    - esp_driver_i2c
  cmake:                           # groups of CMake lines, each in a place of its own
    - label: libs                  # names the group, in the lines around it
      where: component             # component (the default), before-project or after-project
      lines:
        - target_link_libraries(${COMPONENT_LIB} PRIVATE m)
  settings:                        # Kconfig symbols for menuconfig, CONFIG_<name> in the code
    - name: EXAMPLE_POLL_CHUNK     # the symbol, best started with the library's name
      type: int                    # bool, int, hex or string
      default: 32                  # required: true or false, a number, 0x.. or text
      range: [1, 32768]            # int and hex only: [smallest, largest]
      prompt: Bytes read per call  # one line, shown in menuconfig
      help: |                      # as many lines as it takes, shown in menuconfig
        A read by polling moves at most this many bytes per call.
```

Keys only the other installers read, such as `requires.stm32_installer`, `requires.hal_modules` and `zephyr`, can stay in the same file. This installer skips them.

Leave `version` out. The installer reads the version from the `@version` tag in the file comment of the first header listed, so it is written in the code and nowhere else.

`requires.esp32_installer` is the oldest esp32-installer that reads the file correctly. It is checked before anything else in the file is read, so an older installer stops with a message saying to update, rather than read the file wrongly. Write it as three numbers, `1.0.0`: unquoted, YAML reads `1.10` as the decimal number `1.1`, and that is refused.

A library that uses anything 2.0.0 brings says `requires.esp32_installer: 2.0.0`: `once` files in the project's folder, `run`, groups under `esp32.cmake`, or a library it needs given with an `@` or a `manifest`. The version also decides where `once` files go. A manifest asking for 2.0.0 or newer puts them in the project's folder, and one asking for less keeps the meaning it was written for, the library's own folder, so a release tagged before 2.0.0 still installs and builds as it did.

### More CMake for a library

A library that needs more than its files and its defines, a library linked in, an option for its compiler, or a line in the project's own `CMakeLists.txt`, lists the lines under `esp32.cmake`, in groups. Each group has a label, a place and its lines:

```yaml
esp32:
  cmake:
    - label: libs                  # where: component, the default
      lines:
        - target_link_libraries(${COMPONENT_LIB} PRIVATE m)
        - target_compile_options(${COMPONENT_LIB} PRIVATE -O2)
    - label: defaults
      where: before-project
      lines:
        - list(APPEND SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_SOURCE_DIR}/example.defaults")
    - label: main
      where: after-project
      lines:
        - idf_component_get_property(main_lib main COMPONENT_LIB)
        - target_compile_definitions(${main_lib} PRIVATE EXAMPLE_IN_MAIN)
```

| `where` | Written into | For |
|---|---|---|
| `component`, the default | the component's `CMakeLists.txt`, after `idf_component_register()`, where `${COMPONENT_LIB}` is its own library | the component itself |
| `before-project` | the project's `CMakeLists.txt`, above `include($ENV{IDF_PATH}/tools/cmake/project.cmake)` | what ESP-IDF reads as the project starts, such as `EXTRA_COMPONENT_DIRS` or `SDKCONFIG_DEFAULTS` |
| `after-project` | the project's `CMakeLists.txt`, at its end | what needs the project's own targets, every component's library among them |

Each group is written between two lines that name it, `# >>> esp32-installer: example/defaults >>>` and its pair, and groups in one place keep the manifest's order. Every install writes them again: a group whose lines changed is updated, one whose `where` changed is moved, and one the manifest no longer has is taken out. A line keeps the spaces it starts with, so the body of an `if()` can be indented.

The label is lower case letters, digits, `_` and `-`, starting with a letter, and two groups of one library, its options' groups counted, never share one. An option brings groups of its own under `options.<name>.esp32.cmake`, written while it is chosen and taken out by the update that turns it off. A line holding a colon, as `message()` often does, goes in quotes, or YAML reads it as a mapping.

One thing about `SDKCONFIG_DEFAULTS`: once it is set, ESP-IDF reads only the files it lists, and no longer `sdkconfig.defaults` by itself. A group that adds a file to it names `sdkconfig.defaults` first, when the project has one and nothing set the list yet:

```cmake
if(NOT SDKCONFIG_DEFAULTS AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/sdkconfig.defaults")
    set(SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_SOURCE_DIR}/sdkconfig.defaults")
endif()
list(APPEND SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_SOURCE_DIR}/example.defaults")
```

A component of headers alone is an interface library, so its lines use `INTERFACE` where one with sources uses `PRIVATE` or `PUBLIC`. The lines run when the user configures the build, the same as a `CMakeLists.txt` the library ships itself would, so they are the library's to answer for.

The form from before 2.0.0, a plain list of lines, still installs: it is one group in `component`, written as it always was.

The user has a place in the component's file too. Its last lines are a `USER CODE` section, empty to start with, and every install keeps what is written in it, the way a configuration header keeps settings:

```cmake
# USER CODE BEGIN EXAMPLE_CMAKE
target_compile_definitions(${COMPONENT_LIB} PRIVATE EXAMPLE_DEBUG=1)
# USER CODE END EXAMPLE_CMAKE
```

On an uninstall, a section with something in it is saved as a `.bak` before the file goes.

### Files of the project's own

A file that belongs to the project rather than to the library goes under `once`: a `version.txt`, which ESP-IDF reads the project's version from, a file of settings for `SDKCONFIG_DEFAULTS`, a partition table. It is created in the project's folder when it is missing, and is the user's from then on: never replaced by an update, never removed by an uninstall.

```yaml
once:
  - from: project/version.txt          # to: the file's own name, version.txt
  - from: config/partitions.csv
    to: partitions.csv
```

`from` is a file of the library's repository, and `to` its place from the project's folder, its own name when left out. A folder inside the project is fine.

Each is checked before anything is written. `to` stays inside the project, names none of the files the installer manages or reads, `CMakeLists.txt`, `main/CMakeLists.txt`, `sdkconfig`, `sdkconfig.defaults` and the record, and does not point into the library's own folder, which every install replaces. Two entries with one `to` are refused. And `from`, like every file a manifest names, stays inside the library: no `..`, no absolute path, no link leading out of it.

What the user changes in their settings belongs in USER CODE sections of the library's own files, or in menuconfig, not in `once`, which is for files outside the library.

### Steps run after the install

Something no file can carry, such as a key made fresh for each product, is made by a step under `run`. It runs once the library's files are in, in the project's folder:

```yaml
run:
  - label: make-key
    description: Make the product's key, product.key
    script: scripts/make_key.py
    args: [product.key]
    unless: product.key
```

- `label` names the step, typed after `--run`, in lower case letters, digits, `_` and `-`.
- `description` is shown with the question.
- `script` is a Python file of the library, run with the installer's own Python, so it works on every computer the installer does. Or `command`, a program and its arguments as a list, `[openssl, rand, -out, product.key, "32"]`, run as it is, with no shell. One of the two, never both.
- `args` are added after either.
- `unless` names a file the step makes, from the project's folder. When it is there, the step is skipped without a question.

The step sees where things are in its environment: `INSTALLER_PROJECT`, the project's folder, `INSTALLER_LIBRARY`, the library's folder in it, `INSTALLER_NAME` and `INSTALLER_VERSION`, the library's, and `INSTALLER`, `esp32-installer`.

The user is always asked, and is shown exactly what will run. Nothing in the manifest can turn that off, only the user, with `--run` or `--yes`. A step with no `unless` that ran before is not asked about again until what it runs changes, so make it safe to run twice anyway. A step that fails leaves the install as it is and ends the run with exit code 1.

### A library it needs

`requires.libraries` lists the libraries yours needs, each installed first when it is missing or older than the version given:

```yaml
requires:
  libraries:
    - osal >= 1.0.0                    # no owner means nimaltd: github.com/nimaltd/osal
    - someone/lib                      # anyone else's, by owner and name
    - someone/lib@v1.2.0               # exactly this tag, branch or commit
    - source: littlefs-project/littlefs@v2.11.0
      manifest: manifests/littlefs.yml # an installer.yml for a repository without one
      minimum: 2.11.0
```

Without an `@`, a library comes from its repository's default branch. The last form installs a library whose repository has no `installer.yml` of its own: yours carries one for it, at the path given, written as if it sat at the root of that repository.

### Settings in the code

ESP-IDF writes every setting into `sdkconfig.h`, so the library's code reads it as a macro once it includes that. One header can serve ESP-IDF and any other project, taking the setting from Kconfig when it is there:

```c
#if __has_include("sdkconfig.h")
#include "sdkconfig.h"
#endif

#ifdef CONFIG_EXAMPLE_POLL_CHUNK
#define EXAMPLE_POLL_CHUNK          CONFIG_EXAMPLE_POLL_CHUNK
#endif

#ifndef EXAMPLE_POLL_CHUNK
#define EXAMPLE_POLL_CHUNK          32U
#endif
```

A `bool` setting that is off is not defined at all, which is how Kconfig does it, so test it with `#ifdef`. A `string` arrives in quotes, ready for C.

Each setting is checked at install, since all of it is written into a Kconfig file: a default of the wrong type, one outside its range, or a name Kconfig would refuse stops the install with the reason, before anything is written.

### A library with its own component

A library that ships a `CMakeLists.txt` of its own, listed under `extras` or `files` so it is installed, knows its build better than the installer does. It is used as it is: nothing is written into its folder, and only the project's own files get what they need.

---

## Running the tests

The shared core, [core-installer](https://github.com/nimaltd/core-installer), is a git submodule in `src/core`, so clone with it:

```bash
git clone --recursive https://github.com/nimaltd/esp32-installer.git
```

In a clone made without `--recursive`, `git submodule update --init` fetches it. Then:

```bash
python test/run_tests.py
```

CI also installs two small libraries from `test/e2e/` into a project with the installer it just built, one of them with everything 2.0.0 brings: files made once and groups of CMake lines in all three places. It builds the project with ESP-IDF for the `linux` target, runs it, and checks what it prints, then builds it again for the esp32, and last takes that library out and checks nothing of it is left in the project's files. So every release is known to build with real ESP-IDF.

---

## Support

I write these tools and libraries in my own time and give them away, because good tools should be easy to get. If this one saved you an afternoon, there are two things that genuinely help:

**Star the repo.** It costs you one click, it helps other engineers find the tool, and it is the main reason I keep going.

**[Buy me a coffee on Ko-fi](https://ko-fi.com/nimaltd).** Any amount is a real motivation to keep writing, documenting and maintaining this work.

[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=for-the-badge&logo=github)](https://github.com/NimaLTD)
[![YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube)](https://youtube.com/@nimaltd)
[![Instagram](https://img.shields.io/badge/Instagram-Follow-purple?style=for-the-badge&logo=instagram)](https://instagram.com/github.nimaltd)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://linkedin.com/in/nimaltd)
[![Email](https://img.shields.io/badge/Email-Contact-red?style=for-the-badge&logo=gmail)](mailto:nima.askari@gmail.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-orange?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/nimaltd)

---

## License

Apache License 2.0. See [LICENSE](https://github.com/nimaltd/esp32-installer/blob/main/LICENSE).

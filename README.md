# Lexdeck

[![CI](https://github.com/mouransad/lexdeck/actions/workflows/ci.yml/badge.svg)](https://github.com/mouransad/lexdeck/actions/workflows/ci.yml)

**A quiet place to practice English vocabulary in your terminal.** Lexdeck is a
local-first flashcard app with a keyboard-friendly full-screen interface and a
scriptable CLI. Each card has content and an optional meaning in English, Persian,
or any other language.

- Your cards stay in a local SQLite database. No account or network connection is
  required.
- Each study session covers every active card once. Choose a fresh random order or
  A–Z order each time.
- Press `y` when you remember a card. Press `n` to reveal its meaning, then continue
  when you are ready.
- Search, edit, and archive cards without deleting their recall history.
- Select cards in the library and export them as PDF, Excel, or UTF-8 text. PDF
  export includes the Unicode fonts it needs.

Lexdeck is available as a standalone download for Linux, macOS, and Windows. The
standalone app includes Python and its dependencies; users do not need to install
Python, uv, or the source code.

## Install a release

Open the [latest release](https://github.com/mouransad/lexdeck/releases/latest) and
download the archive matching your system:

| System | Release asset |
| --- | --- |
| Linux x86-64 | `lexdeck-vVERSION-linux-x86_64.tar.gz` |
| Linux ARM64 | `lexdeck-vVERSION-linux-arm64.tar.gz` |
| Windows x86-64 | `lexdeck-vVERSION-windows-x86_64.zip` |
| macOS Intel | `lexdeck-vVERSION-macos-x86_64.tar.gz` |
| macOS Apple Silicon | `lexdeck-vVERSION-macos-arm64.tar.gz` |

`VERSION` is the release tag, such as `0.1.0` in `lexdeck-v0.1.0-linux-x86_64.tar.gz`.
Each archive contains the `lexdeck` executable (or `lexdeck.exe`), the MIT license,
and the bundled font license. Download `SHA256SUMS.txt` from the same release if you
want to verify the archive before opening it. On Linux or macOS, run
`sha256sum -c SHA256SUMS.txt --ignore-missing` in the download folder. On
Windows, compare `Get-FileHash .\ARCHIVE.zip -Algorithm SHA256` with the
matching entry in `SHA256SUMS.txt`.

### Linux and macOS

From the folder containing the downloaded archive:

```sh
tar -xzf lexdeck-vVERSION-SYSTEM-ARCH.tar.gz
./lexdeck --version
./lexdeck
```

To make `lexdeck` available from any terminal, move it to a directory on your
`PATH`. For example:

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 lexdeck "$HOME/.local/bin/lexdeck"
```

Ensure `$HOME/.local/bin` is on your `PATH`, then open a new terminal and run
`lexdeck`. Replace the archive name with the exact file you downloaded. The
Linux binaries are built on Ubuntu 22.04; older Linux distributions may need the
Python-based source installation below. The macOS downloads are currently
unsigned, so macOS may ask you to approve opening the app.

### Windows

In PowerShell, from the folder containing the downloaded ZIP:

```powershell
Expand-Archive .\lexdeck-vVERSION-windows-x86_64.zip -DestinationPath .\lexdeck
.\lexdeck\lexdeck.exe --version
.\lexdeck\lexdeck.exe
```

For a permanent installation, keep `lexdeck.exe` in a dedicated folder and add
that folder to your user `PATH`. Open a new terminal and run `lexdeck`. Windows
may show a SmartScreen prompt because the executable is not code-signed yet.

A terminal with Unicode support is recommended. A terminal with bidirectional
text support improves Persian display. On Windows, Windows Terminal is a good
choice.

## Use Lexdeck

Run `lexdeck` to open the full-screen interface. `F2` adds a card, `F3` opens the
library, and `F4` starts Study. Outside text fields, `j` and `k` move focus and
`l` opens the focused control. Arrows, Tab, Enter, visible buttons, and a mouse
also work. Press `?` for in-app help; see the [keyboard guide](docs/keyboard.md)
for the complete reference.

The CLI is useful for quick capture and scripts:

```sh
lexdeck add "run into" --meaning "to meet unexpectedly"
lexdeck add "meticulous" --meaning "دقیق و موشکاف"
lexdeck add "in light of"
lexdeck list --query meticulous
lexdeck list --json
lexdeck study
lexdeck stats
```

Use `lexdeck COMMAND --help` for options and [the CLI reference](docs/cli.md)
for output formats. A card ID may be a full UUID or an unambiguous prefix.

## Your data

`lexdeck data-path` prints the exact location of your SQLite database. On Linux,
it is normally `~/.local/share/lexdeck/lexdeck.db`. Close Lexdeck before copying
this file for a backup. Archiving a card keeps its recall history, and a new
study session shows all active cards again regardless of previous reviews.

To use a separate data directory, set `LEXDECK_DATA_DIR` before running Lexdeck:

```sh
LEXDECK_DATA_DIR="$HOME/my-lexdeck-data" lexdeck
```

On Windows PowerShell, use `$env:LEXDECK_DATA_DIR = 'C:\path\to\data'` before
running the app. Export preferences are stored in your platform's configuration
directory; `LEXDECK_CONFIG_DIR` can override that location.

Updating or replacing the executable does not replace your database. Back up the
database before switching to a new version.

## Develop from source

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-packages
uv run --package lexdeck-cli lexdeck
make check
```

The repository is a uv workspace: `packages/core` owns the domain model,
validation, and SQLite access; `apps/cli` owns the Typer CLI and Textual UI. Tests
use temporary databases. See the [development guide](docs/development.md) and
[architecture notes](docs/architecture.md).

## Releases and license

CI checks formatting, lint, types, tests, and package builds. A version tag runs
the same checks, builds and smoke-tests standalone executables on five native
runners, attaches checksums and build attestations, then publishes a GitHub
release. The [release guide](docs/releasing.md) explains the process and its
platform limits.

Lexdeck is available under the [MIT License](LICENSE). The bundled DejaVu fonts
carry their [own license](apps/cli/src/lexdeck_cli/assets/DEJAVU-LICENSE.txt).

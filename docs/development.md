# Development guide

This guide is for human contributors and coding agents working on Lexdeck.
Repository-wide agent rules are in [`AGENTS.md`](../AGENTS.md).

## Prerequisites and setup

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/).
- A terminal with good Unicode support; a BiDi-aware terminal improves Persian
  display.

```bash
uv sync --all-packages
uv run --package lexdeck-cli lexdeck
```

The workspace uses one root `.venv` and one `uv.lock`. Do not install project
dependencies directly with `pip`, and do not edit `uv.lock` manually.

## Common commands

| Command | Purpose |
| --- | --- |
| `make install` | Synchronize all workspace packages. |
| `make run` | Open the TUI. |
| `make format` | Fix import order and format Python. |
| `make lint` | Run Ruff diagnostics. |
| `make typecheck` | Run strict mypy over both source packages. |
| `make test` | Run the complete pytest suite. |
| `make build` | Build source distributions and wheels for all packages. |
| `make check` | Run the complete non-destructive validation pipeline. |

Useful focused checks:

```bash
uv run pytest packages/core/tests/test_service.py -q
uv run pytest apps/cli/tests/test_cli.py -q
uv run pytest apps/cli/tests/test_tui.py -q
uv run ruff check apps/cli/src/lexdeck_cli/tui.py
uv run mypy packages/core/src apps/cli/src
```

## Workspace layout and dependency direction

```text
apps/cli
    └── depends on packages/core

packages/core
    └── depends only on platformdirs and the Python standard library
```

- `packages/core/src/lexdeck_core/models.py`: immutable domain values.
- `service.py`: validation and user workflows; the public interface for every UI.
- `repository.py`: SQL and row mapping.
- `database.py`: connections and forward-only migrations.
- `paths.py`: platform-specific data location and `LEXDECK_DATA_DIR`.
- `apps/cli/src/lexdeck_cli/cli.py`: Typer/Rich adapter.
- `apps/cli/src/lexdeck_cli/tui.py`: Textual screens, bindings, and CSS.
- `apps/cli/src/lexdeck_cli/exports.py`: selected-card PDF, Excel, and text writers.
- `apps/cli/src/lexdeck_cli/printing.py`: default-printer submission for rendered PDFs.
- `apps/cli/src/lexdeck_cli/settings.py`: persistent interface preferences.

Do not import Typer, Rich, or Textual into `packages/core`. A future web app
belongs in `apps/web` and should call `LexdeckService` rather than SQL.

To add a workspace member, create its own `pyproject.toml` under `apps/` or
`packages/`. The root workspace globs discover it. Declare internal dependencies
with a root `[tool.uv.sources]` entry using `{ workspace = true }`, then run
`uv lock` and `uv sync --all-packages`.

## Product invariants

Before changing behavior, read [architecture.md](architecture.md). The most
important constraints are:

- A card exposes content and an optional meaning—no decks or tags.
- Every Study session contains every active card exactly once.
- Study asks for random or sorted order each time, including Review again.
- Recall is binary: `y` advances without revealing; `n` records a miss, reveals,
  and waits for an explicit continuation.
- Starting a new session never hides cards because they were reviewed earlier.
- Archive is non-destructive and preserves recall history.

## Testing strategy

Core tests use a database under pytest's `tmp_path`. CLI tests set
`LEXDECK_DATA_DIR` to an isolated directory. TUI tests use Textual's
`App.run_test()` and `Pilot`; they do not require a real terminal or mouse.

When changing the TUI:

1. Test direct action keys and the focus-based `j`/`k`/`l` path.
2. Prove printable Vim keys remain typable in `Input` and `TextArea` widgets.
3. Test destructive confirmations with Cancel focused first.
4. Include at least one small-terminal case for new or changed layouts.
5. Prefer semantic widget queries and observable results over screenshot-only
   assertions.

Never run automated tests against the default user database. For manual testing:

```bash
LEXDECK_DATA_DIR=/tmp/lexdeck-manual uv run --package lexdeck-cli lexdeck
```

## Database changes

Migrations are numbered, forward-only, and recorded in `schema_migrations`.
Never modify a migration that may already exist in a user's database. Instead:

1. Increase `SCHEMA_VERSION`.
2. Add a new idempotent migration.
3. Apply migrations in order inside `Database.initialize()`.
4. Add a test that starts from the previous schema and verifies both data and
   constraints after migration.

The current schema still has legacy deck, tag, scheduling, and FSRS columns.
They exist only for compatibility and must not leak back into domain models,
commands, or UI. Migration 2 converts legacy 1–4 ratings into binary recall and
removes the old `reviews` table.

## TUI conventions

- Every multi-button action group is vertical.
- Outside editors: `j` is next, `k` is previous, and `l` activates.
- Inside editors, printable keys must always type text.
- Use priority bindings only when they must work over an editor and cannot be
  valid text, such as `F1`–`F4`, `Ctrl+Q`, save shortcuts, or Add-screen `Esc`.
- Keep Arrow, Tab, Shift+Tab, and Enter alternatives.
- Focus the safest action first in destructive confirmations.
- Give every keyboard action a visible route through buttons, footer bindings,
  hints, help, or the command palette.
- Text must wrap. Long views and modals must scroll. Test narrow terminals.
- Persian and other Unicode text must not be normalized or transliterated.

## Keeping documentation synchronized

Treat documentation as part of the feature:

- CLI option or JSON change: update `docs/cli.md`, CLI tests, and README examples.
- TUI binding or focus change: update `HelpModal`, `docs/keyboard.md`, and TUI tests.
- Product invariant or schema change: update `docs/architecture.md` and
  `AGENTS.md`.
- Setup or validation change: update this file, `Makefile`, and `AGENTS.md`.
- User-facing feature change: update the README summary.

Run link/path checks manually when adding documents, and run `make check` before
declaring the change complete.

## Publishing

Release builds and the version-tag workflow are documented in
[releasing.md](releasing.md). The local release build uses a disposable database
for its smoke test.

## Coding-agent compatibility

`AGENTS.md` is the single repository-wide contract. Keep it concise, concrete,
and focused on commands, boundaries, invariants, and checks that apply to most
changes. `CLAUDE.md` and `GEMINI.md` are deliberately thin adapters that import
the canonical file; do not duplicate the rules in them. Add a nested instruction
file only when one subtree genuinely needs different commands or conventions.

This arrangement follows the native project-context conventions documented by
[Codex](https://developers.openai.com/codex/guides/agents-md),
[Claude Code](https://code.claude.com/docs/en/claude-directory), and
[Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md).
An unfamiliar agent should still begin with `AGENTS.md`, because it is plain
Markdown and does not depend on a vendor-specific runtime.

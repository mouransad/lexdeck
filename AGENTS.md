# Lexdeck repository instructions

These instructions apply to the entire repository. They are the canonical
project rules for Codex, Claude Code, Gemini/Antigravity, and other coding
agents. Read `README.md`, `docs/architecture.md`, and `docs/development.md` before
making a broad change.

## Project truth

- Lexdeck is a local-first Python 3.11+ flashcard CLI/TUI for English practice.
- A card exposes only required content and an optional meaning. Meanings may be
  English, Persian, any other Unicode text, or null.
- Do not add or re-expose decks or tags without an explicit product decision.
- There are no accounts, cloud features, due dates, SRS scheduling, or
  Again/Hard/Good/Easy ratings.
- Every Study session includes every active card exactly once. Ask for random or
  sorted A–Z order before every session, including Review again.
- `y` records remembered and advances without revealing the meaning. `n` records
  not remembered, reveals the meaning, and waits for an explicit continuation.
- A later Study session must show cards again regardless of earlier reviews.
- Remove means soft archive. Preserve recall history.

## Repository map and boundaries

- `packages/core/src/lexdeck_core/models.py`: immutable domain values.
- `service.py`: validation and complete workflows; this is the public UI boundary.
- `repository.py`: all SQL and row mapping.
- `database.py`: connections and forward-only migrations.
- `paths.py`: platform data directory and `LEXDECK_DATA_DIR` override.
- `apps/cli/src/lexdeck_cli/cli.py`: Typer/Rich command adapter.
- `apps/cli/src/lexdeck_cli/tui.py`: Textual screens, bindings, and CSS.
- Tests mirror those layers under each package's `tests/` directory.

Dependency direction is `apps/* -> packages/core -> standard library/platformdirs`.
Never import Typer, Rich, Textual, or a future web framework into the core. New
interfaces call `LexdeckService`; they do not query SQLite directly.

## Development commands

Use uv from the workspace root. Do not use `pip` to mutate `.venv`, and never
edit `uv.lock` manually.

```bash
make install       # uv sync --all-packages
make run           # launch the TUI
make format        # fix imports and format
make lint          # Ruff
make typecheck     # strict mypy
make test          # all pytest tests
make build         # all wheels and sdists
make check         # complete validation pipeline
```

Focused tests:

```bash
uv run pytest packages/core/tests/test_service.py -q
uv run pytest apps/cli/tests/test_cli.py -q
uv run pytest apps/cli/tests/test_tui.py -q
```

Before reporting completion, run `make check`. If a check cannot run, report the
exact missing check and reason. Do not hide failures.

## Change workflow

1. Inspect nearby code, tests, and documentation before editing.
2. Preserve unrelated user changes and keep the patch scoped.
3. Put business behavior in the service and persistence mechanics in repository.
4. Add or update tests at the same layer as the change.
5. Update all affected documentation and in-app help in the same change.
6. Run focused checks during iteration, then `make check`.

Prefer the smallest implementation that preserves current boundaries. Do not
add a production dependency when the standard library or an existing dependency
is sufficient. If a dependency is necessary, explain why and use `uv add` for
the correct workspace package.

## Python conventions

- Target Python 3.11 and keep strict mypy clean.
- Ruff owns formatting and import order; line length is 100.
- Use explicit types at public boundaries and immutable dataclasses for domain
  values.
- Keep functions focused and names descriptive. Avoid speculative abstractions.
- Preserve timezone-aware UTC storage and local-time display conversion.
- Convert empty optional meanings to `None`; reject empty card content.

## Database safety

- Automated and manual tests must never use the user's default database. Use
  `tmp_path` or set `LEXDECK_DATA_DIR` to a disposable directory.
- Migrations are numbered and forward-only. Never rewrite a migration that a
  user may already have applied.
- For a schema change: increment `SCHEMA_VERSION`, add an ordered migration, and
  test migration from the previous schema with data preservation.
- Physical legacy fields (`decks`, `deck_id`, `tags_json`, `fsrs_json`, `due_at`)
  are compatibility scaffolding only. Do not expose them through domain models,
  CLI JSON, commands, or TUI.
- Keep foreign keys enabled and archive behavior non-destructive.
- Do not enable WAL without revisiting the documented single-file backup policy
  and concurrency tests.

## CLI rules

- Keep commands scriptable; interactive prompts are optional conveniences.
- Continue accepting full UUIDs and unambiguous active-card prefixes.
- Keep JSON stable and limited to documented domain fields.
- On a command or option change, update `docs/cli.md`, README examples, Typer
  tests, and generated help expectations if present.

## TUI and accessibility rules

- Every multi-button action group is vertical.
- In non-text contexts, `j` focuses next, `k` focuses previous, and `l` opens.
- Keep arrow, Tab, Shift+Tab, Enter, visible-button, and mouse alternatives.
- Printable Vim keys must remain typable in every `Input` and `TextArea`.
- Use priority bindings sparingly: only safe non-printing global navigation,
  quit/save shortcuts, and Add-screen `Esc` currently qualify.
- Dashboard, order choice, study actions, completion, forms, and confirmations
  must all be keyboard-complete.
- Library retains `j/k`, `gg/G`, `Home/End`, `/`, `o`, edit aliases, and guarded
  `dd/Delete` archive.
- Confirmation dialogs focus Cancel first and support `j/k/l`, `y`, and
  `n/Esc/q`.
- Never rely on color alone. Keep strong visible focus.
- Constrain labels/statics to their parent, wrap text, and make long views
  scrollable. Add a narrow-terminal test for layout changes.
- The in-app `HelpModal` and `docs/keyboard.md` are co-owned sources. Update both
  whenever a key, focus rule, or mode changes.

TUI tests use Textual `run_test()` and `Pilot`. Test behavior and focus, not
private implementation. Include tests proving command letters remain text inside
editors.

## Documentation rules

- `README.md`: accurate quick start and current user-visible feature summary.
- `docs/cli.md`: exact command behavior, options, and JSON shapes.
- `docs/keyboard.md`: complete TUI key and focus reference.
- `docs/architecture.md`: boundaries, invariants, schema compatibility, rationale.
- `docs/development.md`: setup, commands, tests, and change procedures.
- `AGENTS.md`: durable instructions that should apply to every coding task.

Do not describe proposed work as implemented. Mark future ideas explicitly.
When implementation and docs disagree, verify behavior in code/tests, fix the
docs, and consider whether a regression test is missing.

## Code review rules

Prioritize findings that could lose user data, touch the real database in tests,
break old database migration, hide reviewed cards from later sessions, reveal a
meaning after successful recall, steal printable keys from editors, create a
mouse-only action, clip text at narrow widths, or reintroduce deck/tag/SRS
concepts. Require tests for each fixed regression.

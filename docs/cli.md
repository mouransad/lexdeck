# Command-line reference

Lexdeck's CLI is implemented with Typer and is designed for both interactive use
and shell automation. Running `lexdeck` without a command opens the TUI.

Use `lexdeck -h` or `lexdeck COMMAND -h` as the executable source of truth for
option spelling. `lexdeck --version` prints the installed version without opening
the database.

## Commands

| Command | Purpose |
| --- | --- |
| `lexdeck` | Open the TUI. |
| `lexdeck tui` | Open the TUI explicitly. |
| `lexdeck add [CONTENT]` | Add a card, prompting in an interactive terminal when content is omitted. |
| `lexdeck list` | List or search active cards. |
| `lexdeck show CARD_ID` | Show one active card by full UUID or unique prefix. |
| `lexdeck edit CARD_ID` | Change content or meaning. |
| `lexdeck remove CARD_ID` | Archive a card after confirmation. |
| `lexdeck study` | Open the TUI directly in Study. |
| `lexdeck stats` | Show card and recall totals. |
| `lexdeck data-path` | Print the active SQLite database path. |

Lexdeck intentionally has no deck or tag commands. A card contains required
content and an optional meaning.

## Add

```bash
lexdeck add "take into account" -m "to consider something"
lexdeck add "meticulous" --meaning "دقیق و موشکاف"
lexdeck add "in light of"
```

Options:

- `-m`, `--meaning TEXT`: optional English or Persian meaning.

When `CONTENT` is omitted in a terminal, Lexdeck asks for content and then an
optional meaning. In a non-interactive process, missing content is an error.
Content is trimmed and must not be empty; an empty meaning is stored as `null`.

## List and search

```bash
lexdeck list
lexdeck list -q consider
lexdeck list --limit 100
lexdeck list --json
```

Options:

- `-q`, `--query TEXT`: case-insensitive substring search across content and
  meaning.
- `-n`, `--limit INTEGER`: maximum rows; defaults to 50 and must be at least 1.
- `--json`: emit a JSON array instead of a Rich table.

The default order is most recently updated first.

## Show

```bash
lexdeck show 2f6a7c1b
lexdeck show 2f6a7c1b --json
```

`CARD_ID` may be a full UUID or an unambiguous prefix. Archived cards are not
returned by normal commands.

## Edit

```bash
lexdeck edit 2f6a7c1b --content "take account of"
lexdeck edit 2f6a7c1b --meaning "با توجه به"
lexdeck edit 2f6a7c1b --clear-meaning
```

Options:

- `-c`, `--content TEXT`: replace the content.
- `-m`, `--meaning TEXT`: replace the meaning.
- `--clear-meaning`: store a null meaning. This takes precedence over
  `--meaning` when both are supplied.

Unspecified fields keep their existing values.

## Remove

```bash
lexdeck remove 2f6a7c1b
lexdeck remove 2f6a7c1b --yes
```

Removal is a soft archive. The card disappears from normal lists and study
sessions, but its review history remains in the database. `-y` / `--yes` skips
the interactive confirmation.

## Study and statistics

`lexdeck study` opens the study screen and asks for random or sorted A–Z order.
Every active card appears once, including cards without meanings. Starting a
later session includes all active cards again.

`lexdeck stats` reports:

- active cards;
- cards with non-empty meanings;
- reviews recorded today;
- successful recalls today; and
- consecutive review-day streak.

Pass `--json` for a machine-readable object.

## JSON formats

Card output from `list --json` and `show --json`:

```json
{
  "id": "a UUID",
  "content": "run into",
  "meaning": "meet unexpectedly",
  "created_at": "timezone-aware ISO 8601",
  "updated_at": "timezone-aware ISO 8601"
}
```

`meaning` may be `null`. Timestamps are serialized in UTC by the core layer.

Statistics output:

```json
{
  "total_cards": 12,
  "complete_cards": 10,
  "reviewed_today": 8,
  "remembered_today": 6,
  "streak_days": 3
}
```

## Data location and isolated profiles

`lexdeck data-path` prints the current database file. Set `LEXDECK_DATA_DIR` to
choose another directory:

```bash
LEXDECK_DATA_DIR=/tmp/lexdeck-demo lexdeck add "temporary"
```

This is the supported way to isolate tests, demos, and portable profiles.

## Shell completion and exit behavior

Typer provides `lexdeck --install-completion` and `lexdeck --show-completion`.
Validation and lookup errors are printed as errors and exit with status 2.

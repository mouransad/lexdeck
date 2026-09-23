# Architecture and product decisions

This document explains what Lexdeck is, where behavior belongs, and which
decisions are intentional. For commands and contribution mechanics, see
[development.md](development.md).

## System overview

```text
Typer CLI ─┐
           ├──> LexdeckService ──> Repository ──> Database ──> SQLite file
Textual TUI┘          │
                     └──> domain models

future local web UI ──> same LexdeckService boundary
```

Dependencies point inward. Interface packages may depend on the core package;
the core package never imports a user-interface framework.

## Layer responsibilities

1. `models.py` defines immutable, UI-independent values: `Card`, `StudyOrder`,
   `RecallResult`, and `Stats`.
2. `service.py` validates input and expresses complete user workflows. It is the
   public application boundary.
3. `repository.py` owns SQL queries and maps SQLite rows to domain values.
4. `database.py` owns connections, pragmas, and forward-only schema migrations.
5. `paths.py` resolves the platform data path and environment override.
6. `apps/cli/cli.py` adapts workflows to Typer and Rich.
7. `apps/cli/tui.py` adapts workflows to Textual screens and keyboard actions.
8. `apps/cli/exports.py` renders selected cards as local PDF, Excel, or text files.
9. `apps/cli/printing.py` submits that PDF output to the operating system printer.
10. `apps/cli/settings.py` persists interface preferences in the platform config path.

The service is deliberately an in-process Python API rather than HTTP. This
keeps the terminal application fast, private, and offline. A future local web
application can reuse it directly and add an HTTP boundary only when process
separation is useful.

## Domain model

A user-visible card has:

- an immutable UUID;
- required, trimmed content;
- an optional, trimmed meaning;
- UTC creation and update timestamps.

There are intentionally no decks or tags. The small model reduces capture
friction and matches the current learning workflow. Meanings may contain English,
Persian, or any other Unicode text, and may remain null.

An active card is one whose `archived_at` database field is null. Archiving is
the only removal workflow and preserves recall history.

## Study model

Every study session is a complete snapshot of all active cards. Before loading
cards, the user chooses:

- **Random:** a fresh in-memory shuffle for that session.
- **Sorted:** content ordered case-insensitively A–Z, with creation time and UUID
  as stable tie-breakers.

Review history never filters a future session. Entering Study or selecting
Review again always makes all active cards available.

The response model is binary:

```text
question shown
├── y / remembered ──> append successful recall ──> next card
└── n / not remembered ──> append failed recall ──> reveal meaning
                                                   └── explicit next ──> next card
```

Successful recall does not reveal the meaning, preserving active recall. A miss
reveals the meaning and waits so the learner can read it. A card without a
meaning still participates and shows an explicit “no meaning” message.

## Storage and migration strategy

SQLite fits a single-user local application: it is transactional, serverless,
Unicode-safe, easy to inspect, and simple to back up. Connections enable foreign
keys and a five-second busy timeout. Migrations are recorded in
`schema_migrations`.

The current logical records are:

- active or archived cards;
- append-only binary `recall_reviews`.

The physical schema contains compatibility fields from an earlier design:
`decks`, `deck_id`, `tags_json`, `fsrs_json`, and `due_at`. New cards use one
internal Default deck and an empty tag array. These fields are not part of the
domain model and must not be exposed by interfaces.

Migration 2 converts legacy four-level review ratings into binary outcomes
(`rating >= 3` becomes remembered) and removes the legacy `reviews` table. Old
columns remain because rebuilding SQLite tables would add migration risk without
providing user value.

Timestamps are stored as timezone-aware ISO 8601 UTC strings. Interfaces convert
display timestamps to the host timezone. WAL is not enabled while Lexdeck is a
single-process application, which keeps a closed-app backup to one file. Revisit
journal mode if a local server introduces concurrent access.

## CLI design

The CLI follows a command/object style suitable for scripts:

- create: `add`;
- read: `list`, `show`, `stats`, `data-path`;
- update: `edit`;
- archive: `remove`;
- interactive workflow: `study` and the default TUI.

Interactive prompting is optional. Automation can supply every mutable field and
request JSON for card lists, individual cards, and statistics. UUID prefixes are
accepted only when they match one active card unambiguously.

## TUI interaction model

The TUI is keyboard-first but not keyboard-exclusive:

- every button group is vertical;
- `j` and `k` move through controls and `l` activates outside editors;
- library browsing adds Vim motions such as `gg`, `G`, `/`, `o`, and guarded
  `dd`;
- arrows, Tab, Shift+Tab, Enter, visible buttons, and mouse input remain
  equivalent routes;
- input widgets retain printable characters, including Vim command letters;
- only safe non-printing global shortcuts have binding priority;
- destructive actions use a confirmation with Cancel focused first;
- unavailable actions are disabled;
- text wraps within containers and long/narrow views scroll;
- color is never the only signal.

The command palette exposes application navigation for users who remember a
command name but not its key. `?` opens an in-app reference that must remain
synchronized with [keyboard.md](keyboard.md).

Library multi-selection is an explicit mode. Entering the mode reveals checkbox
markers and a selected count; movement does not silently change selection. `l`,
`Enter`, `Space`, or a row click toggles only the current card. Select-all is scoped
to visible search results, while selected cards remain stable when a search hides
them. Export, Print, and Archive are unavailable for an empty selection, and leaving
the mode clears the selection so hidden state cannot leak into normal editing.

Bulk archive is a core workflow. The service resolves and deduplicates the requested
active cards before the repository archives them in one SQLite transaction. A stale
or missing card rolls the whole update back, and recall history remains untouched.

Selected-card export remains an interface concern because it is presentation and
filesystem behavior, not a learning-domain workflow. It receives immutable `Card`
values already returned by `LexdeckService` and never queries SQLite. Files are
written to a temporary sibling and atomically moved into place. Existing files need
an explicit replacement confirmation.

- PDF uses an embedded Unicode TrueType font, text shaping, direction-aware text,
  label-free card blocks, comfortable spacing, and page numbers. Its only
  document-level content is the card count.
- Excel uses one focused worksheet with only Content and Meaning, a filterable table,
  direction-aware wrapped cells, adaptive row heights, frozen headings, and print setup.
- Plain text is UTF-8 with numbered CONTENT and MEANING sections.

The export dialog treats file name and location as separate decisions. The default
location is the operating system's Downloads folder, resolved through `platformdirs`.
A user can change one export's folder without changing the default, or save a new
default through Export settings. The setting is an atomically written JSON file in
the platform-specific per-user configuration directory. File names reject path
separators and characters that are invalid on common desktop platforms; the selected
format owns the extension.

This follows the established save-panel model of presenting file name and location
as distinct controls, while keeping a task-specific setting next to the export flow.

Printing deliberately reuses the PDF exporter so previewed, saved, and printed
content cannot drift. On CUPS systems, `lp` receives the generated PDF and copies it
to the print spool; on Windows, the registered PDF application's `print` shell verb
handles the request. Submission runs off the Textual event loop. Print failures keep
the selection active and explain the PDF-export fallback; unsuccessful submissions
also preserve the rendered temporary PDF when possible.

The interaction follows the discoverable checkbox-style selection guidance from
[Microsoft's selection-mode guidance](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/selection-modes),
the navigation/selection separation in the
[WAI-ARIA grid pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/), and
[Textual's row-key model](https://textual.textualize.io/widgets/data_table/).
System printing follows the documented [CUPS `lp` behavior](https://openprinting.github.io/cups/doc/man-lp.html)
and [Windows `ShellExecute` print verb](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew).
The document implementations use
[fpdf2 Unicode shaping](https://py-pdf.github.io/fpdf2/Unicode.html) and
[XlsxWriter tables](https://xlsxwriter.readthedocs.io/working_with_tables.html).
Export locations follow [platformdirs' platform conventions](https://platformdirs.readthedocs.io/en/latest/platforms.html)
and the [XDG configuration-directory specification](https://specifications.freedesktop.org/basedir/0.8/).
The name/location split follows the convention documented by
[Apple's save panel](https://developer.apple.com/documentation/AppKit/NSSavePanel).

These decisions draw on:

- [Textual input and key bindings](https://textual.textualize.io/guide/input/)
- [Textual Input behavior](https://textual.textualize.io/widgets/input/)
- [Textual actions](https://textual.textualize.io/guide/actions/)
- [Textual command palette](https://textual.textualize.io/guide/command_palette/)
- [Vim motion reference](https://vimhelp.org/motion.txt.html)
- [W3C keyboard-interface practices](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
- [WCAG focus-visible guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible)

## Monorepo strategy

The repository is a uv workspace. GitHub releases package the CLI and core
together into standalone, platform-specific terminal executables. The packaged
PDF exporter uses bundled DejaVu fonts so it does not depend on system fonts.
See [releasing.md](releasing.md) for the build and platform limits.

Each app or reusable package owns its own
`pyproject.toml`; the root owns shared developer tooling, workspace membership,
and the single lockfile. This keeps dependency direction explicit while allowing
future interfaces to share one tested core.

## Current non-goals

The following are not implemented and must not be implied by user documentation:

- accounts, synchronization, or cloud storage;
- decks or tags;
- spaced-repetition scheduling or due-card filtering;
- Again/Hard/Good/Easy ratings;
- restore/archive management UI;
- bulk import or a versioned full-library interchange format;
- pronunciation, examples, media, or card templates;
- a browser front end or HTTP API.

## Planned extension points

Potential future work, not commitments:

- an `apps/web` workspace member for a localhost-only interface;
- versioned full-library import/export;
- an archive recovery view;
- examples or pronunciation fields added through explicit migrations;
- richer binary-recall analytics;
- snapshot or end-to-end tests across more terminal sizes.

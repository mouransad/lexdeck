# Keyboard and TUI reference

Lexdeck is fully operable without a mouse. Its interaction model combines
conventional focus keys with a small Vim-style normal mode.

## Interaction rules

- Every group of buttons is laid out vertically.
- In navigation contexts, `j` moves down, `k` moves up, and `l` opens the
  focused control.
- Arrow keys provide equivalent movement, and `Enter` activates a button.
- `Tab` and `Shift+Tab` traverse focus conventionally.
- Printable keys are never stolen from `Input` or `TextArea` widgets. Typing
  `j`, `k`, `l`, `dd`, or `gg` in a field inserts those characters.
- Only safe non-printing keys use priority bindings over text editors:
  `F1`–`F4`, `Ctrl+Q`, save shortcuts, and Add-screen `Esc`.
- `?` opens the in-app reference. The footer shows primary contextual actions.

## Global keys

| Key | Action |
| --- | --- |
| `F1` | Dashboard, including while typing. |
| `F2` | Add, including while typing. |
| `F3` | Library, including while typing. |
| `F4` | Study, including while typing. |
| `Ctrl+P` | Open Textual's fuzzy command palette with Lexdeck commands. |
| `?` | Open Lexdeck keyboard help outside text fields. |
| `Ctrl+Q` | Quit from any context. |
| `d`, `a`, `s`, `q` | Dashboard, Add, Study, or quit outside text fields unless the current screen assigns that key a more specific action. |
| `j`, `k`, `l` | Next control, previous control, or open outside text fields. |
| `Tab`, `Shift+Tab` | Next or previous focusable control. |
| `Enter` | Activate the focused button. |

The command palette includes Dashboard, Add card, Browse library, Study, and
Keyboard shortcuts in addition to Textual's system commands.

## Dashboard

| Key | Action |
| --- | --- |
| `j` / `Down` | Focus the next action. |
| `k` / `Up` | Focus the previous action. |
| `l` / `Right` / `Enter` | Open the focused action. |
| `o` | Add a card. |
| `r` | Start review. |
| `b` | Browse the library. |

## Add

| Key | Action |
| --- | --- |
| `Ctrl+S` / `Ctrl+Enter` | Save, clear content and meaning, then focus content for the next card. |
| `Alt+S` | Save and open the library. |
| `Esc` | Return to Dashboard. If either field contains unsaved text, open a discard confirmation first. |

Use `Tab` and `Shift+Tab` to move between content, meaning, and the vertical
action buttons. Normal-mode letters remain text while an editor has focus.

## Library

| Key | Action |
| --- | --- |
| `j` / `Down` | Highlight the next card and focus the table. |
| `k` / `Up` | Highlight the previous card and focus the table. |
| `gg` / `Home` | Jump to the first card. |
| `G` / `End` | Jump to the last card. |
| `/` / `Ctrl+F` | Focus search and select the current query. |
| `Esc` | Return from search to the table; from the table, open Dashboard. |
| `h` | Open Dashboard when the table has focus. It inserts text in search. |
| `Enter` / `e` / `i` / `l` | Edit the selected card. |
| `o` | Open Add. |
| `dd` / `Delete` | Open archive confirmation for the selected card. |
| `v` | Enter selection mode. |

The `gg` and `dd` Vim sequences use a one-second sequence window. `Home`, `End`,
and `Delete` are timing-independent alternatives. Search covers content and
meaning. Up and Down intentionally leave search and move through result rows.

The detail panel and action buttons sit beside the table; actions are stacked
vertically. Unavailable Edit and Archive controls are disabled.

### Library selection mode

Selection mode shows a checkbox marker on every visible row and keeps navigation
separate from selection. Search remains available, and selections remain selected
when a query hides them. “Select all” applies only to the currently visible search
results.

| Key | Action |
| --- | --- |
| `j` / `Down` | Highlight the next card without changing selection. |
| `k` / `Up` | Highlight the previous card without changing selection. |
| `l` / `Enter` / `Space` | Toggle the highlighted card. Clicking a row does the same. |
| `Ctrl+A` | Select every visible card. |
| `c` | Clear the complete selection, including cards hidden by search. |
| `Ctrl+E` | Open the export dialog. Disabled until at least one card is selected. |
| `p` | Confirm, then print the selected cards using the polished PDF layout and default printer. |
| `dd` / `Delete` | Confirm, then archive the complete selection in one transaction. |
| `Esc` | Return from search to the table; from the table, leave selection mode and clear it. |

The sidebar always shows the selected count and vertical buttons for Export, Print,
Archive, Select all visible, Clear selection, and Done. Export keeps selection order
and offers PDF (`.pdf`), Excel (`.xlsx`), and UTF-8 plain text (`.txt`). The file name
and export folder are separate fields. The folder defaults to the platform Downloads
directory, or to the saved export-folder setting. The selected format supplies the
extension automatically. Replacing an existing file requires explicit confirmation.

Print and Archive each require a count-aware confirmation with Cancel focused first.
Print renders the same PDF used by export and submits it to the system default
printer. If no print service is available, Lexdeck recommends exporting a PDF and
printing it from a viewer. Archive is a soft archive: all selected cards disappear
together, while their recall history remains stored.

The export dialog initially focuses the format selector. While it is focused, use
`j` / `k` to move through PDF, Excel, and plain text, then `l` to choose the
highlighted format. Arrows also move and `Enter` or `Space` also choose. Use `Tab` or
`Shift+Tab` to move through controls. `Alt+J` and `Alt+K` move to the next or previous
control even while an input is active; ordinary `j`, `k`, and `l` remain typable in
inputs. `Enter` advances from the file-name field and creates the export from the
folder field. `Ctrl+E` or `Ctrl+S` creates from anywhere, and `Esc` cancels.

“Change default export folder” opens Export settings. It is also available from the
command palette. `Ctrl+S` saves the setting, “Use Downloads” restores the platform
default in the field, and `Esc` cancels. Settings are stored in Lexdeck's per-user
configuration directory, separate from the database and exported files.

## Study-order chooser

| Key | Action |
| --- | --- |
| `j` / `Down` | Next choice. |
| `k` / `Up` | Previous choice. |
| `l` / `Right` / `Enter` | Choose the focused option. |
| `r` | Choose a fresh random order immediately. |
| `s` | Choose sorted A–Z immediately. |
| `Esc` / `q` | Cancel and return to Dashboard. |

## Study

Before the meaning is revealed:

| Key | Action |
| --- | --- |
| `y` | Record remembered and advance without showing the meaning. |
| `n` | Record not remembered and reveal the meaning. |
| `j`, `k`, `l` | Move between and activate the vertically stacked Yes/No buttons. |
| `Esc` / `q` | Return to Dashboard. |

After `n`, press `Enter`, `Space`, or activate the Next button to continue. A
card without a meaning shows an explicit message instead of a blank area.

At session completion, `r` opens the order chooser and starts another complete
review. `j`, `k`, and `l` operate the Review again and Back to dashboard buttons.

## Edit dialog

| Key | Action |
| --- | --- |
| `Ctrl+S` | Save changes. |
| `Esc` | Cancel. |
| `Tab` / `Shift+Tab` | Move between editors and vertical action buttons. |

## Archive and discard confirmations

Confirmations initially focus the safer Cancel option.

| Key | Action |
| --- | --- |
| `j` / `Down` | Next action. |
| `k` / `Up` | Previous action. |
| `l` / `Right` / `Enter` | Choose the focused action. |
| `y` | Confirm immediately. |
| `n` / `Esc` / `q` | Cancel immediately. |

## Help and responsive behavior

Press `Esc`, `?`, or `q` to close keyboard help. Help and other long modals are
scrollable. Labels and descriptions wrap within their containers, card details
can scroll, and study content grows instead of being clipped on narrow terminals.

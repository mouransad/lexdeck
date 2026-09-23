"""Textual interface for fast capture, browsing, and focused recall practice."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import ClassVar, cast

from lexdeck_core import Card, LexdeckService, StudyOrder
from lexdeck_core.repository import CardNotFoundError
from lexdeck_core.service import ValidationError
from textual import events, on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    TextArea,
)

from .exports import (
    ExportError,
    ExportFormat,
    export_cards,
    normalize_export_filename,
    normalize_export_path,
)
from .printing import PrintError, print_cards
from .settings import (
    LexdeckSettings,
    SettingsError,
    SettingsStore,
    normalize_export_directory,
)

BindingSpec = Binding | tuple[str, str] | tuple[str, str, str]


class LexdeckScreen(Screen[None]):
    @property
    def service(self) -> LexdeckService:
        return cast("LexdeckApp", self.app).service

    def shell(self, title: str, subtitle: str, *children: object) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="page"):
            yield Label(title, classes="page-title")
            yield Label(subtitle, classes="page-subtitle")
            for child in children:
                yield cast(Static, child)
        yield Footer()


class DashboardScreen(LexdeckScreen):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("j,down", "focus_next_action", "Next action", show=False),
        Binding("k,up", "focus_previous_action", "Previous action", show=False),
        Binding("l,right", "open_focused_action", "Open", show=False),
        Binding("o", "open_add", "New card"),
        Binding("r", "open_study", "Review"),
        Binding("b", "open_library", "Library"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="page"):
            yield Label("Build your English, one recall at a time.", classes="hero-title")
            yield Label(
                "Capture useful language, then practise only what your memory needs.",
                classes="page-subtitle",
            )
            yield Label(
                "What would you like to do?  [dim]J/K move · L open[/dim]",
                classes="section-title",
            )
            with Vertical(classes="action-menu"):
                yield Button("＋ Add cards", id="go-add", variant="primary")
                yield Button("▶ Review cards", id="go-study", variant="success")
                yield Button("≡ Browse library", id="go-library")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#go-add", Button).focus()

    def action_focus_next_action(self) -> None:
        self.focus_next(".action-menu Button")

    def action_focus_previous_action(self) -> None:
        self.focus_previous(".action-menu Button")

    def action_open_focused_action(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()

    def action_open_add(self) -> None:
        self.app.switch_screen("add")

    def action_open_study(self) -> None:
        cast("LexdeckApp", self.app).action_study()

    def action_open_library(self) -> None:
        self.app.switch_screen("library")

    @on(Button.Pressed)
    def navigate(self, event: Button.Pressed) -> None:
        destinations = {
            "go-add": "add",
            "go-study": "study",
            "go-library": "library",
        }
        if destination := destinations.get(event.button.id or ""):
            if destination == "study":
                cast("LexdeckApp", self.app).action_study()
            else:
                self.app.switch_screen(destination)


class AddScreen(LexdeckScreen):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("ctrl+s", "save", "Save card", priority=True),
        Binding("ctrl+enter", "save", "Save card", show=False, priority=True),
        Binding("alt+s", "save_to_library", "Save & library", priority=True),
        Binding("escape", "leave", "Back", priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="page"):
            yield Label("Add a flashcard", classes="page-title")
            yield Label(
                "Add the content and an optional English or Persian meaning.",
                classes="page-subtitle",
            )
            with Container(classes="form-card"):
                yield Label("CONTENT  [dim]required[/dim]", classes="field-label")
                yield TextArea(id="content", language=None)
                yield Label(
                    "MEANING  [dim]optional · English or Persian[/dim]",
                    classes="field-label",
                )
                yield TextArea(id="meaning", language=None)
                with Vertical(classes="vertical-actions"):
                    yield Button("Save & add another", id="save", variant="primary")
                    yield Button("Save & view library", id="save-library")
            yield Static("Ctrl+S saves without leaving this screen.", classes="shortcut-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#content", TextArea).focus()

    @on(Button.Pressed, "#save")
    def save_another(self) -> None:
        self._save(stay=True)

    @on(Button.Pressed, "#save-library")
    def save_library(self) -> None:
        if self._save(stay=False):
            self.app.switch_screen("library")

    def action_save(self) -> None:
        self._save(stay=True)

    def action_save_to_library(self) -> None:
        if self._save(stay=False):
            self.app.switch_screen("library")

    def action_leave(self) -> None:
        content = self.query_one("#content", TextArea).text.strip()
        meaning = self.query_one("#meaning", TextArea).text.strip()
        if not content and not meaning:
            self.app.switch_screen("dashboard")
            return
        self.app.push_screen(
            ConfirmModal(
                "Discard this unfinished card?",
                detail="Your unsaved content and meaning will be lost.",
                confirm_label="Discard",
            ),
            self._leave_if_confirmed,
        )

    def _leave_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.app.switch_screen("dashboard")

    def _save(self, *, stay: bool) -> bool:
        content = self.query_one("#content", TextArea)
        meaning = self.query_one("#meaning", TextArea)
        try:
            card = self.service.add_card(
                content.text,
                meaning.text,
            )
        except ValidationError as error:
            self.app.notify(str(error), title="Could not save", severity="error")
            content.focus()
            return False
        self.app.notify(f"Added “{_one_line(card.prompt, 36)}”", title="Card saved")
        if stay:
            content.load_text("")
            meaning.load_text("")
            content.focus()
        return True


class LibraryScreen(LexdeckScreen):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("enter,l", "open_or_toggle", "Open / select", show=False),
        Binding("space", "toggle_selected", "Select", show=False),
        Binding("e,i", "edit_selected", "Edit"),
        Binding("delete", "delete_selected", "Archive"),
        Binding("ctrl+f,/", "focus_search", "Search"),
        Binding("up", "move_up", "Previous card", show=False, priority=True),
        Binding("down", "move_down", "Next card", show=False, priority=True),
        Binding("j", "move_down", "Next card", show=False),
        Binding("k", "move_up", "Previous card", show=False),
        Binding("home", "first_card", "First card", show=False),
        Binding("end", "last_card", "Last card", show=False),
        Binding("G,shift+g", "last_card", "Last card", show=False),
        Binding("g", "vim_top_prefix", "First card", show=False),
        Binding("d", "vim_archive_prefix", "Archive", show=False),
        Binding("o", "new_card", "New card"),
        Binding("v", "enter_selection", "Select cards"),
        Binding("ctrl+e", "export_selected", "Export"),
        Binding("p", "print_selected", "Print"),
        Binding("ctrl+a", "select_all", "Select all", show=False),
        Binding("c", "clear_selection", "Clear selection", show=False),
        Binding("escape,h", "leave_or_clear_search", "Back", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, Card] = {}
        self.selected_cards: dict[str, Card] = {}
        self.selection_mode = False
        self._pending_vim_key: str | None = None
        self._pending_vim_at = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="library-page"):
            yield Label("Your library", classes="page-title")
            yield Label(
                "Navigate with J/K, jump with gg/G, search with /, and edit with Enter.",
                classes="page-subtitle",
                id="library-subtitle",
            )
            yield Input(placeholder="Search content or meaning…", id="search")
            with Horizontal(id="library-content"):
                yield DataTable(id="card-table", cursor_type="row", zebra_stripes=True)
                with VerticalScroll(id="library-sidebar"):
                    yield Static("Select a card to see its details.", id="card-detail")
                    with Vertical(classes="vertical-actions", id="library-actions"):
                        yield Button("＋ New", id="new-card", variant="primary")
                        yield Button("Edit", id="edit-card")
                        yield Button("Archive", id="delete-card", variant="error")
                        yield Button("Select cards  [V]", id="select-cards")
                    with Vertical(classes="vertical-actions", id="selection-actions"):
                        yield Button(
                            "Export selected  [Ctrl+E]",
                            id="export-selected",
                            variant="primary",
                        )
                        yield Button("Print selected  [P]", id="print-selected")
                        yield Button(
                            "Archive selected  [Delete]",
                            id="archive-selected",
                            variant="error",
                        )
                        yield Button("Select all visible  [Ctrl+A]", id="select-all")
                        yield Button("Clear selection  [C]", id="clear-selection")
                        yield Button("Done", id="finish-selection")
            yield Label("0 cards", id="result-count", classes="shortcut-hint")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#card-table", DataTable)
        table.add_column("", key="selected", width=3)
        table.add_column("Content", key="content")
        table.add_column("Meaning", key="meaning")
        table.add_column("Updated", key="updated")
        self.load_cards()
        table.focus()

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        self.load_cards()

    @on(Input.Changed, "#search")
    def search_changed(self, event: Input.Changed) -> None:
        self.load_cards(event.value)

    def load_cards(self, query: str | None = None) -> None:
        if not self.is_mounted:
            return
        cards = self.service.list_cards(query=query or None, limit=500)
        self.cards = {card.id: card for card in cards}
        for card in cards:
            if card.id in self.selected_cards:
                self.selected_cards[card.id] = card
        table = self.query_one("#card-table", DataTable)
        table.clear()
        for card in cards:
            table.add_row(
                self._selection_marker(card.id),
                _one_line(card.prompt, 36),
                _one_line(card.meaning or "—", 34),
                card.updated_at.astimezone().strftime("%b %d"),
                key=card.id,
            )
        self._refresh_selection_ui()
        if cards:
            self._show_detail(cards[0])
        else:
            self.query_one("#card-detail", Static).update(
                "[bold]No cards found[/bold]\n\nTry another search or add a new card."
            )

    @on(DataTable.RowHighlighted, "#card-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if card := self.cards.get(str(event.row_key.value)):
            self._show_detail(card)

    @on(DataTable.RowSelected, "#card-table")
    def row_selected(self, _: DataTable.RowSelected) -> None:
        self.action_open_or_toggle()

    def _show_detail(self, card: Card) -> None:
        selection_status = ""
        if self.selection_mode:
            selection_status = (
                "[green][x] SELECTED[/green]\n\n"
                if card.id in self.selected_cards
                else "[dim][ ] NOT SELECTED[/dim]\n\n"
            )
        self.query_one("#card-detail", Static).update(
            f"{selection_status}[dim]{card.id[:8]}[/dim]\n\n"
            f"[bold]{card.prompt}[/bold]\n\n"
            f"{card.meaning or '[dim]No meaning yet[/dim]'}\n\n"
            f"[dim]Updated[/dim]  {card.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
        )

    def selected_card(self) -> Card | None:
        table = self.query_one("#card-table", DataTable)
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        return self.cards.get(str(cell_key.row_key.value))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "edit_selected":
            return not self.selection_mode and self.selected_card() is not None
        if action in {"delete_selected", "vim_archive_prefix"}:
            if self.selection_mode:
                return bool(self.selected_cards)
            return self.selected_card() is not None
        if action == "enter_selection":
            return not self.selection_mode and self.selected_card() is not None
        if action == "open_or_toggle":
            return self.selected_card() is not None
        if action == "toggle_selected":
            return self.selection_mode and self.selected_card() is not None
        if action in {"export_selected", "print_selected"}:
            return self.selection_mode and bool(self.selected_cards)
        if action == "select_all":
            return self.selection_mode and bool(self.cards)
        if action == "clear_selection":
            return self.selection_mode and bool(self.selected_cards)
        return True

    def action_focus_search(self) -> None:
        search = self.query_one("#search", Input)
        search.focus()
        search.action_select_all()

    def action_move_up(self) -> None:
        table = self.query_one("#card-table", DataTable)
        table.focus()
        table.action_cursor_up()

    def action_move_down(self) -> None:
        table = self.query_one("#card-table", DataTable)
        table.focus()
        table.action_cursor_down()

    def action_first_card(self) -> None:
        table = self.query_one("#card-table", DataTable)
        table.focus()
        table.action_scroll_top()

    def action_last_card(self) -> None:
        table = self.query_one("#card-table", DataTable)
        table.focus()
        table.action_scroll_bottom()

    def action_vim_top_prefix(self) -> None:
        if self._complete_vim_sequence("g"):
            self.action_first_card()
        else:
            self.app.notify("Press g again to jump to the first card.", title="g…")

    def action_vim_archive_prefix(self) -> None:
        if self._complete_vim_sequence("d"):
            self.action_delete_selected()
        else:
            target = "selected cards" if self.selection_mode else "the selected card"
            self.app.notify(f"Press d again to archive {target}.", title="d…")

    def _complete_vim_sequence(self, key: str) -> bool:
        now = monotonic()
        complete = self._pending_vim_key == key and now - self._pending_vim_at <= 1.0
        self._pending_vim_key = None if complete else key
        self._pending_vim_at = now
        return complete

    def action_new_card(self) -> None:
        self.app.switch_screen("add")

    def action_leave_or_clear_search(self) -> None:
        search = self.query_one("#search", Input)
        table = self.query_one("#card-table", DataTable)
        if search.has_focus:
            table.focus()
        elif self.selection_mode:
            self._leave_selection_mode()
        else:
            self.app.switch_screen("dashboard")

    def action_open_or_toggle(self) -> None:
        if self.selection_mode:
            self._toggle_current_card()
        else:
            self.action_edit_selected()

    def action_toggle_selected(self) -> None:
        if self.selection_mode:
            self._toggle_current_card()

    def action_enter_selection(self) -> None:
        if self.selected_card() is None:
            return
        self.selection_mode = True
        self._pending_vim_key = None
        self._refresh_table_markers()
        self._refresh_selection_ui()
        if current_card := self.selected_card():
            self._show_detail(current_card)
        self.query_one("#card-table", DataTable).focus()

    def action_select_all(self) -> None:
        if not self.selection_mode:
            return
        for card in self.cards.values():
            self.selected_cards[card.id] = card
        self._refresh_table_markers()
        self._refresh_selection_ui()
        if current_card := self.selected_card():
            self._show_detail(current_card)

    def action_clear_selection(self) -> None:
        if not self.selection_mode:
            return
        self.selected_cards.clear()
        self._refresh_table_markers()
        self._refresh_selection_ui()
        if current_card := self.selected_card():
            self._show_detail(current_card)

    def action_export_selected(self) -> None:
        if not self.selection_mode or not self.selected_cards:
            return
        app = cast("LexdeckApp", self.app)
        self.app.push_screen(
            ExportModal(len(self.selected_cards), app.export_directory()),
            self._export_requested,
        )

    def action_print_selected(self) -> None:
        if not self.selection_mode or not self.selected_cards:
            return
        count = len(self.selected_cards)
        noun = "card" if count == 1 else "cards"
        self.app.push_screen(
            ConfirmModal(
                f"Print {count} selected {noun}?",
                detail=(
                    "Lexdeck will create a PDF and send it to your system's default printer "
                    "using its current settings."
                ),
                confirm_label="Print",
                destructive=False,
            ),
            self._print_if_confirmed,
        )

    def _print_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self._submit_print_job(tuple(self.selected_cards.values()))

    @work(thread=True, exclusive=True, group="print-selected")
    def _submit_print_job(self, cards: tuple[Card, ...]) -> None:
        try:
            message = print_cards(cards)
        except PrintError as error:
            self.app.call_from_thread(self._print_failed, str(error))
        else:
            self.app.call_from_thread(self._print_succeeded, message)

    def _print_failed(self, message: str) -> None:
        self.app.notify(message, title="Print failed", severity="error")

    def _print_succeeded(self, message: str) -> None:
        self.app.notify(message, title="Print submitted")
        self._leave_selection_mode()

    def _toggle_current_card(self) -> None:
        card = self.selected_card()
        if card is None:
            return
        if card.id in self.selected_cards:
            del self.selected_cards[card.id]
        else:
            self.selected_cards[card.id] = card
        self._refresh_table_markers()
        self._refresh_selection_ui()
        self._show_detail(card)

    def _selection_marker(self, card_id: str) -> str:
        if not self.selection_mode:
            return ""
        return "[x]" if card_id in self.selected_cards else "[ ]"

    def _refresh_table_markers(self) -> None:
        table = self.query_one("#card-table", DataTable)
        for card_id in self.cards:
            table.update_cell(
                card_id,
                "selected",
                self._selection_marker(card_id),
                update_width=False,
            )

    def _refresh_selection_ui(self) -> None:
        normal_actions = self.query_one("#library-actions", Vertical)
        selection_actions = self.query_one("#selection-actions", Vertical)
        normal_actions.styles.display = "none" if self.selection_mode else "block"
        selection_actions.styles.display = "block" if self.selection_mode else "none"

        visible_count = len(self.cards)
        selected_count = len(self.selected_cards)
        if self.selection_mode:
            self.query_one("#library-subtitle", Label).update(
                "Selection mode: J/K move · L toggle · Ctrl+E export · P print · "
                "Delete archive · Esc finish."
            )
            result = (
                f"{selected_count} selected · {visible_count} visible"
                if visible_count
                else f"{selected_count} selected · no visible results"
            )
        else:
            self.query_one("#library-subtitle", Label).update(
                "Navigate with J/K, jump with gg/G, search with /, and edit with Enter."
            )
            result = f"{visible_count} card{'s' if visible_count != 1 else ''}"
        self.query_one("#result-count", Label).update(result)

        has_visible_card = bool(self.cards)
        self.query_one("#edit-card", Button).disabled = not has_visible_card
        self.query_one("#delete-card", Button).disabled = not has_visible_card
        self.query_one("#select-cards", Button).disabled = not has_visible_card
        self.query_one("#export-selected", Button).disabled = not self.selected_cards
        self.query_one("#print-selected", Button).disabled = not self.selected_cards
        self.query_one("#archive-selected", Button).disabled = not self.selected_cards
        self.query_one("#select-all", Button).disabled = not has_visible_card
        self.query_one("#clear-selection", Button).disabled = not self.selected_cards

    def _leave_selection_mode(self) -> None:
        self.selection_mode = False
        self.selected_cards.clear()
        self._refresh_table_markers()
        self._refresh_selection_ui()
        if card := self.selected_card():
            self._show_detail(card)
        self.query_one("#card-table", DataTable).focus()

    def _export_requested(self, request: ExportRequest | None) -> None:
        if request is None:
            return
        destination = normalize_export_path(request.path, request.export_format)
        normalized_request = ExportRequest(request.export_format, str(destination))
        if destination.exists():
            self.app.push_screen(
                ConfirmModal(
                    f"Replace “{destination.name}”?",
                    detail="The existing file will be replaced with this export.",
                    confirm_label="Replace file",
                ),
                lambda confirmed: self._perform_export(normalized_request) if confirmed else None,
            )
            return
        self._perform_export(normalized_request)

    def _perform_export(self, request: ExportRequest) -> None:
        try:
            destination = export_cards(
                list(self.selected_cards.values()),
                request.path,
                request.export_format,
            )
        except ExportError as error:
            self.app.notify(str(error), title="Export failed", severity="error")
            return
        self.app.notify(str(destination), title=f"{request.export_format.display_name} created")
        self._leave_selection_mode()

    def action_edit_selected(self) -> None:
        card = self.selected_card()
        if card:
            self.app.push_screen(EditCardModal(card), self._apply_edit)

    def _apply_edit(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            self.service.edit_card(
                values["id"],
                prompt=values["content"],
                meaning=values["meaning"],
            )
        except (ValidationError, CardNotFoundError) as error:
            self.app.notify(str(error), title="Could not update", severity="error")
            return
        self.app.notify("Card updated", title="Saved")
        self.load_cards(self.query_one("#search", Input).value)

    def action_delete_selected(self) -> None:
        if self.selection_mode:
            count = len(self.selected_cards)
            if count == 0:
                return
            noun = "card" if count == 1 else "cards"
            self.app.push_screen(
                ConfirmModal(
                    f"Archive {count} selected {noun}?",
                    detail=(
                        "They will leave your library together, but their recall history "
                        "will be preserved."
                    ),
                    confirm_label=f"Archive {count} {noun}",
                ),
                self._archive_selected,
            )
            return
        card = self.selected_card()
        if card:
            self.app.push_screen(
                ConfirmModal(f"Archive “{_one_line(card.prompt, 42)}”?"),
                lambda confirmed: self._archive(card) if confirmed else None,
            )

    def _archive(self, card: Card) -> None:
        try:
            self.service.remove_card(card.id)
        except CardNotFoundError as error:
            self.app.notify(str(error), severity="error")
            return
        self.app.notify("Card archived", title="Library")
        self.load_cards(self.query_one("#search", Input).value)

    def _archive_selected(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        cards = tuple(self.selected_cards.values())
        try:
            archived = self.service.remove_cards(card.id for card in cards)
        except CardNotFoundError as error:
            self.app.notify(str(error), title="Could not archive selection", severity="error")
            self._leave_selection_mode()
            self.load_cards(self.query_one("#search", Input).value)
            return
        self.selection_mode = False
        self.selected_cards.clear()
        self.app.notify(
            f"{len(archived)} card{'s' if len(archived) != 1 else ''} archived",
            title="Library",
        )
        self.load_cards(self.query_one("#search", Input).value)
        self.query_one("#card-table", DataTable).focus()

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-card":
            self.app.switch_screen("add")
        elif event.button.id == "edit-card":
            self.action_edit_selected()
        elif event.button.id == "delete-card":
            self.action_delete_selected()
        elif event.button.id == "select-cards":
            self.action_enter_selection()
        elif event.button.id == "export-selected":
            self.action_export_selected()
        elif event.button.id == "print-selected":
            self.action_print_selected()
        elif event.button.id == "archive-selected":
            self.action_delete_selected()
        elif event.button.id == "select-all":
            self.action_select_all()
        elif event.button.id == "clear-selection":
            self.action_clear_selection()
        elif event.button.id == "finish-selection":
            self._leave_selection_mode()


class StudyScreen(LexdeckScreen):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("y", "remembered", "Yes — remembered"),
        Binding("n", "forgot", "No — show meaning"),
        Binding("enter", "next_card", "Next", show=False),
        Binding("space", "next_card", "Next", show=False),
        Binding("r", "restart", "Review again", show=False),
        Binding("escape,q", "leave", "Back", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cards: list[Card] = []
        self.index = 0
        self.meaning_revealed = False
        self.started_at = monotonic()
        self.session_reviews = 0
        self.remembered_count = 0
        self.order = StudyOrder.SORTED

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="study-page"):
            with Horizontal(id="study-meta"):
                yield Label("STUDY", id="study-mode")
                yield Label("", id="study-progress")
            yield Static("", id="study-card")
            yield Static("Do you remember this card?", id="study-hint")
            with Vertical(id="recall-buttons"):
                yield Button("Y  Yes, I remember", id="remembered", variant="success")
                yield Button("N  No, show meaning", id="forgot", variant="warning")
            yield Button("Next card  [Enter]", id="next-card", variant="primary")
            with Vertical(id="session-actions"):
                yield Button("Review again", id="restart-study", variant="primary")
                yield Button("Back to dashboard", id="finish-study")
        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(self.request_order)

    def request_order(self) -> None:
        self.app.push_screen(StudyOrderModal(), self._order_selected)

    def _order_selected(self, order: StudyOrder | None) -> None:
        if order is None:
            self.app.switch_screen("dashboard")
            return
        self.order = order
        self.cards = self.service.study_cards(order)
        self.index = 0
        self.session_reviews = 0
        self.remembered_count = 0
        self.show_current()

    def show_current(self) -> None:
        recall_buttons = self.query_one("#recall-buttons", Vertical)
        next_button = self.query_one("#next-card", Button)
        session_actions = self.query_one("#session-actions", Vertical)
        if self.index >= len(self.cards):
            self.query_one("#study-progress", Label).update("Session complete")
            forgotten = self.session_reviews - self.remembered_count
            summary = (
                "There are no cards to review yet. Add your first card to begin."
                if not self.cards
                else (
                    f"You reviewed all {self.session_reviews} cards.\n\n"
                    f"[green]{self.remembered_count} remembered[/green]  ·  "
                    f"[yellow]{forgotten} revisited[/yellow]"
                )
            )
            self.query_one("#study-card", Static).update(
                f"[bold green]Review complete.[/bold green]\n\n{summary}"
            )
            self.query_one("#study-hint", Static).update("")
            recall_buttons.display = False
            next_button.display = False
            session_actions.display = True
            self.query_one("#restart-study", Button).focus()
            return
        card = self.cards[self.index]
        self.meaning_revealed = False
        self.started_at = monotonic()
        self.query_one("#study-progress", Label).update(
            f"{self.index + 1} / {len(self.cards)}  ·  {self.order.value.title()}"
        )
        self.query_one("#study-card", Static).update(f"[bold]{card.prompt}[/bold]")
        self.query_one("#study-hint", Static).update("Do you remember this card? Press Y or N.")
        recall_buttons.display = True
        next_button.display = False
        session_actions.display = False
        self.query_one("#remembered", Button).focus()

    def action_remembered(self) -> None:
        if self.index >= len(self.cards) or self.meaning_revealed:
            return
        if self._record(remembered=True):
            self.remembered_count += 1
            self.index += 1
            self.show_current()

    def action_forgot(self) -> None:
        if self.index >= len(self.cards) or self.meaning_revealed:
            return
        if not self._record(remembered=False):
            return
        card = self.cards[self.index]
        self.meaning_revealed = True
        meaning = card.meaning or "[dim]No meaning has been added to this card yet.[/dim]"
        self.query_one("#study-card", Static).update(
            f"[bold]{card.prompt}[/bold]\n\n[dim]MEANING[/dim]\n{meaning}"
        )
        self.query_one("#study-hint", Static).update(
            "Read the meaning, then press Enter or Space to continue."
        )
        self.query_one("#recall-buttons", Vertical).display = False
        next_button = self.query_one("#next-card", Button)
        next_button.display = True
        next_button.focus()

    def _record(self, *, remembered: bool) -> bool:
        duration = int((monotonic() - self.started_at) * 1000)
        try:
            self.service.record_recall(
                self.cards[self.index].id,
                remembered,
                duration_ms=duration,
            )
        except CardNotFoundError as error:
            self.app.notify(str(error), title="Review failed", severity="error")
            return False
        self.session_reviews += 1
        return True

    def action_next_card(self) -> None:
        if not self.meaning_revealed:
            return
        self.index += 1
        self.show_current()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        has_current_card = self.index < len(self.cards)
        if action in {"remembered", "forgot"}:
            return has_current_card and not self.meaning_revealed
        if action == "next_card":
            return has_current_card and self.meaning_revealed
        if action == "restart":
            return not has_current_card
        return True

    def action_restart(self) -> None:
        if self.index >= len(self.cards):
            self.request_order()

    def action_leave(self) -> None:
        self.app.switch_screen("dashboard")

    @on(Button.Pressed, "#remembered")
    def remembered_pressed(self) -> None:
        self.action_remembered()

    @on(Button.Pressed, "#forgot")
    def forgot_pressed(self) -> None:
        self.action_forgot()

    @on(Button.Pressed, "#next-card")
    def next_pressed(self) -> None:
        self.action_next_card()

    @on(Button.Pressed, "#restart-study")
    def restart_pressed(self) -> None:
        self.request_order()

    @on(Button.Pressed, "#finish-study")
    def finish_pressed(self) -> None:
        self.app.switch_screen("dashboard")


class StudyOrderModal(ModalScreen[StudyOrder | None]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("r", "choose_random", "Random", priority=True),
        Binding("s", "choose_sorted", "Sorted", priority=True),
        Binding("j,down", "focus_next_option", "Next option", show=False),
        Binding("k,up", "focus_previous_option", "Previous option", show=False),
        Binding("l,right", "open_focused_option", "Open", show=False),
        Binding("escape,q", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-card", id="order-modal"):
            yield Label("Choose the review order", classes="page-title")
            yield Label(
                "Every card appears once. Use J/K to move and L to choose.",
                classes="page-subtitle",
            )
            with Vertical(id="order-options"):
                yield Button("R  Random order", id="random-order", variant="primary")
                yield Label("A fresh shuffle for this session.", classes="option-hint")
                yield Button("S  Sorted A–Z", id="sorted-order")
                yield Label("Predictable order by card content.", classes="option-hint")
            yield Button("Cancel", id="cancel-order")

    def on_mount(self) -> None:
        self.query_one("#random-order", Button).focus()

    def action_focus_next_option(self) -> None:
        self.focus_next("Button")

    def action_focus_previous_option(self) -> None:
        self.focus_previous("Button")

    def action_open_focused_option(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()

    @on(Button.Pressed, "#random-order")
    def random_pressed(self) -> None:
        self.action_choose_random()

    @on(Button.Pressed, "#sorted-order")
    def sorted_pressed(self) -> None:
        self.action_choose_sorted()

    @on(Button.Pressed, "#cancel-order")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_choose_random(self) -> None:
        self.dismiss(StudyOrder.RANDOM)

    def action_choose_sorted(self) -> None:
        self.dismiss(StudyOrder.SORTED)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditCardModal(ModalScreen[dict[str, str] | None]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, card: Card) -> None:
        super().__init__()
        self.card = card

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-card", id="edit-modal"):
            yield Label("Edit flashcard", classes="page-title")
            yield Label("CONTENT", classes="field-label")
            yield TextArea(self.card.prompt, id="edit-content")
            yield Label("MEANING", classes="field-label")
            yield TextArea(self.card.meaning or "", id="edit-meaning")
            with Vertical(classes="vertical-actions"):
                yield Button("Save changes", id="confirm-edit", variant="primary")
                yield Button("Cancel", id="cancel-edit")

    def on_mount(self) -> None:
        self.query_one("#edit-content", TextArea).focus()

    def action_save(self) -> None:
        self.confirm()

    @on(Button.Pressed, "#confirm-edit")
    def confirm(self) -> None:
        self.dismiss(
            {
                "id": self.card.id,
                "content": self.query_one("#edit-content", TextArea).text,
                "meaning": self.query_one("#edit-meaning", TextArea).text,
            }
        )

    @on(Button.Pressed, "#cancel-edit")
    def cancel_button(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


@dataclass(frozen=True, slots=True)
class ExportRequest:
    export_format: ExportFormat
    path: str


class ExportSettingsModal(ModalScreen[Path | None]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("ctrl+s", "save", "Save setting", priority=True),
        Binding("alt+j", "focus_next_control", "Next", show=False, priority=True),
        Binding("alt+k", "focus_previous_control", "Previous", show=False, priority=True),
        Binding("j,down", "focus_next_control", "Next", show=False),
        Binding("k,up", "focus_previous_control", "Previous", show=False),
        Binding("l,right", "open_focused_control", "Open", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_directory: Path, downloads_directory: Path) -> None:
        super().__init__()
        self.current_directory = current_directory
        self.downloads_directory = downloads_directory

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-card", id="export-settings-modal"):
            yield Label("Export settings", classes="page-title")
            yield Label(
                "Choose the default folder used by PDF, Excel, and text exports.",
                classes="page-subtitle",
            )
            yield Label("DEFAULT EXPORT FOLDER", classes="field-label")
            yield Input(str(self.current_directory), id="settings-export-directory")
            yield Label(
                "Use an absolute path or start with ~. A missing folder is created "
                "when the first file is exported.",
                classes="shortcut-hint",
            )
            yield Label(
                "Alt+J / Alt+K moves between controls while an input is active.",
                classes="shortcut-hint",
            )
            with Vertical(classes="vertical-actions"):
                yield Button(
                    "Save default folder  [Ctrl+S]", id="save-export-settings", variant="primary"
                )
                yield Button("Use Downloads", id="use-downloads")
                yield Button("Cancel", id="cancel-export-settings")

    def on_mount(self) -> None:
        self.query_one("#settings-export-directory", Input).focus()

    def action_focus_next_control(self) -> None:
        self.focus_next("Input, Button")

    def action_focus_previous_control(self) -> None:
        self.focus_previous("Input, Button")

    def action_open_focused_control(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()

    def action_save(self) -> None:
        field = self.query_one("#settings-export-directory", Input)
        try:
            directory = normalize_export_directory(field.value)
        except SettingsError as error:
            self.app.notify(str(error), title="Invalid export folder", severity="error")
            field.focus()
            return
        self.dismiss(directory)

    @on(Input.Submitted, "#settings-export-directory")
    def directory_submitted(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#save-export-settings")
    def save_pressed(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#use-downloads")
    def use_downloads_pressed(self) -> None:
        field = self.query_one("#settings-export-directory", Input)
        field.value = str(self.downloads_directory)
        field.focus()

    @on(Button.Pressed, "#cancel-export-settings")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


class ExportModal(ModalScreen[ExportRequest | None]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("ctrl+e,ctrl+s", "export", "Create export", priority=True),
        Binding("alt+j", "focus_next_control", "Next", show=False, priority=True),
        Binding("alt+k", "focus_previous_control", "Previous", show=False, priority=True),
        Binding("escape", "cancel", "Cancel"),
        Binding("j,down", "focus_next_format_or_control", "Next", show=False),
        Binding("k,up", "focus_previous_format_or_control", "Previous", show=False),
        Binding("l,right", "open_focused_control", "Open", show=False),
    ]

    def __init__(self, card_count: int, export_directory: Path) -> None:
        super().__init__()
        self.card_count = card_count
        self.export_directory = export_directory
        self.export_format = ExportFormat.PDF

    def compose(self) -> ComposeResult:
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M")
        default_name = f"lexdeck-cards-{timestamp}"
        with VerticalScroll(classes="modal-card", id="export-modal"):
            yield Label(
                f"Export {self.card_count} selected card{'s' if self.card_count != 1 else ''}",
                classes="page-title",
            )
            yield Label(
                "Choose a format, file name, and folder. Selected cards keep their "
                "selection order. Use J/K to move through formats and L to choose.",
                classes="page-subtitle",
            )
            yield Label("FORMAT", classes="field-label")
            with RadioSet(id="export-formats"):
                yield RadioButton(
                    "PDF - polished, printable card list",
                    value=True,
                    id="format-pdf",
                )
                yield RadioButton(
                    "Excel - filterable, editable table",
                    id="format-xlsx",
                )
                yield RadioButton(
                    "Plain text - portable UTF-8 document",
                    id="format-txt",
                )
            yield Label("FILE NAME", classes="field-label")
            yield Input(default_name, id="export-name")
            yield Label(
                "The selected format adds the extension automatically.",
                classes="shortcut-hint",
                id="export-extension-hint",
            )
            yield Label("EXPORT FOLDER", classes="field-label")
            yield Input(str(self.export_directory), id="export-directory")
            yield Button("Change default export folder", id="open-export-settings")
            yield Label(
                "Alt+J / Alt+K moves between controls while typing. Existing files "
                "require confirmation before replacement.",
                classes="shortcut-hint",
            )
            with Vertical(classes="vertical-actions"):
                yield Button("Create PDF", id="confirm-export", variant="primary")
                yield Button("Cancel", id="cancel-export")

    def on_mount(self) -> None:
        self.query_one("#export-formats", RadioSet).focus()

    @on(RadioSet.Changed)
    def format_changed(self, event: RadioSet.Changed) -> None:
        format_name = (event.pressed.id or "format-pdf").removeprefix("format-")
        self.export_format = ExportFormat(format_name)
        self.query_one("#export-extension-hint", Label).update(
            f"Lexdeck adds {self.export_format.suffix} automatically."
        )
        self.query_one(
            "#confirm-export", Button
        ).label = f"Create {self.export_format.display_name}"

    def action_focus_next_control(self) -> None:
        self.focus_next("RadioSet, Input, Button")

    def action_focus_previous_control(self) -> None:
        self.focus_previous("RadioSet, Input, Button")

    def action_focus_next_format_or_control(self) -> None:
        if isinstance(self.focused, RadioSet):
            self.focused.action_next_button()
            return
        self.action_focus_next_control()

    def action_focus_previous_format_or_control(self) -> None:
        if isinstance(self.focused, RadioSet):
            self.focused.action_previous_button()
            return
        self.action_focus_previous_control()

    def action_open_focused_control(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()
        elif isinstance(self.focused, RadioSet):
            self.focused.action_toggle_button()

    def action_export(self) -> None:
        name_field = self.query_one("#export-name", Input)
        directory_field = self.query_one("#export-directory", Input)
        try:
            filename = normalize_export_filename(name_field.value, self.export_format)
        except ValueError as error:
            self.app.notify(str(error), title="Invalid file name", severity="error")
            name_field.focus()
            return
        try:
            directory = normalize_export_directory(directory_field.value)
        except SettingsError as error:
            self.app.notify(str(error), title="Invalid export folder", severity="error")
            directory_field.focus()
            return
        destination = normalize_export_path(directory / filename, self.export_format)
        self.dismiss(ExportRequest(self.export_format, str(destination)))

    @on(Input.Submitted, "#export-name")
    def name_submitted(self) -> None:
        self.query_one("#export-directory", Input).focus()

    @on(Input.Submitted, "#export-directory")
    def directory_submitted(self) -> None:
        self.action_export()

    @on(Button.Pressed, "#open-export-settings")
    def open_settings_pressed(self) -> None:
        cast("LexdeckApp", self.app).open_export_settings(self._default_directory_saved)

    def _default_directory_saved(self, directory: Path) -> None:
        self.query_one("#export-directory", Input).value = str(directory)

    @on(Button.Pressed, "#confirm-export")
    def export_pressed(self) -> None:
        self.action_export()

    @on(Button.Pressed, "#cancel-export")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("y", "confirm", "Confirm"),
        Binding("n,escape,q", "cancel", "Cancel"),
        Binding("k,up", "focus_previous_action", "Previous", show=False),
        Binding("j,down", "focus_next_action", "Next", show=False),
        Binding("l,right", "open_focused_action", "Open", show=False),
    ]

    def __init__(
        self,
        message: str,
        *,
        detail: str = "The card leaves your library, but its review history is preserved.",
        confirm_label: str = "Archive",
        destructive: bool = True,
    ) -> None:
        super().__init__()
        self.message = message
        self.detail = detail
        self.confirm_label = confirm_label
        self.destructive = destructive

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-card", id="confirm-modal"):
            yield Label(self.message, id="confirm-message")
            yield Label(self.detail, id="confirm-detail")
            yield Label("J/K move · L choose", classes="shortcut-hint")
            with Vertical(classes="vertical-actions"):
                yield Button(
                    self.confirm_label,
                    id="confirm-delete",
                    variant="error" if self.destructive else "primary",
                )
                yield Button("Cancel", id="cancel-delete")

    def on_mount(self) -> None:
        self.query_one("#cancel-delete", Button).focus()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_focus_next_action(self) -> None:
        self.focus_next("Button")

    def action_focus_previous_action(self) -> None:
        self.focus_previous("Button")

    def action_open_focused_action(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()

    @on(Button.Pressed, "#confirm-delete")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-delete")
    def cancel_button(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(False)


class HelpModal(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("escape", "dismiss_help", "Close"),
        Binding("?", "dismiss_help", "Close", show=False),
        Binding("q", "dismiss_help", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-card", id="help-modal"):
            yield Label("Keyboard shortcuts", classes="page-title")
            yield Static(
                "[dim]GLOBAL[/dim]\n"
                "[bold]F1–F4[/bold]  Dashboard · Add · Library · Study\n"
                "[bold]Ctrl+P[/bold] command palette · [bold]?[/bold] help · "
                "[bold]Ctrl+Q[/bold] quit\n"
                "[bold]j / k[/bold] next / previous · [bold]l / Enter[/bold] open\n"
                "[bold]D / A / S / Q[/bold] dashboard · add · study · quit (outside fields)\n"
                "[bold]Tab / Shift+Tab[/bold] conventional focus movement\n\n"
                "[dim]DASHBOARD[/dim]\n"
                "[bold]j / k / l[/bold] move and open · "
                "[bold]o / r / b[/bold] add · review · browse\n\n"
                "[dim]LIBRARY · VIM NORMAL MODE[/dim]\n"
                "[bold]j / k[/bold] next / previous · "
                "[bold]gg / G[/bold] first / last ([bold]Home / End[/bold] too)\n"
                "[bold]/[/bold] search · [bold]o[/bold] new · [bold]Enter / e / i / l[/bold] edit\n"
                "[bold]dd / Delete[/bold] archive · [bold]v[/bold] select cards · "
                "[bold]Esc / h[/bold] back\n\n"
                "[dim]LIBRARY · SELECTION MODE[/dim]\n"
                "[bold]j / k[/bold] move without selecting · "
                "[bold]l / Enter / Space[/bold] toggle card\n"
                "[bold]Ctrl+A[/bold] select visible · [bold]c[/bold] clear · "
                "[bold]Ctrl+E[/bold] export · [bold]p[/bold] print\n"
                "[bold]dd / Delete[/bold] archive selection · [bold]Esc[/bold] finish\n\n"
                "[dim]EXPORT DIALOG[/dim]\n"
                "[bold]j / k / l[/bold] move and choose a format · "
                "[bold]Tab / Shift+Tab[/bold] move controls · "
                "[bold]Alt+J / Alt+K[/bold] move while typing\n"
                "[bold]Enter[/bold] advances from name and exports from folder · "
                "[bold]Ctrl+E / Ctrl+S[/bold] create · [bold]Esc[/bold] cancel\n\n"
                "[dim]EXPORT SETTINGS[/dim]\n"
                "Open from the export dialog or command palette · "
                "[bold]Ctrl+S[/bold] save · [bold]Esc[/bold] cancel\n\n"
                "[dim]STUDY ORDER[/dim]\n"
                "[bold]j / k / l[/bold] move and choose · [bold]r / s[/bold] random · sorted · "
                "[bold]Esc / q[/bold] cancel\n\n"
                "[dim]STUDY[/dim]\n"
                "[bold]y[/bold] remembered · [bold]n[/bold] reveal meaning · "
                "[bold]Enter / Space[/bold] continue\n"
                "[bold]r[/bold] review again when complete · [bold]Esc / q[/bold] dashboard\n\n"
                "[dim]ADD / EDIT[/dim]\n"
                "Add: [bold]Ctrl+S / Ctrl+Enter[/bold] save · "
                "[bold]Alt+S[/bold] save and browse · [bold]Esc[/bold] leave safely\n"
                "Edit: [bold]Ctrl+S[/bold] save · [bold]Esc[/bold] cancel · "
                "[bold]Tab[/bold] move focus\n\n"
                "[dim]CONFIRMATIONS[/dim]\n"
                "[bold]j / k / l[/bold] move and choose · [bold]y[/bold] confirm · "
                "[bold]n / Esc / q[/bold] cancel\n\n"
                "[dim]Printable Vim keys never override text entry.[/dim]",
                id="help-content",
            )
            yield Button("Close", id="close-help", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#close-help", Button).focus()

    @on(Button.Pressed, "#close-help")
    def close(self) -> None:
        self.action_dismiss_help()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)


class LexdeckApp(App[None]):
    TITLE = "Lexdeck"
    SUB_TITLE = "Local-first flashcards"

    BINDINGS: ClassVar[list[BindingSpec]] = [
        Binding("d", "dashboard", "Dashboard"),
        Binding("a", "add", "Add"),
        Binding("s", "study", "Study"),
        Binding("j", "focus_next", "Next", show=False),
        Binding("k", "focus_previous", "Previous", show=False),
        Binding("l", "press_focused", "Open", show=False),
        Binding("f1", "dashboard", "Dashboard", show=False, priority=True),
        Binding("f2", "add", "Add", show=False, priority=True),
        Binding("f3", "library", "Library", show=False, priority=True),
        Binding("f4", "study", "Study", show=False, priority=True),
        Binding("?", "help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
    ]

    CSS = """
    $bg: #0b1020;
    $panel: #121a2f;
    $panel-2: #19233c;
    $text: #e8edf7;
    $muted: #8995ad;
    $accent: #60a5fa;
    $success: #34d399;

    Screen { background: $bg; color: $text; }
    Header { background: $panel; color: $text; }
    Footer { background: $panel; color: $muted; }
    Label, Static {
        width: 100%; height: auto; text-wrap: wrap; overflow-x: hidden;
    }
    Button { max-width: 100%; }
    Button:focus { text-style: bold; border: tall $accent; }
    #page { padding: 2 5 3 5; }
    .page-title { text-style: bold; color: $text; text-align: left; width: 100%; }
    .hero-title { text-style: bold; color: $text; text-align: center; width: 100%; margin-top: 1; }
    .page-subtitle { color: $muted; margin: 1 0 2 0; width: 100%; }
    DashboardScreen .page-subtitle { text-align: center; }
    .section-title { text-style: bold; margin: 2 0 1 0; }
    .action-menu { height: auto; width: 100%; align-horizontal: center; }
    .action-menu Button { width: 44; margin-bottom: 1; }
    .form-card { background: $panel; border: round #263451; padding: 1 2; height: auto; }
    .field-label { color: $muted; text-style: bold; margin-top: 1; }
    TextArea { height: 5; border: round #33415f; background: #0f172a; }
    TextArea:focus, Input:focus { border: round $accent; }
    Input { border: round #33415f; background: #0f172a; }
    .vertical-actions { height: auto; width: 100%; margin-top: 1; }
    .vertical-actions Button { width: 100%; margin-bottom: 1; }
    .shortcut-hint { color: $muted; margin-top: 1; }
    #library-page { padding: 1 3; }
    #search { width: 100%; }
    #library-content { height: 1fr; margin-top: 1; }
    #card-table { width: 2fr; border: round #263451; background: $panel; }
    #card-table:focus { border: round $accent; }
    #library-sidebar { width: 1fr; min-width: 28; margin-left: 1; }
    #card-detail {
        width: 100%; height: 1fr; padding: 2;
        background: $panel; border: round #263451; overflow-y: auto;
    }
    #library-actions { height: auto; }
    #selection-actions { display: none; height: auto; }
    #study-page { padding: 2 8; align-horizontal: center; }
    #study-meta { width: 80%; max-width: 100; height: auto; min-height: 3; color: $muted; }
    #study-mode { width: 1fr; text-style: bold; color: $accent; }
    #study-progress { width: 1fr; text-align: right; }
    #study-card {
        width: 80%; max-width: 100; height: auto; min-height: 12; padding: 3 5;
        background: $panel; border: round #33415f; content-align: center middle;
        text-align: center;
    }
    #study-hint {
        width: 80%; max-width: 100; color: $muted; height: auto; min-height: 3;
        text-align: center; margin-top: 1;
    }
    #recall-buttons { width: 80%; max-width: 70; height: auto; align-horizontal: center; }
    #recall-buttons Button { width: 100%; margin-bottom: 1; }
    #next-card { display: none; min-width: 28; }
    #session-actions { display: none; width: 80%; max-width: 60; height: auto; }
    #session-actions Button { width: 100%; margin-bottom: 1; }
    ModalScreen { align: center middle; background: rgba(3, 7, 18, 0.75); }
    .modal-card {
        width: 68; max-width: 100%; max-height: 90%; height: auto; padding: 1 2;
        background: $panel; border: round $accent; overflow-x: hidden;
    }
    #edit-modal TextArea { height: 5; }
    #confirm-modal { width: 60; max-width: 100%; }
    #confirm-message { text-style: bold; margin-bottom: 1; }
    #help-modal { width: 64; max-width: 100%; }
    #help-content { margin: 1 0 2 0; }
    #export-modal { width: 72; max-width: 100%; }
    #export-settings-modal { width: 72; max-width: 100%; }
    #export-formats { height: auto; margin-bottom: 1; }
    #export-formats RadioButton { width: 100%; }
    #order-modal { width: 62; max-width: 100%; }
    #order-options { height: auto; margin-bottom: 1; }
    #order-options Button { width: 100%; margin-top: 1; }
    #cancel-order { width: 100%; margin-top: 1; }
    .option-hint { color: $muted; margin-left: 2; }
    """

    def __init__(
        self,
        service: LexdeckService,
        *,
        initial_screen: str = "dashboard",
        settings_store: SettingsStore | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.initial_screen = initial_screen
        self.settings_store = settings_store or SettingsStore()

    def on_mount(self) -> None:
        self.install_screen(DashboardScreen(), "dashboard")
        self.install_screen(AddScreen(), "add")
        self.install_screen(LibraryScreen(), "library")
        self.install_screen(StudyScreen(), "study")
        self.push_screen(self.initial_screen)

    def get_system_commands(self, screen: Screen[object]) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("Dashboard", "Open the Lexdeck dashboard", self.action_dashboard)
        yield SystemCommand("Add card", "Capture a new flashcard", self.action_add)
        yield SystemCommand("Browse library", "Search and edit flashcards", self.action_library)
        yield SystemCommand("Study", "Review every active flashcard", self.action_study)
        yield SystemCommand(
            "Export settings",
            "Change the default folder for exported files",
            self.action_export_settings,
        )
        yield SystemCommand(
            "Keyboard shortcuts", "Open the Lexdeck key reference", self.action_help
        )

    def action_dashboard(self) -> None:
        self.switch_screen("dashboard")

    def action_add(self) -> None:
        self.switch_screen("add")

    def action_library(self) -> None:
        self.switch_screen("library")

    def action_study(self) -> None:
        study_screen = cast(StudyScreen, self.get_screen("study"))
        was_mounted = study_screen.is_mounted
        self.switch_screen(study_screen)
        if was_mounted:
            self.call_after_refresh(study_screen.request_order)

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def export_directory(self) -> Path:
        try:
            return self.settings_store.load().export_directory
        except SettingsError as error:
            self.notify(
                f"{error} Using Downloads for now.",
                title="Export settings",
                severity="warning",
            )
            return self.settings_store.defaults().export_directory

    def action_export_settings(self) -> None:
        self.open_export_settings()

    def open_export_settings(
        self,
        on_saved: Callable[[Path], None] | None = None,
    ) -> None:
        self.push_screen(
            ExportSettingsModal(
                self.export_directory(),
                self.settings_store.defaults().export_directory,
            ),
            lambda directory: self._save_export_settings(directory, on_saved),
        )

    def _save_export_settings(
        self,
        directory: Path | None,
        on_saved: Callable[[Path], None] | None,
    ) -> None:
        if directory is None:
            return
        try:
            settings = self.settings_store.save(LexdeckSettings(directory))
        except SettingsError as error:
            self.notify(str(error), title="Could not save settings", severity="error")
            return
        self.notify(str(settings.export_directory), title="Default export folder saved")
        if on_saved is not None:
            on_saved(settings.export_directory)

    def action_press_focused(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()


def _one_line(value: str, length: int) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= length else normalized[: length - 1] + "…"

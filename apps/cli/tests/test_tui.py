from __future__ import annotations

import lexdeck_cli.tui as tui_module
import pytest
from lexdeck_cli.settings import SettingsStore
from lexdeck_cli.tui import (
    AddScreen,
    ConfirmModal,
    DashboardScreen,
    EditCardModal,
    ExportModal,
    ExportSettingsModal,
    HelpModal,
    LexdeckApp,
    LibraryScreen,
)
from lexdeck_core import LexdeckService
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, RadioSet, Static, TextArea


@pytest.mark.asyncio
async def test_dashboard_and_study_flow(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    service.add_card("run into", "meet unexpectedly")
    app = LexdeckApp(service)

    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        assert "Build your English" in str(app.screen.query_one(".hero-title", Static).render())
        assert "A simple daily loop" not in str(app.screen.render())
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("s")  # Sorted A–Z in the order dialog.
        await pilot.pause()
        card = app.screen.query_one("#study-card", Static)
        assert "run into" in str(card.render())
        await pilot.press("n")
        assert "meet unexpectedly" in str(card.render())
        await pilot.press("enter")
        assert "Review complete" in str(card.render())

        await pilot.click("#restart-study")
        await pilot.press("r")  # Random order; the same card must be available again.
        await pilot.pause()
        assert "run into" in str(app.screen.query_one("#study-card", Static).render())
        await pilot.press("y")
        assert service.stats().reviewed_today == 2


@pytest.mark.asyncio
async def test_add_and_browse_unicode_card_at_small_terminal(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    app = LexdeckApp(service)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#content", TextArea).load_text("meticulous")
        app.screen.query_one("#meaning", TextArea).load_text("دقیق و موشکاف")
        await pilot.press("ctrl+s")
        service.add_card("abate", "become less intense")
        await pilot.press("f3")
        await pilot.pause()

        table = app.screen.query_one("#card-table", DataTable)
        assert table.row_count == 2
        assert table.cursor_coordinate.row == 0
        await pilot.press("ctrl+f")
        await pilot.press("down")
        assert table.has_focus
        assert table.cursor_coordinate.row == 1
        assert any(card.meaning == "دقیق و موشکاف" for card in service.list_cards())


@pytest.mark.asyncio
async def test_library_vim_navigation_search_and_actions(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    for prompt in ("alpha", "bravo", "charlie"):
        service.add_card(prompt, f"meaning of {prompt}")
    app = LexdeckApp(service, initial_screen="library")

    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LibraryScreen)
        table = app.screen.query_one("#card-table", DataTable)

        await pilot.press("j")
        assert table.cursor_coordinate.row == 1
        await pilot.press("k")
        assert table.cursor_coordinate.row == 0
        await pilot.press("G")
        assert table.cursor_coordinate.row == 2
        await pilot.press("g", "g")
        assert table.cursor_coordinate.row == 0

        await pilot.press("/")
        search = app.screen.query_one("#search", Input)
        assert search.has_focus
        await pilot.press("j", "k")
        assert search.value == "jk"
        await pilot.press("escape")
        assert table.has_focus

        search.value = ""
        await pilot.pause()
        await pilot.press("e")
        assert isinstance(app.screen, EditCardModal)
        await pilot.press("escape")
        await pilot.press("d", "d")
        await pilot.press("n")
        assert isinstance(app.screen, LibraryScreen)

        await pilot.press("d", "d")
        assert app.screen.query_one("#cancel-delete", Button).has_focus
        await pilot.press("k")
        assert app.screen.query_one("#confirm-delete", Button).has_focus
        await pilot.press("l")
        assert isinstance(app.screen, LibraryScreen)
        assert len(service.list_cards()) == 2

        await pilot.press("o")
        assert isinstance(app.screen, AddScreen)


@pytest.mark.asyncio
async def test_library_selection_mode_exports_selected_cards(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    service = LexdeckService(tmp_path / "lexdeck.db")
    for prompt in ("alpha", "bravo", "charlie"):
        service.add_card(prompt, f"meaning of {prompt}")
    downloads = tmp_path / "Downloads"
    settings = SettingsStore(
        tmp_path / "config" / "settings.json",
        default_export_directory=downloads,
    )
    app = LexdeckApp(service, initial_screen="library", settings_store=settings)

    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)

        await pilot.press("v")
        assert library.selection_mode
        assert "0 selected" in str(library.query_one("#result-count", Label).render())

        await pilot.press("l", "j", "space")
        assert len(library.selected_cards) == 2
        selected_prompts = {card.prompt for card in library.selected_cards.values()}
        unselected_prompt = ({"alpha", "bravo", "charlie"} - selected_prompts).pop()
        assert "2 selected" in str(library.query_one("#result-count", Label).render())
        assert not library.query_one("#export-selected", Button).disabled

        await pilot.press("ctrl+e")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        format_selector = app.screen.query_one("#export-formats", RadioSet)
        name_input = app.screen.query_one("#export-name", Input)
        directory_input = app.screen.query_one("#export-directory", Input)
        assert format_selector.has_focus
        assert app.screen.export_format.value == "pdf"
        assert directory_input.value == str(downloads)
        name_input.value = "chosen-cards"
        await pilot.press("j")
        assert app.screen.export_format.value == "pdf"
        await pilot.press("l")
        assert app.screen.export_format.value == "xlsx"
        await pilot.press("k")
        assert app.screen.export_format.value == "xlsx"
        await pilot.press("l")
        assert app.screen.export_format.value == "pdf"
        await pilot.press("j", "j", "l")
        await pilot.pause()
        assert app.screen.export_format.value == "txt"
        assert format_selector.has_focus
        assert name_input.value == "chosen-cards"
        assert ".txt" in str(app.screen.query_one("#export-extension-hint", Label).render())
        await pilot.press("ctrl+e")
        await pilot.pause()

        assert isinstance(app.screen, LibraryScreen)
        assert not library.selection_mode
        export = downloads / "chosen-cards.txt"
        assert export.exists()
        content = export.read_text(encoding="utf-8")
        assert all(prompt in content for prompt in selected_prompts)
        assert unselected_prompt not in content


@pytest.mark.asyncio
async def test_library_range_selection_shows_markers_and_preserves_search_typing(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    for prompt in ("alpha", "bravo", "charlie", "delta", "echo"):
        service.add_card(prompt, f"meaning of {prompt}")
    app = LexdeckApp(service, initial_screen="library")

    async with app.run_test(size=(72, 24)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)
        table = library.query_one("#card-table", DataTable)
        visible = list(library.cards.values())

        await pilot.press("v")
        assert all(table.get_cell(card.id, "selected").plain == "[ ]" for card in visible)
        await pilot.press("j", "j", "shift+l")
        assert set(library.selected_cards) == {card.id for card in visible[:3]}
        assert [table.get_cell(card.id, "selected").plain for card in visible] == [
            "[x]",
            "[x]",
            "[x]",
            "[ ]",
            "[ ]",
        ]
        assert "☑ SELECTED" in str(library.query_one("#card-detail", Static).render())

        await pilot.press("c", "j", "l", "k", "k", "shift+enter")
        assert set(library.selected_cards) == {card.id for card in visible[1:4]}
        assert [table.get_cell(card.id, "selected").plain for card in visible] == [
            "[ ]",
            "[x]",
            "[x]",
            "[x]",
            "[ ]",
        ]

        await pilot.press("c", "/")
        assert library.query_one("#search", Input).has_focus
        await pilot.press("L", "shift+enter")
        assert library.query_one("#search", Input).value == "L"
        assert library.selected_cards == {}


@pytest.mark.asyncio
async def test_selection_mode_preserves_typing_and_escape_is_safe(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    service.add_card("alpha", "first")
    settings = SettingsStore(
        tmp_path / "config" / "settings.json",
        default_export_directory=tmp_path / "Downloads",
    )
    app = LexdeckApp(service, initial_screen="library", settings_store=settings)

    async with app.run_test(size=(72, 24)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)
        await pilot.press("v")
        assert library.selection_mode
        sidebar = library.query_one("#library-sidebar", VerticalScroll)
        for selector in (
            "#export-selected",
            "#print-selected",
            "#archive-selected",
            "#select-all",
            "#clear-selection",
            "#finish-selection",
        ):
            assert library.query_one(selector, Button).region.width <= sidebar.content_region.width

        await pilot.press("l", "ctrl+e")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        modal = app.screen.query_one("#export-modal")
        name_input = app.screen.query_one("#export-name", Input)
        directory_input = app.screen.query_one("#export-directory", Input)
        assert modal.region.width <= app.screen.region.width
        name_input.value = ""
        name_input.focus()
        await pilot.press("j", "k", "l", "v", "c", "p")
        assert name_input.value == "jklvcp"
        await pilot.press("alt+j")
        assert directory_input.has_focus
        await pilot.press("alt+k")
        assert name_input.has_focus
        await pilot.press("escape")
        assert isinstance(app.screen, LibraryScreen)
        assert library.selection_mode

        await pilot.press("/")
        search = library.query_one("#search", Input)
        await pilot.press("j", "k", "l", "v", "c", "p")
        assert search.value == "jklvcp"

        await pilot.press("escape")
        assert library.selection_mode
        assert library.query_one("#card-table", DataTable).has_focus
        await pilot.press("escape")
        assert not library.selection_mode
        assert isinstance(app.screen, LibraryScreen)


@pytest.mark.asyncio
async def test_export_folder_setting_updates_modal_and_persists(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    service.add_card("alpha", "first")
    downloads = tmp_path / "Downloads"
    chosen = tmp_path / "Language exports"
    settings = SettingsStore(
        tmp_path / "config" / "settings.json",
        default_export_directory=downloads,
    )
    app = LexdeckApp(service, initial_screen="library", settings_store=settings)

    async with app.run_test(size=(88, 30)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)
        await pilot.press("v", "l", "ctrl+e")
        await pilot.pause()

        assert isinstance(app.screen, ExportModal)
        assert app.screen.query_one("#export-directory", Input).value == str(downloads)
        app.screen.query_one("#open-export-settings", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, ExportSettingsModal)
        settings_input = app.screen.query_one("#settings-export-directory", Input)
        settings_input.value = str(chosen)
        await pilot.press("ctrl+s")
        await pilot.pause()

        assert isinstance(app.screen, ExportModal)
        assert app.screen.query_one("#export-directory", Input).value == str(chosen)
        assert settings.load().export_directory == chosen
        await pilot.press("escape", "ctrl+e")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        assert app.screen.query_one("#export-directory", Input).value == str(chosen)


@pytest.mark.asyncio
async def test_selection_mode_prints_selected_cards_after_confirmation(
    tmp_path, monkeypatch
) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    for prompt in ("alpha", "bravo", "charlie"):
        service.add_card(prompt, f"meaning of {prompt}")
    printed: list[str] = []

    def fake_print_cards(cards) -> str:
        printed.extend(card.prompt for card in cards)
        return "request id is test-printer-1"

    monkeypatch.setattr(tui_module, "print_cards", fake_print_cards)
    app = LexdeckApp(service, initial_screen="library")

    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)
        await pilot.press("v", "l", "j", "l", "p")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        assert app.screen.query_one("#cancel-delete", Button).has_focus
        assert app.screen.query_one("#confirm-delete", Button).variant == "primary"
        await pilot.press("y")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert len(printed) == 2
        assert not library.selection_mode
        assert library.selected_cards == {}


@pytest.mark.asyncio
async def test_selection_mode_bulk_archive_is_confirmed_and_transactional(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    for prompt in ("alpha", "bravo", "charlie"):
        service.add_card(prompt, f"meaning of {prompt}")
    app = LexdeckApp(service, initial_screen="library")

    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        library = app.screen
        assert isinstance(library, LibraryScreen)
        await pilot.press("v", "l", "j", "space", "delete")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmModal)
        assert "Archive 2 selected cards" in str(
            app.screen.query_one("#confirm-message", Label).render()
        )
        assert app.screen.query_one("#cancel-delete", Button).has_focus
        await pilot.press("y")
        await pilot.pause()

        assert len(service.list_cards()) == 1
        assert not library.selection_mode
        assert library.selected_cards == {}


@pytest.mark.asyncio
async def test_vim_letters_remain_typable_in_forms(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    app = LexdeckApp(service, initial_screen="add")

    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        content = app.screen.query_one("#content", TextArea)
        await pilot.press("j", "k", "l", "g", "g", "d", "d", "o", "q")
        assert content.text == "jklggddoq"


@pytest.mark.asyncio
async def test_escape_leaves_add_form_without_mouse(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    app = LexdeckApp(service, initial_screen="add")

    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        content = app.screen.query_one("#content", TextArea)
        await pilot.press("d", "r", "a", "f", "t")
        await pilot.press("escape")
        assert isinstance(app.screen, ConfirmModal)

        await pilot.press("n")
        assert isinstance(app.screen, AddScreen)
        assert content.text == "draft"

        await pilot.press("escape", "y")
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_modal_descriptions_wrap_in_narrow_terminals(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    service.add_card("consider")
    app = LexdeckApp(service, initial_screen="library")

    async with app.run_test(size=(50, 24)) as pilot:
        await pilot.pause()
        await pilot.press("d", "d")
        await pilot.pause()

        detail = app.screen.query_one("#confirm-detail", Label)
        modal = app.screen.query_one("#confirm-modal")
        assert detail.content_size.height >= 2
        assert detail.region.width <= modal.content_size.width


@pytest.mark.asyncio
async def test_dashboard_and_order_dialog_are_keyboard_navigable(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    service.add_card("alpha")
    app = LexdeckApp(service)

    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#go-add", Button).has_focus
        await pilot.press("j")
        assert app.screen.query_one("#go-study", Button).has_focus
        await pilot.press("l")
        await pilot.pause()
        assert app.screen.query_one("#random-order", Button).has_focus
        await pilot.press("j")
        assert app.screen.query_one("#sorted-order", Button).has_focus
        await pilot.press("l")
        await pilot.pause()
        assert "alpha" in str(app.screen.query_one("#study-card", Static).render())
        await pilot.press("j")
        assert app.screen.query_one("#forgot", Button).has_focus
        await pilot.press("l")
        assert "No meaning has been added" in str(
            app.screen.query_one("#study-card", Static).render()
        )


@pytest.mark.asyncio
async def test_in_app_help_documents_current_keyboard_model(tmp_path) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    app = LexdeckApp(service)

    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, HelpModal)
        help_text = str(app.screen.query_one("#help-content", Static).render())
        for expected in (
            "STUDY ORDER",
            "CONFIRMATIONS",
            "LIBRARY · SELECTION MODE",
            "Ctrl+Enter",
            "Ctrl+E",
            "dd / Delete",
            "Printable Vim keys never override text entry",
        ):
            assert expected in help_text

        await pilot.press("q")
        assert isinstance(app.screen, DashboardScreen)

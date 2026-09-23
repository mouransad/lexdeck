from __future__ import annotations

import re
from datetime import UTC, datetime
from zipfile import ZipFile

import pytest
from lexdeck_cli.exports import (
    ExportError,
    ExportFormat,
    _find_pdf_fonts,
    export_cards,
    normalize_export_filename,
    normalize_export_path,
)
from lexdeck_core import Card


@pytest.fixture
def export_cards_fixture() -> list[Card]:
    timestamp = datetime(2026, 9, 21, 12, 30, tzinfo=UTC)
    return [
        Card(
            id="11111111-1111-1111-1111-111111111111",
            prompt="run into",
            meaning="to meet unexpectedly",
            created_at=timestamp,
            updated_at=timestamp,
        ),
        Card(
            id="22222222-2222-2222-2222-222222222222",
            prompt="meticulous",
            meaning="دقیق و موشکاف",
            created_at=timestamp,
            updated_at=timestamp,
        ),
        Card(
            id="33333333-3333-3333-3333-333333333333",
            prompt="=not a formula",
            meaning=None,
            created_at=timestamp,
            updated_at=timestamp,
        ),
    ]


def test_plain_text_export_is_structured_utf8(tmp_path, export_cards_fixture: list[Card]) -> None:
    output = export_cards(
        export_cards_fixture,
        tmp_path / "cards",
        ExportFormat.TEXT,
        generated_at=datetime(2026, 9, 21, 14, 0, tzinfo=UTC),
    )

    assert output == tmp_path / "cards.txt"
    content = output.read_text(encoding="utf-8")
    assert "LEXDECK - SELECTED FLASHCARDS" in content
    assert "3 cards - Exported 2026-09-21 17:30" in content
    assert "2. CONTENT\nmeticulous\n\nMEANING\nدقیق و موشکاف" in content
    assert "3. CONTENT\n=not a formula\n\nMEANING\nNot provided." in content


def test_excel_export_is_filterable_and_preserves_text(
    tmp_path, export_cards_fixture: list[Card]
) -> None:
    output = export_cards(
        export_cards_fixture,
        tmp_path / "cards.pdf",
        ExportFormat.EXCEL,
        generated_at=datetime(2026, 9, 21, 14, 0, tzinfo=UTC),
    )

    assert output == tmp_path / "cards.xlsx"
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "xl/tables/table1.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        table_xml = archive.read("xl/tables/table1.xml").decode("utf-8")
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        shared_strings = archive.read("xl/sharedStrings.xml").decode("utf-8")
        xml = "\n".join(
            archive.read(name).decode("utf-8") for name in names if name.endswith(".xml")
        )
    assert "meticulous" in xml
    assert "دقیق و موشکاف" in xml
    assert "=not a formula" in xml
    assert "autoFilter" in xml
    assert "pane" in xml
    assert 'ref="A5:B8"' in table_xml
    assert table_xml.count("<tableColumn ") == 2
    assert "Updated" not in shared_strings
    assert "2026-09-21" not in shared_strings
    assert "Flashcards!$A$2:$B$8" in xml
    first_row_height = re.search(r'<row r="6"[^>]*\sht="([0-9.]+)"', sheet_xml)
    assert first_row_height is not None
    assert float(first_row_height.group(1)) >= 38


def test_excel_export_gives_long_cards_room_to_wrap(tmp_path) -> None:
    timestamp = datetime(2026, 9, 21, 12, 30, tzinfo=UTC)
    long_card = Card(
        id="44444444-4444-4444-4444-444444444444",
        prompt=" ".join(["A deliberately long flashcard prompt"] * 18),
        meaning=" ".join(["A detailed meaning that also needs comfortable spacing"] * 18),
        created_at=timestamp,
        updated_at=timestamp,
    )

    output = export_cards([long_card], tmp_path / "long-card", ExportFormat.EXCEL)

    with ZipFile(output) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    row_match = re.search(r'<row r="6"[^>]*\sht="([0-9.]+)"', sheet_xml)
    assert row_match is not None
    assert float(row_match.group(1)) > 96


def test_pdf_export_has_multiple_structured_pages_when_needed(
    tmp_path, export_cards_fixture: list[Card]
) -> None:
    cards = export_cards_fixture * 12
    output = export_cards(
        cards,
        tmp_path / "cards",
        ExportFormat.PDF,
        generated_at=datetime(2026, 9, 21, 14, 0, tzinfo=UTC),
    )

    pdf_bytes = output.read_bytes()
    assert output.suffix == ".pdf"
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10_000
    assert pdf_bytes.count(b"/Type /Page") >= 2


def test_pdf_fonts_are_bundled_for_all_platforms() -> None:
    regular, bold = _find_pdf_fonts()
    assert regular.name == "DejaVuSans.ttf"
    assert bold.name == "DejaVuSans-Bold.ttf"
    assert regular.parent.name == bold.parent.name == "assets"


def test_pdf_export_keeps_long_content_readable(tmp_path) -> None:
    timestamp = datetime(2026, 9, 21, 12, 30, tzinfo=UTC)
    cards = [
        Card(
            id=f"{index:08d}-4444-4444-4444-444444444444",
            prompt=" ".join([f"Long flashcard {index} with useful context"] * 7),
            meaning=" ".join(["A detailed meaning with enough room to read comfortably"] * 8),
            created_at=timestamp,
            updated_at=timestamp,
        )
        for index in range(1, 5)
    ]

    output = export_cards(cards, tmp_path / "long-cards", ExportFormat.PDF)

    assert output.read_bytes().startswith(b"%PDF-")


def test_export_rejects_an_empty_selection(tmp_path) -> None:
    with pytest.raises(ExportError, match="Select at least one"):
        export_cards([], tmp_path / "cards.pdf", ExportFormat.PDF)


def test_normalize_export_path_replaces_mismatched_extension(tmp_path) -> None:
    assert normalize_export_path(tmp_path / "cards.txt", ExportFormat.PDF) == (
        tmp_path / "cards.pdf"
    )


def test_export_filename_is_portable_and_uses_selected_extension() -> None:
    assert normalize_export_filename("my cards", ExportFormat.PDF) == "my cards.pdf"
    assert normalize_export_filename("my-cards.pdf", ExportFormat.EXCEL) == "my-cards.xlsx"

    for invalid in ("", "../cards", "folder/cards", "cards\\backup", "CON", "bad:name"):
        with pytest.raises(ValueError):
            normalize_export_filename(invalid, ExportFormat.PDF)

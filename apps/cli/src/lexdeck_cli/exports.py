"""Structured, local exports for selected flashcards."""

from __future__ import annotations

import os
import tempfile
import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime
from enum import StrEnum
from math import floor
from pathlib import Path
from typing import TYPE_CHECKING, cast

import xlsxwriter  # type: ignore[import-untyped]
from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos
from fpdf.errors import FPDFException
from xlsxwriter.exceptions import XlsxWriterException  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from lexdeck_core import Card


class ExportError(RuntimeError):
    """Raised when a selected-card export cannot be completed safely."""


class ExportFormat(StrEnum):
    PDF = "pdf"
    EXCEL = "xlsx"
    TEXT = "txt"

    @property
    def suffix(self) -> str:
        return f".{self.value}"

    @property
    def display_name(self) -> str:
        return {
            self.PDF: "PDF",
            self.EXCEL: "Excel",
            self.TEXT: "Plain text",
        }[self]


_INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*\0')
_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def normalize_export_filename(filename: str, export_format: ExportFormat) -> str:
    """Validate a portable filename and enforce the selected format's extension."""
    cleaned = filename.strip()
    if not cleaned:
        raise ValueError("Enter a file name.")
    if cleaned in {".", ".."} or cleaned.endswith((" ", ".")):
        raise ValueError("Enter a valid file name.")
    if any(character in _INVALID_FILENAME_CHARACTERS for character in cleaned):
        raise ValueError('The file name cannot contain < > : " / \\ | ? or *.')
    normalized = normalize_export_path(Path(cleaned), export_format).name
    stem = Path(normalized).stem
    if not stem or stem.rstrip(" .") != stem or stem.upper() in _RESERVED_FILENAMES:
        raise ValueError("Enter a valid file name.")
    return normalized


def normalize_export_path(path: str | Path, export_format: ExportFormat) -> Path:
    """Expand a user path and enforce the extension selected in the dialog."""
    destination = Path(path).expanduser()
    if destination.suffix.lower() != export_format.suffix:
        destination = destination.with_suffix(export_format.suffix)
    return destination


def export_cards(
    cards: Sequence[Card],
    destination: str | Path,
    export_format: ExportFormat,
    *,
    generated_at: datetime | None = None,
) -> Path:
    """Export cards atomically and return the normalized destination path."""
    if not cards:
        raise ExportError("Select at least one card before exporting.")

    output_path = normalize_export_path(destination, export_format)
    generated_at = generated_at or datetime.now().astimezone()
    writers: dict[ExportFormat, Callable[[Sequence[Card], Path, datetime], None]] = {
        ExportFormat.PDF: _write_pdf,
        ExportFormat.EXCEL: _write_excel,
        ExportFormat.TEXT: _write_text,
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=f".{output_path.stem}-",
            suffix=output_path.suffix,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            writers[export_format](cards, temporary_path, generated_at)
            os.replace(temporary_path, output_path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except (FPDFException, OSError, ValueError, XlsxWriterException) as error:
        raise ExportError(
            f"Could not create {export_format.display_name} export: {error}"
        ) from error

    return output_path


class _LexdeckPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-9)
        self.set_font("Lexdeck", "", 7)
        self.set_text_color(100, 116, 139)
        self.cell(0, 4, f"Page {self.page_no()}", align="R")


def _write_pdf(cards: Sequence[Card], path: Path, _generated_at: datetime) -> None:
    regular_font, bold_font = _find_pdf_fonts()
    pdf = _LexdeckPDF(format="A4")
    pdf.set_title("Lexdeck selected flashcards")
    pdf.set_author("Lexdeck")
    pdf.set_creator("Lexdeck")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_font("Lexdeck", fname=regular_font)
    pdf.add_font("Lexdeck", style="B", fname=bold_font)
    pdf.set_text_shaping(True)
    pdf.add_page()

    pdf.set_font("Lexdeck", "B", 10)
    pdf.set_text_color(15, 23, 42)
    count_label = f"{len(cards)} card{'s' if len(cards) != 1 else ''}"
    pdf.cell(0, 6, count_label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Lexdeck", "B", 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(70, 4, "Content")
    pdf.set_x(pdf.l_margin + 76)
    pdf.cell(0, 4, "Meaning", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    for card in cards:
        _write_pdf_card(pdf, card)

    pdf.output(path)


def _write_pdf_card(pdf: _LexdeckPDF, card: Card) -> None:
    meaning_text = card.meaning or "Not provided."
    prompt_width = 70.0
    meaning_width = pdf.epw - prompt_width - 6
    line_height = 4.6
    row_padding = 1.0
    prompt_lines = _wrap_pdf_text(pdf, card.prompt, width=prompt_width, size=9, bold=True)
    meaning_lines = _wrap_pdf_text(pdf, meaning_text, width=meaning_width, size=8.5)
    total_lines = max(len(prompt_lines), len(meaning_lines))
    start = 0

    while start < total_lines:
        y = pdf.get_y()
        available_lines = floor((pdf.page_break_trigger - y - 2 * row_padding - 0.5) / line_height)
        if available_lines < 1:
            pdf.add_page()
            continue

        end = min(start + available_lines, total_lines)
        for index in range(start, end):
            line_y = y + row_padding + (index - start) * line_height
            if index < len(prompt_lines):
                pdf.set_xy(pdf.l_margin, line_y)
                pdf.set_font("Lexdeck", "B", 9)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(
                    prompt_width,
                    line_height,
                    prompt_lines[index],
                    align=_text_alignment(card.prompt),
                )
            if index < len(meaning_lines):
                pdf.set_xy(pdf.l_margin + prompt_width + 6, line_y)
                pdf.set_font("Lexdeck", "", 8.5)
                pdf.set_text_color(*(71, 85, 105) if card.meaning else (148, 163, 184))
                pdf.cell(
                    meaning_width,
                    line_height,
                    meaning_lines[index],
                    align=_text_alignment(meaning_text),
                )

        row_bottom = y + 2 * row_padding + (end - start) * line_height
        if end == total_lines:
            pdf.set_draw_color(226, 232, 240)
            pdf.line(pdf.l_margin, row_bottom, pdf.w - pdf.r_margin, row_bottom)
            pdf.set_y(row_bottom + 0.3)
        else:
            pdf.add_page()
        start = end


def _wrap_pdf_text(
    pdf: _LexdeckPDF, text: str, *, width: float, size: float, bold: bool = False
) -> list[str]:
    pdf.set_font("Lexdeck", "B" if bold else "", size)
    lines = pdf.multi_cell(
        width,
        4.6,
        text,
        align=_text_alignment(text),
        dry_run=True,
        output=MethodReturnValue.LINES,
    )
    return cast(list[str], lines)


def _find_pdf_fonts() -> tuple[Path, Path]:
    bundled_fonts = Path(__file__).parent / "assets"
    candidates = (
        (
            bundled_fonts / "DejaVuSans.ttf",
            bundled_fonts / "DejaVuSans-Bold.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
            Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    )
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            return regular, bold
    raise ExportError(
        "PDF export needs a Unicode font such as DejaVu Sans, FreeSans, or Arial. "
        "Install one of these fonts, or export as Excel or plain text."
    )


def _write_excel(cards: Sequence[Card], path: Path, _generated_at: datetime) -> None:
    workbook = xlsxwriter.Workbook(path)
    workbook.set_properties(
        {
            "title": "Lexdeck selected flashcards",
            "subject": "Selected English practice cards",
            "author": "Lexdeck",
            "company": "Lexdeck",
            "comments": "Created locally by Lexdeck.",
        }
    )
    worksheet = workbook.add_worksheet("Flashcards")
    worksheet.hide_gridlines(2)
    worksheet.set_zoom(95)
    worksheet.set_tab_color("#2563EB")
    worksheet.set_column("A:A", 46)
    worksheet.set_column("B:B", 62)

    title_format = workbook.add_format(
        {"font_name": "Arial", "font_size": 16, "bold": True, "font_color": "#0F172A"}
    )
    subtitle_format = workbook.add_format(
        {"font_name": "Arial", "font_size": 10, "font_color": "#64748B"}
    )
    header_format = workbook.add_format(
        {
            "font_name": "Arial",
            "font_color": "#FFFFFF",
            "bg_color": "#2563EB",
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 0,
        }
    )
    text_format = workbook.add_format(
        {
            "font_name": "Arial",
            "font_color": "#0F172A",
            "text_wrap": True,
            "valign": "top",
            "reading_order": 1,
            "bottom": 1,
            "bottom_color": "#E2E8F0",
        }
    )
    rtl_text_format = workbook.add_format(
        {
            "font_name": "Arial",
            "font_color": "#0F172A",
            "text_wrap": True,
            "valign": "top",
            "align": "right",
            "reading_order": 2,
            "bottom": 1,
            "bottom_color": "#E2E8F0",
        }
    )
    worksheet.write(1, 0, "Selected flashcards", title_format)
    worksheet.write(
        2,
        0,
        f"{len(cards)} card{'s' if len(cards) != 1 else ''}",
        subtitle_format,
    )

    header_row = 4
    first_data_row = header_row + 1
    for offset, card in enumerate(cards):
        row = first_data_row + offset
        worksheet.write_string(
            row,
            0,
            card.prompt,
            rtl_text_format if _is_rtl(card.prompt) else text_format,
        )
        meaning = card.meaning or ""
        worksheet.write_string(
            row,
            1,
            meaning,
            rtl_text_format if _is_rtl(meaning) else text_format,
        )
        worksheet.set_row(row, _excel_row_height(card.prompt, meaning))

    last_data_row = first_data_row + len(cards) - 1
    worksheet.set_row(header_row, 24)
    worksheet.add_table(
        header_row,
        0,
        last_data_row,
        1,
        {
            "name": "Flashcards",
            "style": "Table Style Medium 2",
            "columns": [
                {"header": "Content", "header_format": header_format},
                {"header": "Meaning", "header_format": header_format},
            ],
        },
    )
    worksheet.freeze_panes(first_data_row, 0)
    worksheet.repeat_rows(header_row)
    worksheet.set_landscape()
    worksheet.set_paper(9)
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(0.35, 0.35, 0.5, 0.5)
    worksheet.print_area(1, 0, last_data_row, 1)
    workbook.close()


def _excel_row_height(prompt: str, meaning: str) -> float:
    content_lines = _estimated_wrapped_lines(prompt, 43)
    meaning_lines = _estimated_wrapped_lines(meaning, 58)
    return float(min(405, max(38, max(content_lines, meaning_lines) * 18 + 16)))


def _estimated_wrapped_lines(text: str, width: int) -> int:
    paragraphs = text.splitlines() or [""]
    return sum(max(1, (_display_width(paragraph) + width - 1) // width) for paragraph in paragraphs)


def _display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"F", "W"} else 1 for character in text
    )


def _write_text(cards: Sequence[Card], path: Path, generated_at: datetime) -> None:
    exported = generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
    lines = [
        "LEXDECK - SELECTED FLASHCARDS",
        f"{len(cards)} card{'s' if len(cards) != 1 else ''} - Exported {exported}",
        "",
    ]
    for index, card in enumerate(cards, start=1):
        lines.extend(
            [
                f"{index}. CONTENT",
                card.prompt,
                "",
                "MEANING",
                card.meaning or "Not provided.",
                "",
                "-" * 72,
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def _text_alignment(value: str) -> str:
    return "R" if _is_rtl(value) else "L"


def _is_rtl(value: str) -> bool:
    for character in value:
        direction = unicodedata.bidirectional(character)
        if direction in {"R", "AL"}:
            return True
        if direction == "L":
            return False
    return False

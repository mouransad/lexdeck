"""Submit selected cards to the operating system's default printer."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from lexdeck_core import Card

from .exports import ExportError, ExportFormat, export_cards


class PrintError(RuntimeError):
    """Raised when a printable PDF cannot be submitted to the system."""


def print_cards(cards: Sequence[Card]) -> str:
    """Render cards as a PDF and submit it to the default system printer."""
    if not cards:
        raise PrintError("Select at least one card to print.")

    if sys.platform == "win32":
        return _print_on_windows(cards)

    lp_command = shutil.which("lp")
    if lp_command is None:
        raise PrintError(
            "No system print service was found. Export the selected cards as PDF, "
            "then print the file from a PDF viewer."
        )

    job_directory, pdf_path = _render_temporary_pdf(cards)
    title = f"Lexdeck - {len(cards)} selected card{'s' if len(cards) != 1 else ''}"
    try:
        result = subprocess.run(
            [lp_command, "-t", title, "--", str(pdf_path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PrintError(
            f"The print job could not be submitted. The printable PDF remains at {pdf_path}."
        ) from error

    if result.returncode != 0:
        reason = result.stderr.strip() or "The system print service rejected the job."
        raise PrintError(f"{reason} The printable PDF remains at {pdf_path}.")

    # CUPS copies submitted files into its spool, so the temporary source is no longer needed.
    shutil.rmtree(job_directory)
    return result.stdout.strip() or "Print job submitted to the default printer."


def _print_on_windows(cards: Sequence[Card]) -> str:
    job_directory, pdf_path = _render_temporary_pdf(cards)
    startfile = getattr(os, "startfile", None)
    if not callable(startfile):
        shutil.rmtree(job_directory)
        raise PrintError(
            "Windows printing is unavailable. Export the selected cards as PDF, "
            "then print the file from a PDF viewer."
        )
    try:
        startfile(str(pdf_path), "print")
    except OSError as error:
        raise PrintError(
            f"Windows could not print the PDF. The printable file remains at {pdf_path}."
        ) from error
    # The associated PDF application may open the file asynchronously, so keep it in temp storage.
    return "Print request sent to the default Windows printer."


def _render_temporary_pdf(cards: Sequence[Card]) -> tuple[Path, Path]:
    job_directory = Path(tempfile.mkdtemp(prefix="lexdeck-print-"))
    pdf_path = job_directory / "selected-flashcards.pdf"
    try:
        export_cards(cards, pdf_path, ExportFormat.PDF)
    except ExportError as error:
        shutil.rmtree(job_directory)
        raise PrintError(str(error)) from error
    return job_directory, pdf_path

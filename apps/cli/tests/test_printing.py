from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from lexdeck_cli import printing
from lexdeck_cli.printing import PrintError
from lexdeck_core import LexdeckService


def test_print_cards_submits_pdf_to_cups_and_cleans_up(tmp_path, monkeypatch) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    cards = [service.add_card("run into", "meet unexpectedly")]
    job_directory = tmp_path / "print-job"
    job_directory.mkdir()
    submitted: list[str] = []

    monkeypatch.setattr(printing.shutil, "which", lambda _: "/usr/bin/lp")
    monkeypatch.setattr(printing.tempfile, "mkdtemp", lambda **_: str(job_directory))

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        submitted.extend(command)
        assert Path(command[-1]).read_bytes().startswith(b"%PDF")
        return subprocess.CompletedProcess(command, 0, "request id is Lexdeck-1\n", "")

    monkeypatch.setattr(printing.subprocess, "run", fake_run)

    message = printing.print_cards(cards)

    assert submitted[:4] == ["/usr/bin/lp", "-t", "Lexdeck - 1 selected card", "--"]
    assert message == "request id is Lexdeck-1"
    assert not job_directory.exists()


def test_print_cards_explains_pdf_fallback_without_print_service(tmp_path, monkeypatch) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    card = service.add_card("meticulous", "very careful")
    monkeypatch.setattr(printing.shutil, "which", lambda _: None)

    with pytest.raises(PrintError, match="Export.*PDF"):
        printing.print_cards([card])


def test_failed_print_job_preserves_rendered_pdf(tmp_path, monkeypatch) -> None:
    service = LexdeckService(tmp_path / "lexdeck.db")
    card = service.add_card("abate", "become less intense")
    job_directory = tmp_path / "failed-print-job"
    job_directory.mkdir()
    monkeypatch.setattr(printing.shutil, "which", lambda _: "/usr/bin/lp")
    monkeypatch.setattr(printing.tempfile, "mkdtemp", lambda **_: str(job_directory))
    monkeypatch.setattr(
        printing.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "printer offline"),
    )

    with pytest.raises(PrintError, match="printer offline") as raised:
        printing.print_cards([card])

    pdf_path = job_directory / "selected-flashcards.pdf"
    assert str(pdf_path) in str(raised.value)
    assert pdf_path.exists()

from __future__ import annotations

import json

from lexdeck_cli import __version__
from lexdeck_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_add_list_and_stats(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LEXDECK_DATA_DIR", str(tmp_path))

    added = runner.invoke(
        app,
        ["add", "meticulous", "--meaning", "دقیق"],
    )
    listed = runner.invoke(app, ["list", "--json"])
    stats = runner.invoke(app, ["stats", "--json"])

    assert added.exit_code == 0, added.output
    cards = json.loads(listed.output)
    assert cards[0]["content"] == "meticulous"
    assert cards[0]["meaning"] == "دقیق"
    assert "deck" not in cards[0]
    assert "tags" not in cards[0]
    assert json.loads(stats.output)["total_cards"] == 1


def test_cli_rejects_missing_content_in_noninteractive_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LEXDECK_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["add"], input="")
    assert result.exit_code != 0


def test_cli_version_does_not_open_the_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LEXDECK_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output == f"Lexdeck {__version__}\n"
    assert not list(tmp_path.iterdir())

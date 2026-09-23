from __future__ import annotations

import json

import pytest
from lexdeck_cli.settings import LexdeckSettings, SettingsError, SettingsStore


def test_settings_default_to_platform_downloads_without_writing(tmp_path) -> None:
    downloads = tmp_path / "Downloads"
    path = tmp_path / "config" / "settings.json"
    store = SettingsStore(path, default_export_directory=downloads)

    settings = store.load()

    assert settings.export_directory == downloads
    assert not path.exists()


def test_settings_are_saved_atomically_and_loaded(tmp_path) -> None:
    path = tmp_path / "config" / "settings.json"
    store = SettingsStore(path, default_export_directory=tmp_path / "Downloads")
    chosen = tmp_path / "exports" / "language"

    saved = store.save(LexdeckSettings(chosen))

    assert saved.export_directory == chosen
    assert store.load() == saved
    assert json.loads(path.read_text(encoding="utf-8")) == {"export_directory": str(chosen)}
    assert list(path.parent.glob("*.tmp")) == []


def test_settings_report_invalid_or_corrupt_values(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"export_directory": 3}', encoding="utf-8")
    store = SettingsStore(path, default_export_directory=tmp_path / "Downloads")

    with pytest.raises(SettingsError, match="Could not read"):
        store.load()


def test_settings_reject_a_file_as_export_directory(tmp_path) -> None:
    existing_file = tmp_path / "not-a-folder"
    existing_file.write_text("content", encoding="utf-8")
    store = SettingsStore(
        tmp_path / "settings.json",
        default_export_directory=tmp_path / "Downloads",
    )

    with pytest.raises(SettingsError, match="points to a file"):
        store.save(LexdeckSettings(existing_file))

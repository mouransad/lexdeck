from __future__ import annotations

from lexdeck_core.paths import config_directory, data_directory


def test_data_and_config_directories_have_independent_overrides(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "data"
    config_path = tmp_path / "config"
    monkeypatch.setenv("LEXDECK_DATA_DIR", str(data_path))
    monkeypatch.setenv("LEXDECK_CONFIG_DIR", str(config_path))

    assert data_directory() == data_path
    assert config_directory() == config_path

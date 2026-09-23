"""Resolve storage paths without coupling the domain to a particular OS."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "lexdeck"
DATA_DIR_ENV = "LEXDECK_DATA_DIR"
CONFIG_DIR_ENV = "LEXDECK_CONFIG_DIR"


def data_directory() -> Path:
    """Return the user data directory, with an override useful for tests and backups."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return PlatformDirs(APP_NAME, appauthor=False).user_data_path


def database_path() -> Path:
    return data_directory() / "lexdeck.db"


def config_directory() -> Path:
    """Return the platform-specific per-user configuration directory."""
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return PlatformDirs(APP_NAME, appauthor=False).user_config_path


def downloads_directory() -> Path:
    """Return the platform-specific Downloads directory."""
    return PlatformDirs(APP_NAME, appauthor=False).user_downloads_path

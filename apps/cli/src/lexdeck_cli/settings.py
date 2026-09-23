"""Persistent interface preferences stored in the platform configuration directory."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

from lexdeck_core.paths import config_directory, downloads_directory


class SettingsError(RuntimeError):
    """Raised when export settings cannot be read, validated, or saved."""


@dataclass(frozen=True, slots=True)
class LexdeckSettings:
    export_directory: Path


def normalize_export_directory(value: str | Path) -> Path:
    """Expand and validate an export-directory value without creating it."""
    raw_value = str(value).strip()
    if not raw_value:
        raise SettingsError("Enter an export folder.")
    directory = Path(raw_value).expanduser()
    if not directory.is_absolute():
        raise SettingsError("Use an absolute folder path, or start it with ~.")
    directory = directory.resolve(strict=False)
    if directory.exists() and not directory.is_dir():
        raise SettingsError("The export folder points to a file, not a directory.")
    return directory


class SettingsStore:
    """Load and atomically save the small set of Lexdeck UI preferences."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        default_export_directory: Path | None = None,
    ) -> None:
        self.path = path or config_directory() / "settings.json"
        self.default_export_directory = normalize_export_directory(
            default_export_directory or downloads_directory()
        )

    def defaults(self) -> LexdeckSettings:
        return LexdeckSettings(export_directory=self.default_export_directory)

    def load(self) -> LexdeckSettings:
        if not self.path.exists():
            return self.defaults()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            raw_directory = payload["export_directory"]
            if not isinstance(raw_directory, str):
                raise TypeError("export_directory must be text")
            directory = normalize_export_directory(raw_directory)
        except (JSONDecodeError, KeyError, OSError, TypeError, SettingsError) as error:
            raise SettingsError(f"Could not read export settings from {self.path}.") from error
        return LexdeckSettings(export_directory=directory)

    def save(self, settings: LexdeckSettings) -> LexdeckSettings:
        normalized = LexdeckSettings(
            export_directory=normalize_export_directory(settings.export_directory)
        )
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.stem}-",
                suffix=".tmp",
                text=True,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(
                    {"export_directory": str(normalized.export_directory)},
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise SettingsError(f"Could not save export settings to {self.path}.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return normalized

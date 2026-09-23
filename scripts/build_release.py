"""Build and smoke-test a self-contained Lexdeck release archive."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

from lexdeck_cli import __version__

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "dist" / "release"


def release_version(tag: str) -> str:
    cli = tomllib.loads((ROOT / "apps/cli/pyproject.toml").read_text())["project"]["version"]
    core = tomllib.loads((ROOT / "packages/core/pyproject.toml").read_text())["project"]["version"]
    if not (cli == core == __version__):
        raise SystemExit("CLI, core, and Python package versions must match before release")
    if tag != f"v{cli}":
        raise SystemExit(f"Tag {tag!r} must match package version v{cli}")
    return cli


def target_name() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    architectures = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
    if system not in {"linux", "darwin", "windows"} or machine not in architectures:
        raise SystemExit(f"Unsupported release target: {system}/{machine}")
    name = "macos" if system == "darwin" else system
    return name, architectures[machine]


def build(tag: str) -> Path:
    version = release_version(tag)
    system, architecture = target_name()
    binary_name = "lexdeck.exe" if system == "windows" else "lexdeck"
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexdeck-build-") as temporary:
        work = Path(temporary)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                "--onefile",
                "--console",
                "--name",
                "lexdeck",
                "--collect-data",
                "lexdeck_cli",
                "--distpath",
                str(work / "dist"),
                "--workpath",
                str(work / "build"),
                "--specpath",
                str(work),
                str(ROOT / "apps/cli/src/lexdeck_cli/__main__.py"),
            ],
            cwd=ROOT,
            check=True,
        )
        binary = work / "dist" / binary_name
        with tempfile.TemporaryDirectory(prefix="lexdeck-smoke-") as data_dir:
            environment = os.environ | {
                "LEXDECK_DATA_DIR": data_dir,
                "LEXDECK_CONFIG_DIR": data_dir,
            }
            version_result = subprocess.run(
                [binary, "--version"], env=environment, text=True, capture_output=True, check=True
            )
            if version_result.stdout.strip() != f"Lexdeck {version}":
                raise SystemExit(f"Unexpected packaged version: {version_result.stdout!r}")
            subprocess.run(
                [binary, "add", "release smoke test", "-m", "works"],
                env=environment,
                check=True,
                capture_output=True,
            )
            listing = subprocess.run(
                [binary, "list", "--json"],
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            if '"content": "release smoke test"' not in listing.stdout:
                raise SystemExit("Packaged CLI did not return the smoke-test card")
        base = f"lexdeck-{tag}-{system}-{architecture}"
        files = {
            binary_name: binary,
            "LICENSE": ROOT / "LICENSE",
            "DEJAVU-LICENSE.txt": ROOT / "apps/cli/src/lexdeck_cli/assets/DEJAVU-LICENSE.txt",
        }
        if system == "windows":
            archive = RELEASE_DIR / f"{base}.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for name, source in files.items():
                    output.write(source, name)
        else:
            archive = RELEASE_DIR / f"{base}.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                for name, source in files.items():
                    output.add(source, arcname=name)
    print(archive)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag, for example v0.1.0")
    parser.add_argument(
        "--check-version", action="store_true", help="Validate tag and versions only"
    )
    args = parser.parse_args()
    if args.check_version:
        release_version(args.tag)
    else:
        build(args.tag)

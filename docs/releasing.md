# Releasing Lexdeck

This is the maintainer's checklist for publishing a GitHub release. Users should
follow the installation instructions in the [README](../README.md).

## Distribution choice

The release assets are PyInstaller one-file executables built on native GitHub
runners. They include Python, application dependencies, and DejaVu fonts so a
user can download an archive, extract it, and run Lexdeck without installing
Python. Building on each target OS is required by PyInstaller. Linux builds use
Ubuntu 22.04 to avoid depending on a newer glibc than necessary. The first
supported targets are Linux x86-64/ARM64, Windows x86-64, and macOS Intel/Apple
Silicon. These are terminal applications, not graphical installers.

The source workspace still builds wheels and sdists for development validation.
The CLI wheel depends on the separate `lexdeck-core` distribution; publishing
just the CLI wheel on GitHub would not provide a simple end-user installation.
Publish both packages to a package index before advertising `pipx` or
`uv tool install` from an index.

One-file executables extract into a temporary directory when launched, so startup
is slower than a one-folder build and Linux systems with a `noexec` temporary
filesystem may not run them. A source install is the fallback for those systems.

The executable archives are unsigned. Apple Gatekeeper and Windows SmartScreen
may warn users. Trusted code signing and Apple notarization require platform
credentials and are a separate future release task.

## Prepare GitHub

1. Create a **public** GitHub repository and push this directory as its `main`
   branch. Do not commit local databases, virtual environments, build outputs,
   or scratch exports; check `git status` before the first push.
2. Enable GitHub Actions for the repository. The release job needs permission to
   write repository contents to create a release. Leave fork pull requests on
   the read-only CI workflow.
3. Let CI pass on `main` before tagging. On a private repository, runner minutes
   and ARM runner availability depend on the GitHub plan.

## Version and tag

Keep these three versions synchronized: `apps/cli/pyproject.toml`,
`packages/core/pyproject.toml`, and `apps/cli/src/lexdeck_cli/__init__.py`.
Update `uv.lock` with `uv lock` after changing package versions. The release
script rejects a tag that differs from the package version, such as `v0.2.0`
for version `0.1.0`.

Before tagging:

```sh
make check
uv run --group release python scripts/build_release.py --tag v0.1.0
```

The local build smoke-tests a standalone executable using a disposable database
and writes an archive under `dist/release/`. It verifies CLI commands, while the
normal tests cover TUI behavior and PDF/Excel/text exports. A local build only
validates the current operating system; the release matrix validates the other
systems on GitHub.

Commit the version change, push `main`, wait for CI, then create and push the
matching tag:

```sh
git tag -a v0.1.0 -m "Lexdeck v0.1.0"
git push origin main
git push origin v0.1.0
```

The tag starts the release workflow. It validates versions, runs `make check`,
builds and smoke-tests each target, creates provenance attestations, and uploads
the assets. Only after every build succeeds does the publish job create a draft
release with all assets and `SHA256SUMS.txt`, then publish it with generated
release notes. Check the resulting release page and download at least one asset.
Do not move an existing release tag to replace a published binary; issue a new
version instead.

## Source and workflow references

- [PyInstaller platform builds](https://pyinstaller.org/en/stable/usage.html)
- [GitHub-hosted runner platforms](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [uv workspace packaging](https://docs.astral.sh/uv/concepts/projects/workspaces/)

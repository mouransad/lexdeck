# Lexdeck documentation

This directory separates documentation by purpose so readers can find the right
level of detail without loading the entire project history.

## Use Lexdeck

- [Project overview and quick start](../README.md)
- [CLI reference](cli.md)
- [Keyboard and TUI reference](keyboard.md)

## Understand and extend Lexdeck

- [Architecture and product decisions](architecture.md)
- [Development workflow](development.md)
- [Release procedure](releasing.md)

## Coding-agent context

The canonical repository instructions are in [`AGENTS.md`](../AGENTS.md).
`CLAUDE.md` and `GEMINI.md` import that file so Claude Code, Gemini CLI, and
Antigravity receive the same rules without duplicated copies drifting apart.

## Documentation ownership

Behavior should be documented next to the audience that needs it:

- User-visible workflows and installation: `README.md`.
- Exact CLI behavior and JSON fields: `docs/cli.md`.
- TUI keys, focus behavior, and modes: `docs/keyboard.md` and in-app `?` help.
- Boundaries, invariants, schema compatibility, and design rationale:
  `docs/architecture.md`.
- Setup, commands, tests, and contribution workflow: `docs/development.md`.
- Durable rules for coding agents: `AGENTS.md`.

When behavior changes, update every affected source in the same change. Do not
document planned behavior as if it already exists; mark future work explicitly.

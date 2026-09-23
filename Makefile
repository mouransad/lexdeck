.PHONY: install run test lint format typecheck build check

install:
	uv sync --all-packages

run:
	uv run --package lexdeck-cli lexdeck

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff check --select I --fix .
	uv run ruff format .

typecheck:
	uv run mypy packages/core/src apps/cli/src

build:
	uv build --all-packages

check: lint
	uv run ruff format --check .
	uv run mypy packages/core/src apps/cli/src
	uv run pytest
	uv build --all-packages

.PHONY: dev run test test-network lint fmt update sync

dev:
	uv run uvicorn app.main:app --reload

run:
	uv run uvicorn app.main:app

test:
	uv run pytest

test-network:
	uv run pytest -m network

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

sync:
	uv sync

# Keep yt-dlp current (sites break; fixes ship in new releases).
update:
	uv lock --upgrade-package yt-dlp
	uv sync

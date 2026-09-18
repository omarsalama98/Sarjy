# The Stop hook (.claude/hooks/verify.sh) runs typecheck and lint. Keep these names.
.PHONY: install typecheck lint test measure dev deploy

install:
	uv sync --extra dev

typecheck:
	uv run mypy app

lint:
	uv run ruff check app tests

fmt:
	uv run ruff format app tests

test:
	uv run pytest -q

# Latency measurement run -> docs/measurements/
measure:
	uv run python -m app.measure

dev:
	uv run uvicorn app.main:app --reload --port 8000

deploy:
	uv run modal deploy modal_app.py

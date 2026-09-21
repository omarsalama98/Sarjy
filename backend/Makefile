# The Stop hook (.claude/hooks/verify.sh) runs typecheck and lint. Keep these names.
.PHONY: install typecheck lint test measure dev deploy build-frontend

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
# Usage: modal app logs sarjy --since 30m --tail 2000 | make measure ARGS="--label deployed-baseline"
#    or: make measure ARGS="--label local /tmp/sarjy.log"
measure:
	uv run python -m app.measure $(ARGS)

dev:
	uv run uvicorn app.main:app --reload --port 8000

# modal_app.py's Image reads the local frontend/dist tree at deploy time
# (add_local_dir) -- it does not know dist/ is stale, so the build is a
# structural prerequisite, not a step someone remembers to run first.
build-frontend:
	cd ../frontend && npm run build

deploy: build-frontend
	uv run modal deploy modal_app.py

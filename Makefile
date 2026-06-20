.PHONY: install server-py build db-pull

install:
	uv sync --project server_py
	npm --prefix client ci

server-py:
	UV_CACHE_DIR=.uv-cache uv run --project server_py uvicorn app:app --app-dir server_py --host 127.0.0.1 --port 8000

build:
	npm --prefix client run build

# Pull production's SQLite DB down to server/anki.db (consistent snapshot).
db-pull:
	./scripts/pull-db.sh

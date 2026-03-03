-include .env
export

.PHONY: install dev kill frontend backend clean migrate makemigration

install:
	cd frontend && npm install
	cd backend && uv sync

kill:
	-lsof -ti :$${BACKEND_PORT:-8000} | xargs kill -9 2>/dev/null || true
	-lsof -ti :$${FRONTEND_PORT:-3000} | xargs kill -9 2>/dev/null || true

dev: kill
	$(MAKE) -j2 frontend backend

frontend:
	cd frontend && npm run dev

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port $${BACKEND_PORT:-8000}

migrate:
	cd backend && uv run alembic upgrade head

makemigration:
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

clean:
	rm -rf frontend/node_modules frontend/dist backend/.venv data/code-chan.db

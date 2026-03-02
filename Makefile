.PHONY: install dev kill frontend backend clean

install:
	cd frontend && npm install
	cd backend && uv sync

kill:
	-lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	-lsof -ti :3000 | xargs kill -9 2>/dev/null || true

dev: kill
	$(MAKE) -j2 frontend backend

frontend:
	cd frontend && npm run dev

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf frontend/node_modules frontend/dist backend/.venv data/code-chan.db

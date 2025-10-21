.PHONY: install run api docker-build docker-run test fmt lint

install:
	python -m venv .venv && . .venv/Scripts/activate && pip install -r requirements.txt

run:
	uvicorn app:app --host 0.0.0.0 --port $${PORT:-8000}

api: run

docker-build:
	docker build -t smartestimator:dev .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env -v $$(pwd)/runs:/app/runs smartestimator:dev

test:
	python -m pytest -q || true

fmt:
	python -m pip install ruff && ruff check . --fix

lint:
	ruff check .

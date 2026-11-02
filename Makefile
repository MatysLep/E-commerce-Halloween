PYTHON := .venv/bin/python
export PYTHONPATH := backend

.PHONY: install init serve worker test lint check build up down
install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.txt
init:
	$(PYTHON) -m shop.cli init
serve:
	$(PYTHON) -m uvicorn shop.api:create_app --factory --host 127.0.0.1 --port 8000
worker:
	$(PYTHON) -m shop.publisher
test:
	$(PYTHON) -m pytest
	node --test tests/cart.test.mjs
lint:
	.venv/bin/ruff check backend scripts tests
	.venv/bin/ruff format --check backend scripts tests
	terraform -chdir=infrastructure fmt -check -recursive
	node --check frontend/app.js
	node --check frontend/auth.js
	npm run format:check
check: lint test
build:
	$(PYTHON) scripts/build.py
up:
	docker compose up --build -d
down:
	docker compose down

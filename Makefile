# Convenience targets. PowerShell equivalents live in scripts/*.ps1.
COMPOSE ?= docker compose
PY      ?= python

.PHONY: help env up down logs ps build test lint k8s-validate kind-up kind-down

help:
	@echo "make env|up|down|logs|ps|build|test|lint|k8s-validate|kind-up|kind-down"

env:  ## create .env from the example (never overwrites)
	@test -f .env || cp .env.example .env
	@echo ".env ready -- change POSTGRES_PASSWORD before exposing anything"

up: env  ## build and start the full stack
	$(COMPOSE) up --build -d
	@echo "UI: http://localhost:$${FRONTEND_PORT:-8080}"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m yamllint -c .yamllint.yml k8s docker-compose.yml docker-compose.override.example.yml
	$(PY) scripts/validate_k8s.py
	cd frontend && npm run lint

k8s-validate:
	$(PY) scripts/validate_k8s.py

kind-up:
	bash scripts/kind-up.sh

kind-down:
	kind delete cluster --name motorsport

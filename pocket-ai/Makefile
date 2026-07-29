.DEFAULT_GOAL := help
UV := uv

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: env
env: ## Set a secret in .env without it hitting your shell history (make env KEY=POCKET_API_KEY)
	@./scripts/set-secret.sh $(or $(KEY),POCKET_API_KEY)

.PHONY: check-auth
check-auth: ## Verify the Pocket key actually works
	@curl -s localhost:8000/api/v1/pocket/status | python3 -m json.tool

.PHONY: install
install: ## Install base + dev dependencies
	$(UV) sync --extra dev

.PHONY: install-all
install-all: ## Install every optional extra (heavy: torch, chromadb)
	$(UV) sync --all-extras

.PHONY: dev
dev: ## Run the API with reload
	$(UV) run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: test
test: ## Run the test suite
	$(UV) run pytest

.PHONY: lint
lint: ## Lint and format-check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

.PHONY: fmt
fmt: ## Auto-format
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

.PHONY: web
web: ## Run the Next.js frontend
	cd frontend && npm run dev

.PHONY: up
up: ## Start Postgres + API via docker compose
	docker compose up -d

.PHONY: down
down: ## Stop docker compose services
	docker compose down

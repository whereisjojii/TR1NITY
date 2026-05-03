.DEFAULT_GOAL := help

# ---------------------------------------------------------------
# TR1NITY top-level Makefile
# ---------------------------------------------------------------
COMPOSE        := docker compose -f deploy/docker-compose.yml
PROJECT_NAME   := tr1nity

.PHONY: help up down restart logs ps build pull clean demo \
        test lint format hooks docs docs-serve

help: ## Show this help
	@echo ""
	@echo "  TR1NITY — Unified SIEM Correlation Platform"
	@echo "  --------------------------------------------"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	    awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[34m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---------------- Stack lifecycle ----------------

up: ## Boot the full Docker Compose stack
	@if [ ! -f deploy/docker-compose.yml ]; then \
	    echo "deploy/docker-compose.yml not present yet (pre-Phase-0). Run 'make help' for the current state."; \
	    exit 1; \
	fi
	$(COMPOSE) up -d

down: ## Stop the stack (volumes preserved)
	@if [ -f deploy/docker-compose.yml ]; then $(COMPOSE) down; fi

restart: down up ## Restart the stack

logs: ## Tail aggregated service logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show running services
	$(COMPOSE) ps

build: ## Build all service images locally
	$(COMPOSE) build

pull: ## Pull upstream images (Wazuh, OpenSearch, Postgres, ...)
	$(COMPOSE) pull

clean: ## Stop the stack and DELETE all volumes (destructive)
	$(COMPOSE) down -v --remove-orphans

# ---------------- Demo / testing ----------------

demo: ## Generate a synthetic Wazuh + firewall + WAF attack chain
	@python3 scripts/demo/synth_attack.py \
	    --base-url $${TR1NITY_INGESTOR_URL:-http://localhost:8001} \
	    $${INGESTOR_AUTH_TOKEN:+--token $$INGESTOR_AUTH_TOKEN}

test: ## Run unit tests across all services
	@set -e; for svc in ingestor correlator ai-assist api; do \
	    if [ -d services/$$svc/tests ]; then \
	        echo "===> services/$$svc"; \
	        ( cd services/$$svc && PYTHONPATH=. pytest -q ); \
	    fi; \
	done

lint: ## Lint all services with ruff
	@set -e; for svc in ingestor correlator ai-assist api; do \
	    if [ -f services/$$svc/pyproject.toml ] || [ -f services/$$svc/requirements.txt ]; then \
	        echo "===> ruff services/$$svc"; \
	        ( cd services/$$svc && ruff check . ); \
	    fi; \
	done

format: ## Auto-format all Python code
	ruff format services/

# ---------------- Dev workflow ----------------

hooks: ## Install pre-commit hooks
	pip install pre-commit
	pre-commit install

# ---------------- Docs ----------------

docs: ## Build the MkDocs site (output: site/)
	@if [ -f mkdocs.yml ]; then mkdocs build; else echo "mkdocs.yml not present yet (pre-Phase-0)."; fi

docs-serve: ## Serve the MkDocs site at http://127.0.0.1:8000
	@if [ -f mkdocs.yml ]; then mkdocs serve; else echo "mkdocs.yml not present yet (pre-Phase-0)."; fi

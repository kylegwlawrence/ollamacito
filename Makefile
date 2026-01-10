.PHONY: help dev up down clean test migrate migrate-up migrate-down backup restore format logs dev-local dev-backend dev-frontend init-db-local test-backend

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Start development environment with hot reload
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

up: ## Start all services in production mode
	docker compose up -d

down: ## Stop all services
	docker compose down

clean: ## Stop all services and remove volumes
	docker compose down -v
	rm -rf backups/*

test: ## Run backend tests
	docker exec -it ollama_backend pytest -v

test-cov: ## Run backend tests with coverage
	docker exec -it ollama_backend pytest --cov=app --cov-report=html --cov-report=term

migrate: ## Create a new database migration (use message="your message")
	docker exec -it ollama_backend alembic revision --autogenerate -m "$(message)"

migrate-up: ## Apply all pending database migrations
	docker exec -it ollama_backend alembic upgrade head

migrate-down: ## Rollback last database migration
	docker exec -it ollama_backend alembic downgrade -1

migrate-history: ## Show migration history
	docker exec -it ollama_backend alembic history

backup: ## Create a manual database backup
	@mkdir -p backups
	@echo "Creating backup..."
	docker exec -t ollama_postgres pg_dump -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) $(shell grep POSTGRES_DB .env | cut -d '=' -f2) > backups/manual_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/ directory"

restore: ## Restore database from backup (use file=backups/backup.sql)
	@if [ -z "$(file)" ]; then \
		echo "Error: Please specify backup file with file=backups/backup.sql"; \
		exit 1; \
	fi
	@echo "Restoring from $(file)..."
	docker exec -i ollama_postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2) < $(file)
	@echo "Restore completed"

format: ## Format code (backend and frontend)
	@echo "Formatting backend..."
	docker exec -it ollama_backend black app/
	@echo "Formatting frontend..."
	docker exec -it ollama_frontend npm run format

lint: ## Lint code
	@echo "Linting backend..."
	docker exec -it ollama_backend ruff check app/
	@echo "Linting frontend..."
	docker exec -it ollama_frontend npm run lint

logs: ## Show logs for all services
	docker compose logs -f

logs-backend: ## Show backend logs
	docker compose logs -f backend

logs-frontend: ## Show frontend logs
	docker compose logs -f frontend

logs-db: ## Show database logs
	docker compose logs -f postgres

shell-backend: ## Open a shell in the backend container
	docker exec -it ollama_backend /bin/bash

shell-db: ## Open a PostgreSQL shell
	docker exec -it ollama_postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2)

build: ## Build all Docker images
	docker compose build

rebuild: ## Rebuild all Docker images without cache
	docker compose build --no-cache

ps: ## Show running containers
	docker compose ps

healthcheck: ## Check health of all services
	@echo "Checking Ollama..."
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "✓ Ollama is running" || echo "✗ Ollama is not running"
	@echo "Checking Backend..."
	@curl -s http://localhost:8000/api/v1/ollama/status > /dev/null && echo "✓ Backend is running" || echo "✗ Backend is not running"
	@echo "Checking Frontend..."
	@curl -s http://localhost:5173 > /dev/null && echo "✓ Frontend is running" || echo "✗ Frontend is not running"
	@echo "Checking Database..."
	@docker exec ollama_postgres pg_isready -U postgres > /dev/null 2>&1 && echo "✓ Database is running" || echo "✗ Database is not running"

# Local Development (Non-Docker) Commands

dev-local: ## Start all services locally (without Docker) - requires PostgreSQL and Ollama running
	@echo "Starting local development environment..."
	@echo ""
	@echo "Prerequisites:"
	@echo "  - PostgreSQL must be running"
	@echo "  - Ollama must be running (ollama serve)"
	@echo "  - .env.local must be configured"
	@echo ""
	@echo "Starting backend and frontend in parallel..."
	@echo "Open http://localhost:5173 in your browser"
	@echo ""
	@bash -c 'cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 & cd frontend && npm run dev'

dev-backend: ## Start only the backend service locally
	@echo "Starting backend on http://localhost:8000"
	@echo "Make sure .env.local is configured with local database settings"
	@cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start only the frontend service locally
	@echo "Starting frontend on http://localhost:5173"
	@cd frontend && npm run dev

init-db-local: ## Initialize local PostgreSQL database
	@bash scripts/init-local-db.sh

backup-local: ## Create a backup of the local database
	@bash scripts/backup-local-db.sh

restore-local: ## Restore from a local database backup (use file=backups/filename)
	@bash scripts/restore-local-db.sh $(file)

test-backend: ## Run backend tests locally
	@cd backend && pytest -v

test-backend-cov: ## Run backend tests with coverage report
	@cd backend && pytest --cov=app --cov-report=html --cov-report=term

migrate-local: ## Create a new database migration (use message="your message")
	@cd backend && alembic revision --autogenerate -m "$(message)"

migrate-up-local: ## Apply all pending database migrations locally
	@cd backend && alembic upgrade head

migrate-down-local: ## Rollback last database migration locally
	@cd backend && alembic downgrade -1

format-local: ## Format code locally (no Docker)
	@echo "Formatting backend..."
	@cd backend && black app/
	@echo "Formatting frontend..."
	@cd frontend && npm run format

lint-local: ## Lint code locally (no Docker)
	@echo "Linting backend..."
	@cd backend && ruff check app/
	@echo "Linting frontend..."
	@cd frontend && npm run lint

shell-db-local: ## Open local PostgreSQL shell
	@psql -U postgres -d ollama_chat

setup-local: ## Complete setup for local development
	@echo "Setting up local development environment..."
	@echo ""
	@echo "Step 1: Installing backend dependencies..."
	@cd backend && pip install -r requirements.txt
	@echo ""
	@echo "Step 2: Installing frontend dependencies..."
	@cd frontend && npm install
	@echo ""
	@echo "Step 3: Initializing database..."
	@bash scripts/init-local-db.sh
	@echo ""
	@echo "Step 4: Creating .env.local..."
	@if [ ! -f .env.local ]; then cp .env.example .env.local; echo "✓ .env.local created from .env.example"; else echo "✓ .env.local already exists"; fi
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "1. Edit .env.local to match your local setup if needed"
	@echo "2. Ensure PostgreSQL is running"
	@echo "3. Ensure Ollama is running (ollama serve)"
	@echo "4. Run: make dev-local"

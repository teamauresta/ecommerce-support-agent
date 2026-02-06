.PHONY: help install dev test lint format migrate run docker-up docker-down clean

# Default target
help:
	@echo "E-Commerce Support Agent - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install production dependencies"
	@echo "  make dev         Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run         Run the API server (hot reload)"
	@echo "  make test        Run all tests"
	@echo "  make test-unit   Run unit tests only"
	@echo "  make test-cov    Run tests with coverage"
	@echo "  make lint        Run linting checks"
	@echo "  make format      Auto-format code"
	@echo ""
	@echo "Database:"
	@echo "  make migrate     Run database migrations"
	@echo "  make migrate-new Create new migration"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   Start all services"
	@echo "  make docker-down Stop all services"
	@echo "  make docker-logs View service logs"
	@echo ""
	@echo "Production:"
	@echo "  make build       Build production Docker image"
	@echo "  make deploy      Deploy to Railway (requires CLI)"

# Setup
install:
	pip install -r requirements.txt

dev: install
	pip install -r requirements-dev.txt
	pre-commit install

# Development
run:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit -v

test-component:
	pytest tests/component -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	black --check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	ruff check src/ tests/ --fix
	black src/ tests/

# Database
migrate:
	alembic upgrade head

migrate-new:
	@read -p "Migration name: " name; \
	alembic revision --autogenerate -m "$$name"

migrate-down:
	alembic downgrade -1

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

# Production
build:
	docker build -t ecommerce-support-agent:latest .

deploy:
	railway up

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete

# Widget
widget-dev:
	cd widget && npm run dev

widget-build:
	cd widget && npm run build

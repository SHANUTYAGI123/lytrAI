.PHONY: up down build logs test clean help

help:
	@echo "Available commands:"
	@echo "  make up      - Start the full stack (backend:8000, frontend:3000) using Docker Compose"
	@echo "  make down    - Stop all running containers"
	@echo "  make build   - Rebuild Docker images"
	@echo "  make logs    - Stream container logs"
	@echo "  make test    - Run backend pytest test suite"
	@echo "  make clean   - Stop containers and remove volumes"

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test:
	cd backend && PYTHONPATH=. pytest -v

clean:
	docker compose down -v

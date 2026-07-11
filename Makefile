.DEFAULT_GOAL := help

# Colors for help output
BLUE   := \033[36m
YELLOW := \033[33m
GREEN  := \033[32m
RESET  := \033[0m

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "Usage: make $(YELLOW)<target>$(RESET)"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

.PHONY: install
install: ## Install all dependencies (production & development) using uv
	uv sync

.PHONY: lock
lock: ## Generate or update the uv lockfile
	uv lock

.PHONY: lint
lint: ## Run Ruff linter checks
	uv run ruff check .

.PHONY: format
format: ## Format Python code using Ruff formatter
	uv run ruff format .

.PHONY: lint-fix
lint-fix: ## Run Ruff linter checks and fix issues automatically
	uv run ruff check . --fix

.PHONY: test
test: ## Run the backend tests using pytest
	uv run pytest

.PHONY: test-cov
test-cov: ## Run the backend tests with coverage report
	uv run pytest --cov=src --cov-report=term-missing

.PHONY: migrations
migrations: ## Generate new Django database migrations
	uv run python src/manage.py makemigrations

.PHONY: migrate
migrate: ## Run pending Django database migrations
	uv run python src/manage.py migrate

.PHONY: shell
shell: ## Open a Django interactive shell
	uv run python src/manage.py shell_plus || uv run python src/manage.py shell

.PHONY: run-django
run-django: ## Start the Django development server
	uv run python src/manage.py runserver 0.0.0.0:9000

.PHONY: run-tailwind
run-tailwind: ## Watch and build Tailwind CSS assets
	npm run watch:css

.PHONY: dev
dev: ## Run both Django and Tailwind servers concurrently
	@echo "$(GREEN)Starting Django and Tailwind CSS watch in parallel...$(RESET)"
	@npx -y concurrently \
		--names "django,tailwind" \
		--prefix-colors "blue,magenta" \
		"make run-django" \
		"make run-tailwind"

.PHONY: docker-build
docker-build: ## Build the Docker containers
	docker compose build

.PHONY: docker-up
docker-up: ## Start the Docker containers in the background
	docker compose up -d

.PHONY: docker-down
docker-down: ## Stop and remove the Docker containers
	docker compose down

.PHONY: docker-logs
docker-logs: ## View the logs of the Docker containers
	docker compose logs -f

.PHONY: clean
clean: ## Remove temporary python cache and build files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov

# Makefile for ranked-elections-analyzer development

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python
PIP := pip
DB_FILE := election_data.db
TEST_DB := test_election.db

.PHONY: help
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Development setup
.PHONY: install
install: ## Install development dependencies
	$(PIP) install -e ".[dev]"

.PHONY: install-hooks
install-hooks: ## Install pre-commit hooks
	$(PYTHON) -m pre_commit install

.PHONY: setup
setup: install install-hooks ## Complete development setup
	@echo "✅ Development environment setup complete!"

# Code quality
.PHONY: format
format: ## Format code with black and isort
	$(PYTHON) -m black src/ scripts/ tests/
	$(PYTHON) -m isort src/ scripts/ tests/

.PHONY: lint
lint: ## Run linting with flake8
	$(PYTHON) -m flake8 src/ scripts/ tests/

.PHONY: security
security: ## Run security checks with bandit
	$(PYTHON) -m bandit -r src/ scripts/ -c pyproject.toml

.PHONY: check
check: format lint security ## Run all code quality checks

# Testing
.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit -v

.PHONY: test-golden
test-golden: ## Run golden dataset tests
	$(PYTHON) -m pytest tests/golden -v

.PHONY: test-all
test-all: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

.PHONY: test-fast
test-fast: ## Run fast tests (unit + smoke)
	$(PYTHON) -m pytest tests/unit -m "unit or smoke" -v --tb=short

.PHONY: test-election-hooks
test-election-hooks: ## Run custom election-specific pre-commit hooks
	$(PYTHON) scripts/pre_commit_hooks.py

# Coverage testing
.PHONY: test-cov
test-cov: ## Run all tests with coverage report
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing tests/

.PHONY: test-cov-html
test-cov-html: ## Generate HTML coverage report
	$(PYTHON) -m pytest --cov=src --cov-report=html tests/
	@echo "Coverage report generated in htmlcov/index.html"

.PHONY: test-cov-unit
test-cov-unit: ## Run unit tests with coverage
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing tests/unit

.PHONY: test-cov-golden
test-cov-golden: ## Run golden tests with coverage
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing tests/golden

# Pre-commit
.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	$(PYTHON) -m pre_commit run --all-files

.PHONY: pre-commit-update
pre-commit-update: ## Update pre-commit hook versions
	$(PYTHON) -m pre_commit autoupdate

# Data processing
.PHONY: process-data
process-data: ## Process CVR data (requires CSV file)
	@if [ -z "$(CSV_FILE)" ]; then \
		echo "Usage: make process-data CSV_FILE=your_file.csv"; \
		exit 1; \
	fi
	$(PYTHON) scripts/process_data.py "$(CSV_FILE)" --db $(DB_FILE) --validate

.PHONY: run-stv
run-stv: ## Run STV tabulation on processed data
	$(PYTHON) scripts/run_stv.py --db $(DB_FILE) --seats 3

.PHONY: verify-results
verify-results: ## Verify results against official data
	@if [ -z "$(OFFICIAL_FILE)" ]; then \
		echo "Usage: make verify-results OFFICIAL_FILE=official_results.csv"; \
		exit 1; \
	fi
	$(PYTHON) scripts/verify_results.py --db $(DB_FILE) --official "$(OFFICIAL_FILE)"

# Web server
.PHONY: server
server: ## Start web server
	$(PYTHON) scripts/start_server.py --db $(DB_FILE)

.PHONY: server-dev
server-dev: ## Start web server in development mode with auto-reload
	$(PYTHON) scripts/start_server.py --db $(DB_FILE) --reload

# Database
.PHONY: clean-db
clean-db: ## Remove database files
	@if [ -f "$(DB_FILE)" ]; then rm "$(DB_FILE)"; echo "Removed $(DB_FILE)"; fi
	@if [ -f "$(TEST_DB)" ]; then rm "$(TEST_DB)"; echo "Removed $(TEST_DB)"; fi

# Testing pipeline
.PHONY: test-pipeline
test-pipeline: ## Test complete data processing pipeline
	$(PYTHON) scripts/test_pipeline.py

# Clean up
.PHONY: clean
clean: clean-db ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# CI/CD simulation
.PHONY: ci
ci: check test-cov test-election-hooks ## Simulate CI pipeline (format, lint, comprehensive test with coverage)
	@echo "✅ CI pipeline completed successfully!"

# Development workflow
.PHONY: dev-test
dev-test: test-fast test-election-hooks ## Quick development test cycle
	@echo "✅ Development tests passed!"

# Documentation
.PHONY: readme
readme: ## Display project README
	@if [ -f "CLAUDE.md" ]; then head -50 CLAUDE.md; else echo "CLAUDE.md not found"; fi

# Help for specific workflows
.PHONY: help-workflows
help-workflows: ## Show common development workflows
	@echo "Common development workflows:"
	@echo "  1. Initial setup:        make setup"
	@echo "  2. Before committing:    make ci"
	@echo "  3. Quick development:    make dev-test"
	@echo "  4. Process new data:     make process-data CSV_FILE=your_file.csv"
	@echo "  5. Start web server:     make server"
	@echo "  6. Clean everything:     make clean"

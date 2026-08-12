.PHONY: lint fmt test test-cov install-test-deps

# Install test dependencies (once, local dev)
install-test-deps:
	pip install -r requirements-test.txt

# L0 — Static analysis
lint:
	ruff check erpnext_dsn/ erpnext_facturx/ tests/
	ruff format --check erpnext_dsn/ erpnext_facturx/ tests/
	mypy erpnext_dsn/erpnext_dsn/ erpnext_facturx/erpnext_facturx/ --ignore-missing-imports

# Auto-fix formatting (local only — never run in CI)
fmt:
	ruff format erpnext_dsn/ erpnext_facturx/ tests/
	ruff check --fix erpnext_dsn/ erpnext_facturx/ tests/

# L1 — Unit tests (no Docker, no network)
test:
	pytest tests/unit/ -v

# L1 — Unit tests with coverage report
test-cov:
	pytest tests/unit/ --cov --cov-report=term-missing --cov-fail-under=70

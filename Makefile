# ═══════════════════════════════════════════════════════════════════════════════
# Milaan (मिलान) — Makefile Shortcuts for Hackathon Evaluation & Demo
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: demo eval test ui audit install clean help

help:
	@echo "Milaan (मिलान) — Track 4 AI Finance Controller"
	@echo ""
	@echo "Available commands:"
	@echo "  make demo     - Run end-to-end 3-way reconciliation on 500+ records"
	@echo "  make eval     - Execute continuous evaluation and safety benchmark"
	@echo "  make test     - Run full pytest test suite (unit + integration + UI)"
	@echo "  make ui       - Launch the interactive web dashboard at http://127.0.0.1:8000"
	@echo "  make audit    - Verify cryptographic SHA-256 hash chain integrity"
	@echo "  make install  - Install package and dependencies in editable mode"
	@echo "  make clean    - Remove build artifacts and temporary databases"

install:
	pip install -e ".[dev]"

demo:
	milaan demo

eval:
	milaan eval

test:
	pytest -v

ui:
	milaan ui

audit:
	milaan audit verify

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage data/generated/*.csv milaan.db audit_trail.jsonl

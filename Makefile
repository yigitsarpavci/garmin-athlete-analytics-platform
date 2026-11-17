.PHONY: run test fetch report clean

PORT ?= 8085

run:
	./scripts/run_app.sh $(PORT)

test:
	python3 -B tests/run_tests.py

fetch:
	./scripts/generate_report.sh --fetch

report:
	./scripts/generate_report.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

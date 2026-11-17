.PHONY: run test fetch clean

PORT ?= 8085

run:
	./scripts/run_app.sh $(PORT)

test:
	python3 -B tests/run_tests.py

fetch:
	node ./scripts/fetch_garmin_data.mjs

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

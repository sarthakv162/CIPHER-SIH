PYTHON ?= .venv/bin/python

.PHONY: check check-all check-real fixtures lint typecheck test

check:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests
	$(PYTHON) -m mypy src
	$(PYTHON) -m pytest tests/unit
	$(PYTHON) -m pytest tests/inv

check-all: check
	$(PYTHON) -m pytest tests/integration

check-real: check-all
	$(PYTHON) -m pytest -m slow

fixtures:
	bash scripts/make_fixtures.sh
	cp tests/fixtures/articles/* data/samples/
	cp tests/fixtures/media/* data/samples/
	cp tests/fixtures/artefacts/* data/samples/

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest tests/unit tests/inv

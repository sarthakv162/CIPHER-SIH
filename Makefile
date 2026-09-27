PYTHON ?= .venv/bin/python

.PHONY: check check-all check-real fixtures lint typecheck test \
	docker-build docker-up docker-down docker-test docker-save docker-load

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

IMAGES ?= rupantar:latest nginx:1.27-alpine

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-test:
	docker build --target test -t rupantar:test .
	docker run --rm rupantar:test

docker-save:
	docker pull nginx:1.27-alpine
	mkdir -p vendor
	docker save $(IMAGES) | gzip > vendor/rupantar-images.tar.gz

docker-load:
	gunzip -c vendor/rupantar-images.tar.gz | docker load

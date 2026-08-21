# Bandcamp Album of the Day — common tasks.
# `make help` lists everything.

.PHONY: help install init-db backfill scrape enrich transform load refresh export test lint notebooks clean

PYTHON ?= python

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package and all extras in editable mode
	$(PYTHON) -m pip install -e ".[db,analysis,dev]"

init-db:  ## Apply schema.sql and views.sql to Postgres
	$(PYTHON) -m bandcamp_aotd init-db

backfill:  ## Load the historic CSV export into the warehouse
	$(PYTHON) -m bandcamp_aotd backfill

scrape:  ## Crawl Bandcamp Daily for new articles
	$(PYTHON) -m bandcamp_aotd scrape

enrich:  ## Attach Spotify catalog metadata
	$(PYTHON) -m bandcamp_aotd enrich

transform:  ## Build the analytics table
	$(PYTHON) -m bandcamp_aotd transform

load:  ## Upsert the analytics table into Postgres
	$(PYTHON) -m bandcamp_aotd load

refresh:  ## The scheduled path: scrape -> enrich -> transform -> load
	$(PYTHON) -m bandcamp_aotd refresh

export:  ## Write the Tableau extract
	$(PYTHON) -m bandcamp_aotd export

test:  ## Run the test suite
	$(PYTHON) -m pytest -q

lint:  ## Lint with ruff
	$(PYTHON) -m ruff check src tests tools

notebooks:  ## Regenerate the notebooks from tools/build_notebooks.py
	$(PYTHON) tools/build_notebooks.py

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ipynb_checkpoints -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache

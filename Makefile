.PHONY: install test lint lint-fix typecheck run

VENV ?= .venv

PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
TY := $(VENV)/bin/ty

ARGS ?=

install:
	@if [ ! -d "$(VENV)" ]; then python3 -m venv "$(VENV)"; fi
	"$(PIP)" install --upgrade pip setuptools wheel
	"$(PIP)" install -e ".[dev]"

test:
	"$(PYTEST)"

lint:
	"$(RUFF)" check

lint-fix:
	"$(RUFF)" check --fix

typecheck:
	"$(TY)" check

run:
	"$(PY)" -m movie_renamer.cli $(ARGS)


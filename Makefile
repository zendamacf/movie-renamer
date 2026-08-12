.PHONY: install test lint lint-fix typecheck run changelog-create changelog-draft release

VENV ?= .venv

PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
TY := $(VENV)/bin/ty
TOWNCRIER := $(VENV)/bin/towncrier

ARGS ?=
NAME ?=
VERSION ?=

install:
	@if [ ! -d "$(VENV)" ]; then python3 -m venv "$(VENV)"; fi
	"$(PIP)" install --upgrade pip setuptools wheel
	"$(PIP)" install -e ".[dev]"

test:
	"$(PYTEST)"

lint:
	"$(RUFF)" check
	"$(RUFF)" format --check

lint-fix:
	"$(RUFF)" check --fix
	"$(RUFF)" format

typecheck:
	"$(TY)" check

run:
	"$(PY)" -m movie_renamer.cli $(ARGS)

changelog-create:
	@test -n "$(NAME)" || (echo "Usage: make changelog-create NAME=123.feature" && exit 1)
	"$(TOWNCRIER)" create "$(NAME)"

changelog-draft:
	@test -n "$(VERSION)" || (echo "Usage: make changelog-draft VERSION=0.1.0" && exit 1)
	"$(TOWNCRIER)" build --draft --version "$(VERSION)"

release:
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=0.1.0" && exit 1)
	./scripts/release.sh "$(VERSION)"


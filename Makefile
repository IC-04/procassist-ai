.PHONY: setup test build-b build-a run-b clean help
.DEFAULT_GOAL := help

VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest

# Interpreter used to CREATE the venv. Override with:  make setup BOOTSTRAP_PY=/path/to/python3.12
# pyproject.toml pins requires-python >= 3.10; `setup` refuses to build a venv on anything older
# rather than silently producing an environment that does not match the declared floor.
BOOTSTRAP_PY ?= $(shell for p in python3.13 python3.12 python3.11 python3.10 python3 python; do \
	  command -v $$p >/dev/null 2>&1 || continue; \
	  $$p -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null \
	    && { command -v $$p; break; }; \
	done)

help:
	@echo "setup    create $(VENV) (needs Python >= 3.10) and install procmine + dev extras"
	@echo "test     run the pytest suite"
	@echo "build-b  build perception + TEKG artifacts for dataset_b"
	@echo "build-a  same for dataset_a; degrades gracefully when it is absent"
	@echo "run-b    full dataset_b run (Phase 0: identical to build-b)"
	@echo "clean    remove build/ and Python caches"

setup:
	@if [ -z "$(BOOTSTRAP_PY)" ]; then \
	  echo "ERROR: no Python >= 3.10 found on PATH."; \
	  echo "       pyproject.toml declares requires-python >= 3.10."; \
	  echo "       Install one (python.org installer, or 'brew install python@3.12'),"; \
	  echo "       or point make at it:  make setup BOOTSTRAP_PY=/path/to/python3.12"; \
	  echo "       Detected interpreters:"; \
	  for p in python3 python; do command -v $$p >/dev/null 2>&1 && \
	    printf '         %s -> ' "$$p" && $$p -V; done; \
	  exit 1; \
	fi
	@echo "Using $(BOOTSTRAP_PY) ($$($(BOOTSTRAP_PY) -V 2>&1))"
	$(BOOTSTRAP_PY) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	@if [ -x "$(PYTEST)" ]; then $(PYTEST) -q; \
	else echo "NOTE: $(VENV) absent — falling back to the ambient interpreter. Run 'make setup' for the pinned environment."; \
	     python3 -m pytest -q; fi

build-b:
	@if [ -x "$(PY)" ]; then $(PY) -m procmine.cli --dataset dataset_b; \
	else python3 -m procmine.cli --dataset dataset_b; fi

build-a:
	@if [ -x "$(PY)" ]; then $(PY) -m procmine.cli --dataset dataset_a; \
	else python3 -m procmine.cli --dataset dataset_a; fi

# ADR-010: this target must succeed with dataset_a/ absent from disk.
run-b: build-b

clean:
	rm -rf build
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache

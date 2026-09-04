.PHONY: help install test lint format eval run docker-build clean

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest

help:
	@echo "HR Agentic Solution — Management Makefile"
	@echo "=========================================="
	@echo "make test         Run automated unit and integration tests"
	@echo "make eval         Execute 4-tier golden evaluation dataset"
	@echo "make run          Launch conversational agent in interactive mode"
	@echo "make check        Run code syntax verification and tests"
	@echo "make docker-build Build hardened production container image"
	@echo "make clean        Remove cache and compiled bytecode artifacts"

test:
	$(PYTEST) tests/ -v

eval:
	$(PYTHON) -m evals.run_eval --dataset evals/golden/golden_agent_eval.evalset.json --config evals/golden/eval_config.json

run:
	$(PYTHON) -m agent.agent --interactive

serve:
	$(PYTHON) -m agent.server

check: test
	$(PYTHON) -m py_compile agent/*.py agent/**/*.py tests/*.py

docker-build:
	docker build -t hr-policy-agent:latest .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

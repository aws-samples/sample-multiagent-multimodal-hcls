UV_VENV_CLEAR ?= 1
.PHONY: install deploy run all setup

# Default target
all: setup install deploy run

# Create virtual environment
setup:
	pip install uv
	@if [ "$(UV_VENV_CLEAR)" = "1" ]; then \
		echo "Clearing existing uv virtual environment..."; \
		rm -rf .venv || true; \
	fi
	uv venv

# Install dependencies and package
install:
	. .venv/bin/activate && uv pip install -e . && uv pip list | grep workshop

deploy:
	. .venv/bin/activate && python deploy.py

local:
	. .venv/bin/activate && python local_mcp_client_agent.py

run:
	. .venv/bin/activate && PYTHONPATH=. python agent.py


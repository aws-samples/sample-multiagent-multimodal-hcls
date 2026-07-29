#!/usr/bin/env python3
"""Interactive configuration for the multi-agent HCLS sample.

Prompts for the account-specific values the agents and frontend need, then
writes ``env`` (loaded by the Python agents) and ``frontend/.env`` (read by the
Vite frontend). Existing values are offered as defaults, so re-running only asks
for what you want to change.

Usage:
    python configure.py                 # configure both backend and frontend
    python configure.py --backend       # only write ./env
    python configure.py --frontend      # only write ./frontend/.env

Runtime ARNs and the AgentCore Memory ID are populated automatically by
deploy.py as resources are created, so you can leave them blank here and fill
them in after deploying.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_ENV = REPO_ROOT / "env"
FRONTEND_ENV = REPO_ROOT / "frontend" / ".env"


class Field:
    """A single prompt: its key, help text, default, and whether it's a secret."""

    def __init__(self, key: str, prompt: str, *, default: str = "", secret: bool = False,
                 required: bool = False):
        self.key = key
        self.prompt = prompt
        self.default = default
        self.secret = secret
        self.required = required


# Backend `env` — consumed by deploy.py, main_agent.py, agent.py, invoke_agent.py.
BACKEND_FIELDS = [
    Field("CLIENT_ID", "Cognito app client ID", required=True),
    Field("USERNAME", "Cognito test username", default="testuser", required=True),
    Field("PASSWORD", "Cognito test user password", secret=True, required=True),
    Field("AGENT_ARN", "Orchestrator runtime ARN (blank until deployed)"),
    Field("PUBMED_AGENT_ARN", "PubMed A2A agent ARN (blank until deployed)"),
    Field("CLINICAL_TRIALS_MCP_ARN", "ClinicalTrials MCP runtime ARN (blank until deployed)"),
    Field("PUBMED_MCP_ARN", "PubMed MCP runtime ARN (blank until deployed)"),
    Field("HEALTHLAKE_MCP_ARN", "HealthLake MCP runtime ARN (blank until deployed)"),
    Field("MEMORY_ID", "AgentCore Memory ID (auto-filled by deploy.py)"),
]

# Frontend `frontend/.env` — read by the Vite app.
FRONTEND_FIELDS = [
    Field("VITE_AWS_REGION", "AWS region", default="us-west-2", required=True),
    Field("VITE_COGNITO_USER_POOL_ID", "Cognito user pool ID", required=True),
    Field("VITE_COGNITO_USER_POOL_CLIENT_ID", "Cognito app client ID", required=True),
    Field("VITE_COGNITO_DOMAIN", "Cognito hosted-UI domain", required=True),
    Field("VITE_AGENT_ARN", "Orchestrator runtime ARN (blank until deployed)"),
]


def read_existing(path: Path) -> dict[str, str]:
    """Parse an existing dotenv-style file into a dict, ignoring comments."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip("'\"")
    return values


def prompt(field: Field, current: str) -> str:
    """Ask for one field, showing the current/default value in brackets."""
    default = current or field.default
    if field.secret:
        shown = "********" if default else "none"
        label = f"{field.prompt} [{shown}]: "
        entered = getpass.getpass(label)
        return entered if entered else default

    shown = default if default else "none"
    entered = input(f"{field.prompt} [{shown}]: ").strip()
    value = entered if entered else default
    if field.required and not value:
        print("  (required — please provide a value)")
        return prompt(field, current)
    return value


def write_env(path: Path, fields: list[Field], quote: bool) -> None:
    """Prompt for each field and write the file, preserving existing values."""
    existing = read_existing(path)
    print(f"\n── {path.relative_to(REPO_ROOT)} ──")
    resolved: dict[str, str] = {}
    for field in fields:
        resolved[field.key] = prompt(field, existing.get(field.key, ""))

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for field in fields:
        val = resolved[field.key]
        if quote and val:
            lines.append(f"{field.key}='{val}'")
        else:
            lines.append(f"{field.key}={val}")
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    print(f"  ✓ wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", action="store_true", help="only write ./env")
    parser.add_argument("--frontend", action="store_true", help="only write ./frontend/.env")
    args = parser.parse_args()

    do_backend = args.backend or not args.frontend
    do_frontend = args.frontend or not args.backend

    print("Interactive configuration — press Enter to keep the shown value.")
    if do_backend:
        # The agents load these with load_dotenv("env"); ARNs use single quotes
        # to match the committed template.
        write_env(BACKEND_ENV, BACKEND_FIELDS, quote=True)
    if do_frontend:
        write_env(FRONTEND_ENV, FRONTEND_FIELDS, quote=False)

    print("\nDone. Next: run `python deploy.py` to deploy the agents, then start")
    print("the frontend with `cd frontend && npm install && npm run dev`.")


if __name__ == "__main__":
    main()

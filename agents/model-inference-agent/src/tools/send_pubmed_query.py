"""
send_pubmed_query — Literature delegation tool.

Delegates PubMed literature search + summarization to the existing
``pubmed_agent_a2a-FtQcQXE310`` AgentCore runtime over A2A, replacing the
in-container ``search_literature`` and ``summarize_context`` tools from the v3
source (Requirements 2.3, 2.4, 2.5, 12.7).

Auth pattern: Cognito bearer token obtained from Workshop_Cognito_Pool
(``us-west-2_EXAMPLE`` / client ``EXAMPLECLIENTID123``) using the
same testuser/password flow the rest of the workshop uses — see
``.discovery/orch_orchestrator.py`` and the ``get_bearer_token`` helper in
``utils/utils.py``.

SECURITY TODO: V1 uses hardcoded workshop credentials for parity with the
existing orchestrator and pubmed agent runtimes (``testuser`` /
``ChangeMe123!``). This is unfortunate but matches the pre-existing workshop
pattern. Production should move to IAM-authed workload identity
(``bedrock-agentcore:workload-identity``) or a secrets-manager-backed lookup;
this is tracked in the product backlog but is out of scope for the V1 SMUS
integration.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, List, Optional
from urllib.parse import quote
from uuid import uuid4

from src.observability import (
    log_pubmed_invocation,
    log_tool_end,
    log_tool_error,
    log_tool_start,
)

TOOL_NAME = "send_pubmed_query"

# ── Workshop defaults (override via env) ─────────────────────

DEFAULT_PUBMED_AGENT_ARN = (
    "arn:aws:bedrock-agentcore:us-west-2:123456789012:"
    "runtime/pubmed_agent_a2a-EXAMPLE"
)
DEFAULT_COGNITO_USER_POOL_ID = "us-west-2_EXAMPLE"
DEFAULT_COGNITO_CLIENT_ID = "EXAMPLECLIENTID123"
DEFAULT_COGNITO_USERNAME = "testuser"
DEFAULT_COGNITO_PASSWORD = "ChangeMe123!"  # noqa: S105 - workshop pattern

DEFAULT_TIMEOUT_SEC = 90


def _get_bearer_token(
    client_id: str,
    username: str,
    password: str,
    region: Optional[str] = None,
) -> Optional[str]:
    """Obtain a Cognito bearer token via USER_PASSWORD_AUTH.

    Mirrors the helper in ``utils/utils.py`` so this module doesn't have to
    reach outside the ``model-inference-agent/`` directory at import time.
    """
    import boto3  # lazy so tests can import without boto3 set up

    if not region:
        region = boto3.Session().region_name or "us-west-2"

    cognito = boto3.client("cognito-idp", region_name=region)
    try:
        auth = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        return auth["AuthenticationResult"]["AccessToken"]
    except Exception:
        return None


def _build_prompt(
    disease: str, risk_factors: List[str], max_results: int
) -> str:
    """Compose a natural-language prompt for the PubMed specialist agent."""
    parts = [f"Search PubMed for {max_results} recent papers on {disease}"]
    if risk_factors:
        rf = ", ".join([str(f) for f in risk_factors[:5]])
        parts.append(f"with particular attention to risk factors: {rf}")
    parts.append(
        "Return the title, PMID, and a short abstract excerpt for each paper, "
        "and end with a 2-3 sentence synthesis of the evidence."
    )
    return ". ".join(parts) + "."


def _format_a2a_response(response: Any) -> str:
    """Extract the textual payload from an A2A response object."""
    try:
        # Message objects
        if hasattr(response, "parts") and response.parts:
            part = response.parts[0]
            if hasattr(part, "text"):
                return part.text
            if hasattr(part, "root") and hasattr(part.root, "text"):
                return part.root.text

        # Task objects with artifacts
        if hasattr(response, "artifacts") and response.artifacts:
            artifact = response.artifacts[0]
            if hasattr(artifact, "parts") and artifact.parts:
                p0 = artifact.parts[0]
                if hasattr(p0, "root") and hasattr(p0.root, "text"):
                    return p0.root.text
                if hasattr(p0, "text"):
                    return p0.text

        # Fallback: iterate history messages
        if hasattr(response, "history") and response.history:
            agent_messages: List[str] = []
            for msg in response.history:
                role = getattr(msg, "role", None)
                role_val = getattr(role, "value", None) if role else None
                if role_val == "agent" and getattr(msg, "parts", None):
                    p = msg.parts[0]
                    if hasattr(p, "root") and hasattr(p.root, "text"):
                        agent_messages.append(p.root.text)
                    elif hasattr(p, "text"):
                        agent_messages.append(p.text)
            if agent_messages:
                return "".join(agent_messages)

        return str(response)
    except Exception:
        return str(response)


async def _send_a2a(prompt: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> str:
    """Dispatch a prompt to the PubMed agent via A2A and return its text."""
    # Lazy imports so the module stays import-safe in minimal test envs.
    import httpx
    from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
    from a2a.types import Message, Part, Role, TextPart

    agent_arn = os.environ.get("PUBMED_AGENT_ARN", DEFAULT_PUBMED_AGENT_ARN)
    client_id = os.environ.get("COGNITO_CLIENT_ID", DEFAULT_COGNITO_CLIENT_ID)
    username = os.environ.get("COGNITO_USERNAME", DEFAULT_COGNITO_USERNAME)
    password = os.environ.get("COGNITO_PASSWORD", DEFAULT_COGNITO_PASSWORD)
    region = os.environ.get("AWS_REGION", "us-west-2")

    token = _get_bearer_token(client_id, username, password, region)
    if not token:
        raise RuntimeError(
            "Failed to obtain Cognito bearer token for PubMed agent"
        )

    escaped = quote(agent_arn, safe="")
    runtime_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{escaped}/invocations/"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid4()),
    }

    async with httpx.AsyncClient(timeout=timeout_sec, headers=headers) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=runtime_url)
        card = await resolver.get_agent_card()
        factory = ClientFactory(ClientConfig(httpx_client=http, streaming=False))
        client = factory.create(card)

        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(kind="text", text=prompt))],
            message_id=uuid4().hex,
        )

        last_text = ""
        async for event in client.send_message(msg):
            if isinstance(event, Message):
                last_text = _format_a2a_response(event)
            elif isinstance(event, tuple) and len(event) == 2:
                task, _update = event
                last_text = _format_a2a_response(task)
            else:
                last_text = _format_a2a_response(event)
        return last_text or ""


def send_pubmed_query(
    disease: str,
    risk_factors: Optional[List[str]] = None,
    max_results: int = 5,
) -> dict:
    """Delegate a literature query to the PubMed agent over A2A.

    Returns one of:
      * {"articles": [...], "summary": str, "raw_response": str}
      * {"error_code": str, "message": str}

    Error codes:
      * MISSING_FIELD       — disease argument missing/empty
      * PUBMED_UNAVAILABLE  — A2A call failed (timeout, auth, network)
    """
    start = time.time()
    risk_factors = risk_factors or []

    log_tool_start(TOOL_NAME, disease=disease, risk_factor_count=len(risk_factors))
    log_pubmed_invocation(disease, len(risk_factors))

    if not disease:
        err = {"error_code": "MISSING_FIELD", "message": "disease is required"}
        log_tool_end(
            TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field"
        )
        return err

    prompt = _build_prompt(disease, risk_factors, max_results)

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're inside an already-running loop (e.g. under async
                # Strands Agent), schedule in a fresh loop via run_in_executor.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(asyncio.run, _send_a2a(prompt))
                    text = fut.result()
            else:
                text = loop.run_until_complete(_send_a2a(prompt))
        except RuntimeError:
            text = asyncio.run(_send_a2a(prompt))
    except Exception as exc:
        log_tool_error(
            TOOL_NAME, exc, (time.time() - start) * 1000,
            disease=disease,
        )
        return {
            "error_code": "PUBMED_UNAVAILABLE",
            "message": (
                f"PubMed agent call failed: {type(exc).__name__}: {exc}"
            ),
        }

    result = {
        # The PubMed agent returns free-form text; the orchestrator/LLM
        # can extract articles from it. We preserve the raw response and
        # provide a ``summary`` field for convenience.
        "articles": [],
        "summary": text,
        "raw_response": text,
    }
    log_tool_end(
        TOOL_NAME, (time.time() - start) * 1000,
        disease=disease, response_len=len(text),
    )
    return result

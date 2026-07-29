"""
Property-based tests for the Literature_Delegation_Tool ``send_pubmed_query``.

Uses a fully mocked A2A client so no real network traffic leaves the test
runner (Requirement 8.14). In particular:

* The Cognito ``initiate_auth`` call is monkeypatched to return a synthetic
  token — ``boto3`` is never imported in production mode.
* The internal ``_send_a2a`` coroutine is replaced with an ``AsyncMock`` that
  returns the canned response text for the currently-generated prompt.

**Validates: Requirements 8.14**
"""

from __future__ import annotations

import socket
from typing import List

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import importlib

# Load the module directly — can't use ``import src.tools.send_pubmed_query``
# because ``src.tools.__init__`` re-exports a function of the same name, which
# shadows the submodule attribute when bound via ``as mod``.
mod = importlib.import_module("src.tools.send_pubmed_query")
send_pubmed_query = mod.send_pubmed_query


# ── Network guard ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Fail fast if any test opens a real socket (Requirement 8.14)."""

    def _deny(*args, **kwargs):  # pragma: no cover - defensive
        raise RuntimeError(
            "Network access is blocked in send_pubmed_query PBT — "
            "the A2A client must be mocked."
        )

    monkeypatch.setattr(socket, "create_connection", _deny)


# ── Hypothesis strategies ────────────────────────────────────

diseases = st.sampled_from(
    [
        "Stroke",
        "Hypertension",
        "Coronary Heart Disease",
        "Alzheimer's Disease",
    ]
)

risk_factor_tokens = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz _-",
    min_size=2,
    max_size=20,
)

risk_factor_lists = st.lists(
    risk_factor_tokens, min_size=0, max_size=8
).map(lambda xs: [x.strip() for x in xs if x.strip()])

max_results_values = st.integers(min_value=1, max_value=10)


# ── Helpers ──────────────────────────────────────────────────

CANNED_RESPONSE = (
    "Title: A synthetic PubMed summary\n"
    "PMID: 12345\n"
    "Abstract excerpt: placeholder from the mocked A2A client."
)


@pytest.fixture
def mocked_a2a(monkeypatch):
    """Patch the internal async A2A send + the Cognito token helper."""
    call_log: List[dict] = []

    async def _fake_send_a2a(prompt, timeout_sec=90):
        call_log.append({"prompt": prompt, "timeout_sec": timeout_sec})
        return CANNED_RESPONSE

    monkeypatch.setattr(mod, "_send_a2a", _fake_send_a2a)
    monkeypatch.setattr(
        mod,
        "_get_bearer_token",
        lambda *a, **k: "fake-token",
    )
    return call_log


# ── Property: happy path ─────────────────────────────────────

@settings(
    max_examples=75,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    disease=diseases,
    risk_factors=risk_factor_lists,
    max_results=max_results_values,
)
def test_send_pubmed_query_returns_mocked_summary(
    mocked_a2a, disease, risk_factors, max_results
):
    """For any valid input, ``send_pubmed_query`` returns the canned response
    from the mocked A2A client in ``summary`` and ``raw_response``, and
    records exactly one A2A call."""
    mocked_a2a.clear()

    result = mod.send_pubmed_query(
        disease=disease,
        risk_factors=risk_factors,
        max_results=max_results,
    )

    assert isinstance(result, dict)
    assert result.get("error_code") is None, result
    assert result["summary"] == CANNED_RESPONSE
    assert result["raw_response"] == CANNED_RESPONSE
    assert result["articles"] == []  # articles are embedded in text for V1

    assert len(mocked_a2a) == 1
    sent = mocked_a2a[0]["prompt"]
    # Prompt should mention the disease and the requested result count.
    assert disease in sent
    assert str(max_results) in sent
    if risk_factors:
        # At most 5 risk factors may be surfaced in the prompt (see
        # ``_build_prompt``). Each surfaced factor must appear verbatim.
        for rf in risk_factors[:5]:
            assert rf in sent


# ── Property: missing field error shape ──────────────────────

@settings(max_examples=10, deadline=None)
@given(empty=st.sampled_from(["", None]))
def test_missing_disease_returns_structured_error(empty):
    """Empty or None ``disease`` yields a ``MISSING_FIELD`` structured error
    without hitting the A2A client."""
    # No patching needed — the tool short-circuits before any network path.
    result = mod.send_pubmed_query(disease=empty or "")
    assert result["error_code"] == "MISSING_FIELD"


# ── Property: A2A failure surfaces as PUBMED_UNAVAILABLE ─────

def test_a2a_failure_is_reported_as_pubmed_unavailable(monkeypatch):
    async def _boom(prompt, timeout_sec=90):
        raise RuntimeError("A2A transport blew up")

    monkeypatch.setattr(mod, "_send_a2a", _boom)
    monkeypatch.setattr(mod, "_get_bearer_token", lambda *a, **k: "fake")

    result = mod.send_pubmed_query(disease="Stroke")
    assert result["error_code"] == "PUBMED_UNAVAILABLE"
    assert "A2A transport blew up" in result["message"]

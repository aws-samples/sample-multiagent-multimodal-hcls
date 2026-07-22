"""
Model Inference Agent — AgentCore Runtime entrypoint (A2A server).

Exposes a Strands Agent with 6 in-container tools over the A2A protocol so the
workshop orchestrator can invoke it the same way it invokes pubmed_agent_a2a.

Tools (Req 2.1–2.9, 12.7):
    Pipeline (5):
        parse_query, load_patient_data, select_model,
        run_inference, format_response
    Literature delegation (1):
        send_pubmed_query — calls the existing pubmed_agent_a2a runtime

No AWS Lambda functions are invoked; the five pipeline tools run in-process
and ``run_inference`` calls SageMaker real-time endpoints directly.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import uvicorn
from fastapi import FastAPI
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer

from src.tools.format_response import format_response as _format_response
from src.tools.load_patient_data import load_patient_data as _load_patient_data
from src.tools.parse_query import parse_query as _parse_query
from src.tools.run_inference import run_inference as _run_inference
from src.tools.select_model import select_model as _select_model
from src.tools.send_pubmed_query import send_pubmed_query as _send_pubmed_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AgentCore Runtime fronts the container at this URL/port.
RUNTIME_URL = os.environ.get("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "9000"))

SYSTEM_PROMPT = """You are the Model Inference Agent, a healthcare ML inference \
assistant that predicts disease likelihood using trained models and optionally \
grounds the prediction in PubMed literature.

FOR DISEASE-PREDICTION QUERIES \
(e.g., "What is the likelihood of patient X having stroke?"):
  - Call predict_disease with the full query. It runs the complete pipeline \
    (parse → load → select → infer → format) in one step and returns the \
    structured prediction.

OPTIONAL evidence step (one call only):
  - If the user wants supporting literature, call send_pubmed_query ONCE with \
    the disease and top contributing factors from the prediction.

FOR LITERATURE-ONLY QUERIES \
(e.g., "Tell me about hypertension risk factors"):
  - Call send_pubmed_query ONCE. Do not run the prediction pipeline.

CRITICAL RULES:
  - NEVER predict disease likelihood from text alone — always use predict_disease.
  - NEVER call PubMed directly; always delegate via send_pubmed_query.
  - If a tool returns {"error_code": ..., "message": ...}, surface it verbatim \
    and STOP.
  - Always include the disclaimer text from predict_disease verbatim.

SUPPORTED DISEASES: Hypertension, Stroke, Coronary Heart Disease, Alzheimer's.
"""


# ── Strands @tool wrappers — direct calls to in-container impls ───────

@tool
def parse_query(query: str) -> dict:
    """Extract disease target and patient ID from a natural language query."""
    return _parse_query(query)


@tool
def load_patient_data(patient_id: str, disease_target: str) -> dict:
    """Load patient data from S3 and return the preprocessed feature vector."""
    return _load_patient_data(patient_id, disease_target)


@tool
def select_model(disease_target: str) -> dict:
    """Select the best primary and secondary model for a disease."""
    return _select_model(disease_target)


@tool
def run_inference(
    feature_vector: list,
    feature_names: list,
    disease_target: str,
    primary_model: str,
    secondary_model: Optional[str] = None,
) -> dict:
    """Run dual-model inference via SageMaker real-time endpoints."""
    return _run_inference(
        feature_vector,
        feature_names,
        disease_target,
        primary_model,
        secondary_model,
    )


@tool
def format_response(
    patient_id: str,
    disease_display: str,
    primary: dict,
    secondary: Optional[dict] = None,
    primary_f1: float = 0.0,
    secondary_f1: Optional[float] = None,
) -> dict:
    """Build structured response with confidence, consistency, and disclaimer."""
    return _format_response(
        patient_id, disease_display, primary, secondary, primary_f1, secondary_f1
    )


@tool
def send_pubmed_query(
    disease: str,
    risk_factors: Optional[List[str]] = None,
    max_results: int = 5,
) -> dict:
    """Delegate a literature query to the PubMed A2A specialist agent.

    This tool MUST be used for any literature or evidence need instead of
    performing a PubMed search or Bedrock summarization inside the agent.
    """
    return _send_pubmed_query(disease, risk_factors, max_results)


@tool
def predict_disease(query: str) -> dict:
    """Run the full disease-prediction pipeline for a patient query.

    Takes a natural language query like "What is the likelihood of patient
    0074596f having stroke?" and runs the complete 5-step pipeline:
    parse_query → load_patient_data → select_model → run_inference → format_response.

    Returns the final structured prediction with probability, confidence,
    consistency, contributing factors, and disclaimer.
    """
    from src.config import BENCHMARK_F1

    # Step 1: Parse
    parsed = _parse_query(query)
    if "error_code" in parsed:
        return parsed

    patient_id = parsed["patient_id"]
    disease_target = parsed["disease_target"]
    disease_display = parsed["disease_display"]

    # Step 2: Load patient data
    data = _load_patient_data(patient_id, disease_target)
    if "error_code" in data:
        return data

    # Step 3: Select model
    model_info = _select_model(disease_target)
    if "error_code" in model_info:
        return model_info

    primary_model = model_info["primary"]
    secondary_model = model_info.get("secondary")

    # Step 4: Run inference (parallel via ThreadPoolExecutor)
    inference = _run_inference(
        data["feature_vector"], data["feature_names"],
        disease_target, primary_model, secondary_model,
    )
    if "error_code" in inference:
        return inference

    # Step 5: Format response
    f1_scores = BENCHMARK_F1.get(disease_target, {})
    result = _format_response(
        patient_id, disease_display,
        inference["primary"],
        inference.get("secondary"),
        f1_scores.get(primary_model, 0.0),
        f1_scores.get(secondary_model) if secondary_model else None,
    )
    return result


TOOLS = [
    predict_disease,
    send_pubmed_query,
]


# ── Build the Strands Agent + A2A server ──────────────────────────────

agent = Agent(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    name="predict_disease_likelihood",
    description=(
        "Predicts disease likelihood for a given patient using trained "
        "AutoGluon and TabPFN models, and optionally grounds the result in "
        "PubMed literature via the send_pubmed_query delegation tool. "
        "Supported diseases: Hypertension, Stroke, Coronary Heart Disease, "
        "Alzheimer's."
    ),
)

# A2AServer wraps the Strands agent and publishes `.well-known/agent-card.json`
# at the root URL. The agent card is auto-derived from the Agent's name,
# description, and tool list (matches the existing pubmed_agent_a2a pattern).
a2a_server = A2AServer(
    agent=agent,
    http_url=RUNTIME_URL,
    serve_at_root=True,
)

# Build the FastAPI app: mount A2A at the root so
# `https://<runtime>/.well-known/agent-card.json` resolves, and keep a
# plain /ping so AgentCore's platform health check passes.
app = FastAPI()


@app.get("/ping")
def ping() -> dict:
    return {"status": "healthy"}


app.mount("/", a2a_server.to_fastapi_app())


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)

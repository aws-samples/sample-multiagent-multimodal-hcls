"""
Shared configuration for Healthcare ML Inference Agent V2.

Ported from model_inference_agent/config.py with added AWS resource config.
Disease configs, benchmark scores, and thresholds are identical to v1.
"""

import os

# ── AWS Resource Configuration (env-driven) ───────────────────

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
S3_BUCKET = os.environ.get("MOSAIC_S3_BUCKET", "healthcare-agent-v2")
S3_DATA_PREFIX = os.environ.get("MOSAIC_S3_DATA_PREFIX", "data/")
S3_MODELS_PREFIX = "models/"
S3_RESULTS_PREFIX = "results/"

SAGEMAKER_AUTOGLUON_ENDPOINT = os.environ.get(
    "SAGEMAKER_AUTOGLUON_ENDPOINT", "healthcare-autogluon"
)
SAGEMAKER_TABPFN_ENDPOINT = os.environ.get(
    "SAGEMAKER_TABPFN_ENDPOINT", "healthcare-tabpfn"
)

AGENTCORE_GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL", "")
AGENTCORE_MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")

# PubMed specialist agent (used by send_pubmed_query Literature_Delegation_Tool).
# Requirements 2.3, 2.4, 2.5, 12.7 — MIA_Runtime must NOT call PubMed directly.
PUBMED_AGENT_ARN = os.environ.get(
    "PUBMED_AGENT_ARN",
    "arn:aws:bedrock-agentcore:us-west-2:123456789012:"
    "runtime/pubmed_agent_a2a-EXAMPLE",
)


# ── Disease Configuration (identical to v1) ───────────────────

DISEASE_CODES = {
    "alzheimers_prediction": "26929004",
    "coronary_heart_disease_prediction": "53741008",
    "stroke_prediction": "230690007",
    "hypertension_prediction": "59621000",
}

DISEASE_CONFIG = {
    "hypertension_prediction": {
        "snomed_code": "59621000",
        "display_name": "Hypertension",
        "aliases": ["hypertension", "high blood pressure", "htn"],
        "primary_model": "autogluon",
        "optimal_seed": 11,
    },
    "stroke_prediction": {
        "snomed_code": "230690007",
        "display_name": "Stroke",
        "aliases": ["stroke", "cerebrovascular accident", "cva"],
        "primary_model": "autogluon",
        "optimal_seed": 30,
    },
    "coronary_heart_disease_prediction": {
        "snomed_code": "53741008",
        "display_name": "Coronary Heart Disease",
        "aliases": [
            "coronary heart disease", "chd",
            "coronary artery disease", "cad", "heart disease",
        ],
        "primary_model": "autogluon",
        "optimal_seed": 2,
    },
    "alzheimers_prediction": {
        "snomed_code": "26929004",
        "display_name": "Alzheimer's Disease",
        "aliases": ["alzheimer", "alzheimers", "alzheimer's", "alzheimer's disease"],
        "primary_model": "tabpfn",
        "optimal_seed": 36,
    },
}

# Benchmark F1 scores (combined modality)
BENCHMARK_F1 = {
    "hypertension_prediction":            {"autogluon": 0.909, "tabpfn": 0.833},
    "stroke_prediction":                  {"autogluon": 1.000, "tabpfn": 1.000},
    "coronary_heart_disease_prediction":  {"autogluon": 0.667, "tabpfn": 0.000},
    "alzheimers_prediction":              {"autogluon": 0.400, "tabpfn": 0.857},
}

# Build alias → disease_target lookup
SUPPORTED_DISEASES = {}
for _target, _cfg in DISEASE_CONFIG.items():
    for _alias in _cfg["aliases"]:
        SUPPORTED_DISEASES[_alias.lower()] = _target

# ── Preprocessing Column Drops (identical to v1) ──────────────

CLINICAL_DROP_COLS = [
    "diagnosisDescription", "diagnosisCode", "onsetdatetime",
    "name", "addressline", "city", "state", "country",
    "latitude", "longitude",
]
GENOMIC_DROP_COLS = ["diagnosisDescription", "diagnosisCode"]
IMAGING_DROP_COLS = ["diagnosisDescription", "diagnosisCode"]

# ── Confidence & Consistency Thresholds ───────────────────────

CONFIDENCE_THRESHOLDS = {"high": 0.75, "medium": 0.50}
CONSISTENCY_THRESHOLD = 0.15

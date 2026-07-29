"""
Shared data models for Healthcare ML Inference Agent V2.

Ported from model_inference_agent/agent.py dataclasses with JSON
serialization support for Lambda I/O.
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


@dataclass
class ParsedQuery:
    disease_target: str
    disease_display: str
    patient_id: str
    intent: str = "probability"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=NumpyEncoder)


@dataclass
class ModelSelection:
    primary: str
    secondary: Optional[str]
    primary_f1: float
    secondary_f1: Optional[float]
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=NumpyEncoder)


@dataclass
class PredictionResult:
    model_name: str
    probability: float
    feature_importance: Optional[Dict[str, float]] = None
    inference_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=NumpyEncoder)


@dataclass
class InferenceResponse:
    patient_id: str
    disease: str
    primary_model: str
    primary_probability: float
    secondary_model: Optional[str] = None
    secondary_probability: Optional[float] = None
    confidence: str = "LOW"
    consistency: Optional[str] = None
    contributing_factors: List[str] = field(default_factory=list)
    disclaimer: str = ""
    summary: str = ""
    model_evaluation: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=NumpyEncoder)

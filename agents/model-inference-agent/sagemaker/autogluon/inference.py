"""
SageMaker BYO Container — AutoGluon inference server.
Flask app serving /ping and /invocations endpoints.
"""

import os
import json
import logging
import traceback

import pandas as pd
from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
_predictor_cache = {}


def _get_predictor(disease_target):
    from autogluon.tabular import TabularPredictor
    if disease_target not in _predictor_cache:
        path = os.path.join(MODEL_DIR, disease_target)
        logger.info(f"Loading AutoGluon predictor from {path}")
        _predictor_cache[disease_target] = TabularPredictor.load(
            path, verbosity=0, require_py_version_match=False, require_version_match=False
        )
    return _predictor_cache[disease_target]


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200


@app.route("/invocations", methods=["POST"])
def invoke():
    try:
        payload = request.get_json(force=True)
        feature_vector = payload["feature_vector"]
        feature_names = payload["feature_names"]
        disease_target = payload["disease_target"]

        # Reconstruct DataFrame matching the training format.
        # The preprocessing pipeline converts all values to str with .astype(str),
        # so the model expects string values. JSON serialization preserves this.
        df = pd.DataFrame(feature_vector, columns=feature_names)

        # Convert numeric-looking strings back to their original str representation
        # (AutoGluon was trained on .astype(str) data, so "0" should stay as "0")
        df = df.astype(str)

        # Remove curly braces (matching v1 preprocessing: .replace({"{": "", "}": ""}, regex=True))
        df = df.replace({"{": "", "}": ""}, regex=True)

        predictor = _get_predictor(disease_target)
        X = df.drop(columns=[disease_target], errors="ignore")

        logger.info(f"Predicting {disease_target} with {X.shape[1]} features, dtypes: {X.dtypes.value_counts().to_dict()}")

        proba = predictor.predict_proba(X)

        # Get positive class probability - try both string and int keys
        if "1" in proba.columns:
            pos_prob = float(proba.iloc[0]["1"])
        elif 1 in proba.columns:
            pos_prob = float(proba.iloc[0][1])
        else:
            # Fallback: take the last column (usually positive class)
            pos_prob = float(proba.iloc[0].iloc[-1])

        logger.info(f"Prediction: {pos_prob:.4f}, columns: {list(proba.columns)}")

        importance = {}
        try:
            fi = predictor.feature_importance(X, silent=True)
            if fi is not None and len(fi) > 0:
                top = fi.head(5)
                importance = {c: round(float(v), 4) for c, v in zip(top.index, top["importance"])}
        except Exception as e:
            logger.warning(f"Feature importance failed: {e}")

        return jsonify({
            "probability": round(pos_prob, 4),
            "feature_importance": importance or None,
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

"""
SageMaker BYO Container — TabPFN inference server.
Flask app serving /ping and /invocations endpoints.
"""

import os
import json
import pickle
import logging
import traceback

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
_bundle_cache = {}


def _get_bundle(disease_target):
    if disease_target not in _bundle_cache:
        path = os.path.join(MODEL_DIR, disease_target, "training_data.pkl")
        logger.info(f"Loading TabPFN bundle from {path}")
        with open(path, "rb") as f:
            _bundle_cache[disease_target] = pickle.load(f)
    return _bundle_cache[disease_target]


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200


@app.route("/invocations", methods=["POST"])
def invoke():
    try:
        from tabpfn import TabPFNClassifier

        payload = request.get_json(force=True)
        feature_vector = payload["feature_vector"]
        feature_names = payload["feature_names"]
        disease_target = payload["disease_target"]

        df = pd.DataFrame(feature_vector, columns=feature_names)
        bundle = _get_bundle(disease_target)

        X_train = bundle["X_train"]
        y_train = bundle["y_train"]
        cat_indices = bundle.get("cat_indices", [])
        encoders = bundle.get("encoders", {})
        col_names = bundle["column_names"]

        X = df.drop(columns=[disease_target], errors="ignore").copy()
        X_enc = pd.DataFrame()
        for col in col_names:
            if col in X.columns:
                try:
                    X_enc[col] = pd.to_numeric(X[col])
                except (ValueError, TypeError):
                    if col in encoders:
                        try:
                            X_enc[col] = encoders[col].transform(X[col].astype(str))
                        except ValueError:
                            X_enc[col] = 0
                    else:
                        X_enc[col] = 0
            else:
                X_enc[col] = 0

        X_enc = X_enc.fillna(0).astype(float).values

        clf = TabPFNClassifier(
            random_state=42,
            categorical_features_indices=cat_indices or None,
            ignore_pretraining_limits=True,
        )
        clf.fit(X_train, y_train)
        proba = clf.predict_proba(X_enc)
        pos_prob = float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])

        return jsonify({"probability": round(pos_prob, 4)})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

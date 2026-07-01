"""
train_pipeline.py
=================
PS13 — Predictive Fault ML Training Pipeline

This script:
  1. Compiles synthetic telemetry datasets with data augmentation.
  2. Trains an XGBoost multiclass classifier for fault classification (Q2/Q3 baseline).
  3. Trains an IsolationForest for unsupervised catch-all anomaly detection.
  4. Computes SHAP explainability matrices for the model.
  5. Saves the models to disk (locally) for the dashboard/integration pipeline.

Addresses evaluation dimension: Technical Merit (35% weight)
"""

import os
import joblib
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix
import shap
from typing import Tuple, Dict

# Relative import or add package directory to path
from data_augmentation import compile_training_dataset, FEATURE_COLUMNS

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pipeline execution
# ─────────────────────────────────────────────────────────────────────────────

def train_and_evaluate(
    normal_hours: float = 4.0,
    fault_hours_each: float = 1.0,
    augment_copies: int = 4
) -> Tuple[xgb.XGBClassifier, IsolationForest, pd.DataFrame]:
    """
    Train XGBoost and IsolationForest models.
    """
    # 1. Compile datasets
    train_df, test_df = compile_training_dataset(
        normal_hours=normal_hours,
        fault_hours_each=fault_hours_each,
        augment_copies=augment_copies
    )

    # 2. Extract features and labels
    # Exclude timestamp and label from features
    feature_names = [col for col in FEATURE_COLUMNS if col != "label"]
    
    X_train = train_df[feature_names]
    y_train = train_df["label"]
    X_test = test_df[feature_names]
    y_test = test_df["label"]

    print(f"\nFeature set: {feature_names}")
    print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
    print(f"X_test shape:  {X_test.shape}, y_test shape:  {y_test.shape}")

    # 3. Train XGBoost Multiclass Classifier
    # Shallow depth & high min_child_weight to avoid overfitting on small/synthetic datasets
    print("\nTraining XGBoost fault classifier...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="multi:softprob",
        num_class=5,
        random_state=42
    )
    xgb_model.fit(X_train, y_train)

    # Evaluate XGBoost
    y_pred = xgb_model.predict(X_test)
    print("\n--- XGBoost Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=[
        "Normal", "Congestion", "BGP Instability", "Tunnel Degradation", "Policy Drift"
    ]))

    # 4. Train Isolation Forest (Unsupervised Catch-all)
    # Contamination set to match expected outlier rate in training dataset
    print("\nTraining Isolation Forest anomaly detector...")
    iforest = IsolationForest(
        n_estimators=150,
        contamination=0.15,
        max_features=1.0,
        bootstrap=False,
        n_jobs=-1,
        random_state=42
    )
    # Train only on normal baseline data to learn "normal behavior"
    X_train_normal = X_train[y_train == 0]
    iforest.fit(X_train_normal)

    # Test Isolation Forest (-1 = anomaly, 1 = normal)
    iforest_preds = iforest.predict(X_test)
    # Map back: anomalous is label != 0
    iforest_anomalous_pct = np.mean(iforest_preds[y_test != 0] == -1)
    iforest_normal_pct = np.mean(iforest_preds[y_test == 0] == 1)
    print(f"Isolation Forest accuracy on Normal: {iforest_normal_pct * 100:.1f}%")
    print(f"Isolation Forest detection rate on faults: {iforest_anomalous_pct * 100:.1f}%")

    # 5. Compute SHAP Explainer
    print("\nInitializing SHAP explainer...")
    explainer = shap.TreeExplainer(xgb_model)
    
    # Save models and explainer
    xgb_path = os.path.join(MODELS_DIR, "xgb_fault_model.json")
    iforest_path = os.path.join(MODELS_DIR, "iforest_model.joblib")
    
    xgb_model.save_model(xgb_path)
    joblib.dump(iforest, iforest_path)
    print(f"\nModels saved to disk:\n  - XGBoost: {xgb_path}\n  - IsolationForest: {iforest_path}")

    return xgb_model, iforest, X_test


# ─────────────────────────────────────────────────────────────────────────────
# 2. Explainer API for real-time alerts
# ─────────────────────────────────────────────────────────────────────────────

class RealTimePredictor:
    """
    Wrapper class to run model inference and generate SHAP explainability outputs.
    """
    def __init__(self):
        self.xgb_path = os.path.join(MODELS_DIR, "xgb_fault_model.json")
        self.iforest_path = os.path.join(MODELS_DIR, "iforest_model.joblib")
        
        self.feature_names = [col for col in FEATURE_COLUMNS if col != "label"]
        self.class_labels = ["Normal", "Congestion", "BGP Instability", "Tunnel Degradation", "Policy Drift"]

        # Lazy load models
        self.xgb_model = None
        self.iforest = None
        self.explainer = None

    def _load_models(self):
        if self.xgb_model is None:
            if not os.path.exists(self.xgb_path):
                print("Models not trained. Running training pipeline...")
                train_and_evaluate(normal_hours=2, fault_hours_each=0.5)
            
            self.xgb_model = xgb.XGBClassifier()
            self.xgb_model.load_model(self.xgb_path)
            self.iforest = joblib.load(self.iforest_path)
            self.explainer = shap.TreeExplainer(self.xgb_model)

    def predict_instance(self, features_dict: dict) -> dict:
        """
        Run inference on a single live telemetry sample.

        Returns:
            dict containing class probability, predicted label, Isolation Forest flag,
            and SHAP value array formatted for noc_copilot_prompt.py.
        """
        self._load_models()

        # Build feature DataFrame with correct column order
        row_df = pd.DataFrame([features_dict])[self.feature_names]

        # 1. XGBoost Prediction
        probs = self.xgb_model.predict_proba(row_df)[0]
        pred_idx = np.argmax(probs)
        confidence = float(probs[pred_idx])

        # 2. Isolation Forest Prediction
        if_val = self.iforest.predict(row_df)[0]
        is_anomaly = bool(if_val == -1)

        # 3. Generate SHAP attributions
        # For multiclass, explainer output depends on SHAP library version
        shap_vals = self.explainer.shap_values(row_df)
        
        # Get SHAP values for the predicted class
        if isinstance(shap_vals, list):
            # List of arrays, each of shape (samples, features)
            pred_shap = shap_vals[pred_idx][0]
        elif hasattr(shap_vals, "shape"):
            # Numpy array
            if len(shap_vals.shape) == 3:
                # Shape can be (classes, samples, features) or (samples, features, classes)
                d1, d2, d3 = shap_vals.shape
                if d1 == 5 and d2 == 1:
                    # (classes, samples, features)
                    pred_shap = shap_vals[pred_idx][0]
                elif d1 == 1 and d2 == len(self.feature_names) and d3 == 5:
                    # (samples, features, classes)
                    pred_shap = shap_vals[0, :, pred_idx]
                elif d1 == 1 and d2 == 5 and d3 == len(self.feature_names):
                    # (samples, classes, features)
                    pred_shap = shap_vals[0, pred_idx]
                else:
                    # Default fallback
                    pred_shap = shap_vals[0]
            elif len(shap_vals.shape) == 2:
                # (samples, features)
                pred_shap = shap_vals[0]
            else:
                pred_shap = shap_vals
        else:
            pred_shap = shap_vals

        # Package SHAP values matching what noc_copilot_prompt expects
        shap_list = []
        for feat, val in zip(self.feature_names, pred_shap):
            shap_list.append({
                "feature": feat,
                "shap_value": float(val),
                "current_value": float(row_df[feat].iloc[0]),
                "unit": "%" if "pct" in feat else ("ms" if "ms" in feat else "")
            })

        return {
            "predicted_fault_type": self.class_labels[pred_idx].upper().replace(" ", "_"),
            "confidence_pct": int(confidence * 100),
            "xgboost_class": "CRITICAL" if confidence > 0.8 and pred_idx != 0 else (
                "WARNING" if confidence > 0.5 and pred_idx != 0 else "NORMAL"
            ),
            "isolation_forest_anomaly": is_anomaly,
            "shap_values": shap_list
        }


if __name__ == "__main__":
    print("Running training script...")
    train_and_evaluate(normal_hours=2, fault_hours_each=0.5, augment_copies=2)

    # Test real-time predictor
    print("\nTesting RealTimePredictor on dummy congestion feature sample...")
    dummy_sample = {
        "underlay_if_utilization_pct": 82.5,
        "underlay_if_discards_rate": 15.2,
        "underlay_if_errors_rate": 0.01,
        "underlay_bgp_state_changes": 0,
        "underlay_route_count_delta": 0,
        "overlay_tunnel_latency_ms": 32.5,
        "overlay_tunnel_jitter_ms": 7.4,
        "overlay_tunnel_loss_pct": 2.1,
        "overlay_tunnel_uptime_sec": 3600,
        "overlay_ipsec_rekey_failures": 0,
        "utilization_rate_of_change": 0.42,
        "utilization_5min_ema": 78.4,
        "error_ratio": 0.0001,
        "bytes_asymmetry_ratio": 0.55,
        "voice_traffic_dscp_ratio": 0.20
    }
    predictor = RealTimePredictor()
    result = predictor.predict_instance(dummy_sample)
    
    print(f"\n  Predicted fault: {result['predicted_fault_type']}")
    print(f"  Confidence:      {result['confidence_pct']}%")
    print(f"  I-Forest anomaly: {result['isolation_forest_anomaly']}")
    print(f"  Top SHAP signals:")
    # Print sorted SHAP results
    for s in sorted(result["shap_values"], key=lambda x: abs(x["shap_value"]), reverse=True)[:3]:
        print(f"    - {s['feature']}: {s['current_value']} (SHAP={s['shap_value']:+.4f})")

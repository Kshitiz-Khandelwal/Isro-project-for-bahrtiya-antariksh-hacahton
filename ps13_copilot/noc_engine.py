"""
noc_engine.py
=============
PS13 — Predictive NOC Copilot Integration Engine

This module binds all the other components together:
  - telemetry / mock controller scrapes
  - topology graph correlation (NetworkX)
  - Prophet time-to-impact forecasting
  - BGP instability detection
  - XGBoost classification + SHAP feature attributions
  - RAG vector lookup (ChromaDB)
  - LLM Copilot execution (Ollama + JSON schema)

Usage:
  from noc_engine import NOCEngine
  engine = NOCEngine()
  engine.initialize_rag()
  alert_event = engine.process_polling_cycle(live_telemetry_list, live_syslogs)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Local imports
from topology_graph import TopologyGraph
from time_to_impact import estimate_time_to_impact
from bgp_instability_detector import detect_bgp_instability
from train_pipeline import RealTimePredictor
from noc_copilot_prompt import call_copilot

# RAG dependencies
import chromadb
from chromadb.utils import embedding_functions

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(PACKAGE_DIR, "knowledge_base")
CHROMA_PERSIST_DIR = os.path.join(PACKAGE_DIR, "chroma_db")


class NOCEngine:
    """
    Main orchestrator that processes network events, analyzes telemetry,
    determines affected scope, retrieves runbooks, and calls the Copilot.
    """

    def __init__(self, clab_yaml_path: Optional[str] = None):
        self.topo = TopologyGraph(clab_yaml_path)
        self.predictor = RealTimePredictor()
        
        # Telemetry history buffer (map of device_interface -> list of dicts)
        # Keeps last 100 points for Prophet forecasting
        self.telemetry_history: dict[str, list[dict]] = {}
        self.history_limit = 100

        # RAG items
        self.chroma_client = None
        self.collection = None

    # ─────────────────────────────────────────────────────────────────────────
    # 1. RAG Setup & runbook indexing
    # ─────────────────────────────────────────────────────────────────────────

    def initialize_rag(self):
        """Initialize ChromaDB and index the local runbook markdown files."""
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        
        # Use local SentenceTransformers embedding function (fully offline)
        # Under the hood, this downloads sentence-transformers locally
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Create or fetch collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="noc_runbooks",
            embedding_function=emb_fn
        )

        # Read and index runbooks if empty
        if self.collection.count() == 0:
            print("ChromaDB runbooks collection is empty. Indexing runbooks...")
            runbook_files = [
                ("runbook_congestion.md", "Runbook: Hub-Spoke Congestion Recovery"),
                ("runbook_bgp_flap.md", "Runbook: BGP Flap Diagnosis & Recovery"),
                ("runbook_tunnel_degradation.md", "Runbook: IPSec Tunnel Degradation Recovery"),
                ("runbook_policy_drift.md", "Runbook: QoS Policy Drift Recovery"),
            ]

            docs = []
            metadatas = []
            ids = []

            for filename, title in runbook_files:
                path = os.path.join(KNOWLEDGE_DIR, filename)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    docs.append(content)
                    metadatas.append({"document_name": title, "filename": filename})
                    ids.append(filename.replace(".md", ""))

            if docs:
                self.collection.add(
                    documents=docs,
                    metadatas=metadatas,
                    ids=ids
                )
                print(f"Indexed {len(docs)} runbooks successfully in local ChromaDB.")
            else:
                print("Warning: Runbook markdown files not found. Cannot populate ChromaDB.")
        else:
            print(f"Loaded existing ChromaDB. Found {self.collection.count()} runbooks.")

    def query_runbooks(self, query_text: str, k: int = 1) -> list[dict]:
        """Query ChromaDB for the most relevant runbook excerpt."""
        if not self.collection:
            self.initialize_rag()

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=k
            )

            formatted = []
            if results and results["documents"]:
                for i in range(len(results["documents"][0])):
                    formatted.append({
                        "document_name": results["metadatas"][0][i]["document_name"],
                        "excerpt": results["documents"][0][i],
                        # Chroma returns squared L2 distances (smaller is closer)
                        # We map it roughly to a relevance score [0, 1]
                        "relevance_score": max(0.0, 1.0 - (results["distances"][0][i] / 2.0))
                    })
            return formatted
        except Exception as e:
            print(f"RAG query failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Polling Cycle Processor
    # ─────────────────────────────────────────────────────────────────────────

    def process_polling_cycle(
        self,
        current_telemetry: list[dict],  # list of device telemetry snapshots
        syslogs: list[dict],
        operator_query: Optional[str] = None
    ) -> list[dict]:
        """
        Executes a single processing iteration over the live telemetry data.
        
        Returns:
            list[dict] — A list of generated alert reports with predictions and Copilot advice.
        """
        now = datetime.utcnow()

        # Update telemetry history buffers
        for t in current_telemetry:
            key = f"{t['device']}_{t['interface']}"
            self.telemetry_history.setdefault(key, [])
            self.telemetry_history[key].append({
                "ds": now,
                "y": t.get("underlay_if_utilization_pct", t.get("overlay_tunnel_loss_pct", 0))
            })
            # Enforce sliding window history limit
            if len(self.telemetry_history[key]) > self.history_limit:
                self.telemetry_history[key].pop(0)

        # 1. Run BGP Instability Check
        bgp_status = detect_bgp_instability(syslogs, reference_time=now)
        
        # 2. Run ML predictions and Prophet forecasts for each device/interface
        raw_alerts = []
        for t in current_telemetry:
            key = f"{t['device']}_{t['interface']}"
            
            # Predict fault class + get SHAP values
            ml_res = self.predictor.predict_instance(t)
            
            # Estimate time-to-impact (Prophet)
            history_df = pd.DataFrame(self.telemetry_history[key])
            metric_type = "if_utilization_pct" if "underlay" in key or "eth" in key else "tunnel_packet_loss_pct"
            
            prophet_res = estimate_time_to_impact(
                metric_name=metric_type,
                history_df=history_df
            )
            
            # Combine alert data
            is_anomaly = ml_res["predicted_fault_type"] != "NORMAL" or ml_res["isolation_forest_anomaly"] or prophet_res["will_breach"]
            
            if is_anomaly:
                alert = {
                    "alert_id": f"ALT-{t['device']}-{t['interface']}-{now.strftime('%M%S')}",
                    "timestamp": now.isoformat() + "Z",
                    "device": t["device"],
                    "interface": t["interface"],
                    "predicted_fault_type": ml_res["predicted_fault_type"],
                    "confidence_pct": ml_res["confidence_pct"],
                    "xgboost_class": ml_res["xgboost_class"],
                    "isolation_forest_anomaly": ml_res["isolation_forest_anomaly"],
                    "severity": ml_res["xgboost_class"],
                    # Merge telemetry metrics
                    "utilization_pct": t.get("underlay_if_utilization_pct", 0),
                    "utilization_trend": "RISING" if prophet_res["trend_slope_per_30s"] > 0.05 else (
                        "FALLING" if prophet_res["trend_slope_per_30s"] < -0.05 else "STABLE"
                    ),
                    "utilization_slope": prophet_res["trend_slope_per_30s"],
                    "packet_loss_pct": t.get("overlay_tunnel_loss_pct", 0),
                    "jitter_ms": t.get("overlay_tunnel_jitter_ms", 0),
                    "bgp_state_changes": bgp_status["flap_count"] if t["device"] in bgp_status["affected_devices"] else 0,
                    "if_errors_rate": t.get("underlay_if_errors_rate", 0),
                    "if_discards_rate": t.get("underlay_if_discards_rate", 0),
                    "tunnel_uptime_sec": t.get("overlay_tunnel_uptime_sec", "N/A"),
                    "ipsec_rekey_failures": t.get("overlay_ipsec_rekey_failures", 0),
                    "prophet_forecast": prophet_res,
                    "shap_values": ml_res["shap_values"]
                }
                raw_alerts.append(alert)

        # Inject BGP flaps as their own alert if triggered
        if bgp_status["is_unstable"]:
            for dev in bgp_status["affected_devices"]:
                raw_alerts.append({
                    "alert_id": f"ALT-{dev}-BGP-{now.strftime('%M%S')}",
                    "timestamp": now.isoformat() + "Z",
                    "device": dev,
                    "interface": "bgp-peer",
                    "predicted_fault_type": "BGP_INSTABILITY",
                    "confidence_pct": 95,
                    "xgboost_class": bgp_status["severity"],
                    "isolation_forest_anomaly": True,
                    "severity": bgp_status["severity"],
                    "utilization_pct": 0,
                    "utilization_trend": "STABLE",
                    "utilization_slope": 0.0,
                    "packet_loss_pct": 0.0,
                    "jitter_ms": 0.0,
                    "bgp_state_changes": bgp_status["flap_count"],
                    "if_errors_rate": 0.0,
                    "if_discards_rate": 0.0,
                    "tunnel_uptime_sec": 0,
                    "ipsec_rekey_failures": 0,
                    "prophet_forecast": {},
                    "shap_values": [
                        {"feature": "bgp_state_changes_count", "shap_value": 0.6, "current_value": bgp_status["flap_count"]}
                    ]
                })

        # 3. Graph-based event correlation & deduplication
        correlated_alerts = self.topo.correlate_alerts(raw_alerts)

        # 4. For each correlated alert, query RAG & invoke Copilot
        processed_reports = []
        for alert in correlated_alerts:
            # Skip if normal state
            if alert.get("xgboost_class", "NORMAL") == "NORMAL" and not alert.get("is_correlated"):
                continue
                
            # If correlated, pull stats from primary alert
            is_corr = alert.get("is_correlated", False)
            primary = alert["primary_alert"] if is_corr else alert

            # Determine query text for RAG based on the predicted issue
            issue = primary["predicted_fault_type"]
            
            # Query runbooks
            rag_res = self.query_runbooks(issue, k=1)
            
            # Build topology scope context
            scope = alert["scope"] if not is_corr else alert["scope"]
            
            # Get relevant syslogs for this device
            device_syslogs = [
                s for s in syslogs 
                if s.get("device") == alert["device"] or "BGP" in s.get("message", "")
            ]

            # Invoke LLM Copilot via Ollama (noc_copilot_prompt)
            print(f"\nCalling Copilot for alert on {alert['device']} ({issue})...")
            copilot_res = call_copilot(
                alert_data=primary,
                shap_values=primary.get("shap_values", []),
                topology_ctx=scope,
                rag_results=rag_res,
                syslogs=device_syslogs,
                operator_query=operator_query
            )

            # Store the final report
            alert_report = {
                "alert": alert,
                "copilot": copilot_res,
                "timestamp": now.isoformat(),
            }
            processed_reports.append(alert_report)

        return processed_reports


if __name__ == "__main__":
    print("NOC Engine Integrator — Test Run")
    print("=" * 60)
    
    engine = NOCEngine()
    print("Initializing RAG database...")
    engine.initialize_rag()
    
    # Run test on SCENARIO_1_CONGESTION from noc_copilot_prompt.py
    from noc_copilot_prompt import SCENARIO_1_CONGESTION
    
    # Adapt to list formats
    mock_telemetry = [{
        "device": "PE-1",
        "interface": "eth1",
        "underlay_if_utilization_pct": 74.2,
        "underlay_if_discards_rate": 1.8,
        "underlay_if_errors_rate": 0.01,
        "overlay_tunnel_loss_pct": 0.12,
        "overlay_tunnel_jitter_ms": 8.4,
        "overlay_tunnel_uptime_sec": 43200,
        "overlay_ipsec_rekey_failures": 0,
        "utilization_rate_of_change": 0.38,
        "utilization_5min_ema": 68.7,
        "error_ratio": 0.0001,
        "bytes_asymmetry_ratio": 0.55,
        "voice_traffic_dscp_ratio": 0.20
    }]
    
    mock_syslogs = SCENARIO_1_CONGESTION["syslogs"]
    
    # Process cycle
    reports = engine.process_polling_cycle(mock_telemetry, mock_syslogs)
    print(f"\nProcessing completed. Generated {len(reports)} incident reports.")
    for idx, r in enumerate(reports, 1):
        c = r["copilot"]
        if c["success"]:
            resp = c["response"]
            print(f"\nReport #{idx}:")
            print(f"  Device:       {r['alert']['device']}")
            print(f"  Issue:        {resp['issue_type']}")
            print(f"  Severity:     {resp['severity']}")
            print(f"  Confidence:   {resp['confidence_pct']}%")
            print(f"  Operator summary: {resp['operator_summary']}")
            print(f"  Root cause:   {resp['root_cause_hypothesis']}")
            print("  Recommended Actions:")
            for a in resp["recommended_actions"]:
                print(f"    - [{a['priority']}] {a['action']} targeting {a['target']}")
        else:
            print(f"  Report #{idx} FAILED: {c['error']}")

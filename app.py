"""
app.py
======
PS13 — Predictive NOC Copilot Streamlit Dashboard

This is the main graphical user interface for the air-gapped copilot.
It displays:
  1. Live Network Topology (NetworkX + Plotly)
  2. Air-Gap Verification Status (live execution of airgap_verify.py)
  3. Real-time Telemetry Charts & Prophet Forecasts (time_to_impact.py)
  4. Deduplicated Alert Feed (topology_graph.py)
  5. The AI Copilot Structured Analysis Panel (noc_engine.py + Ollama)
  6. Demo Fault Injector (sends triggers to mock_sdwan_controller.py or simulates locally)

Usage:
  streamlit run app.py
"""

import os
import sys
import json
import time
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta

# Import ps13_copilot modules
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps13_copilot"))
from airgap_verify import run_full_verification
from topology_graph import TopologyGraph
from time_to_impact import estimate_time_to_impact, generate_congestion_ramp
from bgp_instability_detector import detect_bgp_instability
from noc_engine import NOCEngine


# ─────────────────────────────────────────────────────────────────────────────
# 1. Page Configuration & Theme
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ISRO PS13 — Air-Gapped Predictive NOC Copilot",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium dark theme styling
st.markdown("""
<style>
    .reportview-container {
        background: #0f111a;
    }
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1a1c24;
        border: 1px solid #2d3139;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .status-badge {
        font-size: 14px;
        font-weight: bold;
        padding: 4px 10px;
        border-radius: 20px;
    }
    .badge-ok { background-color: #1b4d3e; color: #52c41a; }
    .badge-warn { background-color: #5c3e1b; color: #faad14; }
    .badge-crit { background-color: #5c1b1b; color: #f5222d; }
    
    .copilot-response {
        background-color: #141722;
        border-left: 5px solid #1890ff;
        padding: 15px;
        border-radius: 5px;
        font-family: 'Courier New', Courier, monospace;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. State & Session Variables
# ─────────────────────────────────────────────────────────────────────────────
if "noc_engine" not in st.session_state:
    st.session_state.noc_engine = NOCEngine()
    st.session_state.noc_engine.initialize_rag()
if "telemetry_history" not in st.session_state:
    st.session_state.telemetry_history = []
if "syslogs" not in st.session_state:
    st.session_state.syslogs = []
if "alerts_history" not in st.session_state:
    st.session_state.alerts_history = []
if "simulation_step" not in st.session_state:
    st.session_state.simulation_step = 0
if "active_scenario" not in st.session_state:
    st.session_state.active_scenario = "Normal Operations"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sidebar — Controls & Fault Injector
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 📡 NOC Copilot")
st.sidebar.title("NOC Controls")
st.sidebar.markdown("---")

# Fault scenarios selection
scenario = st.sidebar.selectbox(
    "Active Network Scenario",
    ["Normal Operations", "Scenario 1: Congestion Buildup", "Scenario 2: BGP Route Flap", 
     "Scenario 3: Tunnel Degradation", "Scenario 4: Policy Drift"]
)

# Communicate with mock controller if present
CONTROLLER_URL = "http://localhost:8080/api/v1"
controller_connected = False

try:
    resp = requests.get(f"{CONTROLLER_URL}/health", timeout=1)
    if resp.status_code == 200:
        controller_connected = True
except requests.exceptions.RequestException:
    pass

if controller_connected:
    st.sidebar.success("📡 Connected to Mock SD-WAN Controller")
    # Trigger scenario on controller
    if scenario != st.session_state.active_scenario:
        st.session_state.active_scenario = scenario
        if "Scenario 1" in scenario:
            # We simulate progressive congestion inside our local loop below
            requests.post(f"{CONTROLLER_URL}/inject/clear")
        elif "Scenario 2" in scenario:
            requests.post(f"{CONTROLLER_URL}/inject/clear")
        elif "Scenario 3" in scenario:
            requests.post(f"{CONTROLLER_URL}/scenario/tunnel_degradation")
        elif "Scenario 4" in scenario:
            requests.post(f"{CONTROLLER_URL}/inject/rekey_failure", json={"tunnel": "IPSec-Branch1-Hub", "value": 0.6})
            requests.post(f"{CONTROLLER_URL}/inject/jitter", json={"tunnel": "IPSec-Branch1-Hub", "value": 35.0})
        else:
            requests.post(f"{CONTROLLER_URL}/inject/clear")
else:
    st.sidebar.warning("⚠️ Running local offline simulation (Controller not started)")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Simulation Engine Loop
# ─────────────────────────────────────────────────────────────────────────────
def get_simulated_telemetry(scenario_name: str, step: int) -> tuple[list[dict], list[dict]]:
    """Simulates live telemetry lists and syslogs depending on active scenario and step."""
    base_t = [
        # PE-1 Interface eth2 (Branch 1)
        {
            "device": "PE-1", "interface": "eth2",
            "underlay_if_utilization_pct": 32.5 + np.sin(step/10)*2.0,
            "underlay_if_discards_rate": 0.0, "underlay_if_errors_rate": 0.0,
            "underlay_bgp_state_changes": 0, "underlay_route_count_delta": 0,
            "overlay_tunnel_latency_ms": 12.0, "overlay_tunnel_loss_pct": 0.0,
            "overlay_tunnel_jitter_ms": 2.0, "overlay_tunnel_uptime_sec": 3600 + step*30,
            "overlay_ipsec_rekey_failures": 0, "utilization_rate_of_change": 0.0,
            "utilization_5min_ema": 32.5, "error_ratio": 0.0,
            "bytes_asymmetry_ratio": 0.5, "voice_traffic_dscp_ratio": 0.20
        },
        # PE-1 Interface eth3 (Branch 2)
        {
            "device": "PE-1", "interface": "eth3",
            "underlay_if_utilization_pct": 28.0 + np.cos(step/10)*1.5,
            "underlay_if_discards_rate": 0.0, "underlay_if_errors_rate": 0.0,
            "underlay_bgp_state_changes": 0, "underlay_route_count_delta": 0,
            "overlay_tunnel_latency_ms": 12.0, "overlay_tunnel_loss_pct": 0.0,
            "overlay_tunnel_jitter_ms": 1.8, "overlay_tunnel_uptime_sec": 3600 + step*30,
            "overlay_ipsec_rekey_failures": 0, "utilization_rate_of_change": 0.0,
            "utilization_5min_ema": 28.0, "error_ratio": 0.0,
            "bytes_asymmetry_ratio": 0.5, "voice_traffic_dscp_ratio": 0.20
        }
    ]
    syslogs = []

    if "Scenario 1: Congestion" in scenario_name:
        # Gradually ramp up utilization on PE-1 eth2
        util = min(40.0 + step * 4.0, 96.0)
        base_t[0]["underlay_if_utilization_pct"] = util
        base_t[0]["utilization_rate_of_change"] = 0.42
        base_t[0]["utilization_5min_ema"] = 40.0 + step * 3.5
        if util > 75:
            base_t[0]["underlay_if_discards_rate"] = (util - 75) * 0.8
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "WARNING", "message": "Interface eth2: output drops incrementing"})
        if util > 85:
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "CRITICAL", "message": "QoS class VOICE-PRIORITY: queue depth exceeded SLA limit"})

    elif "Scenario 2: BGP Route Flap" in scenario_name:
        # Keep utilization normal, but trigger BGP flaps in syslog
        if step % 2 == 0:
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "ERROR", "message": "BGP neighbor 10.0.0.1 went from Established to Idle"})
        else:
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "INFO", "message": "BGP neighbor 10.0.0.1 Established — 312 prefixes received"})
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "WARNING", "message": "Route count dropped by 47 prefixes — convergence event"})

    elif "Scenario 3: Tunnel Degradation" in scenario_name:
        # Degrade IPSec overlay tunnel metrics on PE-1 eth2
        base_t[0]["overlay_tunnel_loss_pct"] = min(0.5 + step * 1.5, 14.5)
        base_t[0]["overlay_tunnel_latency_ms"] = min(12.0 + step * 4.0, 52.0)
        base_t[0]["overlay_tunnel_jitter_ms"] = min(2.0 + step * 3.5, 34.0)
        base_t[0]["overlay_tunnel_uptime_sec"] = max(10, 1800 - step*120)
        if step > 2:
            base_t[0]["overlay_ipsec_rekey_failures"] = step - 2
            syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "CE-Branch1", "severity": "ERROR", "message": "IPSec SA rekey failed: IKE timeout waiting for response"})

    elif "Scenario 4: Policy Drift" in scenario_name:
        # Drop VOICE DSCP ratio to near-zero, spike jitter
        base_t[0]["voice_traffic_dscp_ratio"] = max(0.20 - step * 0.04, 0.01)
        base_t[0]["overlay_tunnel_jitter_ms"] = min(2.0 + step * 8.0, 42.0)
        syslogs.append({"timestamp": datetime.utcnow().strftime("%H:%M:%S"), "device": "PE-1", "severity": "INFO", "message": "QoS policy VOICE-PRIORITY removed from interface eth2 by admin"})

    return base_t, syslogs


# Update state step and data
st.session_state.simulation_step += 1
telemetry, new_logs = get_simulated_telemetry(scenario, st.session_state.simulation_step)
st.session_state.syslogs.extend(new_logs)
if len(st.session_state.syslogs) > 30:
    st.session_state.syslogs = st.session_state.syslogs[-30:]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Header Section & Air-Gap Compliance Indicator
# ─────────────────────────────────────────────────────────────────────────────
st.title("📡 Secure Predictive NOC Copilot (PS13)")

col_head1, col_head2, col_head3 = st.columns([3, 1, 1])

with col_head1:
    st.write("Real-time telemetry analysis, NetworkX event correlation, and offline LLM incident management.")

with col_head2:
    if st.button("🔄 Trigger Polling Cycle"):
        st.rerun()

with col_head3:
    # Live execution of airgap_verify.py
    gap_report = run_full_verification()
    if gap_report["overall_compliant"]:
        st.markdown("<span class='status-badge badge-ok'>🔒 AIR-GAP COMPLIANT</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='status-badge badge-crit'>⚠️ COMPROMISED</span>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main Dashboard Columns
# ─────────────────────────────────────────────────────────────────────────────
col_body1, col_body2 = st.columns([1, 1])

# ── COLUMN 1: Topology & Charts ──
with col_body1:
    st.subheader("Network Topology Graph")
    
    # Generate NetworkX Plotly visualization
    plotly_data = st.session_state.noc_engine.topo.get_plotly_data()
    fig = go.Figure()
    
    # Draw edges
    fig.add_trace(go.Scatter(
        x=plotly_data["edges"]["x"], y=plotly_data["edges"]["y"],
        line=dict(width=1.5, color='#3b3d4a'),
        hoverinfo='none',
        mode='lines'
    ))
    
    # Draw nodes
    fig.add_trace(go.Scatter(
        x=plotly_data["nodes"]["x"], y=plotly_data["nodes"]["y"],
        mode='markers+text',
        hoverinfo='text',
        text=[t.split(" (")[0] for t in plotly_data["nodes"]["text"]],
        textposition="top center",
        marker=dict(
            showscale=False,
            colorscale='YlGnBu',
            color=plotly_data["nodes"]["color"],
            size=22,
            line=dict(width=2, color='#fff')
        )
    ))
    
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=0, l=0, r=0, t=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=320
    )
    st.plotly_chart(fig, use_container_width=True)

    # Real-time Telemetry plots
    st.subheader("Live Telemetry Performance")
    t_df = pd.DataFrame(telemetry)
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.write("Interface Utilization (%)")
        st.line_chart(t_df.set_index("interface")["underlay_if_utilization_pct"])
    with chart_col2:
        st.write("Packet Loss (%)")
        st.line_chart(t_df.set_index("interface")["overlay_tunnel_loss_pct"])


# ── COLUMN 2: Alert Feed & Copilot Assistant ──
with col_body2:
    st.subheader("Predictive Alert Feed")
    
    # Execute single NOC polling cycle
    reports = st.session_state.noc_engine.process_polling_cycle(
        current_telemetry=telemetry,
        syslogs=st.session_state.syslogs
    )

    if not reports:
        st.info("🟢 No active predictive warnings. Underlay and overlay are normal.")
    else:
        for idx, report in enumerate(reports):
            alert = report["alert"]
            copilot = report["copilot"]
            is_corr = alert.get("is_correlated", False)
            primary = alert["primary_alert"] if is_corr else alert
            
            # Severity coloring
            sev = primary.get("xgboost_class", "WARNING")
            badge_class = "badge-crit" if sev == "CRITICAL" else "badge-warn"
            
            st.markdown(f"""
            <div style='background-color:#1a1c24; border:1px solid #2d3139; padding:15px; border-radius:8px; margin-bottom:10px;'>
                <div style='display:flex; justify-content:space-between;'>
                    <b>{primary['predicted_fault_type']} ({primary['device']}/{primary['interface']})</b>
                    <span class='status-badge {badge_class}'>{sev}</span>
                </div>
                <div style='margin-top:8px; font-size:12px; color:#a0a0a0;'>
                    Prediction Confidence: {primary['confidence_pct']}% | 
                    IsolationForest Outlier: {primary['isolation_forest_anomaly']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show copilot recommendations
            if copilot["success"]:
                resp = copilot["response"]
                
                st.subheader("🤖 AI Copilot Analysis")
                st.markdown(f"**Operator Summary:** *{resp['operator_summary']}*")
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown(f"**Time-to-Impact:** `{resp['time_to_impact_min']} mins`")
                    st.markdown(f"**Runbook Ref:** `{resp['runbook_reference']}`")
                with col_c2:
                    st.markdown(f"**Affected Scope:** {', '.join(resp['affected_devices'])}")
                    st.markdown(f"**Affected Services:** {', '.join(resp['affected_services'])}")
                
                st.markdown("**Root Cause Hypothesis:**")
                st.write(resp["root_cause_hypothesis"])

                # Draw SHAP contributing signals
                st.markdown("**Contributing Signals (SHAP):**")
                shap_df = pd.DataFrame(primary.get("shap_values", []))
                if not shap_df.empty:
                    st.bar_chart(shap_df.set_index("feature")["shap_value"])

                st.markdown("**Ordered Recommended Actions Checklist:**")
                for action in resp["recommended_actions"]:
                    checked = st.checkbox(
                        f"[{action['priority']}] {action['action']} targeting {action['target']} (Rationale: {action['rationale']})",
                        key=f"act-{idx}-{action['priority']}"
                    )
            else:
                st.error(f"AI Copilot Inference Failed: {copilot['error']}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Syslog and RAG Runbook Tab Viewers
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📜 Live Syslog Buffer", "📚 RAG Knowledge Base Search", "🔒 Air-Gap Security Inspector"])

with tab1:
    st.subheader("Syslog Buffer (Last 30 Events)")
    if not st.session_state.syslogs:
        st.write("No events in buffer.")
    else:
        for l in reversed(st.session_state.syslogs):
            st.code(f"[{l['timestamp']}] {l['device']} [{l['severity']}] {l['message']}")

with tab2:
    st.subheader("Search Local Runbook Database")
    search_query = st.text_input("Enter issue type to search RAG:")
    if search_query:
        rag_hits = st.session_state.noc_engine.query_runbooks(search_query, k=2)
        if not rag_hits:
            st.info("No matching runbooks found.")
        else:
            for hit in rag_hits:
                st.markdown(f"### {hit['document_name']} (Relevance: {hit['relevance_score']:.2f})")
                st.markdown(hit["excerpt"])
                st.markdown("---")

with tab3:
    st.subheader("Air-Gap Compliance Auditor (Verification logs)")
    st.write(gap_report)

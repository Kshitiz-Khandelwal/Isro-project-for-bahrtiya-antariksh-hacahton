# Slide-by-Slide Guide: Idea Submission Template
## Problem Statement 13: Air-Gapped Predictive Copilot for Secure MPLS Operations

This document provides a detailed layout, text, tables, and visualization ideas to fill in the PPTX submission template (`[Pub] ISRO BAH 2026 _ Idea Submission Template.pptx`).

---

## 🎨 Design Theme Advice for PPT
- **Colors:** Use a modern dark theme to match our dashboard (Background: dark slate `#0f111a` or `#161925`; Accents: cyan `#00e5ff`, green `#52c41a` for normal/verified states, red `#f5222d` for failure alerts).
- **Typography:** Sans-serif (e.g., *Inter*, *Outfit*, or *Roboto*).
- **Visuals:** Avoid generic network icons. Use vector representations of routers, code snippets, and actual screenshots of the Streamlit app.

---

## Slide 1: Title Slide
### 📝 Text to Place:
*   **Title:** Air-Gapped Predictive Copilot for Secure MPLS Operations (Problem Statement 13)
*   **Sub-title:** An autonomous, offline AI NOC assistant for predictive network health monitoring.
*   **Team Name:** [Insert your Team Name]
*   **Team Leader Name:** [Insert Team Leader Name]

---

## Slide 2: Team Members
### 📝 Text to Place:
Create a grid/table listing each member, their college, and their specific role in this technical stack:
- **Member 1 (Team Leader):** [Name] (College: [Name])
  - **Role:** AI/ML Developer & Integrator (Prophet, XGBoost, and SHAP Explainability pipeline).
- **Member 2:** [Name] (College: [Name])
  - **Role:** Network Architect & Simulation Lead (Containerlab, FRRouting configurations, MPLS/BGP setup).
- **Member 3:** [Name] (College: [Name])
  - **Role:** NLP/RAG Developer (Ollama deployment, ChromaDB vector indexing, structured prompting).
- **Member 4:** [Name] (College: [Name])
  - **Role:** UI/UX Engineer (Streamlit dashboard, NetworkX topology plotter, live metrics panels).

---

## Slide 3: Opportunity & Solution (USP)
### 📝 Text to Place:
*   **How will it solve the problem?**
    - Moves network operations from **reactive to predictive** by analyzing telemetry precursors before SLA breaches occur.
    - Operates **100% locally** via a self-hosted quantized LLM (Qwen-3 8B) running inside a secure, disconnected environment.
*   **How is it different from existing ideas?**
    - **Cloud-free reasoning:** Most network copilots require external API keys (OpenAI/Claude). Ours runs local inference.
    - **Precursor forecasting:** Standard tools monitor thresholds (e.g., alert at 90% CPU). Our engine predicts *when* it will cross the line using time-series trends.
*   **Unique Selling Proposition (USP):**
    > *"The only fully air-gapped, explainable predictive NOC assistant that forecasts network failures with confidence scoring and exact time-to-SLA-breach estimation, maps affected service topologies via graph analysis, and directs remediation actions using a local quantized LLM — with zero external API calls or outbound telemetry leakage."*

---

## Slide 4: List of Features & Visuals
### 📝 Text to Place:
- **SLA Breach Forecasting:** Prophet model looks 30 minutes ahead to estimate minutes-to-breach.
- **Explainable Signals (SHAP):** Deconstructs the XGBoost warning to show the top 3 contributing indicators on a bar chart.
- **Topological Affected Scope:** NetworkX performs BFS on the active topology to find downstream branches and VRF services affected.
- **Local RAG Playbooks:** Automatically retrieves matching network runbooks (e.g., `runbook_bgp_flap.md`) and binds them into the LLM prompt.
- **Air-Gap Compliance Auditor:** Running `airgap_verify.py` live to prove all connections are locally loopbacked and outbound requests are blocked.

### 📊 Visuals to Add:
1. **Streamlit UI Screenshot:** A screenshot of your running dashboard displaying the visual topology, the alert feed, and the Copilot reasoning cards.
2. **SHAP Chart Plot:** An image of the horizontal bar chart showing how specific variables (e.g., `utilization_rate_of_change = +0.42`) weigh on the alert.

---

## Slide 5: Process Flow Diagram
### 📝 Text to Place:
Explain the step-by-step telemetry-to-chat flow:
1. **Ingest:** Telegraf polls SNMP MIBs, collects NetFlow records, and captures syslogs from simulated FRR routers.
2. **Forecast:** Prophet predicts future metric thresholds.
3. **Classify:** XGBoost determines the active fault class; Isolation Forest checks for outliers.
4. **Correlate:** NetworkX groups alerts based on node adjacencies to prevent alert floods.
5. **Contextualize:** SHAP values, topology scope, and matching RAG runbooks are compiled into a prompt.
6. **Reason:** Ollama runs Qwen-3 8B locally to generate a structured JSON remediation checklist.

### 📊 Visuals to Add:
- Copy the **Mermaid diagram** from Section 2 of [documentation.md](file:///c:/Users/Admin/Desktop/Kshitiz/Isro%20Projeect/documentation.md) and draw it as a block flowchart.

---

## Slide 6: Wireframes & Mock Diagrams (Optional)
### 📊 Visuals to Add:
Include layout diagrams of the Streamlit dashboard:
- **Left Sidebar:** Fault Injector Panel (Buttons to trigger Congestion, BGP flap, Tunnel loss, QoS drift).
- **Center Panel:** Interactive topology map (nodes connected by color-coded green/red/yellow link states) + live metrics charts.
- **Right Panel:** Copilot AI Assistant Chat & Remediation checklist showing the generated checklist targets.
- **Bottom Tabs:** Syslog console, RAG database search, and the Air-gap auditor panel.

---

## Slide 7: Architecture Diagram
### 📊 Visuals to Add:
- Place a high-quality rendering of the **System Architecture Diagram** containing the 4 core layers (Infrastructure, Data, Intelligence, Presentation) as shown in [documentation.md](file:///c:/Users/Admin/Desktop/Kshitiz/Isro%20Projeect/documentation.md). Use distinct color blocks for each layer.

---

## Slide 8: Technologies Used
### 📝 Text to Place:
Create a table mapping technologies to their roles:

| Category | Technology | Role in Solution |
|:---|:---|:---|
| **Network Sim** | Containerlab + FRRouting | Replicates multi-site MPLS/WAN topologies as code |
| **Telemetry Ingestion** | Telegraf + softflowd + nfdump | Extracts SNMP MIBs, syslogs, and NetFlow streams |
| **Predictive Engine** | Prophet + XGBoost + scikit-learn | Time-series forecasting, state classification, outlier detection |
| **Explainable AI** | SHAP | Attributes which metrics contributed to the warning |
| **Local LLM Server** | Ollama (Qwen3 8B / Phi4-mini) | Serves the quantized reasoning models locally |
| **Local Vector DB** | ChromaDB + LlamaIndex | Indexes and retrieves runbooks offline via SentenceTransformers |
| **NOC Web App** | Streamlit + Plotly + NetworkX | Interactive dashboard, graph plots, and incident log visualizer |

---

## Slide 9: Cost Analysis (Optional)
### 📝 Text to Place:
One of the strongest arguments for this solution is **zero recurring software or licensing costs**:
- **Software Cost:** **$0** (Entirely built on open-source libraries, local LLMs, and free networking container runtimes).
- **Infrastructure Overhead:** **$0 cloud fees** (All computation occurs on standard on-premise hardware).
- **Required Hardware:** Standard local workstation (16GB RAM, 1x NVIDIA GPU e.g. RTX 3060/4060) ~ **$1,000 one-time cost**.
- **Security Savings:** Eliminates compliance risks and costly audit processes associated with piping classified network data to external cloud LLM APIs.

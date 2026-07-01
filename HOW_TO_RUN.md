# 🗂️ PS13 Project — Complete File Guide & Run Instructions

> **Who is this for?** If you open this project and have no idea what any file does or how to run it — this guide is for you. Read it top to bottom once, then follow the "Quick Start" at the bottom.

---

## 📁 Project Folder Structure

```
Isro Projeect/
│
├── app.py                          ← 🖥️  THE MAIN DASHBOARD (run this)
├── topology.yaml                   ← 🗺️  Network map definition
├── documentation.md                ← 📖  Architecture & design reference
├── submission_ppt_guide.md         ← 🎯  PPT slide filling guide
│
└── ps13_copilot/                   ← 🐍  All the AI/Python code lives here
    │
    ├── __init__.py                 ← (ignore — just marks it as a package)
    ├── requirements.txt            ← 📦  Python packages list
    │
    ├── noc_copilot_prompt.py       ← 🤖  The LLM brain (most important file)
    ├── noc_engine.py               ← 🔗  Glue that wires everything together
    │
    ├── train_pipeline.py           ← 🏋️  Train the ML models (run this first)
    ├── data_augmentation.py        ← 📊  Generates synthetic training data
    │
    ├── time_to_impact.py           ← ⏱️  "When will it fail?" forecasting
    ├── topology_graph.py           ← 🌐  Network map & alert correlation
    ├── bgp_instability_detector.py ← 📡  Detects BGP routing failures
    ├── airgap_verify.py            ← 🔒  Proves no internet connectivity
    ├── mock_sdwan_controller.py    ← 🎮  Fake SD-WAN API for demo data
    │
    └── knowledge_base/             ← 📚  Runbooks for the AI to read
        ├── runbook_congestion.md
        ├── runbook_bgp_flap.md
        ├── runbook_tunnel_degradation.md
        └── runbook_policy_drift.md
```

---

## 📘 What Every File Does — Plain English

---

### `app.py` — The Dashboard
**What it is:** The main Streamlit web app. This is the thing you show to judges.
**What it shows:**
- A live interactive network topology map
- Real-time metrics (utilization %, packet loss, jitter)
- AI-generated alert cards with root cause explanations
- A SHAP signal importance bar chart
- Air-gap compliance auditor panel
- Syslog console

**You run it like this:**
```bash
streamlit run app.py
```
Then open your browser at `http://localhost:8501`

---

### `topology.yaml` — Network Map Definition
**What it is:** A YAML config file describing your simulated 5-node network.
**What it defines:**
- Node names: `CE-Hub`, `PE-Hub`, `P-1`, `PE-1`, `CE-Branch1`
- What role each node plays: hub, PE router, P router, branch
- Which links connect which nodes and at what speeds (1Gbps / 10Gbps)
- Which VRFs (virtual networks) each node participates in

**You don't run this.** It gets read automatically by `topology_graph.py`.
If you had Containerlab installed, you'd run it with:
```bash
containerlab deploy -t topology.yaml
```

---

### `ps13_copilot/noc_copilot_prompt.py` — The LLM Brain ⭐ Most Important
**What it is:** The code that talks to the local AI model (Ollama/Qwen-3 8B) and gets back structured JSON responses.
**What it does:**
- Builds a detailed system prompt injecting: telemetry values, SHAP signals, topology scope, and runbook excerpts
- Calls `http://localhost:11434` (Ollama server) with `format: "json"` mode
- Validates the response against a strict 12-field JSON schema
- Auto-retries up to 3 times if validation fails

**What it outputs** (the JSON fields judges care about):
```json
{
  "issue_type": "CONGESTION_BUILDUP",
  "severity": "CRITICAL",
  "confidence_pct": 87,
  "time_to_impact_min": 14,
  "affected_devices": ["PE-1", "CE-Branch1"],
  "root_cause_hypothesis": "...",
  "recommended_actions": [{"priority": 1, "action": "...", "target": "..."}],
  "operator_summary": "..."
}
```

**You don't run this directly.** It's called by `noc_engine.py`. But you can test it standalone:
```bash
python ps13_copilot/noc_copilot_prompt.py
```
> ⚠️ Requires Ollama to be running first (see Quick Start below)

---

### `ps13_copilot/train_pipeline.py` — ML Model Trainer 🏋️
**What it is:** A script that trains and saves the two predictive ML models to disk.
**What it trains:**
1. **XGBoost classifier** — Learns to tell the difference between Normal, Congestion, BGP Flap, Tunnel Degradation, and Policy Drift from telemetry features
2. **IsolationForest** — Learns what "normal" looks like so it can flag anything weird as an outlier

**Where models get saved:**
```
ps13_copilot/models/xgb_fault_model.json     ← XGBoost model file
ps13_copilot/models/iforest_model.joblib     ← IsolationForest model file
```

**You run it ONCE before starting the dashboard:**
```bash
python ps13_copilot/train_pipeline.py
```

**Expected output:**
```
XGBoost accuracy: 94%
IsolationForest fault detection: 93.8%
Models saved to disk.
Predicted fault: CONGESTION | Confidence: 87%
```
Once run, the models are saved and the dashboard loads them automatically.

---

### `ps13_copilot/data_augmentation.py` — Fake Training Data Generator 📊
**What it is:** The code that creates synthetic (made-up but realistic) network telemetry data for training the ML models.
**Why it exists:** We don't have weeks of real network data. This generates:
- Hours of normal baseline traffic (utilization 20–45%, low jitter, no BGP flaps)
- Simulated congestion ramps (utilization slowly climbing to 95%)
- Simulated BGP flapping events (routes dropping every 7.5 minutes)
- Simulated tunnel degradation (packet loss rising 0% → 14%)
- Simulated policy drift (DSCP ratio falling 0.20 → 0.01)

Also applies **data augmentation** — adds tiny random noise to make 5× more training samples.

**You don't run this directly.** `train_pipeline.py` calls it automatically.
But if you want to test data generation alone:
```bash
python ps13_copilot/data_augmentation.py
```

---

### `ps13_copilot/time_to_impact.py` — "When Will It Fail?" Forecaster ⏱️
**What it is:** Uses Facebook's Prophet library to forecast metric trends and predict the exact minute when a metric will cross the SLA danger threshold.
**What it does:**
- Takes the last 30 minutes of a metric (e.g., interface utilization history)
- Fits a trend model
- Projects 30 minutes forward
- Finds the first point where the prediction exceeds the threshold (e.g., 85%)
- Returns: `"will breach in 14 minutes"`

**SLA thresholds it monitors:**
| Metric | Alert Threshold |
|:---|:---|
| Interface utilization | > 85% |
| Packet loss | > 1% |
| Jitter | > 30 ms |
| Latency | > 50 ms |

**You don't run this directly.** It's called by `noc_engine.py` during each polling cycle.
Test it standalone with:
```bash
python ps13_copilot/time_to_impact.py
```

---

### `ps13_copilot/topology_graph.py` — Network Map & Alert Scope 🌐
**What it is:** Loads the 5-node network from `topology.yaml` into a NetworkX graph, then uses BFS (like a flood-fill from a root node) to find all downstream devices that are impacted when one node fails.
**What it does:**
- Parses `topology.yaml` to build the node/link graph
- When alert fires on `PE-1`, it finds: `CE-Branch1`, `CE-Branch2` are downstream
- Deduplicates alerts (if 3 alerts all point to the same upstream failure, collapse them into 1)
- Generates Plotly visualization data for the dashboard map

**You don't run this directly.** It's used by `noc_engine.py`.

---

### `ps13_copilot/bgp_instability_detector.py` — BGP Routing Failure Detector 📡
**What it is:** Reads live syslog messages and counts how many BGP neighbor state-change events happened in the last 10 minutes using a sliding window.
**What it detects:** Lines like:
```
BGP neighbor 10.0.0.1 went from Established to Idle
BGP neighbor 10.0.0.1 Established — 312 prefixes received
Route count dropped by 47 prefixes
```
**Severity rules:**
- 1–2 flaps in 10 min → `WARNING`
- 3–5 flaps in 10 min → `HIGH`
- 6+ flaps in 10 min → `CRITICAL`

**You don't run this directly.** It's called by `noc_engine.py`.
Test it standalone with:
```bash
python ps13_copilot/bgp_instability_detector.py
```

---

### `ps13_copilot/airgap_verify.py` — Air-Gap Proof 🔒
**What it is:** A security verification script that proves our system has zero internet access.
**What it checks:**
1. Tries to connect to `8.8.8.8` (Google DNS) → must fail
2. Tries to connect to `1.1.1.1` (Cloudflare DNS) → must fail
3. Tries to resolve `google.com` → must fail
4. Tries to connect to `api.openai.com` → must fail
5. Tries to connect to `ollama.com` → must fail
6. Scans active network connections for any non-local IPs
7. Confirms LLM model weights exist locally on disk

**Run this live during your demo** to prove air-gap compliance:
```bash
python ps13_copilot/airgap_verify.py
```
**Expected output:**
```
✅ BLOCKED  — 8.8.8.8:53 (Google DNS)
✅ BLOCKED  — 1.1.1.1:53 (Cloudflare DNS)
✅ BLOCKED  — api.openai.com:443
✅ BLOCKED  — ollama.com:443
✅ 0 active external connections found
✅ Local model weights found at C:\Users\...
[COMPLIANT] All air-gap checks passed.
```

---

### `ps13_copilot/mock_sdwan_controller.py` — Fake Network API 🎮
**What it is:** A FastAPI web server that pretends to be an SD-WAN network controller. It provides fake tunnel metrics so Telegraf has something to scrape — no real routers needed for the demo.
**What it serves:** REST API at `http://localhost:8080`
```
GET  /api/v1/health              → Check if controller is running
GET  /api/v1/tunnels             → Returns 5 IPSec tunnel states with metrics
POST /api/v1/inject/loss         → Inject packet loss on a tunnel
POST /api/v1/inject/latency      → Inject latency spike
POST /api/v1/inject/jitter       → Inject jitter spike
POST /api/v1/inject/rekey_failure→ Simulate IPSec rekey failure
POST /api/v1/inject/clear        → Remove all injected faults
POST /api/v1/scenario/tunnel_degradation → Auto-run Scenario 3
```

**Run it in a separate terminal before starting the dashboard:**
```bash
python -m uvicorn ps13_copilot.mock_sdwan_controller:app --host 0.0.0.0 --port 8080
```
Then test it works:
```bash
curl http://localhost:8080/api/v1/tunnels
```

---

### `ps13_copilot/noc_engine.py` — The Glue Layer 🔗
**What it is:** The main orchestrator that runs one complete "polling cycle" — calls every other module in the right order and returns a final incident report.
**What happens each cycle:**
1. Receives current telemetry list + syslog list
2. Updates sliding telemetry history buffer
3. Runs BGP flap detector on syslogs
4. For each device, runs ML prediction + SHAP + Prophet forecast
5. Correlates alerts using NetworkX topology
6. Queries ChromaDB for matching runbook
7. Calls Ollama to generate the final structured JSON report

**You don't run this directly.** `app.py` calls it every time you click "Trigger Polling Cycle".
Test it with the built-in test scenario:
```bash
python ps13_copilot/noc_engine.py
```

---

### `ps13_copilot/knowledge_base/` — AI Runbook Library 📚
**What these are:** 4 plain-text markdown files that act as the AI's "knowledge source". ChromaDB converts them into vectors and retrieves the relevant one when an alert fires.

| File | Covers |
|:---|:---|
| `runbook_congestion.md` | How to diagnose and fix link congestion |
| `runbook_bgp_flap.md` | How to diagnose and fix BGP routing instability |
| `runbook_tunnel_degradation.md` | How to fix IPSec tunnel packet loss |
| `runbook_policy_drift.md` | How to restore missing QoS policies |

**You don't run these.** `noc_engine.py` indexes them automatically on first startup.

---

---

## 🚀 Quick Start — Step by Step

### Step 1: Install Ollama (the local AI server)
Download from https://ollama.com and install it.
Then pull the model:
```bash
ollama pull qwen3:8b
```
> This downloads ~5GB. Do it on WiFi. Once downloaded, you can disconnect internet for the demo.
> If 8B is too slow on your machine, use: `ollama pull phi4-mini` (smaller, faster)

---

### Step 2: Install Python packages (already done if you ran pip before)
```bash
pip install -r ps13_copilot/requirements.txt
```

---

### Step 3: Train the ML models (run ONCE)
```bash
cd "c:\Users\Admin\Desktop\Kshitiz\Isro Projeect"
python ps13_copilot/train_pipeline.py
```
Wait for it to finish. You'll see `Models saved to disk.` when done.

---

### Step 4: Start the Mock SD-WAN Controller (in Terminal 1)
Open a new terminal window and run:
```bash
cd "c:\Users\Admin\Desktop\Kshitiz\Isro Projeect"
python -m uvicorn ps13_copilot.mock_sdwan_controller:app --host 0.0.0.0 --port 8080
```
Leave this running. You'll see: `Uvicorn running on http://0.0.0.0:8080`

---

### Step 5: Start Ollama (in Terminal 2)
```bash
ollama serve
```
> If Ollama was already running in the background, skip this. Check by visiting http://localhost:11434

---

### Step 6: Launch the Dashboard (in Terminal 3)
```bash
cd "c:\Users\Admin\Desktop\Kshitiz\Isro Projeect"
streamlit run app.py
```
Open browser at: **http://localhost:8501**

---

### Step 7: Demo Walkthrough
Once the dashboard is open:
1. **Select "Scenario 1: Congestion Buildup"** from the left sidebar dropdown
2. Click **"🔄 Trigger Polling Cycle"** to run one analysis
3. Watch the **alert card appear** on the right panel with AI reasoning
4. **Select "Scenario 2: BGP Route Flap"** and trigger again
5. Go to the **"🔒 Air-Gap Security Inspector"** tab to show compliance
6. Go to the **"📚 Search Runbooks"** tab, type "congestion" — see ChromaDB return the right runbook

---

### Step 8: Run Air-Gap Verification (for judges)
In a separate terminal, run:
```bash
python ps13_copilot/airgap_verify.py
```
Show the terminal output live to the judges.

---

## ⚠️ Common Problems & Fixes

| Problem | Cause | Fix |
|:---|:---|:---|
| `ModuleNotFoundError: xgboost` | pip packages not installed | Run `pip install -r ps13_copilot/requirements.txt` |
| `ConnectionRefusedError` on port 11434 | Ollama not running | Run `ollama serve` in a terminal |
| Dashboard says "Models not trained" | `train_pipeline.py` hasn't been run | Run `python ps13_copilot/train_pipeline.py` first |
| No alert cards appear | Scenario is set to "Normal Operations" | Change scenario in sidebar dropdown |
| `streamlit: command not found` | Streamlit not installed or not on PATH | Run `pip install streamlit` |
| Controller shows disconnected | `mock_sdwan_controller.py` not running | Run uvicorn command from Step 4 |

---

## 🎯 Which Files to Show During the Demo

| Demo Moment | What to Show |
|:---|:---|
| "This is our network topology" | `topology.yaml` (open in VS Code) |
| "This is how we predict failures" | `time_to_impact.py` (show the Prophet logic briefly) |
| "This is our ML classifier" | Terminal output of `train_pipeline.py` (94% accuracy) |
| "This is our AI copilot" | `noc_copilot_prompt.py` (show the JSON schema section) |
| "This proves we're offline" | Run `airgap_verify.py` live |
| "This is the full system" | Streamlit dashboard at `http://localhost:8501` |

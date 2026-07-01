# Problem Statement 13 — Full Roadmap & Options Guide
## Air-Gapped Predictive Copilot for Secure MPLS Operations

---

## What Are They Actually Asking For?

In plain English, ISRO wants you to build a **smart, self-contained network operations center (NOC) assistant** that:

1. **Runs a fake network** (simulated routers, switches, tunnels) so you have something to monitor.
2. **Predicts problems before they happen** — not after. If a link is slowly getting congested, or a routing protocol is starting to flap, your system should raise a warning **before** the network actually breaks.
3. **Has a local AI chatbot** (like ChatGPT but running entirely on your laptop/server with zero internet) that can explain to a network operator: "Hey, link between Branch-2 and Hub is likely to saturate in ~15 minutes because traffic has increased 40% in the last hour. Here's what you should do..."
4. **Zero internet dependency.** Everything runs offline. No cloud APIs, no external calls. This is the "air-gapped" part.

### The 3 Questions Your System Must Answer

| # | Question | What It Means |
|:--|:---------|:-------------|
| Q1 | "What is likely to fail next — and when?" | Your ML model must **forecast** faults with a measurable lead time |
| Q2 | "Why is the risk elevated — which signals contributed?" | Your system must provide **explainable** reasoning (not just "alert!") |
| Q3 | "What corrective action should be taken?" | Your LLM copilot must suggest **specific remediation steps** |

---

## Evaluation Weights — Where the Marks Are

This is critical. Know where the judges are allocating points:

| Dimension | Weight | What They're Grading |
|:----------|:------:|:---------------------|
| **Technical Merit** | **35%** | Prediction accuracy, lead time before failure, false-positive rate |
| **Copilot Effectiveness** | **35%** | Are LLM explanations correct, grounded in local data, no hallucinations? |
| **Security & Offline Compliance** | **20%** | Zero outbound network calls during runtime, all data stays local |
| **Documentation Quality** | **10%** | Architecture diagrams, design rationale, clear writeup |

> [!IMPORTANT]
> Technical Merit and Copilot together = **70%** of your score. The ML prediction engine and the LLM chatbot quality are equally important. Don't sacrifice one for the other.

---

## The 4 Objectives — Broken Down

### Objective 1: Simulated SD-WAN/MPLS Network
**What they want:** A fake but realistic multi-site network with routers, VPN tunnels, and traffic flowing through it.

**Key components to simulate:**
- **Branch sites** (small offices) connecting to a **Hub** (central office) and **Datacenter**
- **CE/PE/P routers:** Customer Edge → Provider Edge → Provider core (the MPLS hierarchy)
- **MPLS forwarding** with VPN segmentation (VRFs)
- **SD-WAN overlay:** IPSec tunnels running on top of the MPLS underlay
- **Dynamic routing:** BGP (between sites) and OSPF (within sites)
- **QoS policies:** Priority marking for voice/video traffic
- **Traffic generation:** Realistic flows (HTTP, DNS, video streaming)
- **Fault injection:** Ability to break things on purpose (drop a link, cause congestion, flap a route)

---

### Objective 2: Predictive Fault Analytics Engine
**What they want:** ML models that detect **precursor** conditions — signals that a failure is building up, not that it has already happened.

**4 prediction targets:**
1. **Congestion forecasting:** Interface utilization slowly climbing toward 100%
2. **Routing instability:** BGP/OSPF adjacency flaps, route withdrawals, path asymmetry
3. **Tunnel health degradation:** Packet loss increasing, jitter spiking, IPSec rekey failures
4. **Time-to-impact estimation:** "This link will saturate in approximately 12 minutes"

---

### Objective 3: Offline LLM NOC Copilot
**What they want:** A local, fully offline chatbot that:
- Reads topology maps, runbooks, and past incident records via RAG
- Produces structured responses: **predicted issue, confidence score, root cause, affected scope, recommended actions**
- Has a natural-language query interface for NOC operators

---

### Objective 4: Integrated NOC Workflow Automation
**What they want:** Tying everything together:
- Continuous topology awareness (knows which devices are connected to what)
- Confidence-scored alert prioritization (most dangerous first)
- Automated playbook suggestions
- Operator-ready incident summaries

---

## Component-by-Component Options Analysis

### 🔧 Component 1: Network Simulation

| Tool | Type | Setup Time | Best For | Recommendation |
|:-----|:-----|:----------:|:---------|:---------------|
| **Containerlab** | Container-native (Docker) | ~1-2 hrs | Hackathons, IaC, fast spin-up | ⭐ **RECOMMENDED** |
| **GNS3** | Desktop VM-based | ~2-4 hrs | Solo prototyping, visual topology | Good alternative |
| **EVE-NG** | Web GUI, VM-based | ~2-4+ hrs | Enterprise multi-vendor labs | Overkill for hackathon |

#### Why Containerlab wins for a hackathon:
- **Speed:** Topologies are defined in a single YAML file. `clab deploy` and your entire network is up in seconds.
- **Git-friendly:** Your entire network topology is version-controlled as code.
- **Lightweight:** Uses Docker containers, not heavy VMs. Runs on a laptop.
- **Integration:** Native support for Nokia SR Linux, Arista cEOS, and FRRouting (open-source router) containers.

#### What router images to use:
| Option | License | MPLS Support | BGP/OSPF | Ease of Use |
|:-------|:--------|:-------------|:---------|:------------|
| **FRRouting (FRR)** | Free/Open-source | Yes (LDP) | Full | ⭐ **RECOMMENDED** |
| **Nokia SR Linux** | Free Community | Yes (SR-MPLS) | Full | Good but complex |
| **Arista cEOS** | Free with registration | Limited | Full | Good for L3 |
| **Cisco IOSv** | Requires license | Full | Full | Not free |

> [!TIP]
> **For a hackathon, use FRRouting containers inside Containerlab.** FRR is fully open-source, supports MPLS/LDP, BGP, OSPF, and is the backbone of many production Linux-based routers. Zero licensing issues.

#### Traffic generation tools:
| Tool | What It Does | Why Use It |
|:-----|:------------|:-----------|
| **iperf3** | Generate TCP/UDP traffic at controlled bandwidth | Simple, reliable, controls bandwidth |
| **TRex (by Cisco)** | Realistic multi-protocol traffic generation | Most realistic, supports replaying pcaps |
| **hping3** | Craft custom TCP/UDP/ICMP packets | Good for fault injection (SYN floods, etc.) |
| **tc (Linux traffic control)** | Add latency, jitter, packet loss to interfaces | Perfect for simulating degradation |

#### Fault injection strategies:
| Fault Scenario | How to Inject | What It Tests |
|:---------------|:-------------|:-------------|
| Progressive congestion | `iperf3` slowly increasing bandwidth | Congestion forecasting |
| BGP route flap | `vtysh` commands to toggle BGP neighbor | Routing instability detection |
| Link failure | `ip link set dev ethX down` | Tunnel failover detection |
| Latency/jitter spike | `tc qdisc add dev ethX netem delay 100ms 50ms` | Tunnel health scoring |
| Packet loss ramp | `tc qdisc add dev ethX netem loss 5%` → 10% → 20% | Gradual degradation tracking |

---

### 📊 Component 2: Telemetry Pipeline

You need to **collect** data from the simulated devices and **store** it in a time-series format for ML consumption.

#### Collection Agent Options:
| Tool | Role | Footprint | Best For |
|:-----|:-----|:----------|:---------|
| **Telegraf** | Universal collector agent | Very light (single binary) | ⭐ **RECOMMENDED** — 400+ input plugins |
| **OpenTelemetry Collector** | Unified metrics/logs/traces | Medium | Good if you want industry-standard format |
| **Custom Python scripts** | Direct SNMP polling / log parsing | Minimal | Full control, more code to write |

#### Storage Backend Options:
| Tool | Role | Footprint | Best For |
|:-----|:-----|:----------|:---------|
| **Prometheus** | Time-series metrics DB | Medium | ⭐ **RECOMMENDED for metrics** — PromQL querying, built-in alerting |
| **InfluxDB** | Time-series DB | Medium | Alternative to Prometheus, SQL-like query |
| **Elasticsearch (ELK)** | Log search/indexing engine | Heavy (JVM) | Only if you need full-text log search |
| **SQLite / CSV files** | Flat file storage | Minimal | Simplest option for hackathon — just dump to CSV |

#### Recommended Stack for Hackathon:
```
Simulated Network (Containerlab + FRR)
          ↓
    Telegraf Agent
    (collects SNMP, syslog, interface stats)
          ↓
    Prometheus (metrics storage)
          ↓
    Export to CSV/Parquet for ML training
```

> [!TIP]
> **Hackathon shortcut:** If time is tight, skip Prometheus entirely. Use **Telegraf → CSV output plugin** to dump metrics directly into flat files. Then load them into Pandas for ML. You can always add Prometheus later for the dashboard.

---

### 🧠 Component 3: Predictive ML Models — The Feature Engineering & Model Selection

This is the **35% Technical Merit** portion. Here's everything you need to know.

#### Feature Categories to Extract

##### A. Interface/Link Health Features (from SNMP or Telegraf)

| Feature | Source | What It Captures | Transform |
|:--------|:-------|:-----------------|:----------|
| `if_in_octets` / `if_out_octets` | SNMP ifTable | Bytes flowing through interface | **Rate (delta/sec)** then **log1p** |
| `if_in_errors` / `if_out_errors` | SNMP ifTable | Physical/data-link errors | **Rate** |
| `if_in_discards` / `if_out_discards` | SNMP ifTable | Packets dropped due to congestion | **Rate** — high signal for congestion |
| `if_utilization_pct` | Derived | % of interface bandwidth used | `(octets_rate * 8) / if_speed * 100` |
| `if_in_ucast_pkts` / `if_in_broadcast_pkts` | SNMP ifTable | Unicast vs broadcast ratio | High broadcast = possible loop |

##### B. Routing Protocol Features (from Syslog / BGP-MIB)

| Feature | Source | What It Captures | Why It Matters |
|:--------|:-------|:-----------------|:-------------|
| `bgp_state_changes_count` | Syslog events | Number of BGP state transitions in window | Flapping = instability |
| `bgp_prefixes_received` | BGP-MIB | Routes learned from neighbor | Sudden drop = route withdrawal |
| `ospf_neighbor_state` | OSPF-MIB | Neighbor adjacency status | Going to "Init" from "Full" = problem |
| `route_count_delta` | Routing table | Change in total route count per window | Large delta = convergence event |

##### C. Tunnel / Overlay Features (from SD-WAN controller or ping probes)

| Feature | Source | What It Captures | Why It Matters |
|:--------|:-------|:-----------------|:-------------|
| `tunnel_latency_ms` | ICMP probes / BFD | Round-trip time through tunnel | Drift = degradation |
| `tunnel_jitter_ms` | Derived | Variance in latency measurements | High jitter = bad for VoIP/video |
| `tunnel_packet_loss_pct` | Ping loss count | % of packets dropped | Progressive loss = link dying |
| `tunnel_uptime_sec` | Controller stats | Time since last tunnel reset | Frequent resets = instability |
| `ipsec_rekey_failures` | Syslog | Failed IPSec re-negotiations | Rekey anomalies = security issue |

##### D. Temporal / Derived Features (Engineered)

| Feature | How to Compute | Why It Helps |
|:--------|:---------------|:-------------|
| `utilization_rate_of_change` | Slope of utilization over last N windows | Positive slope = congestion building |
| `utilization_5min_avg` / `15min_avg` | Moving average | Smooths noise, captures trends |
| `error_ratio` | `errors / total_packets` | Normalizes error count by traffic volume |
| `bytes_asymmetry_ratio` | `in_bytes / (in_bytes + out_bytes)` | Extreme asymmetry = DDoS or exfiltration |
| `time_of_day_encoded` | sin/cos encoding of hour | Captures daily traffic cycles |
| `is_business_hours` | Binary flag | Different baselines for day vs night |

> [!IMPORTANT]
> **The judges grade on "prediction lead time."** Your features must capture **trends** (rates of change, moving averages, slopes), not just instantaneous values. A model trained only on snapshot values will detect failures at the moment they happen, not predict them. That scores poorly.

#### ML Model Options Comparison

| Model | Best For | Pros | Cons | Hackathon Fit |
|:------|:---------|:-----|:-----|:-------------|
| **XGBoost / LightGBM** | Tabular anomaly classification | ⭐ Fast training, handles mixed features, excellent on tabular data, explainable (SHAP) | Doesn't natively model sequences | ⭐⭐⭐⭐⭐ |
| **LSTM** | Time-series sequence modeling | Captures long-range temporal dependencies | Slow training, needs GPU, black-box | ⭐⭐⭐☆☆ |
| **Prophet** | Seasonal trend forecasting | Dead-simple API, handles seasonality and holidays | Too simple for complex multivariate signals | ⭐⭐⭐⭐☆ |
| **Isolation Forest** | Unsupervised anomaly detection | No labels needed, finds outliers automatically | Can't predict "when" — only "something is weird" | ⭐⭐⭐⭐☆ |
| **LSTM Autoencoder** | Unsupervised anomaly via reconstruction error | Learns "normal" baseline, flags deviations | Harder to train, needs tuning | ⭐⭐⭐☆☆ |
| **Transformer (PatchTST)** | State-of-the-art time-series forecasting | Best accuracy on benchmarks | Complex, heavy, overkill for 30hrs | ⭐⭐☆☆☆ |

#### ⭐ Recommended Strategy: Hybrid Ensemble

Use **multiple models** together for maximum score:

```
Telemetry Features (windowed)
         ↓
┌────────────────────────────────────────┐
│                                        │
│  Prophet           → Forecast next     │
│  (per-metric)        15-30 min values  │
│                                        │
│  XGBoost/LightGBM → Classify current   │
│  (multi-feature)    state as Normal /  │
│                     Warning / Critical │
│                                        │
│  Isolation Forest  → Flag unseen       │
│  (unsupervised)     anomaly patterns   │
│                                        │
└────────────────────────────────────────┘
         ↓
    Ensemble Logic
    (weighted vote or stacked meta-classifier)
         ↓
    Alert with:
    - Predicted issue type
    - Confidence score
    - Estimated time-to-impact
    - Contributing features (SHAP values)
```

**Why this works:**
- **Prophet** gives you the "when" — time-series forecasting extrapolates utilization curves into the future.
- **XGBoost** gives you the "what" — classifies the current multivariate state into Normal/Warning/Critical.
- **Isolation Forest** catches the "unknown unknowns" — anomalies you didn't inject during training.
- **SHAP** gives you the "why" — feature importance explains which signals contributed (directly feeds Q2 to the LLM copilot).

> [!TIP]
> **Your TON-IoT pipeline already does the XGBoost/LightGBM classification part.** You can directly reuse your feature engineering logic (`log1p` transforms, ratio features, label encoding) from [splitfed_toniot_train.py](file:///c:/Users/Admin/Desktop/Kshitiz/ton-iot-project/splitfed_toniot_train.py).

---

### 🤖 Component 4: Offline LLM — The NOC Copilot

This is the other **35%** of your score. Choose carefully.

#### LLM Model Options

| Model | Size | VRAM Needed (Q4) | Strengths | License |
|:------|:-----|:-----------------:|:----------|:--------|
| **Qwen3 8B** | 8B | ~5 GB | ⭐ Best all-rounder, strong reasoning + multilingual | Apache 2.0 |
| **Llama 4 Scout** | 8-17B | ~6-10 GB | Industry standard, massive ecosystem | Llama License |
| **Mistral Small 3.1** | 24B | ~14 GB | Excellent for agentic + structured output | Apache 2.0 |
| **Phi-4-mini** | 3.8B | ~2.5 GB | Runs on potato hardware, surprisingly smart | MIT |
| **DeepSeek-R1-Distill 8B** | 8B | ~5 GB | Best step-by-step reasoning | MIT |
| **Gemma 3 4B** | 4B | ~3 GB | Good balance of size and capability | Apache 2.0 |

#### Recommendation by Hardware:

| Your Hardware | Model to Use | Why |
|:-------------|:------------|:----|
| **Laptop with no GPU** | Phi-4-mini (Q4) | Only needs ~3 GB RAM, runs on CPU |
| **8 GB VRAM (RTX 3060/4060)** | Qwen3 8B (Q4_K_M) | ⭐ **Best option** — strong reasoning in small package |
| **12-16 GB VRAM (RTX 4070/4080)** | Mistral Small 3.1 or DeepSeek-R1-Distill 14B | Excellent structured output |
| **24+ GB VRAM** | Qwen3 32B or DeepSeek-R1-Distill 32B | Maximum intelligence |

#### LLM Runtime / Serving Options

| Tool | Ease of Use | Performance | Best For |
|:-----|:------------|:-----------|:---------|
| **Ollama** | ⭐ Easiest (1 command to run) | Good | ⭐ **RECOMMENDED for hackathon** |
| **llama.cpp (llama-server)** | Hard (manual setup) | ⭐ Best raw speed | If you need max performance |
| **LocalAI** | Medium (Docker) | Good | If you want OpenAI-compatible API in Docker |
| **vLLM** | Medium | ⭐ Best for production | Overkill for hackathon |

#### Why Ollama:
```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Pull model (one command)
ollama pull qwen3:8b

# Run with OpenAI-compatible API
ollama serve
# API available at http://localhost:11434
```
- Zero config. Works immediately.
- OpenAI-compatible API → integrates with LangChain, LlamaIndex, or raw HTTP calls.
- Manages model files, GPU offloading, and quantization automatically.

---

### 📚 Component 5: RAG Pipeline (Retrieval-Augmented Generation)

The RAG system feeds your LLM copilot with **local context** — topology docs, runbooks, past incidents — so it gives grounded answers instead of hallucinating.

#### Vector Database Options

| DB | Ease of Use | Performance | Metadata Support | Best For |
|:---|:------------|:-----------|:----------------|:---------|
| **ChromaDB** | ⭐ Easiest | Good | Built-in | ⭐ **RECOMMENDED** — fastest to set up |
| **LanceDB** | High | ⭐ Best disk efficiency | Built-in (columnar) | Production-grade local apps |
| **FAISS** | Low (library, not DB) | ⭐ Fastest raw search | None (manual) | If you need max speed and will build the plumbing |

#### Why ChromaDB for hackathon:
```python
import chromadb

# 3 lines to create a collection
client = chromadb.Client()
collection = client.create_collection("noc_knowledge")

# Add documents
collection.add(
    documents=["Runbook: If BGP flaps, check MTU mismatch first..."],
    metadatas=[{"type": "runbook", "topic": "bgp"}],
    ids=["doc1"]
)

# Query
results = collection.query(query_texts=["BGP neighbor is flapping"], n_results=3)
```

#### Embedding Model Options (for converting text → vectors)

| Model | Size | Quality | Offline? |
|:------|:-----|:--------|:---------|
| **all-MiniLM-L6-v2** | 80 MB | Good | ⭐ Yes — runs locally via sentence-transformers |
| **nomic-embed-text** | 274 MB | Better | Yes — available via Ollama |
| **bge-small-en-v1.5** | 130 MB | Good | Yes |
| **GTE-base** | 220 MB | ⭐ Best quality in class | Yes |

#### RAG Framework Options

| Framework | Best For | Complexity | Recommendation |
|:----------|:---------|:-----------|:---------------|
| **LlamaIndex** | Document-heavy Q&A RAG | Medium | ⭐ **RECOMMENDED** — built specifically for retrieval, less code |
| **LangChain** | Complex multi-step agentic workflows | High | Good if you want agentic copilot with tool-calling |
| **Raw Python** | Full control, no dependencies | Low | If you want minimal deps and understand the pipeline |

#### What documents to put in the RAG knowledge base:

| Document Type | Contents | Why It Helps |
|:-------------|:---------|:-------------|
| **Topology Map** | JSON/YAML describing all devices, interfaces, IPs, connections | LLM can say "the link between Router-PE1 and Router-P1" |
| **Runbooks** | Step-by-step troubleshooting guides for common issues | LLM can recommend specific actions |
| **Past Incidents** | Historical alert logs with root causes and resolutions | LLM can pattern-match to past events |
| **Device Configs** | Router/switch configuration snippets | LLM can reference specific QoS policies or routing configs |
| **SLA Definitions** | Service-level thresholds (e.g., latency < 50ms) | LLM can calculate time-to-SLA-breach |

---

### 🖥️ Component 6: Dashboard / UI

| Tool | Type | Best For | Recommendation |
|:-----|:-----|:---------|:---------------|
| **Streamlit** | Python-native web app | ⭐ **RECOMMENDED** — fastest to build, you have experience | Rapid prototyping |
| **Grafana** | Metrics dashboarding | Pre-built Prometheus integration, time-series graphs | Good for metrics visualization |
| **Next.js + React** | Full web application | Production-grade frontend | Overkill for 30-hour hackathon |
| **Streamlit + Grafana hybrid** | Best of both | Grafana for metrics, Streamlit for copilot chat | ⭐ Ideal if time allows |

#### Dashboard Must-Have Panels:

1. **Network Topology View** — Visual map of devices and link states (green/yellow/red)
2. **Real-Time Metrics** — Time-series charts of interface utilization, latency, jitter
3. **Alert Feed** — Confidence-scored, prioritized alerts with severity badges
4. **Copilot Chat** — Text input where operator types questions, LLM responds with structured analysis
5. **Prediction Timeline** — Bar showing "time to predicted failure" for each active warning

---

## 30-Hour Hackathon Timeline

| Phase | Hours | What To Do | Deliverable |
|:------|:-----:|:-----------|:-----------|
| **Phase 1: Network Sim** | 0-4 | Deploy Containerlab + FRR topology (3-5 routers), configure BGP/OSPF, run iperf3 traffic | Working simulated network |
| **Phase 2: Telemetry** | 4-8 | Set up Telegraf → CSV/Prometheus, collect interface stats, syslog, routing events | Clean telemetry dataset |
| **Phase 3: Fault Injection** | 8-10 | Run fault scenarios (congestion ramp, BGP flap, link drop), label data with ground truth | Labeled training dataset |
| **Phase 4: ML Training** | 10-16 | Feature engineering, train Prophet + XGBoost + IsolationForest ensemble, validate lead time | Working prediction engine |
| **Phase 5: LLM + RAG** | 16-22 | Deploy Ollama + Qwen3, set up ChromaDB with topology docs and runbooks, wire ML alerts into LLM context | Working copilot |
| **Phase 6: Dashboard** | 22-26 | Build Streamlit UI with topology view, alert feed, copilot chat, prediction timeline | Interactive demo |
| **Phase 7: Validation** | 26-28 | Run 4 evaluation scenarios, record lead times, copilot accuracy, take screenshots | Validation results |
| **Phase 8: Documentation** | 28-30 | Architecture diagram, design rationale document, demo preparation | Final submission |

---

## Your Existing Codebase — What You Can Directly Reuse

| Your Existing Code | Where It Fits in PS13 | How to Adapt |
|:-------------------|:---------------------|:-------------|
| [TON-IoT feature engineering](file:///c:/Users/Admin/Desktop/Kshitiz/ton-iot-project/PROJECT_CONTEXT.md) | Telemetry feature pipeline | Replace network flow columns with SNMP/interface metrics. Keep `log1p`, ratio, and encoding logic |
| [XGBoost/LightGBM classifiers](file:///c:/Users/Admin/Desktop/Kshitiz/ton-iot-project/splitfed_toniot_train.py) | Predictive fault classifier | Retrain on network telemetry instead of IoT flows. Same hyperparameter tuning approach |
| [SplitFed framework](file:///c:/Users/Admin/Desktop/Kshitiz/ton-iot-project/src/splitfed/) | Air-gap innovation (bonus points) | Demonstrate that branch nodes train locally, send only quantized activations to hub |
| [NoPeek + DP + 8-bit Quantization](file:///c:/Users/Admin/Desktop/Kshitiz/reports/) | Security compliance (20% weight) | Show that raw telemetry never leaves the branch site |
| [Streamlit dashboard](file:///c:/Users/Admin/Desktop/Kshitiz/healthcare%20project/) | NOC Dashboard UI | Adapt patient triage layout → network health monitoring layout |

---

## Full Technology Stack Summary

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                    │
│                                                         │
│  Streamlit Dashboard                                    │
│  ├── Network Topology Map (NetworkX + Plotly)           │
│  ├── Real-Time Metrics Charts (Plotly/Altair)           │
│  ├── Alert Feed with Confidence Scores                  │
│  ├── Copilot Chat Interface                             │
│  └── Prediction Timeline                                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    INTELLIGENCE LAYER                    │
│                                                         │
│  Predictive Engine          │  LLM Copilot              │
│  ├── Prophet (forecast)     │  ├── Ollama runtime        │
│  ├── XGBoost (classify)     │  ├── Qwen3 8B (Q4_K_M)    │
│  ├── IsolationForest        │  ├── ChromaDB (vector DB)  │
│  │   (unsupervised)         │  ├── LlamaIndex (RAG)      │
│  └── SHAP (explainability)  │  └── Sentence-Transformers │
│                              │      (embeddings)          │
├─────────────────────────────────────────────────────────┤
│                    DATA LAYER                            │
│                                                         │
│  Telegraf (collection) → Prometheus (storage)           │
│  → Export to CSV/Parquet for ML training                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                  │
│                                                         │
│  Containerlab (orchestrator)                            │
│  ├── FRRouting containers (CE/PE/P routers)             │
│  ├── BGP + OSPF + MPLS/LDP                             │
│  ├── iperf3 / TRex (traffic generation)                │
│  └── tc netem (fault injection)                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Python Libraries You'll Need

```
# ML & Data
pandas
numpy
scikit-learn
xgboost
lightgbm
prophet
shap

# LLM & RAG
ollama                    # Ollama Python client
chromadb                  # Vector database
llama-index               # RAG framework
sentence-transformers     # Local embedding models

# Telemetry & Networking
pysnmp                    # SNMP polling (if not using Telegraf)
networkx                  # Graph topology modeling

# Dashboard
streamlit
plotly
altair

# Data I/O
pyarrow                   # Parquet file handling
prometheus-api-client     # Query Prometheus from Python
```

---

## Validation Scenarios (What Judges Will Test)

The problem statement explicitly lists 4 scenarios you must demonstrate:

| # | Scenario | What Happens | What Your System Should Do |
|:--|:---------|:------------|:--------------------------|
| 1 | **Progressive congestion** on hub-spoke link | iperf3 slowly ramps bandwidth to 90%+ | Prophet forecasts saturation in N minutes. XGBoost flags "Warning". Copilot says "Reroute traffic via backup path" |
| 2 | **BGP route flap** with cascade | BGP neighbor repeatedly drops and re-establishes | Routing instability detector fires. Copilot explains "BGP peer 10.0.0.1 flapped 5 times in 2 minutes, possible MTU mismatch" |
| 3 | **Intermittent MPLS underlay failure** | Periodic packet loss spikes on underlay link | Tunnel health scorer degrades. Copilot says "Underlay link eth1 showing 12% packet loss, recommend failover to secondary tunnel" |
| 4 | **Controller misconfiguration** causing policy drift | QoS policy changed incorrectly | Anomaly in traffic pattern detected. Copilot says "Voice traffic no longer prioritized, check QoS policy on PE-1" |

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| Team has no networking knowledge | Can't build simulation, features are meaningless | Start with a dead-simple 3-router topology. FRR has excellent docs. Focus on interface-level metrics first |
| LLM hallucinating technical advice | Loses 35% copilot score | Ground ALL responses via RAG. Always inject topology context and alert data into the prompt. Use structured output (JSON mode) |
| Not enough time to train ML models | Loses 35% technical score | Use pre-built Prophet for forecasting (fits in seconds). XGBoost trains in seconds on small datasets. Don't attempt deep learning |
| Judges test with a scenario you didn't prepare for | System looks broken | Train Isolation Forest as catch-all unsupervised detector. Even unknown anomalies get flagged |

"""
noc_copilot_prompt.py
=====================
PS13 — Air-Gapped Predictive NOC Copilot
Structured LLM prompt engineering module.

This module provides:
  1. SYSTEM_PROMPT          — the constant system instruction sent on every call
  2. NOC_OUTPUT_SCHEMA      — the enforced JSON output schema (for docs + validation)
  3. build_alert_context()  — assembles the full context string from ML + topology + RAG data
  4. call_copilot()         — makes the Ollama API call and returns a validated dict
  5. validate_response()    — ensures LLM output matches the required schema
  6. format_*()             — helper formatters for SHAP, syslog, RAG, topology

Usage:
  from noc_copilot_prompt import call_copilot, build_alert_context
  response = call_copilot(alert_data, shap_values, topology_ctx, rag_results, syslogs)
"""

import json
import time
import requests
import jsonschema
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 1. SYSTEM PROMPT
#    Sent as the "system" role on every Ollama call.
#    Rules: JSON-only output, no hallucination, confidence grounding.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert NOC (Network Operations Center) AI assistant embedded in a \
secure, air-gapped enterprise SD-WAN/MPLS network. Your role is to help network operators \
predict, diagnose, and remediate network faults before they impact services.

━━━ ABSOLUTE RULES ━━━

1. OUTPUT FORMAT: You MUST respond ONLY with a single valid JSON object matching the schema \
provided below. No markdown, no prose before or after, no code fences, no apologies.

2. NO HALLUCINATION: Only reference device names, IP addresses, interface names, VRF names, \
and metric values that appear verbatim in the provided context. If a fact is not in the \
context, set the relevant field to null. Never invent topology details.

3. CONFIDENCE GROUNDING: The confidence_pct field must reflect the strength of evidence in \
the provided telemetry signals and SHAP attributions — not your general knowledge. If signals \
are weak or ambiguous, the confidence must be lower (< 50).

4. ACTIONABLE SPECIFICITY: Every recommended action must name a specific device, interface, \
policy, or command. Generic advice ("check the network") is not acceptable.

5. SCOPE HONESTY: The affected_devices and affected_services fields must be derived from \
the "AFFECTED TOPOLOGY SCOPE" section of the context. Do not infer additional affected \
devices beyond what is listed there.

6. INSUFFICIENT DATA: If you cannot produce a meaningful analysis, set issue_type to \
"INSUFFICIENT_DATA", confidence_pct to 0, and explain in the reasoning field. \
Do NOT fabricate an analysis.

━━━ OUTPUT JSON SCHEMA ━━━

{
  "issue_type": "<string: one of CONGESTION_BUILDUP | BGP_INSTABILITY | TUNNEL_DEGRADATION | POLICY_DRIFT | UNKNOWN_ANOMALY | INSUFFICIENT_DATA>",
  "severity": "<string: CRITICAL | HIGH | MEDIUM | LOW>",
  "confidence_pct": <integer 0-100>,
  "time_to_impact_min": <integer | null>,
  "affected_devices": ["<device name>", ...],
  "affected_services": ["<VRF or application name>", ...],
  "root_cause_hypothesis": "<1-2 sentences, specific, grounded in the telemetry signals>",
  "contributing_signals": [
    {
      "feature": "<telemetry feature name>",
      "value": "<current observed value with unit>",
      "significance": "<high | medium | low>",
      "interpretation": "<one sentence explaining what this value implies>"
    }
  ],
  "recommended_actions": [
    {
      "priority": <integer starting from 1>,
      "action": "<specific, imperative action verb phrase>",
      "target": "<specific device, interface, or policy>",
      "rationale": "<one sentence explaining why this action addresses the root cause>",
      "estimated_impact": "<what will improve if this action is taken>"
    }
  ],
  "runbook_reference": "<runbook name from knowledge base | null>",
  "operator_summary": "<exactly one sentence in plain English for a Tier-1 operator>",
  "reasoning": "<internal chain-of-thought: which signals you weighted, why you chose this issue_type, what alternative hypotheses you ruled out>"
}

Remember: respond ONLY with the JSON object. Nothing else."""


# ─────────────────────────────────────────────────────────────────────────────
# 2. JSON OUTPUT SCHEMA (for jsonschema validation)
# ─────────────────────────────────────────────────────────────────────────────

NOC_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "issue_type", "severity", "confidence_pct", "time_to_impact_min",
        "affected_devices", "affected_services", "root_cause_hypothesis",
        "contributing_signals", "recommended_actions", "runbook_reference",
        "operator_summary", "reasoning"
    ],
    "properties": {
        "issue_type": {
            "type": "string",
            "enum": [
                "CONGESTION_BUILDUP", "BGP_INSTABILITY", "TUNNEL_DEGRADATION",
                "POLICY_DRIFT", "UNKNOWN_ANOMALY", "INSUFFICIENT_DATA"
            ]
        },
        "severity": {
            "type": "string",
            "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        },
        "confidence_pct": {"type": "integer", "minimum": 0, "maximum": 100},
        "time_to_impact_min": {"type": ["integer", "null"]},
        "affected_devices": {"type": "array", "items": {"type": "string"}},
        "affected_services": {"type": "array", "items": {"type": "string"}},
        "root_cause_hypothesis": {"type": "string", "minLength": 10},
        "contributing_signals": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["feature", "value", "significance", "interpretation"],
                "properties": {
                    "feature": {"type": "string"},
                    "value": {"type": "string"},
                    "significance": {"type": "string", "enum": ["high", "medium", "low"]},
                    "interpretation": {"type": "string"}
                }
            }
        },
        "recommended_actions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["priority", "action", "target", "rationale", "estimated_impact"],
                "properties": {
                    "priority": {"type": "integer"},
                    "action": {"type": "string"},
                    "target": {"type": "string"},
                    "rationale": {"type": "string"},
                    "estimated_impact": {"type": "string"}
                }
            }
        },
        "runbook_reference": {"type": ["string", "null"]},
        "operator_summary": {"type": "string", "minLength": 10},
        "reasoning": {"type": "string", "minLength": 10}
    },
    "additionalProperties": False
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. HELPER FORMATTERS
# ─────────────────────────────────────────────────────────────────────────────

def format_shap_values(shap_values: list[dict]) -> str:
    """
    Convert SHAP output into a human-readable string for LLM context injection.

    Expected shap_values format:
      [{"feature": "utilization_rate_of_change", "shap_value": 0.42, "current_value": 2.3, "unit": "%/30s"}, ...]

    Sort by abs(shap_value) descending, take top 5.
    """
    if not shap_values:
        return "No SHAP attribution data available."

    sorted_shap = sorted(shap_values, key=lambda x: abs(x["shap_value"]), reverse=True)[:5]
    lines = []
    for rank, s in enumerate(sorted_shap, 1):
        direction = "↑ increases" if s["shap_value"] > 0 else "↓ decreases"
        significance = "HIGH" if abs(s["shap_value"]) > 0.3 else ("MEDIUM" if abs(s["shap_value"]) > 0.1 else "LOW")
        lines.append(
            f"  [{rank}] {s['feature']}: {s['current_value']}{s.get('unit', '')} "
            f"(SHAP={s['shap_value']:+.3f}, {direction} fault probability, significance={significance})"
        )
    return "\n".join(lines)


def format_topology_context(topology_ctx: dict) -> str:
    """
    Format the NetworkX-derived topology context for LLM injection.

    Expected topology_ctx format:
      {
        "alert_device": "PE-1",
        "alert_interface": "eth1",
        "peer_device": "P-1",
        "link_type": "MPLS underlay",
        "affected_scope": {
          "downstream_devices": ["CE-Branch2", "CE-Branch3"],
          "affected_vrfs": ["VRF-CORP", "VRF-MGMT"],
          "affected_tunnels": ["tunnel0", "tunnel1"],
          "hub_device": "HUB-1"
        },
        "full_path": ["CE-Branch2 → PE-1 → P-1 → PE-Hub → CE-HUB"]
      }
    """
    scope = topology_ctx.get("affected_scope", {})
    lines = [
        f"Alert origin:      {topology_ctx.get('alert_device', 'unknown')} / {topology_ctx.get('alert_interface', 'unknown')}",
        f"Link type:         {topology_ctx.get('link_type', 'unknown')}",
        f"Peer device:       {topology_ctx.get('peer_device', 'unknown')}",
        f"Downstream sites:  {', '.join(scope.get('downstream_devices', [])) or 'none identified'}",
        f"Affected VRFs:     {', '.join(scope.get('affected_vrfs', [])) or 'none identified'}",
        f"Affected tunnels:  {', '.join(scope.get('affected_tunnels', [])) or 'none identified'}",
        f"Traffic path:      {scope.get('full_path', 'unknown')}"
    ]
    return "\n".join(lines)


def format_prophet_forecast(forecast: dict) -> str:
    """
    Format Prophet time-to-impact output for LLM context.

    Expected forecast format:
      {
        "metric": "if_utilization_pct",
        "current_value": 72.4,
        "threshold": 85.0,
        "will_breach": true,
        "breach_time_utc": "2025-08-01T14:37:00",
        "minutes_to_breach": 14,
        "forecast_at_30min": 91.2,
        "trend_slope_per_30s": 0.34
      }
    """
    if not forecast:
        return "No forecast data available."

    breach_str = (
        f"Will breach {forecast['threshold']}% threshold in approximately "
        f"{forecast['minutes_to_breach']} minutes (at {forecast['breach_time_utc']} UTC)."
    ) if forecast.get("will_breach") else f"No threshold breach predicted within the next 30 minutes."

    return (
        f"Metric:             {forecast.get('metric', 'unknown')}\n"
        f"Current value:      {forecast.get('current_value', 'N/A')}%\n"
        f"SLA threshold:      {forecast.get('threshold', 'N/A')}%\n"
        f"Trend slope:        {forecast.get('trend_slope_per_30s', 0):+.3f}% per 30-second interval\n"
        f"Forecast (30 min):  {forecast.get('forecast_at_30min', 'N/A')}%\n"
        f"Breach assessment:  {breach_str}"
    )


def format_syslogs(syslogs: list[dict]) -> str:
    """
    Format recent syslog events for LLM context.

    Expected format:
      [{"timestamp": "14:22:05", "device": "PE-1", "severity": "WARNING",
        "message": "BGP neighbor 10.0.0.2 went from Established to Idle"}, ...]
    """
    if not syslogs:
        return "No recent syslog events."

    lines = []
    for s in syslogs[-10:]:  # limit to last 10 events
        lines.append(
            f"  [{s.get('timestamp', '?')}] {s.get('device', '?')} [{s.get('severity', '?')}] "
            f"{s.get('message', '')}"
        )
    return "\n".join(lines)


def format_rag_results(rag_results: list[dict]) -> str:
    """
    Format ChromaDB/LlamaIndex retrieved runbook excerpts for LLM context.

    Expected format:
      [{"document_name": "Runbook: BGP Flap Recovery",
        "excerpt": "Step 1: Check MTU mismatch...",
        "relevance_score": 0.87}, ...]
    """
    if not rag_results:
        return "No relevant runbooks found in knowledge base."

    lines = []
    for r in rag_results[:3]:  # top 3 most relevant
        lines.append(
            f"  [{r.get('document_name', 'Unknown doc')}] "
            f"(relevance: {r.get('relevance_score', 0):.2f})\n"
            f"  {r.get('excerpt', '')[:400]}"   # cap at 400 chars per excerpt
        )
    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONTEXT BUILDER
#    Assembles the full user-turn context string from all data sources.
#    This is injected as the "user" message after the system prompt.
# ─────────────────────────────────────────────────────────────────────────────

def build_alert_context(
    alert_data: dict,
    shap_values: list[dict],
    topology_ctx: dict,
    rag_results: list[dict],
    syslogs: list[dict],
    operator_query: Optional[str] = None
) -> str:
    """
    Build the full context string for a single alert or operator query.

    Parameters
    ----------
    alert_data : dict
        Output from your predictive ML engine. Required keys:
          alert_id, timestamp, predicted_fault_type, confidence_pct,
          device, interface, utilization_pct, utilization_trend,
          utilization_slope, packet_loss_pct, jitter_ms,
          bgp_state_changes, if_errors_rate
        Optional: time_to_impact_min, prophet_forecast

    shap_values : list[dict]
        Top SHAP feature attributions from XGBoost.

    topology_ctx : dict
        NetworkX-derived topology scope from graph traversal.

    rag_results : list[dict]
        Top-k retrieved documents from ChromaDB.

    syslogs : list[dict]
        Recent syslog events from Telegraf/syslog pipeline.

    operator_query : str, optional
        Free-text question from NOC operator. Defaults to a standard
        structured analysis request.

    Returns
    -------
    str — the full context string to use as the "user" message.
    """
    query = operator_query or (
        "Analyze this alert. Provide your full structured analysis including "
        "the probable root cause, affected scope, estimated time to impact, "
        "and ordered remediation steps."
    )

    context = f"""=== NETWORK TOPOLOGY CONTEXT ===
{format_topology_context(topology_ctx)}

=== ACTIVE ALERT ===
Alert ID:             {alert_data.get('alert_id', 'UNKNOWN')}
Timestamp:            {alert_data.get('timestamp', datetime.utcnow().isoformat())}
Predicted fault type: {alert_data.get('predicted_fault_type', 'UNKNOWN')}
ML model confidence:  {alert_data.get('confidence_pct', 0)}%
XGBoost class:        {alert_data.get('xgboost_class', 'UNKNOWN')}
IsolationForest flag: {alert_data.get('isolation_forest_anomaly', 'N/A')}

=== TELEMETRY SNAPSHOT (last 5 minutes) ===
Device:                    {alert_data.get('device', 'unknown')}
Interface:                 {alert_data.get('interface', 'unknown')}
Current utilization:       {alert_data.get('utilization_pct', 0):.1f}%
5-min utilization trend:   {alert_data.get('utilization_trend', 'unknown')} \
(slope: {alert_data.get('utilization_slope', 0):+.4f}%/30s)
Packet loss (5-min avg):   {alert_data.get('packet_loss_pct', 0):.2f}%
Jitter (5-min avg):        {alert_data.get('jitter_ms', 0):.1f} ms
BGP state changes (10 min):{alert_data.get('bgp_state_changes', 0)}
Interface errors:          {alert_data.get('if_errors_rate', 0):.2f} errors/sec
Interface discards:        {alert_data.get('if_discards_rate', 0):.2f} discards/sec
Tunnel uptime:             {alert_data.get('tunnel_uptime_sec', 'N/A')} sec
IPSec rekey failures:      {alert_data.get('ipsec_rekey_failures', 0)}

=== TOP PREDICTIVE SIGNALS — SHAP FEATURE ATTRIBUTION ===
(These are the specific telemetry features that most influenced the fault prediction.)
{format_shap_values(shap_values)}

=== PROPHET FORECAST (next 30 minutes) ===
{format_prophet_forecast(alert_data.get('prophet_forecast', {}))}

=== AFFECTED TOPOLOGY SCOPE (from graph traversal) ===
{format_topology_context(topology_ctx)}

=== RECENT SYSLOG EVENTS (last 15 minutes) ===
{format_syslogs(syslogs)}

=== RELEVANT RUNBOOK EXCERPTS (retrieved from local knowledge base) ===
{format_rag_results(rag_results)}

=== SLA THRESHOLDS (reference) ===
Interface utilization:     > 85% = SLA breach
Packet loss:               > 1% = SLA breach
Latency (end-to-end):      > 50 ms = SLA breach
Jitter:                    > 20 ms = SLA breach
BGP reconvergence time:    > 60 sec = SLA breach

=== OPERATOR QUERY ===
{query}"""

    return context


# ─────────────────────────────────────────────────────────────────────────────
# 5. VALIDATION
#    Validates LLM JSON output against NOC_OUTPUT_SCHEMA.
# ─────────────────────────────────────────────────────────────────────────────

def validate_response(raw_text: str) -> tuple[bool, dict | None, str]:
    """
    Parse and validate the LLM's raw text output.

    Returns
    -------
    (is_valid, parsed_dict, error_message)

    is_valid   : True if the response is valid JSON matching NOC_OUTPUT_SCHEMA
    parsed_dict: the parsed dict if valid, else None
    error_msg  : empty string if valid, else a human-readable error description
    """
    # Strip any accidental markdown fences the model might add despite instructions
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {e}. Raw output: {raw_text[:200]}"

    try:
        jsonschema.validate(instance=parsed, schema=NOC_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as e:
        return False, parsed, f"Schema validation failed: {e.message} (path: {list(e.path)})"

    # Additional semantic checks
    if parsed["confidence_pct"] > 90 and parsed["issue_type"] == "INSUFFICIENT_DATA":
        return False, parsed, "Semantic error: confidence > 90% but issue_type is INSUFFICIENT_DATA"

    if parsed["time_to_impact_min"] is not None and parsed["time_to_impact_min"] < 0:
        return False, parsed, "Semantic error: time_to_impact_min cannot be negative"

    return True, parsed, ""


# ─────────────────────────────────────────────────────────────────────────────
# 6. OLLAMA API CALL
#    Wraps the HTTP call to the local Ollama server.
#    All inference happens locally — zero outbound traffic.
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"   # local Ollama server — no internet
DEFAULT_MODEL = "qwen3:8b"                   # change to phi4-mini for low-RAM machines
FALLBACK_MODEL = "phi4-mini"                 # fallback if primary model not loaded


def call_copilot(
    alert_data: dict,
    shap_values: list[dict],
    topology_ctx: dict,
    rag_results: list[dict],
    syslogs: list[dict],
    operator_query: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
    temperature: float = 0.1    # low temperature = more deterministic, less hallucination
) -> dict:
    """
    Main entry point. Builds context, calls Ollama, validates output.

    Returns a dict with keys:
      "success"   : bool
      "response"  : parsed NOC response dict (if success) or None
      "raw_output": raw LLM text
      "error"     : error description (if not success) or None
      "latency_ms": inference latency in milliseconds
      "model_used": model name that produced the response
    """
    context = build_alert_context(
        alert_data, shap_values, topology_ctx, rag_results, syslogs, operator_query
    )

    payload = {
        "model": model,
        "format": "json",           # Ollama JSON mode — enforces JSON output at sampler level
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 1500,    # max tokens for response
            "top_p": 0.9,
            "repeat_penalty": 1.1
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context}
        ]
    }

    for attempt in range(max_retries + 1):
        try:
            t_start = time.time()
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=120   # 2-minute timeout for 8B model inference
            )
            latency_ms = int((time.time() - t_start) * 1000)
            resp.raise_for_status()

            raw_output = resp.json()["message"]["content"]
            is_valid, parsed, error_msg = validate_response(raw_output)

            if is_valid:
                return {
                    "success": True,
                    "response": parsed,
                    "raw_output": raw_output,
                    "error": None,
                    "latency_ms": latency_ms,
                    "model_used": model
                }
            else:
                if attempt < max_retries:
                    # On retry, append validation error to prompt so model can self-correct
                    correction_note = (
                        f"\n\nYour previous response failed validation: {error_msg}\n"
                        "Please fix it and return ONLY the corrected JSON."
                    )
                    payload["messages"].append({"role": "assistant", "content": raw_output})
                    payload["messages"].append({"role": "user", "content": correction_note})
                    continue
                else:
                    return {
                        "success": False,
                        "response": parsed,  # return partial parse even if invalid
                        "raw_output": raw_output,
                        "error": f"Validation failed after {max_retries + 1} attempts: {error_msg}",
                        "latency_ms": latency_ms,
                        "model_used": model
                    }

        except requests.exceptions.ConnectionError:
            return {
                "success": False, "response": None, "raw_output": "",
                "error": f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. Is `ollama serve` running?",
                "latency_ms": 0, "model_used": model
            }
        except requests.exceptions.Timeout:
            return {
                "success": False, "response": None, "raw_output": "",
                "error": "Ollama inference timed out after 120 seconds. Try a smaller model.",
                "latency_ms": 120000, "model_used": model
            }
        except Exception as e:
            return {
                "success": False, "response": None, "raw_output": "",
                "error": f"Unexpected error: {e}",
                "latency_ms": 0, "model_used": model
            }


# ─────────────────────────────────────────────────────────────────────────────
# 7. EXAMPLE DATA — all 4 PS13 validation scenarios
#    Use these to test your copilot before the hackathon demo.
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_1_CONGESTION = {
    "alert_data": {
        "alert_id": "ALT-001",
        "timestamp": "2025-08-01T14:22:00Z",
        "predicted_fault_type": "CONGESTION_BUILDUP",
        "confidence_pct": 87,
        "xgboost_class": "WARNING",
        "isolation_forest_anomaly": True,
        "device": "PE-1",
        "interface": "eth1",
        "utilization_pct": 74.2,
        "utilization_trend": "RISING",
        "utilization_slope": 0.38,
        "packet_loss_pct": 0.12,
        "jitter_ms": 8.4,
        "bgp_state_changes": 0,
        "if_errors_rate": 0.01,
        "if_discards_rate": 1.8,
        "ipsec_rekey_failures": 0,
        "tunnel_uptime_sec": 43200,
        "prophet_forecast": {
            "metric": "if_utilization_pct",
            "current_value": 74.2,
            "threshold": 85.0,
            "will_breach": True,
            "breach_time_utc": "2025-08-01T14:37:00Z",
            "minutes_to_breach": 15,
            "forecast_at_30min": 92.1,
            "trend_slope_per_30s": 0.38
        }
    },
    "shap_values": [
        {"feature": "utilization_rate_of_change", "shap_value": 0.42, "current_value": 0.38, "unit": "%/30s"},
        {"feature": "if_discards_rate",           "shap_value": 0.31, "current_value": 1.8,  "unit": "pkt/s"},
        {"feature": "utilization_15min_avg",      "shap_value": 0.18, "current_value": 68.7, "unit": "%"},
        {"feature": "bytes_asymmetry_ratio",       "shap_value": 0.09, "current_value": 0.71, "unit": ""},
        {"feature": "if_out_octets_rate",          "shap_value": 0.07, "current_value": 94.2, "unit": "Mbps"},
    ],
    "topology_ctx": {
        "alert_device": "PE-1",
        "alert_interface": "eth1",
        "peer_device": "P-1",
        "link_type": "MPLS underlay (GE 1Gbps)",
        "affected_scope": {
            "downstream_devices": ["CE-Branch2", "CE-Branch3"],
            "affected_vrfs": ["VRF-CORP", "VRF-VOICE"],
            "affected_tunnels": ["IPSec-Branch2-Hub", "IPSec-Branch3-Hub"],
            "full_path": "CE-Branch2 → PE-1 → P-1 → PE-Hub → CE-Hub"
        }
    },
    "rag_results": [
        {
            "document_name": "Runbook: Hub-Spoke Congestion Recovery",
            "relevance_score": 0.91,
            "excerpt": "Step 1: Identify the congested link using 'show interface eth1 counters'. "
                       "Step 2: Check if QoS policy is enforcing traffic shaping on VRF-VOICE. "
                       "Step 3: If utilization > 80%, consider traffic steering via backup path "
                       "BGP community 65001:200. Step 4: Notify application teams if voice QoS is impacted."
        }
    ],
    "syslogs": [
        {"timestamp": "14:18:02", "device": "PE-1", "severity": "INFO",    "message": "Interface eth1: output rate 742 Mbps"},
        {"timestamp": "14:19:33", "device": "PE-1", "severity": "WARNING", "message": "Interface eth1: output drops incrementing"},
        {"timestamp": "14:21:55", "device": "PE-1", "severity": "WARNING", "message": "QoS policy VOICE-PRIORITY: queue depth > 80%"},
    ]
}

SCENARIO_2_BGP_FLAP = {
    "alert_data": {
        "alert_id": "ALT-002",
        "timestamp": "2025-08-01T15:05:00Z",
        "predicted_fault_type": "BGP_INSTABILITY",
        "confidence_pct": 92,
        "xgboost_class": "CRITICAL",
        "isolation_forest_anomaly": True,
        "device": "PE-2",
        "interface": "eth0",
        "utilization_pct": 38.1,
        "utilization_trend": "STABLE",
        "utilization_slope": 0.02,
        "packet_loss_pct": 2.3,
        "jitter_ms": 42.7,
        "bgp_state_changes": 8,
        "if_errors_rate": 0.0,
        "if_discards_rate": 0.2,
        "ipsec_rekey_failures": 0,
        "tunnel_uptime_sec": 320,
        "prophet_forecast": {}
    },
    "shap_values": [
        {"feature": "bgp_state_changes_count",  "shap_value": 0.61, "current_value": 8,    "unit": "events/10min"},
        {"feature": "route_count_delta",         "shap_value": 0.29, "current_value": -47,  "unit": "routes"},
        {"feature": "tunnel_packet_loss_pct",    "shap_value": 0.22, "current_value": 2.3,  "unit": "%"},
        {"feature": "tunnel_jitter_ms",          "shap_value": 0.14, "current_value": 42.7, "unit": "ms"},
        {"feature": "tunnel_uptime_sec",         "shap_value": -0.11,"current_value": 320,  "unit": "sec"},
    ],
    "topology_ctx": {
        "alert_device": "PE-2",
        "alert_interface": "eth0",
        "peer_device": "P-1",
        "link_type": "MPLS underlay BGP session",
        "affected_scope": {
            "downstream_devices": ["CE-Branch4", "CE-Branch5"],
            "affected_vrfs": ["VRF-CORP", "VRF-MGMT"],
            "affected_tunnels": ["IPSec-Branch4-Hub", "IPSec-Branch5-Hub"],
            "full_path": "CE-Branch4 → PE-2 → P-1 → PE-Hub → CE-Hub"
        }
    },
    "rag_results": [
        {
            "document_name": "Runbook: BGP Flap Diagnosis",
            "relevance_score": 0.95,
            "excerpt": "Step 1: Run 'show bgp summary' on PE-2 to confirm neighbor state. "
                       "Step 2: Check MTU mismatch with 'ping 10.0.0.1 df-bit size 1500'. "
                       "Step 3: Inspect BGP hold-timer vs keepalive settings. "
                       "Step 4: Check physical interface error counters for CRC errors. "
                       "Step 5: Consider BGP BFD to detect link failures faster."
        }
    ],
    "syslogs": [
        {"timestamp": "14:58:11", "device": "PE-2", "severity": "ERROR",   "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
        {"timestamp": "14:58:43", "device": "PE-2", "severity": "INFO",    "message": "BGP neighbor 10.0.0.1 went to Active state"},
        {"timestamp": "14:59:02", "device": "PE-2", "severity": "INFO",    "message": "BGP neighbor 10.0.0.1 Established — 312 prefixes received"},
        {"timestamp": "15:01:18", "device": "PE-2", "severity": "ERROR",   "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
        {"timestamp": "15:02:55", "device": "PE-2", "severity": "WARNING", "message": "Route count dropped by 47 prefixes — convergence event"},
        {"timestamp": "15:04:33", "device": "PE-2", "severity": "ERROR",   "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
    ]
}

SCENARIO_3_TUNNEL_DEGRADATION = {
    "alert_data": {
        "alert_id": "ALT-003",
        "timestamp": "2025-08-01T16:10:00Z",
        "predicted_fault_type": "TUNNEL_DEGRADATION",
        "confidence_pct": 79,
        "xgboost_class": "WARNING",
        "isolation_forest_anomaly": True,
        "device": "CE-Branch1",
        "interface": "tunnel0",
        "utilization_pct": 41.2,
        "utilization_trend": "STABLE",
        "utilization_slope": 0.05,
        "packet_loss_pct": 8.7,
        "jitter_ms": 34.1,
        "bgp_state_changes": 1,
        "if_errors_rate": 0.3,
        "if_discards_rate": 0.1,
        "ipsec_rekey_failures": 3,
        "tunnel_uptime_sec": 1840,
        "prophet_forecast": {}
    },
    "shap_values": [
        {"feature": "tunnel_packet_loss_pct",    "shap_value": 0.55, "current_value": 8.7,  "unit": "%"},
        {"feature": "ipsec_rekey_failures",      "shap_value": 0.38, "current_value": 3,    "unit": "failures/hr"},
        {"feature": "tunnel_jitter_ms",          "shap_value": 0.27, "current_value": 34.1, "unit": "ms"},
        {"feature": "tunnel_uptime_sec",         "shap_value": -0.15,"current_value": 1840, "unit": "sec"},
        {"feature": "if_in_errors_rate",         "shap_value": 0.08, "current_value": 0.3,  "unit": "errors/sec"},
    ],
    "topology_ctx": {
        "alert_device": "CE-Branch1",
        "alert_interface": "tunnel0",
        "peer_device": "CE-Hub",
        "link_type": "SD-WAN IPSec overlay tunnel",
        "affected_scope": {
            "downstream_devices": ["CE-Branch1"],
            "affected_vrfs": ["VRF-CORP"],
            "affected_tunnels": ["IPSec-Branch1-Hub"],
            "full_path": "CE-Branch1 → (IPSec tunnel0) → CE-Hub"
        }
    },
    "rag_results": [
        {
            "document_name": "Runbook: IPSec Tunnel Degradation",
            "relevance_score": 0.89,
            "excerpt": "Step 1: Check MPLS underlay health with 'ping mpls ldp 10.1.1.1'. "
                       "Step 2: Verify IKE phase 1 and phase 2 SA status with 'show crypto ipsec sa'. "
                       "Step 3: If rekey failures, check certificate expiry or PSK mismatch. "
                       "Step 4: Consider failover to secondary tunnel if primary loss > 5%."
        }
    ],
    "syslogs": [
        {"timestamp": "15:58:20", "device": "CE-Branch1", "severity": "ERROR",   "message": "IPSec SA rekey failed: IKE timeout waiting for response from 10.0.1.1"},
        {"timestamp": "16:02:44", "device": "CE-Branch1", "severity": "ERROR",   "message": "IPSec SA rekey failed: IKE timeout waiting for response from 10.0.1.1"},
        {"timestamp": "16:08:11", "device": "CE-Branch1", "severity": "WARNING", "message": "Tunnel0: packet loss rate exceeded 5% threshold"},
        {"timestamp": "16:09:55", "device": "CE-Branch1", "severity": "ERROR",   "message": "IPSec SA rekey failed: IKE timeout waiting for response from 10.0.1.1"},
    ]
}

SCENARIO_4_POLICY_DRIFT = {
    "alert_data": {
        "alert_id": "ALT-004",
        "timestamp": "2025-08-01T17:00:00Z",
        "predicted_fault_type": "POLICY_DRIFT",
        "confidence_pct": 68,
        "xgboost_class": "WARNING",
        "isolation_forest_anomaly": True,
        "device": "PE-1",
        "interface": "eth1",
        "utilization_pct": 62.0,
        "utilization_trend": "STABLE",
        "utilization_slope": 0.01,
        "packet_loss_pct": 0.05,
        "jitter_ms": 41.3,
        "bgp_state_changes": 0,
        "if_errors_rate": 0.0,
        "if_discards_rate": 0.0,
        "ipsec_rekey_failures": 0,
        "tunnel_uptime_sec": 86400,
        "prophet_forecast": {}
    },
    "shap_values": [
        {"feature": "voice_traffic_dscp_ratio",  "shap_value": -0.48, "current_value": 0.02, "unit": "ratio"},
        {"feature": "tunnel_jitter_ms",           "shap_value":  0.39, "current_value": 41.3, "unit": "ms"},
        {"feature": "bytes_asymmetry_ratio",      "shap_value":  0.21, "current_value": 0.55, "unit": ""},
        {"feature": "qos_queue_depth_voice",      "shap_value": -0.17, "current_value": 0,    "unit": "packets"},
        {"feature": "time_of_day_encoded",        "shap_value":  0.09, "current_value": 0.87, "unit": ""},
    ],
    "topology_ctx": {
        "alert_device": "PE-1",
        "alert_interface": "eth1",
        "peer_device": "P-1",
        "link_type": "MPLS underlay (GE 1Gbps)",
        "affected_scope": {
            "downstream_devices": ["CE-Branch2", "CE-Branch3"],
            "affected_vrfs": ["VRF-VOICE"],
            "affected_tunnels": ["IPSec-Branch2-Hub"],
            "full_path": "CE-Branch2 → PE-1 → P-1 → PE-Hub → CE-Hub"
        }
    },
    "rag_results": [
        {
            "document_name": "Runbook: QoS Policy Drift Recovery",
            "relevance_score": 0.82,
            "excerpt": "Step 1: Check current QoS policy applied to interface with 'show policy-map interface eth1'. "
                       "Step 2: Compare against baseline config in /configs/pe1-baseline.cfg. "
                       "Step 3: If VOICE-PRIORITY class is missing or misconfigured, re-apply with 'service-policy output VOICE-PRIORITY'. "
                       "Step 4: Verify DSCP EF markings are preserved end-to-end."
        }
    ],
    "syslogs": [
        {"timestamp": "16:51:02", "device": "PE-1", "severity": "INFO",    "message": "Configuration change applied by admin session from 10.0.0.100"},
        {"timestamp": "16:51:04", "device": "PE-1", "severity": "INFO",    "message": "QoS policy VOICE-PRIORITY removed from interface eth1"},
        {"timestamp": "16:55:20", "device": "CE-Branch2", "severity": "WARNING", "message": "VoIP call quality degraded: MOS score dropped to 2.1"},
    ]
}

ALL_SCENARIOS = {
    "scenario_1_congestion":         SCENARIO_1_CONGESTION,
    "scenario_2_bgp_flap":           SCENARIO_2_BGP_FLAP,
    "scenario_3_tunnel_degradation": SCENARIO_3_TUNNEL_DEGRADATION,
    "scenario_4_policy_drift":       SCENARIO_4_POLICY_DRIFT,
}


# ─────────────────────────────────────────────────────────────────────────────
# 8. QUICK TEST — run all 4 scenarios
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("PS13 NOC Copilot — Prompt Engineering Test\n" + "=" * 50)

    for name, scenario in ALL_SCENARIOS.items():
        print(f"\n[TEST] Running {name}...")
        result = call_copilot(
            alert_data=scenario["alert_data"],
            shap_values=scenario["shap_values"],
            topology_ctx=scenario["topology_ctx"],
            rag_results=scenario["rag_results"],
            syslogs=scenario["syslogs"]
        )

        if result["success"]:
            r = result["response"]
            print(f"  ✓  Issue type:       {r['issue_type']}")
            print(f"     Severity:          {r['severity']}")
            print(f"     Confidence:        {r['confidence_pct']}%")
            print(f"     Time to impact:    {r['time_to_impact_min']} min")
            print(f"     Operator summary:  {r['operator_summary']}")
            print(f"     Actions:           {len(r['recommended_actions'])} recommended")
            print(f"     Latency:           {result['latency_ms']} ms")
        else:
            print(f"  ✗  FAILED: {result['error']}")
            if result["raw_output"]:
                print(f"     Raw output preview: {result['raw_output'][:200]}")

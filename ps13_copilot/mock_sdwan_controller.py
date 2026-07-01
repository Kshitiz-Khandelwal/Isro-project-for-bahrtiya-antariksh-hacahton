"""
mock_sdwan_controller.py
========================
PS13 — Simulated SD-WAN Controller REST API

Addresses PS requirement: "Streaming telemetry from SD-WAN controllers"

This mock controller:
  1. Exposes a REST API on port 8080 returning tunnel health stats
  2. Telegraf scrapes /api/v1/tunnels every 30s
  3. Supports fault injection via /api/v1/inject endpoints
  4. Returns realistic JSON matching what real SD-WAN controllers emit

Usage:
  # Start the controller:
  uvicorn mock_sdwan_controller:app --host 0.0.0.0 --port 8080

  # Scrape manually:
  curl http://localhost:8080/api/v1/tunnels

  # Inject a fault (for demo):
  curl -X POST http://localhost:8080/api/v1/inject/loss -d '{"tunnel": "IPSec-Branch1-Hub", "loss_pct": 15.0}'

Telegraf config:
  [[inputs.http]]
    urls = ["http://localhost:8080/api/v1/tunnels"]
    data_format = "json"
    interval = "30s"
"""

import time
import random
import threading
from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    # Fallback: if FastAPI not installed, provide a simple Flask-like stub
    print("Warning: FastAPI not installed. Install with: pip install fastapi uvicorn")
    raise


app = FastAPI(
    title="PS13 Mock SD-WAN Controller",
    description="Simulated SD-WAN controller for ISRO PS13 hackathon",
    version="1.0.0"
)


# ─────────────────────────────────────────────────────────────────────────────
# Tunnel definitions — matches the topology in topology_graph.py
# ─────────────────────────────────────────────────────────────────────────────

class TunnelState:
    """Mutable state for a single IPSec tunnel."""
    def __init__(self, name: str, src: str, dst: str, baseline_latency: float = 12.0):
        self.name = name
        self.src = src
        self.dst = dst
        self.status = "UP"
        self.baseline_latency = baseline_latency
        self.injected_loss = 0.0       # fault injection override
        self.injected_latency = 0.0    # fault injection override
        self.injected_jitter = 0.0     # fault injection override
        self.rekey_failure_rate = 0.0  # probability of rekey failure per interval
        self.uptime_start = time.time()
        self.bytes_in_total = random.randint(1_000_000_000, 50_000_000_000)
        self.bytes_out_total = random.randint(1_000_000_000, 50_000_000_000)

    def get_stats(self) -> dict:
        """Generate current tunnel stats with noise + any injected faults."""
        # Base metrics with realistic noise
        latency = max(1.0, random.gauss(self.baseline_latency + self.injected_latency, 3.0))
        jitter = max(0.0, random.gauss(2.0 + self.injected_jitter, 1.5))
        loss = max(0.0, random.gauss(0.05 + self.injected_loss, 0.3 if self.injected_loss > 0 else 0.05))
        rekey_failures = 1 if random.random() < self.rekey_failure_rate else 0

        # Simulate traffic flow
        bytes_in_delta = random.randint(500_000, 5_000_000)
        bytes_out_delta = random.randint(500_000, 5_000_000)
        self.bytes_in_total += bytes_in_delta
        self.bytes_out_total += bytes_out_delta

        uptime = int(time.time() - self.uptime_start)

        return {
            "tunnel_name": self.name,
            "source_device": self.src,
            "destination_device": self.dst,
            "status": self.status,
            "metrics": {
                "latency_ms": round(latency, 1),
                "jitter_ms": round(jitter, 1),
                "packet_loss_pct": round(loss, 2),
                "uptime_sec": uptime,
                "ipsec_rekey_failures": rekey_failures,
                "bytes_in": self.bytes_in_total,
                "bytes_out": self.bytes_out_total,
                "bytes_in_rate": bytes_in_delta,
                "bytes_out_rate": bytes_out_delta,
            },
            "ipsec": {
                "phase1_state": "ACTIVE",
                "phase2_state": "ACTIVE" if rekey_failures == 0 else "REKEYING",
                "encryption": "AES-256-GCM",
                "auth": "SHA256",
                "dh_group": 14,
            },
            "qos": {
                "voice_queue_depth": random.randint(0, 50),
                "data_queue_depth": random.randint(0, 200),
                "dscp_ef_marked_pct": round(random.uniform(0.1, 0.3), 2),
            }
        }


# Initialize tunnel states
TUNNELS: dict[str, TunnelState] = {
    "IPSec-Branch1-Hub": TunnelState("IPSec-Branch1-Hub", "CE-Branch1", "CE-Hub", 12.0),
    "IPSec-Branch2-Hub": TunnelState("IPSec-Branch2-Hub", "CE-Branch2", "CE-Hub", 15.0),
    "IPSec-Branch3-Hub": TunnelState("IPSec-Branch3-Hub", "CE-Branch3", "CE-Hub", 18.0),
    "IPSec-Branch4-Hub": TunnelState("IPSec-Branch4-Hub", "CE-Branch4", "CE-Hub", 14.0),
    "IPSec-Branch5-Hub": TunnelState("IPSec-Branch5-Hub", "CE-Branch5", "CE-Hub", 10.0),
}


# ─────────────────────────────────────────────────────────────────────────────
# API endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/tunnels")
def get_all_tunnels():
    """
    Returns current stats for all IPSec tunnels.
    Telegraf scrapes this endpoint every 30 seconds.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "controller_id": "SDWAN-CTRL-01",
        "tunnel_count": len(TUNNELS),
        "tunnels": [t.get_stats() for t in TUNNELS.values()]
    }


@app.get("/api/v1/tunnels/{tunnel_name}")
def get_tunnel(tunnel_name: str):
    """Returns stats for a specific tunnel."""
    if tunnel_name not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tunnel": TUNNELS[tunnel_name].get_stats()
    }


@app.get("/api/v1/topology")
def get_topology():
    """Returns the SD-WAN overlay topology."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sites": [
            {"name": t.src, "role": "branch", "tunnel": t.name}
            for t in TUNNELS.values()
        ] + [
            {"name": "CE-Hub", "role": "hub", "tunnel": None}
        ],
        "tunnels": [
            {"name": t.name, "source": t.src, "destination": t.dst, "status": t.status}
            for t in TUNNELS.values()
        ]
    }


@app.get("/api/v1/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "uptime_sec": int(time.time() - min(t.uptime_start for t in TUNNELS.values())),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fault injection endpoints — use during demo to trigger scenarios
# ─────────────────────────────────────────────────────────────────────────────

class FaultConfig(BaseModel):
    tunnel: str
    value: float
    duration_sec: Optional[int] = None  # auto-clear after N seconds

def _schedule_clear(tunnel_name: str, attr: str, delay: int):
    """Clear a fault injection after a delay."""
    def _clear():
        time.sleep(delay)
        if tunnel_name in TUNNELS:
            setattr(TUNNELS[tunnel_name], attr, 0.0)
    t = threading.Thread(target=_clear, daemon=True)
    t.start()


@app.post("/api/v1/inject/loss")
def inject_packet_loss(config: FaultConfig):
    """Inject packet loss into a specific tunnel."""
    if config.tunnel not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {config.tunnel} not found")
    TUNNELS[config.tunnel].injected_loss = config.value
    if config.duration_sec:
        _schedule_clear(config.tunnel, "injected_loss", config.duration_sec)
    return {"status": "injected", "tunnel": config.tunnel, "loss_pct": config.value}


@app.post("/api/v1/inject/latency")
def inject_latency(config: FaultConfig):
    """Inject additional latency into a specific tunnel."""
    if config.tunnel not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {config.tunnel} not found")
    TUNNELS[config.tunnel].injected_latency = config.value
    if config.duration_sec:
        _schedule_clear(config.tunnel, "injected_latency", config.duration_sec)
    return {"status": "injected", "tunnel": config.tunnel, "latency_ms": config.value}


@app.post("/api/v1/inject/jitter")
def inject_jitter(config: FaultConfig):
    """Inject additional jitter into a specific tunnel."""
    if config.tunnel not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {config.tunnel} not found")
    TUNNELS[config.tunnel].injected_jitter = config.value
    if config.duration_sec:
        _schedule_clear(config.tunnel, "injected_jitter", config.duration_sec)
    return {"status": "injected", "tunnel": config.tunnel, "jitter_ms": config.value}


@app.post("/api/v1/inject/rekey_failure")
def inject_rekey_failure(config: FaultConfig):
    """Inject IPSec rekey failure probability."""
    if config.tunnel not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {config.tunnel} not found")
    TUNNELS[config.tunnel].rekey_failure_rate = min(1.0, config.value)
    if config.duration_sec:
        _schedule_clear(config.tunnel, "rekey_failure_rate", config.duration_sec)
    return {"status": "injected", "tunnel": config.tunnel, "rekey_rate": config.value}


@app.post("/api/v1/inject/clear")
def clear_all_faults():
    """Clear all injected faults — reset to baseline."""
    for tunnel in TUNNELS.values():
        tunnel.injected_loss = 0.0
        tunnel.injected_latency = 0.0
        tunnel.injected_jitter = 0.0
        tunnel.rekey_failure_rate = 0.0
    return {"status": "all faults cleared", "timestamp": datetime.now(timezone.utc).isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# Progressive degradation scenario (for Scenario 3 demo)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/scenario/tunnel_degradation")
def run_tunnel_degradation_scenario(tunnel_name: str = "IPSec-Branch1-Hub"):
    """
    Simulate progressive tunnel degradation over 10 minutes.
    Loss: 0 → 2% → 5% → 10% → 15%
    Jitter: 0 → 5 → 15 → 30 → 45 ms
    Rekey failures start appearing after 5 minutes.
    """
    if tunnel_name not in TUNNELS:
        raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

    def _ramp():
        stages = [
            (0.0, 0.0, 0.0),     # baseline
            (2.0, 5.0, 0.0),     # 2 min
            (5.0, 15.0, 0.1),    # 4 min
            (10.0, 30.0, 0.3),   # 6 min
            (15.0, 45.0, 0.5),   # 8 min
        ]
        for loss, jitter, rekey in stages:
            TUNNELS[tunnel_name].injected_loss = loss
            TUNNELS[tunnel_name].injected_jitter = jitter
            TUNNELS[tunnel_name].rekey_failure_rate = rekey
            time.sleep(120)  # 2 minutes per stage

        # Clear after scenario
        TUNNELS[tunnel_name].injected_loss = 0.0
        TUNNELS[tunnel_name].injected_jitter = 0.0
        TUNNELS[tunnel_name].rekey_failure_rate = 0.0

    t = threading.Thread(target=_ramp, daemon=True)
    t.start()
    return {
        "status": "scenario started",
        "tunnel": tunnel_name,
        "duration": "10 minutes",
        "description": "Progressive loss, jitter, and rekey failure ramp"
    }

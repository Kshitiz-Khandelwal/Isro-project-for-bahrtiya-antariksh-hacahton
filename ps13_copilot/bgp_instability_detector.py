"""
bgp_instability_detector.py
============================
PS13 — Routing Instability Detection via Sliding Window

Simple but effective: counts BGP state transitions in a sliding
time window. If count >= threshold, flags routing instability.

This was identified as a missing model in the architect review:
"BGP flap detection needs a separate model — a simple sliding window
counter on BGP state change events works well."

Usage:
  from bgp_instability_detector import detect_bgp_instability
  result = detect_bgp_instability(syslog_events, window_minutes=10, flap_threshold=3)
"""

from datetime import datetime, timedelta
from typing import Optional
import re


# ─────────────────────────────────────────────────────────────────────────────
# BGP state change keywords to look for in syslog messages
# ─────────────────────────────────────────────────────────────────────────────

BGP_DOWN_PATTERNS = [
    r"BGP.*Established.*to.*Idle",
    r"BGP.*neighbor.*down",
    r"BGP.*peer.*lost",
    r"BGP.*session.*reset",
    r"BGP.*adjacency.*change.*down",
    r"bgpd.*Notification.*sent",
]

BGP_UP_PATTERNS = [
    r"BGP.*neighbor.*Established",
    r"BGP.*peer.*up",
    r"BGP.*adjacency.*change.*up",
    r"bgpd.*prefixes received",
]

ROUTE_CHANGE_PATTERNS = [
    r"route.*count.*dropped",
    r"convergence.*event",
    r"prefix.*withdrawn",
    r"route.*flap",
]


def parse_syslog_timestamp(ts_str: str, reference_date: Optional[datetime] = None) -> datetime:
    """
    Parse various syslog timestamp formats.
    Handles: "14:22:05", "2025-08-01T14:22:05Z", "Aug  1 14:22:05"
    """
    # Try ISO format first
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%H:%M:%S"]:
        try:
            parsed = datetime.strptime(ts_str, fmt)
            # If only time was parsed, add reference date
            if fmt == "%H:%M:%S":
                ref = reference_date or datetime.utcnow()
                parsed = parsed.replace(year=ref.year, month=ref.month, day=ref.day)
            return parsed
        except ValueError:
            continue

    # Fallback: return current time
    return datetime.utcnow()


def detect_bgp_instability(
    syslog_events: list[dict],
    window_minutes: int = 10,
    flap_threshold: int = 3,
    reference_time: Optional[datetime] = None,
) -> dict:
    """
    Count BGP state transitions in the last N minutes.
    If count >= threshold, flag as routing instability.

    Parameters
    ----------
    syslog_events : list[dict]
        Each dict should have: timestamp, device, severity, message

    window_minutes : int
        Sliding window size in minutes. Default: 10.

    flap_threshold : int
        Number of BGP down events in the window to trigger instability.
        Default: 3 (same device going down 3+ times = flapping).

    reference_time : datetime, optional
        Current time reference. Defaults to utcnow().

    Returns
    -------
    dict:
        is_unstable     : bool — whether instability is detected
        flap_count      : int — number of BGP down events in window
        up_count        : int — number of BGP up events in window
        route_changes   : int — number of route change events
        window_minutes  : int — window size used
        threshold       : int — threshold used
        severity        : str — CRITICAL / HIGH / MEDIUM / NORMAL
        affected_devices: list — devices showing instability
        events          : list — the matched BGP events within the window
        recommendation  : str — suggested action
    """
    now = reference_time or datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)

    bgp_down_events = []
    bgp_up_events = []
    route_events = []

    for event in syslog_events:
        msg = event.get("message", "")
        ts_str = event.get("timestamp", "")
        device = event.get("device", "unknown")

        try:
            event_time = parse_syslog_timestamp(ts_str, now)
        except Exception:
            continue

        if event_time < window_start:
            continue

        # Check for BGP down events
        for pattern in BGP_DOWN_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                bgp_down_events.append({
                    "timestamp": ts_str,
                    "device": device,
                    "type": "BGP_DOWN",
                    "message": msg,
                })
                break

        # Check for BGP up events
        for pattern in BGP_UP_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                bgp_up_events.append({
                    "timestamp": ts_str,
                    "device": device,
                    "type": "BGP_UP",
                    "message": msg,
                })
                break

        # Check for route change events
        for pattern in ROUTE_CHANGE_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                route_events.append({
                    "timestamp": ts_str,
                    "device": device,
                    "type": "ROUTE_CHANGE",
                    "message": msg,
                })
                break

    flap_count = len(bgp_down_events)
    up_count = len(bgp_up_events)
    route_changes = len(route_events)
    is_unstable = flap_count >= flap_threshold

    # Determine severity
    if flap_count >= flap_threshold * 3:
        severity = "CRITICAL"
    elif flap_count >= flap_threshold * 2:
        severity = "HIGH"
    elif is_unstable:
        severity = "MEDIUM"
    else:
        severity = "NORMAL"

    # Find affected devices
    affected_devices = list(set(e["device"] for e in bgp_down_events))

    # Generate recommendation
    if severity == "CRITICAL":
        recommendation = (
            f"CRITICAL: {flap_count} BGP state drops in {window_minutes} min on {affected_devices}. "
            f"Immediate action: check physical links for CRC errors, verify MTU matches across peers, "
            f"consider increasing BGP hold timer to stabilize sessions."
        )
    elif severity == "HIGH":
        recommendation = (
            f"HIGH: {flap_count} BGP flaps detected on {affected_devices}. "
            f"Check for MTU mismatch, intermittent link issues, or CPU overload on routing process."
        )
    elif is_unstable:
        recommendation = (
            f"MEDIUM: BGP instability detected ({flap_count} flaps in {window_minutes} min). "
            f"Monitor closely. Consider enabling BFD for faster detection."
        )
    else:
        recommendation = "No BGP instability detected. Routing is stable."

    return {
        "is_unstable": is_unstable,
        "flap_count": flap_count,
        "up_count": up_count,
        "route_changes": route_changes,
        "window_minutes": window_minutes,
        "threshold": flap_threshold,
        "severity": severity,
        "affected_devices": affected_devices,
        "events": bgp_down_events + bgp_up_events + route_events,
        "recommendation": recommendation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("PS13 BGP Instability Detector — Test Run")
    print("=" * 50)

    # Simulate syslog events from Scenario 2 (BGP flap)
    test_events = [
        {"timestamp": "14:58:11", "device": "PE-2", "severity": "ERROR",
         "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
        {"timestamp": "14:58:43", "device": "PE-2", "severity": "INFO",
         "message": "BGP neighbor 10.0.0.1 went to Active state"},
        {"timestamp": "14:59:02", "device": "PE-2", "severity": "INFO",
         "message": "BGP neighbor 10.0.0.1 Established — 312 prefixes received"},
        {"timestamp": "15:01:18", "device": "PE-2", "severity": "ERROR",
         "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
        {"timestamp": "15:02:55", "device": "PE-2", "severity": "WARNING",
         "message": "Route count dropped by 47 prefixes — convergence event"},
        {"timestamp": "15:04:33", "device": "PE-2", "severity": "ERROR",
         "message": "BGP neighbor 10.0.0.1 went from Established to Idle"},
    ]

    result = detect_bgp_instability(test_events)

    print(f"\n  Is unstable:        {result['is_unstable']}")
    print(f"  BGP down events:    {result['flap_count']}")
    print(f"  BGP up events:      {result['up_count']}")
    print(f"  Route changes:      {result['route_changes']}")
    print(f"  Severity:           {result['severity']}")
    print(f"  Affected devices:   {result['affected_devices']}")
    print(f"  Recommendation:     {result['recommendation']}")

    print(f"\n  Events matched:")
    for e in result["events"]:
        print(f"    [{e['timestamp']}] {e['device']} — {e['type']}: {e['message'][:60]}...")

    print("\nDone.")

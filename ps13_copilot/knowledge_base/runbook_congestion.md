# Runbook: Hub-Spoke Congestion Recovery

## Description
This runbook addresses link capacity saturation and queue discards on underlay physical paths. High traffic volumes from downstream sites exceed the configured egress rates of PE-to-P links or PE-to-CE access interfaces.

## Diagnostic Steps
1. Log in to the affected PE router.
2. Run `show interface ethX` or check telemetry metric `underlay_if_utilization_pct`.
3. Verify discards rate with `show interface ethX counters` or metric `underlay_if_discards_rate`. If utilization > 80% and discards are rising, congestion is occurring.
4. Run `show policy-map interface ethX` to inspect queue utilization.

## Corrective Actions
1. **Traffic Steering:** Steer non-critical traffic (e.g. general data) via the secondary backup underlay path (e.g., using BGP community tagging or routing metric changes).
   - Command: Set BGP community value `65001:200` to lower path preference.
2. **QoS Adjustment:** Ensure VOICE-PRIORITY queue limits are set correctly. If necessary, allocate more bandwidth temporarily to the voice class.
3. **Application Throttle:** Instruct application team to temporarily throttle non-critical backups or file transfers.

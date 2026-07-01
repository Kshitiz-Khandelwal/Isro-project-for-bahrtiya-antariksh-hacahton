# Runbook: QoS Policy Drift Recovery

## Description
This runbook addresses network policy drift, typically caused by unauthorized configuration edits. Voice queue metrics (dscp_ef_marked_pct) drop to zero, resulting in high voice jitter and MOS score degradation.

## Diagnostic Steps
1. Log in to the PE or CE router.
2. Inspect the applied policy maps on egress interfaces:
   - Command: `show policy-map interface ethX`
3. Verify DSCP EF marking ratios (metric `voice_traffic_dscp_ratio`). If ratio < 0.05, QoS policy mapping is lost.
4. Compare current active configuration against local baseline configurations stored in `/configs/pe1-baseline.cfg`.

## Corrective Actions
1. **Re-apply QoS Policy:** If class map `VOICE-PRIORITY` is missing from the interface configuration, re-apply the service policy map to egress interface.
   - Command: `config t`
   - Command: `interface ethX`
   - Command: `service-policy output VOICE-PRIORITY`
2. **Verify DSCP Preservation:** Validate that the upstream provider edge does not strip DSCP EF markings.

# Runbook: IPSec Tunnel Degradation Recovery

## Description
This runbook addresses SD-WAN IPSec overlay tunnel degradation. Telemetry shows progressive packet loss (> 5%), latency spikes (> 50ms), and key exchange renegotiation (rekey) failures on overlay tunnel interfaces.

## Diagnostic Steps
1. Log in to the CE branch router.
2. Verify underlay path health by pinging the underlay PE/P interfaces.
3. Verify IPSec SA security associations status:
   - Command: `show crypto ipsec sa`
   - Command: `show crypto ikev2 sa`
4. Inspect the `overlay_ipsec_rekey_failures` metric. Rekey failures indicate IKE negotiation timeout or key mismatch.

## Corrective Actions
1. **Force Tunnel Reset:** If Phase 2 SA is stalled, clear current SAs to force IKE renegotiation.
   - Command: `clear crypto ipsec sa`
2. **Tunnel Failover:** If overlay packet loss exceeds 5% and underlay is healthy, route traffic over the secondary overlay tunnel interface.
   - Action: Change policy routing weight to redirect VRF-CORP traffic to tunnel1.
3. **Verify PSK/Certs:** Check pre-shared key (PSK) alignment or verify local TLS certificate validity if rekeying continues to fail.

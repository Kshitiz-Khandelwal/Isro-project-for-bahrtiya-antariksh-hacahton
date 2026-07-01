# Runbook: BGP Flap Diagnosis & Recovery

## Description
This runbook addresses dynamic routing instability under the underlay. A BGP neighbor session is flapping between Established, Active, and Idle states, leading to route withdrawals and network convergence loops.

## Diagnostic Steps
1. Log in to the affected PE or P router.
2. Run `show ip bgp summary` to confirm neighbor peer status.
3. Verify the state changes count using `bgp_state_changes_count`.
4. Validate physical link errors by checking CRC/MTU:
   - Run `show interface ethX` to inspect input errors, output errors, and interface MTU.
5. Check for MTU mismatch by pinging the neighbor peer with the DF (Don't Fragment) bit set:
   - Command: `ping <peer-ip> df-bit size 1500`

## Corrective Actions
1. **MTU Alignment:** If ping fails at 1500 bytes, configure matching interface MTU (typically 1500 or 9000 bytes) on both sides of the link.
2. **Hold-Timer Tuning:** If session flaps due to keepalive loss, temporarily increase BGP holdtime to 180 seconds and keepalive to 60 seconds to prevent session resets.
   - Command: `neighbor <peer-ip> timers 60 180`
3. **Enable BFD:** Enable Bidirectional Forwarding Detection (BFD) for sub-second failure detection once peer is stable.
   - Command: `neighbor <peer-ip> bfd`

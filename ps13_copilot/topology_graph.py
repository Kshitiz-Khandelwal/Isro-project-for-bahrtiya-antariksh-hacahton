"""
topology_graph.py
=================
PS13 — NetworkX-Based Topology Awareness & Event Correlation

Addresses Objective 4: "dynamic graph-based event correlation"

This module:
  1. Builds a NetworkX graph from Containerlab topology YAML
  2. On alert, runs BFS to determine affected downstream scope
  3. Deduplicates/correlates alerts from the same failure domain
  4. Produces structured topology context for LLM copilot injection

Usage:
  from topology_graph import TopologyGraph
  topo = TopologyGraph("topology.yaml")         # from Containerlab YAML
  # -- or --
  topo = TopologyGraph.from_dict(topology_dict)  # from Python dict

  scope = topo.get_affected_scope("PE-1", "eth1")
  # scope feeds into topology_ctx parameter of build_alert_context()

  correlated = topo.correlate_alerts(raw_alerts)
  # reduces 5 interface alerts into 2 correlated events
"""

import networkx as nx
import yaml
import json
from typing import Optional
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Default topology definition (used when Containerlab YAML isn't available)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TOPOLOGY = {
    "nodes": {
        "CE-Hub":     {"role": "hub",    "vrfs": ["VRF-CORP", "VRF-VOICE", "VRF-MGMT"], "tunnels": []},
        "PE-Hub":     {"role": "pe",     "vrfs": ["VRF-CORP", "VRF-VOICE", "VRF-MGMT"], "tunnels": []},
        "P-1":        {"role": "p",      "vrfs": [],                                     "tunnels": []},
        "PE-1":       {"role": "pe",     "vrfs": ["VRF-CORP", "VRF-VOICE"],              "tunnels": []},
        "PE-2":       {"role": "pe",     "vrfs": ["VRF-CORP", "VRF-MGMT"],               "tunnels": []},
        "CE-Branch1": {"role": "branch", "vrfs": ["VRF-CORP"],                            "tunnels": ["IPSec-Branch1-Hub"]},
        "CE-Branch2": {"role": "branch", "vrfs": ["VRF-CORP", "VRF-VOICE"],              "tunnels": ["IPSec-Branch2-Hub"]},
        "CE-Branch3": {"role": "branch", "vrfs": ["VRF-CORP", "VRF-VOICE"],              "tunnels": ["IPSec-Branch3-Hub"]},
        "CE-Branch4": {"role": "branch", "vrfs": ["VRF-CORP", "VRF-MGMT"],               "tunnels": ["IPSec-Branch4-Hub"]},
        "CE-Branch5": {"role": "branch", "vrfs": ["VRF-MGMT"],                            "tunnels": ["IPSec-Branch5-Hub"]},
    },
    "links": [
        # Hub core
        {"endpoints": ["CE-Hub:eth0", "PE-Hub:eth0"], "type": "access", "bandwidth": "10Gbps"},
        {"endpoints": ["PE-Hub:eth1", "P-1:eth0"],    "type": "core",   "bandwidth": "10Gbps"},
        # PE-1 spoke (Branch 1, 2, 3)
        {"endpoints": ["P-1:eth1", "PE-1:eth0"],       "type": "core",   "bandwidth": "1Gbps"},
        {"endpoints": ["PE-1:eth1", "CE-Branch1:eth0"],"type": "access", "bandwidth": "1Gbps"},
        {"endpoints": ["PE-1:eth2", "CE-Branch2:eth0"],"type": "access", "bandwidth": "1Gbps"},
        {"endpoints": ["PE-1:eth3", "CE-Branch3:eth0"],"type": "access", "bandwidth": "1Gbps"},
        # PE-2 spoke (Branch 4, 5)
        {"endpoints": ["P-1:eth2", "PE-2:eth0"],       "type": "core",   "bandwidth": "1Gbps"},
        {"endpoints": ["PE-2:eth1", "CE-Branch4:eth0"],"type": "access", "bandwidth": "1Gbps"},
        {"endpoints": ["PE-2:eth2", "CE-Branch5:eth0"],"type": "access", "bandwidth": "1Gbps"},
    ]
}


class TopologyGraph:
    """
    NetworkX-backed topology graph with event correlation capabilities.
    """

    def __init__(self, clab_yaml_path: Optional[str] = None):
        """
        Initialize from a Containerlab YAML file.
        If no path provided, uses DEFAULT_TOPOLOGY.
        """
        self.G = nx.Graph()

        if clab_yaml_path and Path(clab_yaml_path).exists():
            self._load_from_clab_yaml(clab_yaml_path)
        else:
            self._load_from_dict(DEFAULT_TOPOLOGY)

    @classmethod
    def from_dict(cls, topology_dict: dict) -> "TopologyGraph":
        """Create from a Python dictionary (same format as DEFAULT_TOPOLOGY)."""
        instance = cls.__new__(cls)
        instance.G = nx.Graph()
        instance._load_from_dict(topology_dict)
        return instance

    def _load_from_clab_yaml(self, path: str):
        """Parse Containerlab topology YAML into NetworkX graph."""
        with open(path) as f:
            topo = yaml.safe_load(f)

        clab_topo = topo.get("topology", topo)

        # Add nodes
        for node_name, node_conf in clab_topo.get("nodes", {}).items():
            self.G.add_node(
                node_name,
                role=node_conf.get("role", self._infer_role(node_name)),
                kind=node_conf.get("kind", "unknown"),
                vrfs=node_conf.get("vrfs", []),
                tunnels=node_conf.get("tunnels", []),
            )

        # Add edges from links
        for link in clab_topo.get("links", []):
            endpoints = link.get("endpoints", [])
            if len(endpoints) == 2:
                a_dev, a_iface = endpoints[0].split(":")
                b_dev, b_iface = endpoints[1].split(":")
                self.G.add_edge(
                    a_dev, b_dev,
                    a_interface=a_iface,
                    b_interface=b_iface,
                    link_type=link.get("type", "MPLS underlay"),
                    bandwidth=link.get("bandwidth", "unknown"),
                )

    def _load_from_dict(self, topo: dict):
        """Load from the DEFAULT_TOPOLOGY format."""
        for node_name, attrs in topo.get("nodes", {}).items():
            self.G.add_node(
                node_name,
                role=attrs.get("role", "unknown"),
                vrfs=attrs.get("vrfs", []),
                tunnels=attrs.get("tunnels", []),
            )

        for link in topo.get("links", []):
            endpoints = link.get("endpoints", [])
            if len(endpoints) == 2:
                a_dev, a_iface = endpoints[0].split(":")
                b_dev, b_iface = endpoints[1].split(":")
                self.G.add_edge(
                    a_dev, b_dev,
                    a_interface=a_iface,
                    b_interface=b_iface,
                    link_type=link.get("type", "MPLS underlay"),
                    bandwidth=link.get("bandwidth", "unknown"),
                )

    def _infer_role(self, name: str) -> str:
        """Infer device role from naming convention."""
        name_lower = name.lower()
        if "hub" in name_lower:
            return "hub"
        if "branch" in name_lower:
            return "branch"
        if name_lower.startswith("pe"):
            return "pe"
        if name_lower.startswith("p-") or name_lower == "p":
            return "p"
        if name_lower.startswith("ce"):
            return "ce" if "hub" not in name_lower else "hub"
        return "unknown"

    # ─────────────────────────────────────────────────────────────────────
    # Core: Affected Scope Determination (BFS)
    # ─────────────────────────────────────────────────────────────────────

    def get_affected_scope(self, alert_device: str, alert_interface: str = "") -> dict:
        """
        BFS from the alert device to find all affected downstream scope.

        This is the core function that grounds the copilot's
        'affected_devices' and 'affected_services' fields.

        Parameters
        ----------
        alert_device : str
            Device that triggered the alert (e.g., "PE-1")
        alert_interface : str
            Interface on that device (e.g., "eth1")

        Returns
        -------
        dict compatible with topology_ctx format in noc_copilot_prompt.py:
            {
                "alert_device": "PE-1",
                "alert_interface": "eth1",
                "peer_device": "P-1",
                "link_type": "MPLS underlay (1Gbps)",
                "affected_scope": {
                    "downstream_devices": ["CE-Branch2", "CE-Branch3"],
                    "affected_vrfs": ["VRF-CORP", "VRF-VOICE"],
                    "affected_tunnels": ["IPSec-Branch2-Hub"],
                    "full_path": "CE-Branch2 → PE-1 → P-1 → PE-Hub → CE-Hub"
                }
            }
        """
        if alert_device not in self.G:
            return self._empty_scope(alert_device, alert_interface)

        # Find peer device on the alerted interface
        peer_device = self._find_peer(alert_device, alert_interface)

        # Find link type
        edge_data = self.G.get_edge_data(alert_device, peer_device) if peer_device else {}
        link_type = edge_data.get("link_type", "unknown") if edge_data else "unknown"
        bandwidth = edge_data.get("bandwidth", "") if edge_data else ""
        if bandwidth:
            link_type = f"{link_type} ({bandwidth})"

        # BFS to find all reachable devices (excluding the alert device itself)
        reachable = set(nx.bfs_tree(self.G, alert_device)) - {alert_device}

        # Filter to downstream branch/CE devices
        downstream = sorted([
            n for n in reachable
            if self.G.nodes[n].get("role") in ("branch", "ce")
        ])

        # Collect VRFs and tunnels from downstream devices
        affected_vrfs = set()
        affected_tunnels = set()
        for dev in downstream:
            affected_vrfs.update(self.G.nodes[dev].get("vrfs", []))
            affected_tunnels.update(self.G.nodes[dev].get("tunnels", []))

        # Find path to hub (for display)
        full_path = self._find_path_to_hub(alert_device)

        return {
            "alert_device": alert_device,
            "alert_interface": alert_interface,
            "peer_device": peer_device or "unknown",
            "link_type": link_type,
            "affected_scope": {
                "downstream_devices": downstream,
                "affected_vrfs": sorted(affected_vrfs),
                "affected_tunnels": sorted(affected_tunnels),
                "full_path": full_path,
            }
        }

    def _find_peer(self, device: str, interface: str) -> Optional[str]:
        """Find the neighbor device connected via a specific interface."""
        for neighbor in self.G.neighbors(device):
            edge = self.G.get_edge_data(device, neighbor)
            if edge:
                if edge.get("a_interface") == interface or edge.get("b_interface") == interface:
                    return neighbor
        # Fallback: return first neighbor
        neighbors = list(self.G.neighbors(device))
        return neighbors[0] if neighbors else None

    def _find_path_to_hub(self, device: str) -> str:
        """Find the shortest path from device to any hub/datacenter node."""
        hub_nodes = [
            n for n in self.G.nodes
            if self.G.nodes[n].get("role") in ("hub", "datacenter")
        ]
        if not hub_nodes:
            return "No hub node in topology"

        for hub in hub_nodes:
            try:
                path = nx.shortest_path(self.G, device, hub)
                return " → ".join(path)
            except nx.NetworkXNoPath:
                continue

        return f"No path from {device} to hub"

    def _empty_scope(self, device: str, interface: str) -> dict:
        """Return empty scope when device isn't in the graph."""
        return {
            "alert_device": device,
            "alert_interface": interface,
            "peer_device": "unknown",
            "link_type": "unknown",
            "affected_scope": {
                "downstream_devices": [],
                "affected_vrfs": [],
                "affected_tunnels": [],
                "full_path": f"{device} not found in topology graph",
            }
        }

    # ─────────────────────────────────────────────────────────────────────
    # Alert Correlation — deduplicate related alerts
    # ─────────────────────────────────────────────────────────────────────

    def correlate_alerts(self, alerts: list[dict]) -> list[dict]:
        """
        Deduplicate/correlate alerts from the same device or failure domain.

        If 3 interfaces on PE-1 all alert simultaneously, emit 1 correlated
        event instead of 3 independent alerts. This reduces alert fatigue.

        Parameters
        ----------
        alerts : list[dict]
            Raw alerts, each with at least 'device' and 'interface' keys.

        Returns
        -------
        list[dict] — deduplicated/correlated alerts with added 'scope' key.
        """
        # Group by device
        device_groups: dict[str, list[dict]] = {}
        for alert in alerts:
            dev = alert.get("device", "unknown")
            device_groups.setdefault(dev, []).append(alert)

        correlated = []
        for device, dev_alerts in device_groups.items():
            if len(dev_alerts) > 1:
                # Multiple alerts on same device → correlate
                primary = dev_alerts[0]
                scope = self.get_affected_scope(device, primary.get("interface", ""))

                correlated.append({
                    "correlated_id": f"CORR-{device}-{len(dev_alerts)}",
                    "is_correlated": True,
                    "device": device,
                    "alert_count": len(dev_alerts),
                    "interfaces": [a.get("interface", "?") for a in dev_alerts],
                    "highest_severity": self._max_severity(dev_alerts),
                    "primary_alert": primary,
                    "scope": scope,
                })
            else:
                alert = dev_alerts[0]
                alert["is_correlated"] = False
                alert["scope"] = self.get_affected_scope(
                    device, alert.get("interface", "")
                )
                correlated.append(alert)

        return correlated

    def _max_severity(self, alerts: list[dict]) -> str:
        """Find the highest severity from a list of alerts."""
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_sev = max(
            alerts,
            key=lambda a: severity_order.get(a.get("severity", "LOW"), 0)
        )
        return max_sev.get("severity", "LOW")

    # ─────────────────────────────────────────────────────────────────────
    # Topology info for dashboard / documentation
    # ─────────────────────────────────────────────────────────────────────

    def get_topology_summary(self) -> dict:
        """Return a summary of the topology for display."""
        roles = {}
        for node in self.G.nodes:
            role = self.G.nodes[node].get("role", "unknown")
            roles.setdefault(role, []).append(node)

        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_links": self.G.number_of_edges(),
            "nodes_by_role": roles,
            "all_vrfs": sorted(set(
                vrf for n in self.G.nodes
                for vrf in self.G.nodes[n].get("vrfs", [])
            )),
            "all_tunnels": sorted(set(
                t for n in self.G.nodes
                for t in self.G.nodes[n].get("tunnels", [])
            )),
        }

    def get_plotly_data(self) -> dict:
        """
        Return node positions and edge data for Plotly graph visualization
        in the Streamlit dashboard.
        """
        pos = nx.spring_layout(self.G, seed=42, k=2)

        node_x, node_y, node_text, node_color = [], [], [], []
        role_colors = {
            "hub": "#FF6B6B", "pe": "#4ECDC4", "p": "#45B7D1",
            "branch": "#96CEB4", "ce": "#FFEAA7", "unknown": "#DDD"
        }

        for node in self.G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            role = self.G.nodes[node].get("role", "unknown")
            node_text.append(f"{node} ({role})")
            node_color.append(role_colors.get(role, "#DDD"))

        edge_x, edge_y = [], []
        for edge in self.G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        return {
            "nodes": {"x": node_x, "y": node_y, "text": node_text, "color": node_color},
            "edges": {"x": edge_x, "y": edge_y},
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("PS13 Topology Graph — Test Run")
    print("=" * 50)

    topo = TopologyGraph()  # uses DEFAULT_TOPOLOGY
    summary = topo.get_topology_summary()

    print(f"\nTopology loaded: {summary['total_nodes']} nodes, {summary['total_links']} links")
    print(f"Roles: {json.dumps(summary['nodes_by_role'], indent=2)}")
    print(f"VRFs:  {summary['all_vrfs']}")
    print(f"Tunnels: {summary['all_tunnels']}")

    # Test: alert on PE-1 eth1
    print(f"\n{'─' * 50}")
    print("Test: Alert on PE-1 / eth1")
    scope = topo.get_affected_scope("PE-1", "eth1")
    print(f"  Peer device:       {scope['peer_device']}")
    print(f"  Link type:         {scope['link_type']}")
    print(f"  Downstream:        {scope['affected_scope']['downstream_devices']}")
    print(f"  Affected VRFs:     {scope['affected_scope']['affected_vrfs']}")
    print(f"  Affected tunnels:  {scope['affected_scope']['affected_tunnels']}")
    print(f"  Path to hub:       {scope['affected_scope']['full_path']}")

    # Test: alert on PE-2 eth0
    print(f"\n{'─' * 50}")
    print("Test: Alert on PE-2 / eth0")
    scope2 = topo.get_affected_scope("PE-2", "eth0")
    print(f"  Peer device:       {scope2['peer_device']}")
    print(f"  Downstream:        {scope2['affected_scope']['downstream_devices']}")
    print(f"  Affected VRFs:     {scope2['affected_scope']['affected_vrfs']}")

    # Test: alert correlation
    print(f"\n{'─' * 50}")
    print("Test: Alert correlation (3 alerts on PE-1)")
    raw_alerts = [
        {"device": "PE-1", "interface": "eth1", "severity": "HIGH"},
        {"device": "PE-1", "interface": "eth2", "severity": "CRITICAL"},
        {"device": "PE-1", "interface": "eth3", "severity": "MEDIUM"},
        {"device": "PE-2", "interface": "eth1", "severity": "HIGH"},
    ]
    correlated = topo.correlate_alerts(raw_alerts)
    print(f"  Input:  {len(raw_alerts)} raw alerts")
    print(f"  Output: {len(correlated)} correlated events")
    for c in correlated:
        if c.get("is_correlated"):
            print(f"    CORR: {c['device']} — {c['alert_count']} alerts on {c['interfaces']} — severity: {c['highest_severity']}")
        else:
            print(f"    SINGLE: {c['device']}/{c.get('interface', '?')} — severity: {c.get('severity', '?')}")

    print(f"\nDone. Scope dicts feed into topology_ctx parameter of build_alert_context()")

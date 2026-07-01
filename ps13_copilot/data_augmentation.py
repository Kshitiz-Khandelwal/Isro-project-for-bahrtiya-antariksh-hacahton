"""
data_augmentation.py
====================
PS13 — Data Augmentation & Telemetry Dataset Generator

This module handles:
  1. Generating realistic normal network baseline telemetry.
  2. Simulating the 4 fault scenarios (Congestion, BGP flaps, Tunnel drops, Policy drift).
  3. Applying data augmentation (Gaussian noise, time shifts, scaling) to expand small datasets.
  4. Formulating labeled datasets for training supervised ML models (XGBoost/LightGBM).

Addresses review gap: "2 hours of fault injection = ~240 data points. This is marginal for XGBoost.
Need data augmentation and synthetic baseline generation."
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, List, Dict

# Set random seed for reproducibility
np.random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Telemetry Feature Columns (Matches improved feature list in v2 roadmap)
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS = [
    # Underlay (MPLS)
    "underlay_if_utilization_pct",
    "underlay_if_discards_rate",
    "underlay_if_errors_rate",
    "underlay_bgp_state_changes",
    "underlay_route_count_delta",
    # Overlay (SD-WAN IPSec Tunnels)
    "overlay_tunnel_latency_ms",
    "overlay_tunnel_jitter_ms",
    "overlay_tunnel_loss_pct",
    "overlay_tunnel_uptime_sec",
    "overlay_ipsec_rekey_failures",
    # Derived / Engineered
    "utilization_rate_of_change",
    "utilization_5min_ema",
    "error_ratio",
    "bytes_asymmetry_ratio",
    "voice_traffic_dscp_ratio",
    # Label (Normal = 0, Congestion = 1, BGP Flap = 2, Tunnel Degradation = 3, Policy Drift = 4)
    "label"
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Synthetic Telemetry Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_base_timeline(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """Create a DataFrame with timestamps."""
    now = datetime.utcnow()
    total_steps = int((duration_hours * 3600) / interval_seconds)
    timestamps = [now - timedelta(seconds=interval_seconds * (total_steps - i)) for i in range(total_steps)]
    df = pd.DataFrame(index=range(total_steps))
    df["timestamp"] = timestamps
    return df


def generate_normal_baseline(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """
    Generate normal baseline telemetry under stable conditions.
    """
    df = generate_base_timeline(duration_hours, interval_seconds)
    n = len(df)
    
    # Underlay (stable & quiet)
    # Utilization has small cyclic variation + noise (20% - 45%)
    cycles = np.sin(np.linspace(0, duration_hours * np.pi * 2, n))
    df["underlay_if_utilization_pct"] = 30.0 + 10.0 * cycles + np.random.normal(0, 2.0, n)
    df["underlay_if_utilization_pct"] = df["underlay_if_utilization_pct"].clip(5, 95)
    
    df["underlay_if_discards_rate"] = np.random.exponential(0.02, n)
    df["underlay_if_errors_rate"] = np.random.exponential(0.005, n)
    df["underlay_bgp_state_changes"] = 0
    df["underlay_route_count_delta"] = np.random.choice([0, 0, 0, 0, 1, -1], n, p=[0.9, 0.08, 0.01, 0.01, 0.00, 0.00])
    
    # Overlay (stable & healthy)
    df["overlay_tunnel_latency_ms"] = 12.0 + np.random.normal(0, 0.8, n)
    df["overlay_tunnel_jitter_ms"] = 2.0 + np.random.normal(0, 0.3, n)
    df["overlay_tunnel_loss_pct"] = np.random.exponential(0.05, n).clip(0, 100)
    df["overlay_tunnel_uptime_sec"] = np.arange(n) * interval_seconds + 3600
    df["overlay_ipsec_rekey_failures"] = 0
    
    # Derived
    df["utilization_rate_of_change"] = np.random.normal(0, 0.05, n)
    df["utilization_5min_ema"] = df["underlay_if_utilization_pct"].ewm(span=10).mean()
    df["error_ratio"] = df["underlay_if_errors_rate"] / (df["underlay_if_utilization_pct"] + 1)
    df["bytes_asymmetry_ratio"] = 0.5 + np.random.normal(0, 0.02, n)
    df["voice_traffic_dscp_ratio"] = 0.2 + np.random.normal(0, 0.01, n)
    
    df["label"] = 0  # Normal
    
    return df


def generate_congestion_buildup(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """
    Generate congestion buildup: utilization steadily climbs to 90%+.
    Discards spike. Latency and jitter rise.
    """
    df = generate_base_timeline(duration_hours, interval_seconds)
    n = len(df)
    
    # Underlay (ramping up)
    # Utilization starts at 40% and ramps up linearly to 95%
    ramp = np.linspace(40.0, 95.0, n)
    df["underlay_if_utilization_pct"] = ramp + np.random.normal(0, 1.5, n)
    df["underlay_if_utilization_pct"] = df["underlay_if_utilization_pct"].clip(5, 100)
    
    # Discards increase exponentially as queue fills up
    df["underlay_if_discards_rate"] = np.exp((df["underlay_if_utilization_pct"] - 75.0) / 8.0) * np.random.exponential(1.0, n)
    df["underlay_if_discards_rate"] = df["underlay_if_discards_rate"].clip(0, 50)
    df["underlay_if_errors_rate"] = np.random.exponential(0.05, n)
    df["underlay_bgp_state_changes"] = 0
    df["underlay_route_count_delta"] = 0
    
    # Overlay suffers from queuing delay
    df["overlay_tunnel_latency_ms"] = 12.0 + (df["underlay_if_utilization_pct"] - 40.0) * 0.4 + np.random.normal(0, 1.0, n)
    df["overlay_tunnel_jitter_ms"] = 2.0 + (df["underlay_if_utilization_pct"] - 40.0) * 0.15 + np.random.normal(0, 0.5, n)
    df["overlay_tunnel_loss_pct"] = (df["underlay_if_discards_rate"] / 5.0) + np.random.exponential(0.05, n)
    df["overlay_tunnel_loss_pct"] = df["overlay_tunnel_loss_pct"].clip(0, 100)
    df["overlay_tunnel_uptime_sec"] = np.arange(n) * interval_seconds + 3600
    df["overlay_ipsec_rekey_failures"] = 0
    
    # Derived
    df["utilization_rate_of_change"] = np.gradient(df["underlay_if_utilization_pct"])
    df["utilization_5min_ema"] = df["underlay_if_utilization_pct"].ewm(span=10).mean()
    df["error_ratio"] = df["underlay_if_errors_rate"] / (df["underlay_if_utilization_pct"] + 1)
    df["bytes_asymmetry_ratio"] = 0.55 + np.random.normal(0, 0.05, n)
    df["voice_traffic_dscp_ratio"] = 0.2 + np.random.normal(0, 0.01, n)
    
    df["label"] = 1  # Congestion
    
    return df


def generate_bgp_instability(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """
    Generate BGP flaps: route flaps, route count spikes and drops, packet loss spikes on control traffic.
    """
    df = generate_base_timeline(duration_hours, interval_seconds)
    n = len(df)
    
    # Underlay (BGP flapping)
    df["underlay_if_utilization_pct"] = 35.0 + np.random.normal(0, 3.0, n)
    df["underlay_if_discards_rate"] = np.random.exponential(0.05, n)
    df["underlay_if_errors_rate"] = np.random.exponential(0.1, n)
    
    # BGP flips every 5-10 minutes
    flaps = np.zeros(n)
    routes_delta = np.zeros(n)
    for i in range(1, n):
        if i % 15 == 0:  # ~7.5 minutes
            flaps[i] = 1
            routes_delta[i] = -47  # routes withdrawn
        elif (i - 4) % 15 == 0:
            flaps[i] = 1
            routes_delta[i] = 47   # routes re-learned
            
    df["underlay_bgp_state_changes"] = flaps.astype(int)
    df["underlay_route_count_delta"] = routes_delta
    
    # Overlay degrades slightly during routing convergence
    df["overlay_tunnel_latency_ms"] = 15.0 + 35.0 * (df["underlay_bgp_state_changes"].rolling(5, min_periods=1).max()) + np.random.normal(0, 2.0, n)
    df["overlay_tunnel_jitter_ms"] = 2.0 + 20.0 * (df["underlay_bgp_state_changes"].rolling(5, min_periods=1).max()) + np.random.normal(0, 1.0, n)
    df["overlay_tunnel_loss_pct"] = 3.0 * (df["underlay_bgp_state_changes"].rolling(3, min_periods=1).max()) + np.random.exponential(0.1, n)
    df["overlay_tunnel_loss_pct"] = df["overlay_tunnel_loss_pct"].clip(0, 100)
    df["overlay_tunnel_uptime_sec"] = np.where(flaps > 0, 10, np.arange(n) * interval_seconds + 120)
    df["overlay_ipsec_rekey_failures"] = 0
    
    # Derived
    df["utilization_rate_of_change"] = np.random.normal(0, 0.05, n)
    df["utilization_5min_ema"] = df["underlay_if_utilization_pct"].ewm(span=10).mean()
    df["error_ratio"] = df["underlay_if_errors_rate"] / (df["underlay_if_utilization_pct"] + 1)
    df["bytes_asymmetry_ratio"] = 0.5 + np.random.normal(0, 0.05, n)
    df["voice_traffic_dscp_ratio"] = 0.2 + np.random.normal(0, 0.02, n)
    
    df["label"] = 2  # BGP Instability
    
    return df


def generate_tunnel_degradation(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """
    Generate tunnel degradation: IPSec rekeys fail, overlay loss and jitter climb,
    underlay remains normal.
    """
    df = generate_base_timeline(duration_hours, interval_seconds)
    n = len(df)
    
    # Underlay remains stable
    df["underlay_if_utilization_pct"] = 40.0 + np.random.normal(0, 2.0, n)
    df["underlay_if_discards_rate"] = np.random.exponential(0.02, n)
    df["underlay_if_errors_rate"] = np.random.exponential(0.005, n)
    df["underlay_bgp_state_changes"] = 0
    df["underlay_route_count_delta"] = 0
    
    # Overlay falls apart
    # Latency ramps up, jitter ramps up, loss jumps to 8%+
    loss_curve = np.linspace(0.1, 12.0, n)
    df["overlay_tunnel_loss_pct"] = loss_curve + np.random.exponential(0.5, n)
    df["overlay_tunnel_loss_pct"] = df["overlay_tunnel_loss_pct"].clip(0, 100)
    
    df["overlay_tunnel_latency_ms"] = 12.0 + np.linspace(0, 30.0, n) + np.random.normal(0, 1.5, n)
    df["overlay_tunnel_jitter_ms"] = 2.0 + np.linspace(0, 25.0, n) + np.random.normal(0, 1.0, n)
    df["overlay_tunnel_uptime_sec"] = np.arange(n) * interval_seconds + 500
    
    # Simulate IPSec rekey failures towards the end
    rekey = np.zeros(n)
    for i in range(int(n * 0.5), n):
        if i % 20 == 0:
            rekey[i] = 1
    df["overlay_ipsec_rekey_failures"] = rekey.astype(int)
    
    # Derived
    df["utilization_rate_of_change"] = np.random.normal(0, 0.05, n)
    df["utilization_5min_ema"] = df["underlay_if_utilization_pct"].ewm(span=10).mean()
    df["error_ratio"] = df["underlay_if_errors_rate"] / (df["underlay_if_utilization_pct"] + 1)
    df["bytes_asymmetry_ratio"] = 0.5 + np.random.normal(0, 0.02, n)
    df["voice_traffic_dscp_ratio"] = 0.2 + np.random.normal(0, 0.01, n)
    
    df["label"] = 3  # Tunnel Degradation
    
    return df


def generate_policy_drift(duration_hours: float, interval_seconds: int = 30) -> pd.DataFrame:
    """
    Generate policy drift: QoS policy is removed or misconfigured.
    Voice DSCP ratio drops to near-zero, jitter spikes for voice, underlay normal.
    """
    df = generate_base_timeline(duration_hours, interval_seconds)
    n = len(df)
    
    # Underlay normal
    df["underlay_if_utilization_pct"] = 55.0 + np.random.normal(0, 2.0, n)
    df["underlay_if_discards_rate"] = np.random.exponential(0.02, n)
    df["underlay_if_errors_rate"] = np.random.exponential(0.005, n)
    df["underlay_bgp_state_changes"] = 0
    df["underlay_route_count_delta"] = 0
    
    # Overlay: Voice DSCP ratio falls from 0.2 to 0.01
    dscp_drop = np.linspace(0.2, 0.01, n)
    df["voice_traffic_dscp_ratio"] = dscp_drop + np.random.normal(0, 0.005, n)
    df["voice_traffic_dscp_ratio"] = df["voice_traffic_dscp_ratio"].clip(0.001, 1.0)
    
    # Voice queue queue-depth/jitter spikes because EF classification is gone
    df["overlay_tunnel_jitter_ms"] = 2.0 + (0.2 - df["voice_traffic_dscp_ratio"]) * 150.0 + np.random.normal(0, 2.0, n)
    df["overlay_tunnel_latency_ms"] = 15.0 + (0.2 - df["voice_traffic_dscp_ratio"]) * 50.0 + np.random.normal(0, 1.0, n)
    df["overlay_tunnel_loss_pct"] = np.random.exponential(0.05, n)
    df["overlay_tunnel_uptime_sec"] = np.arange(n) * interval_seconds + 3600
    df["overlay_ipsec_rekey_failures"] = 0
    
    # Derived
    df["utilization_rate_of_change"] = np.random.normal(0, 0.05, n)
    df["utilization_5min_ema"] = df["underlay_if_utilization_pct"].ewm(span=10).mean()
    df["error_ratio"] = df["underlay_if_errors_rate"] / (df["underlay_if_utilization_pct"] + 1)
    df["bytes_asymmetry_ratio"] = 0.5 + np.random.normal(0, 0.02, n)
    
    df["label"] = 4  # Policy Drift
    
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Data Augmentation
# ─────────────────────────────────────────────────────────────────────────────

def augment_data(
    df: pd.DataFrame,
    n_copies: int = 5,
    noise_std: float = 0.02,
    time_shift_range: int = 5
) -> pd.DataFrame:
    """
    Perform data augmentation on a telemetry dataset:
      - Appends copies with small Gaussian noise added to numeric columns
      - Adds time shifts (jittering timestamps) to simulate variable collection skew
    """
    augmented_dfs = [df]
    numeric_cols = [
        col for col in df.columns 
        if col not in ["timestamp", "label"] and np.issubdtype(df[col].dtype, np.number)
    ]
    
    for c in range(n_copies):
        noisy_copy = df.copy()
        
        # 1. Add Gaussian noise to numeric columns
        for col in numeric_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            col_range = max(col_max - col_min, 1.0)
            
            # Noise scale is relative to the feature's natural range
            noise = np.random.normal(0, noise_std * col_range, len(df))
            noisy_copy[col] = noisy_copy[col] + noise
            
            # Clip bounds logically
            if "pct" in col or "ratio" in col:
                noisy_copy[col] = noisy_copy[col].clip(0, 100 if "pct" in col else 1.0)
            elif "rate" in col or "failures" in col or "uptime" in col or "ms" in col:
                noisy_copy[col] = noisy_copy[col].clip(0, None)
                
        # 2. Add timestamp shifts (seconds)
        time_shift = timedelta(seconds=int(np.random.randint(-time_shift_range, time_shift_range + 1)))
        noisy_copy["timestamp"] = noisy_copy["timestamp"] + time_shift
        
        augmented_dfs.append(noisy_copy)
        
    return pd.concat(augmented_dfs, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Dataset Compiler
# ─────────────────────────────────────────────────────────────────────────────

def compile_training_dataset(
    normal_hours: float = 4.0,
    fault_hours_each: float = 1.0,
    augment_copies: int = 5
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Builds the complete labeled dataset for predictive modeling.
    Returns:
      (train_df, test_df) - split datasets with normal and fault telemetry
    """
    print(f"Generating synthetic telemetry...")
    normal_df = generate_normal_baseline(normal_hours)
    congestion_df = generate_congestion_buildup(fault_hours_each)
    bgp_df = generate_bgp_instability(fault_hours_each)
    tunnel_df = generate_tunnel_degradation(fault_hours_each)
    policy_df = generate_policy_drift(fault_hours_each)
    
    # Split into train and test before augmentation (avoid leakage)
    splits = []
    for name, df in [
        ("normal", normal_df),
        ("congestion", congestion_df),
        ("bgp", bgp_df),
        ("tunnel", tunnel_df),
        ("policy", policy_df)
    ]:
        n = len(df)
        split_idx = int(n * 0.8)
        train_part = df.iloc[:split_idx].copy()
        test_part = df.iloc[split_idx:].copy()
        
        splits.append((train_part, test_part))
        
    train_dfs = [s[0] for s in splits]
    test_dfs = [s[1] for s in splits]
    
    raw_train = pd.concat(train_dfs, ignore_index=True)
    raw_test = pd.concat(test_dfs, ignore_index=True)
    
    print(f"  Raw Train size: {len(raw_train)} samples")
    print(f"  Raw Test size:  {len(raw_test)} samples")
    
    # Augment ONLY the training set to prevent leakage
    print(f"Applying data augmentation (n_copies={augment_copies})...")
    augmented_train = augment_data(raw_train, n_copies=augment_copies)
    print(f"  Augmented Train size: {len(augmented_train)} samples")
    
    return augmented_train, raw_test


if __name__ == "__main__":
    print("PS13 Telemetry Generator & Augmentation — Test Run")
    print("=" * 60)
    train, test = compile_training_dataset(normal_hours=2, fault_hours_each=0.5, augment_copies=4)
    print(f"\nFinal training dataset shapes:")
    print(f"  Train: {train.shape}")
    print(f"  Test:  {test.shape}")
    print(f"\nClass Distribution in Train:")
    print(train["label"].value_counts())
    print("\nDone.")

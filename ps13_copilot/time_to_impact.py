"""
time_to_impact.py
=================
PS13 — Prophet-Based Time-to-Impact Estimator

Answers Q1: "What is likely to fail next — and WHEN?"

This module:
  1. Takes a recent history of a single metric (e.g., interface utilization)
  2. Fits a Prophet model on it
  3. Forecasts forward (default 30 minutes)
  4. Finds the first timestamp where the forecast crosses the SLA threshold
  5. Returns a structured dict that plugs into noc_copilot_prompt.py

Usage:
  from time_to_impact import estimate_time_to_impact, SLA_THRESHOLDS
  result = estimate_time_to_impact("if_utilization_pct", history_df)
  # result feeds into alert_data["prophet_forecast"] in the copilot module

Evaluation dimension: Technical Merit (35% weight) — lead time scoring
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Optional

# Suppress Prophet's verbose output during fitting
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

# Lazy import Prophet — it's heavy and only needed when called
_prophet_imported = False
_Prophet = None

def _ensure_prophet():
    global _prophet_imported, _Prophet
    if not _prophet_imported:
        from prophet import Prophet
        _Prophet = Prophet
        _prophet_imported = True
    return _Prophet


# ─────────────────────────────────────────────────────────────────────────────
# SLA Thresholds — these define "breach" for each metric
# ─────────────────────────────────────────────────────────────────────────────

SLA_THRESHOLDS = {
    "if_utilization_pct":       85.0,   # Interface capacity
    "tunnel_packet_loss_pct":    1.0,   # Acceptable packet loss
    "tunnel_jitter_ms":         20.0,   # Jitter for VoIP quality
    "tunnel_latency_ms":        50.0,   # End-to-end latency
    "if_discards_rate":         10.0,   # Discards per second
    "if_errors_rate":            5.0,   # Errors per second
    "bgp_reconvergence_sec":    60.0,   # BGP reconvergence time
}


# ─────────────────────────────────────────────────────────────────────────────
# Core function
# ─────────────────────────────────────────────────────────────────────────────

def estimate_time_to_impact(
    metric_name: str,
    history_df: pd.DataFrame,
    threshold: Optional[float] = None,
    forecast_horizon_sec: int = 1800,
    polling_interval_sec: int = 30
) -> dict:
    """
    Fit Prophet on recent metric history, forecast forward, and find
    the first timestamp where the forecast crosses the SLA threshold.

    Parameters
    ----------
    metric_name : str
        Name of the metric (used for SLA threshold lookup and reporting).

    history_df : pd.DataFrame
        Must have columns ['ds', 'y'] where:
        - ds: datetime timestamps (at least 10 data points)
        - y: metric values (e.g., utilization percentage)

    threshold : float, optional
        SLA threshold. If None, looked up from SLA_THRESHOLDS.

    forecast_horizon_sec : int
        How far ahead to forecast in seconds. Default: 1800 (30 minutes).

    polling_interval_sec : int
        Data collection interval. Default: 30 seconds.

    Returns
    -------
    dict with keys:
        metric              : str
        current_value       : float
        threshold           : float
        will_breach         : bool
        breach_time_utc     : str | None
        minutes_to_breach   : int | None
        forecast_at_30min   : float
        trend_slope_per_30s : float
        confidence_lower    : float | None  (Prophet yhat_lower at breach)
        confidence_upper    : float | None  (Prophet yhat_upper at breach)

    This dict plugs directly into alert_data["prophet_forecast"] in
    noc_copilot_prompt.py, which format_prophet_forecast() renders
    for LLM context injection.
    """
    Prophet = _ensure_prophet()

    if threshold is None:
        threshold = SLA_THRESHOLDS.get(metric_name, 85.0)

    # Validate input
    if history_df is None or len(history_df) < 5:
        return _empty_forecast(metric_name, threshold, reason="Insufficient history data (need ≥5 points)")

    # Ensure correct column names and types
    df = history_df[["ds", "y"]].copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.dropna()

    if len(df) < 5:
        return _empty_forecast(metric_name, threshold, reason="Too few valid data points after cleaning")

    current_value = float(df["y"].iloc[-1])
    now = df["ds"].max()

    # Already breached?
    if current_value >= threshold:
        return {
            "metric": metric_name,
            "current_value": round(current_value, 1),
            "threshold": threshold,
            "will_breach": True,
            "breach_time_utc": now.isoformat(),
            "minutes_to_breach": 0,
            "forecast_at_30min": round(current_value, 1),
            "trend_slope_per_30s": 0.0,
            "confidence_lower": None,
            "confidence_upper": None,
            "note": "Threshold already breached at current value"
        }

    # Fit Prophet
    try:
        model = Prophet(
            changepoint_prior_scale=0.5,
            seasonality_mode="additive",
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=False,
            interval_width=0.80,        # 80% confidence interval
        )
        model.fit(df)
    except Exception as e:
        return _empty_forecast(metric_name, threshold, reason=f"Prophet fitting failed: {e}")

    # Forecast forward
    periods = max(1, forecast_horizon_sec // polling_interval_sec)
    future = model.make_future_dataframe(periods=periods, freq=f"{polling_interval_sec}s")
    forecast = model.predict(future)

    # Find future-only rows
    future_forecast = forecast[forecast["ds"] > now].copy()

    if future_forecast.empty:
        return _empty_forecast(metric_name, threshold, reason="No future forecast generated")

    # Find threshold crossing
    breach_rows = future_forecast[future_forecast["yhat"] >= threshold]
    forecast_at_end = float(future_forecast["yhat"].iloc[-1])

    # Calculate trend slope from recent history
    trend_slope = _calculate_slope(df, polling_interval_sec)

    if not breach_rows.empty:
        breach_row = breach_rows.iloc[0]
        breach_time = breach_row["ds"]
        minutes_to_breach = max(1, int((breach_time - now).total_seconds() / 60))

        return {
            "metric": metric_name,
            "current_value": round(current_value, 1),
            "threshold": threshold,
            "will_breach": True,
            "breach_time_utc": breach_time.isoformat(),
            "minutes_to_breach": minutes_to_breach,
            "forecast_at_30min": round(forecast_at_end, 1),
            "trend_slope_per_30s": round(trend_slope, 4),
            "confidence_lower": round(float(breach_row["yhat_lower"]), 1),
            "confidence_upper": round(float(breach_row["yhat_upper"]), 1),
        }
    else:
        return {
            "metric": metric_name,
            "current_value": round(current_value, 1),
            "threshold": threshold,
            "will_breach": False,
            "breach_time_utc": None,
            "minutes_to_breach": None,
            "forecast_at_30min": round(forecast_at_end, 1),
            "trend_slope_per_30s": round(trend_slope, 4),
            "confidence_lower": None,
            "confidence_upper": None,
        }


def _calculate_slope(df: pd.DataFrame, interval_sec: int) -> float:
    """Calculate the average slope (change per interval) from recent data."""
    if len(df) < 2:
        return 0.0
    recent = df.tail(min(10, len(df)))
    n = len(recent)
    if n < 2:
        return 0.0
    return float((recent["y"].iloc[-1] - recent["y"].iloc[0]) / (n - 1))


def _empty_forecast(metric_name: str, threshold: float, reason: str = "") -> dict:
    """Return a safe empty forecast dict when computation isn't possible."""
    return {
        "metric": metric_name,
        "current_value": None,
        "threshold": threshold,
        "will_breach": False,
        "breach_time_utc": None,
        "minutes_to_breach": None,
        "forecast_at_30min": None,
        "trend_slope_per_30s": 0.0,
        "confidence_lower": None,
        "confidence_upper": None,
        "note": reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch forecasting — run Prophet on multiple metrics simultaneously
# ─────────────────────────────────────────────────────────────────────────────

def batch_forecast(
    metrics_data: dict[str, pd.DataFrame],
    custom_thresholds: Optional[dict[str, float]] = None,
) -> dict[str, dict]:
    """
    Run time-to-impact estimation on multiple metrics.

    Parameters
    ----------
    metrics_data : dict
        Mapping of metric_name → DataFrame with ['ds', 'y'] columns.
        e.g., {"if_utilization_pct": df1, "tunnel_packet_loss_pct": df2}

    custom_thresholds : dict, optional
        Override default SLA thresholds for specific metrics.

    Returns
    -------
    dict mapping metric_name → forecast result dict
    """
    thresholds = {**SLA_THRESHOLDS, **(custom_thresholds or {})}
    results = {}

    for metric_name, history_df in metrics_data.items():
        threshold = thresholds.get(metric_name, 85.0)
        results[metric_name] = estimate_time_to_impact(
            metric_name, history_df, threshold=threshold
        )

    return results


def get_most_critical_forecast(forecasts: dict[str, dict]) -> Optional[dict]:
    """
    From batch_forecast results, find the metric closest to breaching SLA.
    Returns the forecast with the shortest minutes_to_breach.
    """
    breaching = [
        (name, fc) for name, fc in forecasts.items()
        if fc.get("will_breach") and fc.get("minutes_to_breach") is not None
    ]
    if not breaching:
        return None

    breaching.sort(key=lambda x: x[1]["minutes_to_breach"])
    return breaching[0][1]


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data generator — for testing without a live network
# ─────────────────────────────────────────────────────────────────────────────

def generate_congestion_ramp(
    start_value: float = 40.0,
    slope_per_30s: float = 0.35,
    noise_std: float = 2.0,
    duration_minutes: int = 30,
    interval_sec: int = 30,
) -> pd.DataFrame:
    """
    Generate a synthetic congestion ramp for testing time-to-impact.

    Returns DataFrame with ['ds', 'y'] columns simulating a gradually
    rising utilization metric.
    """
    now = datetime.utcnow()
    n_points = (duration_minutes * 60) // interval_sec
    timestamps = [now - timedelta(seconds=interval_sec * (n_points - i)) for i in range(n_points)]
    values = [
        start_value + slope_per_30s * i + np.random.normal(0, noise_std)
        for i in range(n_points)
    ]

    return pd.DataFrame({"ds": timestamps, "y": values})


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("PS13 Time-to-Impact Estimator — Test Run")
    print("=" * 50)

    # Generate synthetic congestion ramp starting at 40%, rising ~0.35%/30s
    print("\nGenerating synthetic congestion ramp (40% → rising)...")
    history = generate_congestion_ramp(start_value=40.0, slope_per_30s=0.35)
    print(f"  Data points: {len(history)}")
    print(f"  Time range: {history['ds'].iloc[0]} → {history['ds'].iloc[-1]}")
    print(f"  Value range: {history['y'].min():.1f}% → {history['y'].max():.1f}%")

    print("\nFitting Prophet and forecasting...")
    result = estimate_time_to_impact("if_utilization_pct", history)

    print(f"\n  Metric:            {result['metric']}")
    print(f"  Current value:     {result['current_value']}%")
    print(f"  SLA threshold:     {result['threshold']}%")
    print(f"  Will breach:       {result['will_breach']}")
    if result["will_breach"]:
        print(f"  Breach time:       {result['breach_time_utc']}")
        print(f"  Minutes to breach: {result['minutes_to_breach']} min")
    print(f"  Forecast at 30min: {result['forecast_at_30min']}%")
    print(f"  Trend slope:       {result['trend_slope_per_30s']:+.4f}%/30s")

    print("\nDone. This result plugs into alert_data['prophet_forecast'] in noc_copilot_prompt.py")

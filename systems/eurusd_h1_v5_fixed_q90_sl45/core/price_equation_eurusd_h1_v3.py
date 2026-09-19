#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Price Equation EURUSD H1 V3

Research-grade evolution of the original PriceEquationModel.
Key ideas:
1) never judge a price forecast without comparing it to Close(t+1)=Close(t);
2) model the next move (stationary-ish target), not the raw price level;
3) keep chronological train / validation / OOS splits;
4) exclude weekend/holiday gaps from the strict 1-hour target;
5) use two heads:
   - Ridge regression for expected move size in pips;
   - HistGradientBoosting classifier for direction/confidence;
6) choose the confidence gate only on validation and never retune on OOS.

Expected input columns:
Time,Open,High,Low,Close,TickVolume,Spread,RealVolume
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PIP = 1e-4


@dataclass
class SplitBundle:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    train_end: pd.Timestamp
    val_end: pd.Timestamp


def load_quotes(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["Time", "Open", "High", "Low", "Close", "TickVolume", "Spread", "RealVolume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Time"] = pd.to_datetime(df["Time"], format="%Y.%m.%d %H:%M", errors="raise")
    df = df.sort_values("Time").drop_duplicates("Time").reset_index(drop=True)

    bad_ohlc = (
        (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
        | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
    )
    if bad_ohlc.any():
        raise ValueError(f"Found {int(bad_ohlc.sum())} invalid OHLC rows")
    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    d = df.copy()
    logc = np.log(d["Close"].astype(float))
    d["ret1"] = logc.diff() * 1e4  # relative bp-like scale used only as a feature

    for lag in [1, 2, 3, 4, 5, 6, 8, 12, 18, 24, 36, 48, 72]:
        d[f"r_lag{lag}"] = d["ret1"].shift(lag - 1)

    for w in [2, 3, 4, 6, 8, 12, 24, 48, 72, 120]:
        d[f"mom{w}"] = d["ret1"].rolling(w).sum()
        d[f"vol{w}"] = d["ret1"].rolling(w).std()
        d[f"absmean{w}"] = d["ret1"].abs().rolling(w).mean()

    for w in [6, 12, 24, 48, 72, 120, 240]:
        ma = d["Close"].rolling(w).mean()
        sd = d["Close"].rolling(w).std()
        d[f"zprice{w}"] = (d["Close"] - ma) / (sd + 1e-12)

    d["range_pips"] = (d["High"] - d["Low"]) * 1e4
    d["body_pips"] = (d["Close"] - d["Open"]) * 1e4
    d["upper_wick_pips"] = (d["High"] - d[["Open", "Close"]].max(axis=1)) * 1e4
    d["lower_wick_pips"] = (d[["Open", "Close"]].min(axis=1) - d["Low"]) * 1e4
    bar_range = (d["High"] - d["Low"]).replace(0.0, np.nan)
    d["close_pos"] = (d["Close"] - d["Low"]) / bar_range
    d["body_frac"] = (d["Close"] - d["Open"]) / bar_range
    d["gap_pips"] = (d["Open"] - d["Close"].shift(1)) * 1e4

    d["log_tickvol"] = np.log1p(d["TickVolume"].astype(float))
    for w in [24, 120]:
        mu = d["log_tickvol"].rolling(w).mean()
        sd = d["log_tickvol"].rolling(w).std()
        d[f"volz{w}"] = (d["log_tickvol"] - mu) / (sd + 1e-12)
    d["spread_pips"] = d["Spread"].astype(float) / 10.0

    hour = d["Time"].dt.hour.astype(float)
    dow = d["Time"].dt.dayofweek.astype(float)
    d["sin_hour"] = np.sin(2 * np.pi * hour / 24.0)
    d["cos_hour"] = np.cos(2 * np.pi * hour / 24.0)
    d["sin_hour2"] = np.sin(4 * np.pi * hour / 24.0)
    d["cos_hour2"] = np.cos(4 * np.pi * hour / 24.0)
    d["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
    d["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)

    eps = 1e-6
    d["r1_over_vol24"] = d["ret1"] / (d["vol24"] + eps)
    d["tanh_r1_vol24"] = np.tanh(d["r1_over_vol24"])
    d["mom3_over_vol24"] = d["mom3"] / (d["vol24"] + eps)
    d["mom12_over_vol24"] = d["mom12"] / (d["vol24"] + eps)
    d["range_over_vol24"] = d["range_pips"] / (d["vol24"] + eps)
    d["r1_x_body"] = d["ret1"] * d["body_pips"]
    d["r1_x_closepos"] = d["ret1"] * (d["close_pos"] - 0.5)
    d["mom3_x_vol24"] = d["mom3"] * d["vol24"]

    # True next-bar targets. y_pips is actual EURUSD pips, not log-return units.
    d["y_pips"] = (d["Close"].shift(-1) - d["Close"]) / PIP
    d["next_gap_h"] = (d["Time"].shift(-1) - d["Time"]).dt.total_seconds() / 3600.0

    feature_cols = [c for c in d.columns if c.startswith(("r_lag", "mom", "vol", "absmean", "zprice"))]
    feature_cols += [
        "range_pips", "body_pips", "upper_wick_pips", "lower_wick_pips",
        "close_pos", "body_frac", "gap_pips", "log_tickvol", "volz24", "volz120",
        "spread_pips", "sin_hour", "cos_hour", "sin_hour2", "cos_hour2", "sin_dow", "cos_dow",
        "r1_over_vol24", "tanh_r1_vol24", "mom3_over_vol24", "mom12_over_vol24",
        "range_over_vol24", "r1_x_body", "r1_x_closepos", "mom3_x_vol24",
    ]

    d = d.replace([np.inf, -np.inf], np.nan)
    clean = d.dropna(subset=feature_cols + ["y_pips", "next_gap_h"]).reset_index(drop=True)
    return clean, feature_cols


def chronological_split_then_strict(data: pd.DataFrame) -> SplitBundle:
    """Split first, then keep only true +1h transitions inside each block.

    This prevents the strict-gap filter from moving the chronological split boundaries.
    """
    n = len(data)
    i1, i2 = int(n * 0.60), int(n * 0.80)
    train_end = data.iloc[i1 - 1]["Time"]
    val_end = data.iloc[i2 - 1]["Time"]

    strict = data[data["next_gap_h"].between(0.99, 1.01)].copy()
    train = strict[strict["Time"] <= train_end].copy()
    val = strict[(strict["Time"] > train_end) & (strict["Time"] <= val_end)].copy()
    test = strict[strict["Time"] > val_end].copy()
    return SplitBundle(train, val, test, train_end, val_end)


def fit_original_equation_ols(raw: pd.DataFrame, train_end: pd.Timestamp, val_end: pd.Timestamp):
    """Exact global least-squares solution of the user's original equation.

    The original formula is nonlinear in price but LINEAR in its coefficients,
    so Nelder-Mead is unnecessary and can only make optimization less reliable.
    """
    b = raw.copy()
    b["prev_close"] = b["Close"].shift(1)
    b["next_close"] = b["Close"].shift(-1)
    b["next_gap_h"] = (b["Time"].shift(-1) - b["Time"]).dt.total_seconds() / 3600.0

    fit = b[(b["Time"] <= train_end) & b["next_gap_h"].between(0.99, 1.01)].dropna()
    test = b[(b["Time"] > val_end) & b["next_gap_h"].between(0.99, 1.01)].dropna()

    def matrix(z: pd.DataFrame) -> np.ndarray:
        x1 = z["Close"].to_numpy(float)
        x2 = z["prev_close"].to_numpy(float)
        return np.column_stack([
            x1, x1**2, x2, x2**2, x1 - x2, np.sin(x1), np.ones_like(x1)
        ])

    X, y = matrix(fit), fit["next_close"].to_numpy(float)
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)

    Xt = matrix(test)
    pred = Xt @ coeffs
    actual = test["next_close"].to_numpy(float)
    current = test["Close"].to_numpy(float)

    original = {
        "rmse_pips": float(np.sqrt(np.mean((pred - actual) ** 2)) / PIP),
        "mae_pips": float(np.mean(np.abs(pred - actual)) / PIP),
        "direction_accuracy": float(np.mean(np.sign(pred - current) == np.sign(actual - current))),
        "predicted_move_std_pips": float(np.std(pred - current) / PIP),
    }
    naive = {
        "rmse_pips": float(np.sqrt(np.mean((current - actual) ** 2)) / PIP),
        "mae_pips": float(np.mean(np.abs(current - actual)) / PIP),
    }
    return coeffs, original, naive


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(center - half), float(center + half)


def monthly_block_bootstrap(selected: pd.DataFrame, n_boot: int = 5000, seed: int = 42):
    tmp = selected.copy()
    tmp["month"] = tmp["Time"].dt.to_period("M").astype(str)
    groups = [g[["gross_pips", "correct"]].copy() for _, g in tmp.groupby("month")]
    if not groups:
        return None
    rng = np.random.default_rng(seed)
    bm = np.empty(n_boot)
    ba = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(groups), len(groups))
        arr = pd.concat([groups[j] for j in idx], ignore_index=True)
        bm[i] = arr["gross_pips"].mean()
        ba[i] = arr["correct"].mean()
    return {
        "months": len(groups),
        "gross_mean_95ci": [float(x) for x in np.quantile(bm, [0.025, 0.975])],
        "accuracy_95ci_block": [float(x) for x in np.quantile(ba, [0.025, 0.975])],
    }


def run(csv_path: str | Path, output_dir: str | Path, confidence_quantile: float = 0.99):
    raw = load_quotes(csv_path)
    data, features = build_features(raw)
    sp = chronological_split_then_strict(data)

    # Baseline: original formula, solved exactly.
    orig_coeffs, orig_metrics, naive_metrics = fit_original_equation_ols(raw, sp.train_end, sp.val_end)

    Xtr, Xv, Xt = sp.train[features], sp.val[features], sp.test[features]
    ytr = sp.train["y_pips"].to_numpy(float)
    yv = sp.val["y_pips"].to_numpy(float)
    yt = sp.test["y_pips"].to_numpy(float)
    ytr_up = (ytr > 0).astype(int)
    yv_up = (yv > 0).astype(int)
    yt_up = (yt > 0).astype(int)

    magnitude_model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=100000.0)),
    ])
    magnitude_model.fit(Xtr, ytr)

    direction_imputer = SimpleImputer(strategy="median")
    Xtr_i = direction_imputer.fit_transform(Xtr)
    Xv_i = direction_imputer.transform(Xv)
    Xt_i = direction_imputer.transform(Xt)

    direction_model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=150,
        max_leaf_nodes=31,
        min_samples_leaf=100,
        l2_regularization=3.0,
        random_state=42,
    )
    direction_model.fit(Xtr_i, ytr_up)

    # Calibration/gating uses validation ONLY.
    pv = direction_model.predict_proba(Xv_i)[:, 1]
    validation_conf = np.abs(pv - 0.5)
    confidence_threshold = float(np.quantile(validation_conf, confidence_quantile))

    # Locked OOS evaluation.
    pt = direction_model.predict_proba(Xt_i)[:, 1]
    signal = np.where(pt >= 0.5, 1.0, -1.0)
    confidence = np.abs(pt - 0.5)
    selected_mask = confidence >= confidence_threshold
    gross_pips = signal * yt
    correct = signal == np.sign(yt)

    selected = sp.test.loc[selected_mask, ["Time", "Close", "Spread"]].copy()
    selected["prob_up"] = pt[selected_mask]
    selected["confidence"] = confidence[selected_mask]
    selected["signal"] = signal[selected_mask]
    selected["actual_move_pips"] = yt[selected_mask]
    selected["gross_pips"] = gross_pips[selected_mask]
    selected["correct"] = correct[selected_mask]

    # Regression metrics on all strict OOS bars.
    mag_pred = magnitude_model.predict(Xt)
    ridge_metrics = {
        "rmse_pips": float(np.sqrt(np.mean((mag_pred - yt) ** 2))),
        "mae_pips": float(np.mean(np.abs(mag_pred - yt))),
        "correlation": float(np.corrcoef(mag_pred, yt)[0, 1]),
        "direction_accuracy": float(np.mean(np.sign(mag_pred) == np.sign(yt))),
        "predicted_move_std_pips": float(np.std(mag_pred)),
    }

    n_sel = int(selected_mask.sum())
    k_correct = int(correct[selected_mask].sum())
    acc_ci = wilson_interval(k_correct, n_sel)

    classifier_metrics = {
        "auc_all_oos": float(roc_auc_score(yt_up, pt)),
        "direction_accuracy_all_oos": float(np.mean(signal == np.sign(yt))),
        "confidence_quantile_validation": confidence_quantile,
        "confidence_threshold": confidence_threshold,
        "selected_signals": n_sel,
        "signal_rate": float(selected_mask.mean()),
        "high_conf_direction_accuracy": float(k_correct / n_sel),
        "high_conf_accuracy_wilson_95ci": list(acc_ci),
        "high_conf_gross_mean_pips": float(selected["gross_pips"].mean()),
        "high_conf_gross_median_pips": float(selected["gross_pips"].median()),
        "high_conf_gross_sum_pips": float(selected["gross_pips"].sum()),
        "high_conf_mean_abs_move_pips": float(selected["actual_move_pips"].abs().mean()),
    }

    costs = [0.0, 0.2, 0.5, 0.8, 1.0, 1.2]
    cost_sensitivity = []
    for cost in costs:
        net = selected["gross_pips"] - cost
        cost_sensitivity.append({
            "all_in_cost_pips": cost,
            "net_mean_pips_per_signal": float(net.mean()),
            "net_total_pips": float(net.sum()),
        })

    # Concentration by hour is essential because time-of-day is a real feature here.
    hour_stats = (
        selected.assign(hour=selected["Time"].dt.hour)
        .groupby("hour")
        .agg(
            n=("gross_pips", "size"),
            accuracy=("correct", "mean"),
            gross_mean_pips=("gross_pips", "mean"),
            mean_abs_move_pips=("actual_move_pips", lambda x: float(np.mean(np.abs(x)))),
        )
        .reset_index()
        .sort_values("n", ascending=False)
    )

    boot = monthly_block_bootstrap(selected)

    report = {
        "data": {
            "rows": int(len(raw)),
            "start": str(raw["Time"].min()),
            "end": str(raw["Time"].max()),
            "feature_rows": int(len(data)),
            "features": len(features),
            "strict_train_rows": int(len(sp.train)),
            "strict_validation_rows": int(len(sp.val)),
            "strict_oos_rows": int(len(sp.test)),
            "train_end": str(sp.train_end),
            "validation_end": str(sp.val_end),
        },
        "naive_close_equals_next_close": naive_metrics,
        "original_equation_exact_ols": {
            "coefficients": [float(x) for x in orig_coeffs],
            **orig_metrics,
        },
        "improved_magnitude_ridge": ridge_metrics,
        "improved_direction_classifier": classifier_metrics,
        "cost_sensitivity": cost_sensitivity,
        "monthly_block_bootstrap": boot,
        "top_hours": hour_stats.head(10).to_dict(orient="records"),
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "price_equation_v3_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    selected.to_csv(out / "price_equation_v3_oos_signals.csv", index=False)
    hour_stats.to_csv(out / "price_equation_v3_hour_stats.csv", index=False)

    model_bundle = {
        "version": "PriceEquation EURUSD H1 V3",
        "feature_cols": features,
        "magnitude_model": magnitude_model,
        "direction_imputer": direction_imputer,
        "direction_model": direction_model,
        "confidence_threshold": confidence_threshold,
        "confidence_quantile": confidence_quantile,
        "pip": PIP,
        "train_end": sp.train_end,
        "validation_end": sp.val_end,
    }
    joblib.dump(model_bundle, out / "price_equation_eurusd_h1_v3.joblib", compress=3)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", help="Path to EURUSD_H1.csv")
    p.add_argument("--output-dir", default="price_equation_v3_output")
    p.add_argument("--confidence-quantile", type=float, default=0.99)
    args = p.parse_args()
    run(args.csv, args.output_dir, args.confidence_quantile)


if __name__ == "__main__":
    main()

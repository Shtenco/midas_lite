# MIDAS EURUSD H1 V5 — Fixed-q90 + Hard SL 4.5 pip

Frozen research/deployment snapshot of the EURUSD H1 specialist discovered and validated inside MIDAS.

## Frozen logic

- Market: EURUSD, H1.
- Specialist transition: strict `23:00 -> 00:00` one-hour transition only.
- Model family: `HistGradientBoostingClassifier` over the leakage-free V3 feature set.
- Confidence gate: fixed validation quantile `q = 0.90`; no adaptive quantile optimization in production logic.
- Direction: `BUY` when `P(up) >= 0.5`, otherwise `SELL`.
- Risk rule: hard stop-loss `SL = 4.5 pip`.
- Exit: if SL is not hit inside the next H1 bar, close at the next H1 close.
- No averaging, martingale, trailing stop, or adaptive SL in this frozen version.

## Walk-forward evidence

The fixed-q90 regime was evaluated over 100 consecutive two-month pseudo-OOS windows from December 2009 through July 2026. The signal set contains 415 fixed-q90 OOS trades. Directional accuracy before execution filtering is about 68.67%.

Applying a 4.5-pip hard SL to the same OOS signal sequence using the actual next-bar High/Low gives:

- 415 trades.
- Gross mean: +1.6578 pip/trade.
- Gross total: +688.0 pip.
- Win rate after SL: 63.13%.
- Profit factor: 2.47.
- Maximum single-trade loss: -4.5 pip before slippage/costs.
- Maximum gross drawdown: about -30.9 pip.
- Mean after the recorded historical spread field: about +1.020 pip/trade.

The SL was selected on the first 70 rolling-OOS windows and then checked on the last 30 windows. In those last 30 windows the result was +1.410 pip/trade gross with max drawdown about -11.2 pip.

These are historical research results, not a guarantee of future profitability. Live execution must account for bid/ask spread, commission, slippage, rollover/session conventions, broker-server timezone and DST effects.

## Contents

- `core/price_equation_eurusd_h1_v3.py` — leakage-free feature builder and V3 research core.
- `research/price_equation_eurusd_h1_v4_rolling_100.py` — 100 x 2-month rolling pseudo-OOS protocol.
- `research/price_equation_eurusd_h1_v4_rolling_batch.py` — batch runner used for the rolling study.
- `research/consolidate_v4_rolling.py` — consolidation/reporting utilities.
- `model/price_equation_eurusd_h1_v4_deploy_pre_june2026.joblib` — frozen deployment snapshot trained through 2026-05-31. The model artifact itself is V4; V5 adds the hard 4.5-pip SL execution rule.
- `reports/v4_rolling_100_report.json` — full rolling report.
- `reports/v4_sealed_2m_report.json` — sealed June-July 2026 report from before the SL layer.
- `reports/sl_grid_metrics.csv` — SL grid analysis.
- `reports/fixed_q90_trades_with_excursions.csv` — fixed-q90 OOS trades with next-bar MAE/MFE used to evaluate hard stops.
- `V5_CONFIG.json` — frozen V5 parameters.
- `SHA256SUMS.txt` — package checksums.

## Data

The full raw `EURUSD_H1.csv` is intentionally not duplicated into every Git repository. The canonical data and full binary bundles are stored in Google Drive under `EURUSD_H1_PRICE_EQUATION_SYSTEM_V4`.

Canonical Drive folder:
https://drive.google.com/drive/folders/14F65_6drsAtOoRWVAHxgRNRDUMgT_5_4

Dataset used in the study: 165,467 H1 bars, 2000-01-03 through 2026-07-31. Only targets with an exact +1 hour next timestamp are eligible, preventing weekend/session gaps from being treated as ordinary one-hour targets.

## Version policy

This directory is a synchronized duplicate. Keep the same path and package version across MIDAS repositories. Do not silently retune `q`, the target hour, or the SL and still call the result V5. Any changed research configuration should become a new version and be re-run through the rolling OOS protocol.

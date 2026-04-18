# Round 2 — ACO + IPR (carry-over, critical FV fix)

Same products as Round 1. Round 2 introduced a fresh set of 3 days of market data and carried over the same product mechanics.

## Critical Bug Fixed: ACO Fair Value

**The bug (Round 1 v2)**: ACO FV was hardcoded at `10 000`.

**What the feedback logs revealed**: In Round 2 market data, ACO `wall_mid` averaged **10 004** — 85% of timesteps had `wall_mid > 10 001`. With FV=10 000, we were selling bids at 10 001–10 004 thinking they were overpriced, when they were actually fair. This drove us to max short (−76) and lost significant PnL.

**The fix (v3)**: Use `wall_mid` as FV for ACO, exactly like IPR. `wall_mid` is always the correct anchor regardless of the absolute level.

## Strategy (v3 — final)

### IPR — Unchanged from Round 1
- FV = `wall_mid`
- Lean long +70, take width 3.5 pts (tightened from 1.5)
- Round 1 PnL: **+72 164 seashells**, position: **+78**

### ACO — FV Fix + Spike Mode
- FV = `wall_mid` (not hardcoded 10 000)
- Spike threshold: `|mid_price − wall_mid| ≥ 5` → spike mode (skip making in spike direction)
- Inventory soft cap removed (no longer needed — the FV fix resolved the drift)

## Feedback Analysis

The `feedback/` folder contains logs from **4 test submissions** on Round 2 data before the final submission:

| Log | Submission ID | Notes |
|-----|--------------|-------|
| `282095.log` | 282095 | Initial v2 with hardcoded FV — bug visible |
| `282314.log` | 282314 | Intermediate fix attempt |
| `282476.log` | 282476 | Further tuning |
| `282601.log` | 282601 | Pre-final version |

`feedback/analyze_feedback.py` — script to parse these logs and extract per-product PnL, position, and wall_mid statistics.

## EDA Findings (6 plots)

| Plot | Finding |
|------|---------|
| `plot1_IPR_trend.png` | IPR linear trend confirmed on Round 2 data — R²=1.000 |
| `plot2_ACO_spikes.png` | ~1 686 spikes ≥ 5 per day — pattern persists |
| `plot3_ACO_postspike.png` | Post-spike reversion: −4.00 / +4.09 at t+1 |
| `plot4_spreads.png` | IPR spread ≈ 13, ACO spread ≈ 16 — stable |
| `plot5_wallmid_spike.png` | **KEY**: wall_mid ≠ 10 000 during spikes — validates FV fix |
| `plot6_ACO_inventory.png` | Inventory drift under old FV — confirms the bug diagnosis |

## Files

| File | Description |
|------|-------------|
| `trader.py` | Final submitted algorithm (v3) |
| `eda/eda_round2.py` | EDA script — generates all 6 plots |
| `eda/plots/` | PNG plots from EDA |
| `data/` | Market data CSVs — 3 days (day -1, 0, 1) |
| `feedback/analyze_feedback.py` | Script to parse feedback submission logs |
| `feedback/logs/` | 4 test submission logs from the platform |
| `analysis/analyze_log.py` | Final log analysis script |

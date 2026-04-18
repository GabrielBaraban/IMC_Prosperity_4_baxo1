# Round 1 — ASH_COATED_OSMIUM + INTARIAN_PEPPER_ROOT

## Products

| Product | Ticker | Position Limit | Fair Value | Nature |
|---------|--------|----------------|------------|--------|
| Ash Coated Osmium | ACO | ±80 | ~10 000 (fixed) | Mean-reverting with spikes |
| Intarian Pepper Root | IPR | ±80 | Linear trend +0.001/ts | Trending |

## Strategy

Architecture inspired by **Frankfurt Hedgehogs** (top 3 Prosperity 3 worldwide).

### IPR — Linear Trend Market Making
- `FV = wall_mid` (tracks `10000 + 1000*(day+2) + 0.001*t` exactly, R²=1.000)
- **Lean long +70**: carry a +70 position to capture the +0.001/ts drift → ~70 seashells/day
- Take any ask ≤ `wall_mid − 1.5`, sell any bid ≥ `wall_mid + 1.5`
- Make at `best_bid+1` / `best_ask-1` from `wall_mid`
- Round 1 PnL: **+72 164 seashells**

### ACO — Mean Reversion + Spike Filter
- `FV = 10 000` hardcoded (later discovered to be a bug — see Round 2)
- **~1 700 spikes ≥ 5 pts per day** — mean reversion of −4.00 at t+1
- Spike mode: skip making on the spike direction when `|mid_price − wall_mid| ≥ 5`
- Inventory soft cap at ±35 to prevent unintended drift

## EDA Findings

### Plot 1 — IPR Trend
`wall_mid` follows a perfect linear trend (R²=1.000). Deviations have std ≈ 2.2.
The trend leaks +0.001/ts, making it profitable to stay long.

### Plot 2 — ACO Spike Distribution
~1 739 spikes ≥ 5 per day. Distribution is bimodal: flat + fat spike tails.

### Plot 3 — ACO Post-Spike Mean Reversion ← KEY FINDING
After a spike ≥+5: next 20 timesteps average **−3.91** from peak.
After a spike ≤−5: next 20 timesteps average **+4.04** from peak.
→ Strong signal: skip making into the spike, wait for reversion.

### Plot 4 — Spreads
IPR spread ≈ 13 pts. ACO spread ≈ 16 pts. Both stable, wide enough for market making.

## Files

| File | Description |
|------|-------------|
| `trader.py` | Final submitted algorithm |
| `datamodel.py` | Platform datamodel |
| `eda/analyse.py` | EDA script — generates all 4 plots |
| `eda/plots/` | PNG plots from EDA |
| `data/` | Market data CSVs — 3 days (day -2, -1, 0) |
| `analysis/ANALYSIS_ROUND1.md` | Detailed post-round analysis + what we missed |
| `analysis/analyze_log.py` | Script to parse and analyze submission logs |
| `submission/272806.log` | Official submission log from the platform (Round 1) |
| `references/frankfurt_hedgehogs_prosperity3_playbook.md` | Reference playbook we based our strategy on |

## What We Missed / Could Improve

From `analysis/ANALYSIS_ROUND1.md`:
- ACO `wall_mid` was not exactly 10 000 — small drift existed that hardcoded FV missed
- IPR spread widens to 20 at times → dynamic spread adjustment could help
- Post-spike logic was passive (waiting for mispriced orders) not active (going directional)

# IMC Prosperity 4 — Team baxo1

> IMC Prosperity is an algorithmic trading competition where participants write Python bots to trade synthetic financial instruments. Each round introduces new products and market dynamics.

## Team

| Name             | School                 |
|------------------|------------------------|
| Gabriel Baraban  | École Polytechnique    |
| Hedi Fourati     | École Polytechnique    |
| Louis Moncla     | École Polytechnique    |

## Competition Structure

| Round | Products | Status |
|-------|----------|--------|
| [Round 0](round0/) | Tutorial — RAINFOREST_RESIN, KELP, SQUID_INK | ✅ Completed |
| [Round 1](round1/) | ASH_COATED_OSMIUM (ACO) + INTARIAN_PEPPER_ROOT (IPR) | ✅ Completed |
| [Round 2](round2/) | ACO + IPR (carry-over + critical FV fix) | ✅ Completed |

## Core Strategy (Frankfurt Hedgehogs architecture)

Every product follows a 3-step loop per timestep:

1. **Fair Value Taker** — cross any mispriced order vs our fair value estimate
2. **Position Reducer** — close position when price returns to fair value
3. **Penny Jump Maker** — passive quotes at `best_bid+1` / `best_ask-1`

**Key insight**: `wall_mid = (worst_bid + worst_ask) / 2` is the true fair value anchor.
Persistent market makers sit at the walls — those are the "true" prices.
Near-mid orders from other bots are noise and create the mispricings we exploit.

## Repo Structure

```
round0/          Tutorial round (Round 0)
round1/          Round 1 main competition
  trader.py        Final submitted algorithm
  eda/             Exploratory Data Analysis scripts + plots
  data/            Market data CSVs (prices + trades, 3 days)
  analysis/        Post-round log analysis + findings
  submission/      Official submission log from the platform
  references/      External references (Frankfurt Hedgehogs P3 playbook)
round2/          Round 2 main competition
  trader.py        Final submitted algorithm (v3, post-feedback fix)
  eda/             EDA scripts + plots (6 plots)
  data/            Market data CSVs (prices + trades, 3 days)
  feedback/        Feedback logs from the platform + analysis script
  analysis/        Log analysis script
```

## Key EDA Findings

### IPR (INTARIAN_PEPPER_ROOT)
- **FV = linear trend**: `10000 + 1000*(day+2) + 0.001*t` — R²=1.000
- `wall_mid` tracks the trend perfectly → no formula needed, just use `wall_mid`
- Spread ≈ 13 pts, deviation std ≈ 2.2 pts → tight, predictable
- **Lean long +70** to capture the +0.001/ts drift = ~70 seashells/day free PnL

### ACO (ASH_COATED_OSMIUM)
- **FV fixed** at ~10 000 (with small drift discovered in Round 2 feedback)
- **~1 700 spikes ≥ 5 pts per day** — mean reversion: −4.00 at t+1 after positive spike
- Post-spike pattern persists for 20+ timesteps → skip making into the spike direction
- **Critical bug fixed in Round 2**: hardcoded FV=10 000 caused systematic wrong-side positions when `wall_mid` drifted to 10 004

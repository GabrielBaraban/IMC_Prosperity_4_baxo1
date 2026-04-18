# Round 0 — Tutorial Round

> This is the tutorial/practice round used to learn the platform mechanics. Products and strategies here are intentionally simple.

## Products

- **RAINFOREST_RESIN** — stable FV, basic market making
- **KELP** — trending product
- **SQUID_INK** — mean-reverting product

## Files

| File | Description |
|------|-------------|
| `trader.py` | Submitted algorithm (v1) |
| `datamodel.py` | Platform datamodel (provided by IMC) |
| `data/` | Market data CSVs — 2 training days |
| `results/` | Official submission result (ID: 60068) |

## Notes

This round established our baseline understanding of:
- The `wall_mid` concept as a fair value anchor
- The 3-step trading loop (take → reduce → make)
- Position limit management

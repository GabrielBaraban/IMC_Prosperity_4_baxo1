"""
Analyzer for Round 2 feedback log (282095.log).
Compares vs Round 1 baseline (91 711 total, IPR 72 164, ACO 19 547).

Run: python3 analyze_feedback.py [path]
Default: ./282095.log
"""

import sys, json, re
from collections import defaultdict

LOG_PATH = sys.argv[1] if len(sys.argv) > 1 else "282095.log"

# ── Round 1 baseline ──────────────────────────────────────
R1 = {"INTARIAN_PEPPER_ROOT": 72_164.25,
      "ASH_COATED_OSMIUM":    19_546.91,
      "total":                91_711.16,
      "IPR_pos": 78, "ACO_pos": 39}

SEP = "=" * 62

def to_float(s):
    try: return float(s)
    except: return None

# ── Load ──────────────────────────────────────────────────
print(f"Loading {LOG_PATH}...")
with open(LOG_PATH) as f:
    data = json.load(f)

print(f"Keys: {list(data.keys())}")

# Activities
rows = []
header = None
for line in data.get("activitiesLog","").split("\n"):
    line = line.strip()
    if not line: continue
    if header is None: header = line.split(";"); continue
    parts = line.split(";")
    if len(parts) >= 3:
        rows.append({header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))})

# Sandbox / lambda logs
sandbox, lambdalog = [], []
for e in data.get("logs", []):
    sandbox  += e.get("sandboxLog","").split("\n")
    lambdalog += e.get("lambdaLog","").split("\n")
all_logs = [l for l in sandbox + lambdalog if l.strip()]

# Trade history
trades = data.get("tradeHistory", [])

products = sorted(set(r.get("product","") for r in rows if r.get("product","")))
days     = sorted(set(r.get("day","")     for r in rows if r.get("day","")))
print(f"Rows: {len(rows)} | Products: {products} | Days: {days}")
print(f"Log lines: {len(all_logs)} | Trades: {len(trades)}")

# Group by product
by_prod = defaultdict(list)
for r in rows:
    p = r.get("product","")
    if p: by_prod[p].append(r)
for p in by_prod:
    by_prod[p].sort(key=lambda r: (int(r.get("day",0)), int(r.get("timestamp",0))))

# ── Q5 — PnL split ───────────────────────────────────────
print(f"\n{SEP}")
print("PnL SPLIT")
print(SEP)

totals = {}
for prod, prows in by_prod.items():
    day_last = {}
    for r in prows:
        pnl = to_float(r.get("profit_and_loss"))
        if pnl is not None: day_last[r.get("day")] = pnl
    if not day_last: continue
    final = max(day_last.values())
    totals[prod] = final
    r1 = R1.get(prod, 0)
    delta = final - r1
    print(f"\n  {prod}:")
    for d,p in sorted(day_last.items()):
        print(f"    Day {d}: {p:>12,.2f}")
    print(f"    FINAL : {final:>12,.2f}  |  R1: {r1:,.2f}  |  Δ: {delta:+,.2f}  {'✅' if delta>0 else '❌'}")

grand = sum(totals.values())
r1_total = R1["total"]
print(f"\n  GRAND TOTAL : {grand:>12,.2f}  |  R1: {r1_total:,.2f}  |  Δ: {grand-r1_total:+,.2f}  {'✅' if grand>r1_total else '❌'}")

# ── Q4 — Positions ────────────────────────────────────────
print(f"\n{SEP}")
print("FINAL POSITIONS  (from tradeHistory)")
print(SEP)

pos_by_sym = defaultdict(int)
cnt_by_sym = defaultdict(int)
for t in trades:
    sym = t.get("symbol","")
    qty = int(t.get("quantity", 0))
    if t.get("buyer") == "SUBMISSION":
        pos_by_sym[sym] += qty; cnt_by_sym[sym] += 1
    elif t.get("seller") == "SUBMISSION":
        pos_by_sym[sym] -= qty; cnt_by_sym[sym] += 1

if pos_by_sym:
    for sym, pos in sorted(pos_by_sym.items()):
        r1_pos = R1.get("IPR_pos" if "PEPPER" in sym else "ACO_pos", 0)
        print(f"  {sym}: pos={pos:+d} ({cnt_by_sym[sym]} trades)  |  R1 pos: {r1_pos:+d}  |  Δ: {pos-r1_pos:+d}")
else:
    print("  No SUBMISSION trades found.")
    if trades:
        buyers  = list(set(str(t.get("buyer",""))  for t in trades[:30]))
        sellers = list(set(str(t.get("seller","")) for t in trades[:30]))
        print(f"  Buyers seen:  {buyers[:8]}")
        print(f"  Sellers seen: {sellers[:8]}")

# ── Q3 — ACO spike analysis ───────────────────────────────
print(f"\n{SEP}")
print("ACO SPIKE ANALYSIS  (wall_mid stability + post-spike reversion)")
print(SEP)

ACO_KEY = next((k for k in by_prod if "OSMIUM" in k or "ACO" in k), None)
if ACO_KEY:
    prows = by_prod[ACO_KEY]
    mid_vals, wm_vals = [], []
    for r in prows:
        mid = to_float(r.get("mid_price"))
        if mid is None or mid < 100:
            mid_vals.append(None); wm_vals.append(None); continue
        bp3 = to_float(r.get("bid_price_3")) or to_float(r.get("bid_price_2")) or to_float(r.get("bid_price_1"))
        ap3 = to_float(r.get("ask_price_3")) or to_float(r.get("ask_price_2")) or to_float(r.get("ask_price_1"))
        if bp3 and abs(bp3-mid)>500: bp3=None
        if ap3 and abs(ap3-mid)>500: ap3=None
        wm = (bp3+ap3)/2 if (bp3 and ap3) else mid
        mid_vals.append(mid); wm_vals.append(wm)

    FV = 10_000
    spikes, wall_moved, wm_deltas = 0, 0, []
    pos_next, neg_next = [], []
    for i in range(1, len(mid_vals)):
        if mid_vals[i] is None or mid_vals[i-1] is None: continue
        d = mid_vals[i] - mid_vals[i-1]
        if abs(d) > 200: continue
        if abs(d) >= 5:
            spikes += 1
            if wm_vals[i] is not None and wm_vals[i-1] is not None:
                wd = abs(wm_vals[i] - wm_vals[i-1])
                wm_deltas.append(wd)
                if wd >= 1: wall_moved += 1
            if i+1 < len(mid_vals) and mid_vals[i+1] is not None:
                nxt = mid_vals[i+1] - mid_vals[i]
                (pos_next if d>0 else neg_next).append(nxt)

    print(f"  Spikes ≥|5|: {spikes}")
    if wm_deltas:
        import statistics
        pct = 100*wall_moved/len(wm_deltas)
        print(f"  Wall moved (≥1) during spike: {wall_moved}/{len(wm_deltas)} ({pct:.1f}%)")
        print(f"  Avg |Δwall|: {statistics.mean(wm_deltas):.3f}")
    if pos_next:
        print(f"  Post pos-spike t+1: mean={sum(pos_next)/len(pos_next):+.2f}  (n={len(pos_next)})")
    if neg_next:
        print(f"  Post neg-spike t+1: mean={sum(neg_next)/len(neg_next):+.2f}  (n={len(neg_next)})")

    valid_mid = [m for m in mid_vals if m]
    valid_wm  = [w for w in wm_vals  if w]
    if valid_mid:
        print(f"  ACO mid  — mean={sum(valid_mid)/len(valid_mid):.2f}  min={min(valid_mid):.0f}  max={max(valid_mid):.0f}")
    if valid_wm:
        print(f"  ACO wall — mean={sum(valid_wm)/len(valid_wm):.2f}  min={min(valid_wm):.0f}  max={max(valid_wm):.0f}")

# ── Q2 — IPR trend check ──────────────────────────────────
print(f"\n{SEP}")
print("IPR TREND CHECK")
print(SEP)

IPR_KEY = next((k for k in by_prod if "PEPPER" in k or "IPR" in k), None)
if IPR_KEY:
    prows = by_prod[IPR_KEY]
    day_pnl = defaultdict(list)
    for r in prows:
        pnl = to_float(r.get("profit_and_loss"))
        if pnl is not None: day_pnl[r.get("day")].append(pnl)
    for d in sorted(day_pnl):
        vals = day_pnl[d]
        deltas = [vals[i]-vals[i-1] for i in range(1,len(vals)) if vals[i] is not None and vals[i-1] is not None]
        avg_d = sum(deltas)/len(deltas) if deltas else 0
        print(f"  Day {d}: PnL {vals[0]:.1f} → {vals[-1]:.1f}  |  avg Δ/step={avg_d:.4f}  "
              f"(implied lean={avg_d/0.001:.0f} units via trend)")

# ── Q1 — Lambda/sandbox logs ─────────────────────────────
print(f"\n{SEP}")
print("SANDBOX / LAMBDA LOGS")
print(SEP)

if all_logs:
    print(f"  {len(all_logs)} log lines found.")
    print("  Sample (first 25 non-empty):")
    for l in all_logs[:25]:
        print(f"    {l[:140]}")
else:
    print("  No logs (no print() in trader). Add prints for future diagnosis.")

# ── Diagnostic summary ────────────────────────────────────
print(f"\n{SEP}")
print("DIAGNOSTIC SUMMARY")
print(SEP)

for prod in [IPR_KEY, ACO_KEY]:
    if not prod: continue
    final = totals.get(prod, 0)
    r1    = R1.get(prod, 0)
    delta = final - r1
    sign  = "✅ improved" if delta > 0 else "❌ regressed"
    print(f"  {prod[:25]}: {final:>10,.0f}  (R1={r1:,.0f}  Δ={delta:+,.0f})  {sign}")

print(f"\n  TOTAL: {grand:>10,.0f}  (R1={r1_total:,.0f}  Δ={grand-r1_total:+,.0f})")
print()
if grand < r1_total:
    print("  ⚠️  REGRESSION DETECTED. Investigate:")
    print("     - Did ACO spike mode hurt making PnL?")
    print("     - Did inventory cap cut profitable makes?")
    print("     - Check final positions above for drift.")
else:
    print("  Strategy improved vs Round 1.")

print(f"\n{SEP}\nDONE\n{SEP}")

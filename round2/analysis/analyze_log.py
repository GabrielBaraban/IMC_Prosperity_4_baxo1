"""
Log analyzer for Prosperity Round 1 submission log (272806.log).
Answers 5 questions from ANALYSIS_ROUND1.md.

Run: python analyze_log.py [path_to_log]
Default: ./272806.log
"""

import sys
import json
import re
from collections import defaultdict

LOG_PATH = sys.argv[1] if len(sys.argv) > 1 else "272806.log"

# ─── Load JSON ────────────────────────────────────────────────────────────────

print(f"Loading {LOG_PATH}...")
with open(LOG_PATH, "r") as f:
    data = json.load(f)

print(f"Top-level keys: {list(data.keys())}")

# ─── Parse activitiesLog ──────────────────────────────────────────────────────

activities_csv = data.get("activitiesLog", "")
rows = []
header = None
for line in activities_csv.split("\n"):
    line = line.strip()
    if not line:
        continue
    if header is None:
        header = line.split(";")
        continue
    parts = line.split(";")
    if len(parts) >= 3:
        row = {}
        for i, col in enumerate(header):
            row[col] = parts[i] if i < len(parts) else ""
        rows.append(row)

print(f"Activities rows: {len(rows)}")
if rows:
    products = sorted(set(r.get("product", "") for r in rows))
    days = sorted(set(r.get("day", "") for r in rows))
    print(f"Products: {products}")
    print(f"Days: {days}")

# ─── Parse sandbox/lambda logs ────────────────────────────────────────────────

logs_list = data.get("logs", [])
sandbox_lines = []
lambda_lines = []
for entry in logs_list:
    sl = entry.get("sandboxLog", "")
    ll = entry.get("lambdaLog", "")
    if sl:
        sandbox_lines.extend(sl.split("\n"))
    if ll:
        lambda_lines.extend(ll.split("\n"))

print(f"Sandbox log lines: {len(sandbox_lines)}")
print(f"Lambda log lines: {len(lambda_lines)}")

# ─── Parse tradeHistory ───────────────────────────────────────────────────────

trade_history = data.get("tradeHistory", [])
print(f"Trade history entries: {len(trade_history)}")

# ─── Helper ───────────────────────────────────────────────────────────────────

def to_float(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

def activities_by_product():
    by_product = defaultdict(list)
    for row in rows:
        product = row.get("product", "")
        if product:
            by_product[product].append(row)
    result = {}
    for product, prows in by_product.items():
        prows.sort(key=lambda r: (int(r.get("day", 0)), int(r.get("timestamp", 0))))
        result[product] = prows
    return result

act = activities_by_product()

# ─── Q5 — PnL split ───────────────────────────────────────────────────────────

print("\n" + "="*60)
print("Q5 — PnL SPLIT per product")
print("="*60)
total_by_product = {}
for product, prows in act.items():
    day_last_pnl = {}
    for r in prows:
        d = r.get("day")
        pnl = to_float(r.get("profit_and_loss"))
        if pnl is not None:
            day_last_pnl[d] = pnl
    if not day_last_pnl:
        continue
    print(f"\n  {product}:")
    for d, p in sorted(day_last_pnl.items()):
        print(f"    Day {d}: final PnL = {p:,.2f}")
    vals = sorted(day_last_pnl.items())
    daily = [vals[i][1] - vals[i-1][1] for i in range(1, len(vals))]
    if daily:
        print(f"    Daily gains: {[round(g, 1) for g in daily]}")
    total_by_product[product] = vals[-1][1]

grand_total = sum(total_by_product.values())
print(f"\n  GRAND TOTAL: {grand_total:,.2f}")
for p, v in sorted(total_by_product.items(), key=lambda x: -abs(x[1])):
    pct = 100 * v / grand_total if grand_total else 0
    print(f"    {p}: {v:,.2f} ({pct:+.1f}%)")

# ─── Q1 — Take vs Make (from lambda/sandbox logs) ─────────────────────────────

print("\n" + "="*60)
print("Q1 — TAKE vs MAKE analysis")
print("="*60)

all_log_lines = sandbox_lines + lambda_lines
if all_log_lines:
    print(f"  Total log lines: {len(all_log_lines)}")
    # Show non-empty lines sample
    non_empty = [l for l in all_log_lines if l.strip()]
    print(f"  Non-empty log lines: {len(non_empty)}")
    if non_empty:
        print("  Sample (first 20):")
        for l in non_empty[:20]:
            print(f"    {l[:140]}")

    # Try to detect take/make patterns
    take_re = re.compile(r"take|taker|aggressive", re.IGNORECASE)
    make_re = re.compile(r"make|maker|passive|penny", re.IGNORECASE)
    aco_re = re.compile(r"ACO|ASH_COATED", re.IGNORECASE)
    ipr_re = re.compile(r"IPR|INTARIAN|PEPPER", re.IGNORECASE)

    aco_takes = [l for l in non_empty if aco_re.search(l) and take_re.search(l)]
    aco_makes = [l for l in non_empty if aco_re.search(l) and make_re.search(l)]
    print(f"\n  ACO take-related lines: {len(aco_takes)}, make-related: {len(aco_makes)}")
    if aco_takes:
        for l in aco_takes[:5]:
            print(f"    {l[:140]}")
else:
    print("  No lambda/sandbox logs in this submission.")
    print("  NOTE: Add print() statements to trader.py to capture take/make info in future runs.")

# ─── Q2 — IPR LEAN ────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("Q2 — IPR LEAN: did position reach 70?")
print("="*60)

IPR_KEY = next((k for k in act if "PEPPER" in k or "IPR" in k), None)
if IPR_KEY:
    prows = act[IPR_KEY]
    print(f"  IPR product: {IPR_KEY}, rows: {len(prows)}")

    # PnL progression per day
    day_pnl = defaultdict(list)
    for r in prows:
        d = r.get("day")
        pnl = to_float(r.get("profit_and_loss"))
        if pnl is not None:
            day_pnl[d].append(pnl)

    print("\n  PnL progression per day:")
    for d in sorted(day_pnl):
        vals = day_pnl[d]
        n = len(vals)
        # PnL increments
        deltas = [vals[i] - vals[i-1] for i in range(1, n) if vals[i] is not None and vals[i-1] is not None]
        avg_delta = sum(deltas)/len(deltas) if deltas else 0
        print(f"    Day {d}: {n} steps, PnL {vals[0]:.1f}→{vals[-1]:.1f}, avg delta/step={avg_delta:.4f}")
        # Expected for lean=70: trend component = 70 * 1/1000 = 0.07/step
        # But also making PnL. The trend income alone would give 70*0.001=0.07/step
        expected_trend = 70 * 0.001
        if avg_delta > 0:
            implied_lean = avg_delta / 0.001
            print(f"      Expected delta for lean=70: {expected_trend:.4f} | Implied lean from delta: {implied_lean:.0f}")
else:
    print("  IPR product not found.")

# ─── Q3 — ACO spikes: does wall_mid move? ────────────────────────────────────

print("\n" + "="*60)
print("Q3 — ACO SPIKES: wall_mid stability during spikes")
print("="*60)

ACO_KEY = next((k for k in act if "ACO" in k or "OSMIUM" in k), None)
if ACO_KEY:
    prows = act[ACO_KEY]
    print(f"  ACO product: {ACO_KEY}, rows: {len(prows)}")

    mid_vals = []
    wm_vals = []
    for r in prows:
        mid = to_float(r.get("mid_price"))
        # Filter invalid rows (empty book, mid=0)
        if mid is None or mid < 100:
            mid_vals.append(None)
            wm_vals.append(None)
            continue
        # bid_price_1 = best bid (highest), bid_price_3 = worst bid (lowest = wall)
        # ask_price_1 = best ask (lowest), ask_price_3 = worst ask (highest = wall)
        bp3 = to_float(r.get("bid_price_3")) or to_float(r.get("bid_price_2")) or to_float(r.get("bid_price_1"))
        ap3 = to_float(r.get("ask_price_3")) or to_float(r.get("ask_price_2")) or to_float(r.get("ask_price_1"))
        # Sanity check: prices must be near mid
        if bp3 and abs(bp3 - mid) > 500: bp3 = None
        if ap3 and abs(ap3 - mid) > 500: ap3 = None
        wm = (bp3 + ap3) / 2 if (bp3 and ap3) else mid
        mid_vals.append(mid)
        wm_vals.append(wm)

    SPIKE_THRESH = 5
    spike_count = 0
    wall_moved = 0
    wm_deltas_at_spike = []
    pos_spike_next = []
    neg_spike_next = []

    for i in range(1, len(mid_vals)):
        if mid_vals[i] is None or mid_vals[i-1] is None:
            continue
        delta = mid_vals[i] - mid_vals[i-1]
        # Skip inter-day jumps (consecutive rows with different days)
        if abs(delta) > 200:
            continue
        if abs(delta) >= SPIKE_THRESH:
            spike_count += 1
            if wm_vals[i] is not None and wm_vals[i-1] is not None:
                wm_delta = wm_vals[i] - wm_vals[i-1]
                wm_deltas_at_spike.append(abs(wm_delta))
                if abs(wm_delta) >= 1:
                    wall_moved += 1
            # Post-spike reversion
            if i + 1 < len(mid_vals) and mid_vals[i+1] is not None:
                next_ret = mid_vals[i+1] - mid_vals[i]
                if delta > 0:
                    pos_spike_next.append(next_ret)
                else:
                    neg_spike_next.append(next_ret)

    print(f"\n  Total spikes (|Δmid| >= {SPIKE_THRESH}): {spike_count}")
    if spike_count > 0 and wm_deltas_at_spike:
        pct = 100 * wall_moved / len(wm_deltas_at_spike)
        avg_wm = sum(wm_deltas_at_spike) / len(wm_deltas_at_spike)
        print(f"  Wall moved (|Δwm| >= 1) during spike: {wall_moved}/{len(wm_deltas_at_spike)} ({pct:.1f}%)")
        print(f"  Avg |wall_mid delta| during spike: {avg_wm:.3f}")
        if pct < 20:
            print("  → WALL STABLE: take logic correctly captures mispricings")
        else:
            print("  → WALL MOVES: we miss some mispricings when wall follows the spike")

    if pos_spike_next:
        avg = sum(pos_spike_next) / len(pos_spike_next)
        print(f"\n  Post-positive spike t+1 mean return: {avg:+.2f} (n={len(pos_spike_next)})")
    if neg_spike_next:
        avg = sum(neg_spike_next) / len(neg_spike_next)
        print(f"  Post-negative spike t+1 mean return: {avg:+.2f} (n={len(neg_spike_next)})")

    # ACO mid_price stats
    valid_mid = [m for m in mid_vals if m is not None]
    print(f"\n  ACO mid_price stats: mean={sum(valid_mid)/len(valid_mid):.2f}, "
          f"min={min(valid_mid):.1f}, max={max(valid_mid):.1f}")

    # Wall mid stats
    valid_wm = [w for w in wm_vals if w is not None]
    print(f"  ACO wall_mid stats: mean={sum(valid_wm)/len(valid_wm):.2f}, "
          f"min={min(valid_wm):.1f}, max={max(valid_wm):.1f}")

else:
    print(f"  ACO product not found. Available: {list(act.keys())}")

# ─── Q4 — End-of-day positions ────────────────────────────────────────────────

print("\n" + "="*60)
print("Q4 — END-OF-DAY POSITIONS (inferred from PnL slope)")
print("="*60)

# From trade history, try to infer final positions
if trade_history:
    print(f"  Trade history entries: {len(trade_history)}")
    sample = trade_history[:3]
    print(f"  Sample trade: {sample[0] if sample else 'N/A'}")

    # Build position by tracking our trades
    # We need to know which side is "us" — check buyer/seller fields
    our_positions = defaultdict(int)
    our_trades_count = defaultdict(int)
    for t in trade_history:
        buyer = t.get("buyer", "")
        seller = t.get("seller", "")
        symbol = t.get("symbol", "")
        qty = int(t.get("quantity", 0))
        price = to_float(t.get("price", ""))

        # In Prosperity, SUBMISSION = us
        if buyer == "SUBMISSION":
            our_positions[symbol] += qty
            our_trades_count[symbol] += 1
        elif seller == "SUBMISSION":
            our_positions[symbol] -= qty
            our_trades_count[symbol] += 1

    if our_positions:
        print("\n  Our final net positions from trade history:")
        for sym, pos in sorted(our_positions.items()):
            print(f"    {sym}: position = {pos:+d} ({our_trades_count[sym]} trades)")
    else:
        print("  No SUBMISSION buyer/seller found in trade history.")
        if trade_history:
            buyers = list(set(str(t.get("buyer","")) for t in trade_history[:50]))
            sellers = list(set(str(t.get("seller","")) for t in trade_history[:50]))
            print(f"  Buyer values seen: {buyers[:10]}")
            print(f"  Seller values seen: {sellers[:10]}")
else:
    print("  No trade history in this log.")

# Infer from PnL what the implied position was during IPR trend
if IPR_KEY:
    prows = act[IPR_KEY]
    day_last_pnl = {}
    for r in prows:
        d = r.get("day")
        pnl = to_float(r.get("profit_and_loss"))
        if pnl is not None:
            day_last_pnl[d] = pnl
    vals = sorted(day_last_pnl.items())
    print(f"\n  IPR ({IPR_KEY}) PnL by day:")
    for d, p in vals:
        print(f"    Day {d}: {p:,.2f}")

print("\n" + "="*60)
print("DONE")
print("="*60)

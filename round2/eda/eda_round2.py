"""
EDA Round 2 — ASH_COATED_OSMIUM (ACO) + INTARIAN_PEPPER_ROOT (IPR)
Days: -1, 0, 1

Generates 6 plots:
  plot1_IPR_trend.png       — IPR wall_mid vs FV théorique
  plot2_ACO_spikes.png      — ACO distribution des returns + fréquence spikes
  plot3_ACO_postspike.png   — Mean reversion post-spike ACO
  plot4_spreads.png         — Distribution des spreads L1 (ACO + IPR)
  plot5_wallmid_spike.png   — Wall_mid stability pendant les spikes ACO
  plot6_ACO_inventory.png   — Pression inventaire ACO (buy vs sell side volume)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).parent
DAYS = [-1, 0, 1]
COLORS = {-1: "#2196F3", 0: "#FF9800", 1: "#4CAF50"}
DAY_LABELS = {-1: "Day -1", 0: "Day 0", 1: "Day 1"}

# ─── Load data ────────────────────────────────────────────────────────────────

def load_prices():
    frames = []
    for d in DAYS:
        path = DATA_DIR / f"prices_round_2_day_{d}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # Wall mid = (worst_bid + worst_ask) / 2
    # bid_price_3 = worst bid (lowest), ask_price_3 = worst ask (highest)
    # Fallback: use bid_price_2, then bid_price_1
    df["worst_bid"] = df["bid_price_3"].fillna(df["bid_price_2"]).fillna(df["bid_price_1"])
    df["worst_ask"] = df["ask_price_3"].fillna(df["ask_price_2"]).fillna(df["ask_price_1"])
    df["wall_mid"] = (df["worst_bid"] + df["worst_ask"]) / 2
    df["spread_l1"] = df["ask_price_1"] - df["bid_price_1"]
    # Global time index (continuous across days)
    df["t_global"] = df["day"] * 1_000_000 + df["timestamp"]
    return df

def load_trades():
    frames = []
    for d in DAYS:
        path = DATA_DIR / f"trades_round_2_day_{d}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = d
        frames.append(df)
    return pd.concat(frames, ignore_index=True)

print("Loading data...")
prices = load_prices()
trades = load_trades()

ipr = prices[prices["product"] == "INTARIAN_PEPPER_ROOT"].copy().sort_values(["day", "timestamp"])
aco = prices[prices["product"] == "ASH_COATED_OSMIUM"].copy().sort_values(["day", "timestamp"])
ipr_trades = trades[trades["symbol"] == "INTARIAN_PEPPER_ROOT"].copy()
aco_trades = trades[trades["symbol"] == "ASH_COATED_OSMIUM"].copy()

print(f"IPR rows: {len(ipr)}, ACO rows: {len(aco)}")
print(f"IPR trades: {len(ipr_trades)}, ACO trades: {len(aco_trades)}")

# ─── PLOT 1 — IPR Trend ───────────────────────────────────────────────────────

print("\nGenerating Plot 1: IPR Trend...")
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("PLOT 1 — INTARIAN_PEPPER_ROOT: Wall_mid vs FV Théorique (Round 2)", fontsize=14, fontweight="bold")

for col, day in enumerate(DAYS):
    df_d = ipr[ipr["day"] == day].copy()
    ax_top = axes[0, col]
    ax_bot = axes[1, col]

    # Theoretical FV: FV = 10000 + 1000*(day+2) + 0.001*t
    # Round 2 days: -1 → day index 1 (since R1 ended at day 0), 0 → 2, 1 → 3
    # Let's fit empirically AND show theoretical
    t = df_d["timestamp"].values
    fv_theoretical = 10000 + 1000 * (day + 2) + 0.001 * t
    wall_mid_vals = df_d["wall_mid"].dropna().values
    mid_vals = df_d["mid_price"].values

    # Regression on wall_mid to get empirical FV
    valid = df_d["wall_mid"].notna()
    t_v = t[valid]
    wm_v = df_d["wall_mid"][valid].values
    if len(t_v) > 10:
        coeffs = np.polyfit(t_v, wm_v, 1)
        fv_empirical = np.polyval(coeffs, t)
        slope_empirical = coeffs[0]
        intercept_empirical = coeffs[1]
    else:
        fv_empirical = fv_theoretical
        slope_empirical = 0.001
        intercept_empirical = 10000 + 1000 * (day + 2)

    r2_num = np.sum((wm_v - np.polyval(coeffs, t_v))**2) if len(t_v) > 10 else 0
    r2_den = np.sum((wm_v - np.mean(wm_v))**2) if len(t_v) > 10 and np.var(wm_v) > 0 else 1
    r2 = 1 - r2_num / r2_den if r2_den > 0 else 0

    ax_top.plot(t, mid_vals, color=COLORS[day], alpha=0.4, linewidth=0.6, label="mid_price")
    ax_top.plot(t[valid], wm_v, color="black", linewidth=0.8, alpha=0.7, label="wall_mid")
    ax_top.plot(t, fv_theoretical, "--", color="red", linewidth=1.2, label="FV théorique")
    ax_top.plot(t, fv_empirical, "-.", color="purple", linewidth=1.2, label=f"FV empirique (R²={r2:.4f})")
    ax_top.set_title(f"Day {day}", fontsize=11)
    ax_top.set_xlabel("Timestamp")
    ax_top.set_ylabel("Prix")
    ax_top.legend(fontsize=7)
    ax_top.grid(True, alpha=0.3)

    # Bottom: deviation from FV
    dev = wm_v - np.polyval(coeffs, t_v) if len(t_v) > 10 else wm_v - fv_theoretical[valid]
    ax_bot.plot(t_v, dev, color=COLORS[day], alpha=0.5, linewidth=0.6)
    ax_bot.axhline(0, color="black", linewidth=1)
    ax_bot.axhline(np.mean(dev), color="red", linestyle="--", linewidth=1, label=f"mean={np.mean(dev):.2f}")
    ax_bot.fill_between(t_v, 0, dev, where=dev > 0, color="green", alpha=0.2, label="above FV")
    ax_bot.fill_between(t_v, 0, dev, where=dev < 0, color="red", alpha=0.2, label="below FV")
    ax_bot.set_title(f"Déviation wall_mid - FV | σ={np.std(dev):.2f}", fontsize=10)
    ax_bot.set_xlabel("Timestamp")
    ax_bot.set_ylabel("Déviation")
    ax_bot.legend(fontsize=7)
    ax_bot.grid(True, alpha=0.3)
    ax_bot.text(0.02, 0.95, f"slope={slope_empirical:.5f}\nintercept={intercept_empirical:.1f}",
                transform=ax_bot.transAxes, fontsize=8, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

plt.tight_layout()
plt.savefig(DATA_DIR / "plot1_IPR_trend.png", dpi=150, bbox_inches="tight")
plt.close()
print("  → plot1_IPR_trend.png saved")

# ─── PLOT 2 — ACO Spikes ─────────────────────────────────────────────────────

print("Generating Plot 2: ACO Spikes...")
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("PLOT 2 — ASH_COATED_OSMIUM: Distribution des Returns & Spikes (Round 2)", fontsize=14, fontweight="bold")

total_spikes = 0
for col, day in enumerate(DAYS):
    df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
    df_d = df_d[df_d["mid_price"] > 100]  # filter invalid
    mid = df_d["mid_price"].values
    t = df_d["timestamp"].values

    returns = np.diff(mid)
    spikes = returns[np.abs(returns) >= 5]
    spike_ts = t[1:][np.abs(returns) >= 5]
    n_spikes = len(spikes)
    total_spikes += n_spikes

    ax_top = axes[0, col]
    ax_bot = axes[1, col]

    # Top: mid_price with spikes highlighted
    ax_top.plot(t, mid, color=COLORS[day], linewidth=0.7, alpha=0.7)
    if len(spike_ts) > 0:
        spike_mids = mid[1:][np.abs(returns) >= 5]
        pos_mask = spikes > 0
        neg_mask = spikes < 0
        if pos_mask.any():
            ax_top.scatter(spike_ts[pos_mask], spike_mids[pos_mask], color="red", s=8, zorder=5, label="spike +")
        if neg_mask.any():
            ax_top.scatter(spike_ts[neg_mask], spike_mids[neg_mask], color="blue", s=8, zorder=5, label="spike -")
    ax_top.axhline(10000, color="black", linestyle="--", linewidth=1, alpha=0.5, label="FV=10000")
    ax_top.set_title(f"Day {day} — {n_spikes} spikes ≥|5| ({n_spikes/100:.1f}/1000ts)", fontsize=10)
    ax_top.set_xlabel("Timestamp")
    ax_top.set_ylabel("mid_price")
    ax_top.legend(fontsize=7)
    ax_top.grid(True, alpha=0.3)

    # Bottom: distribution of returns
    clip_returns = returns[np.abs(returns) < 30]
    bins = np.arange(-25.5, 26.5, 1)
    ax_bot.hist(clip_returns, bins=bins, color=COLORS[day], edgecolor="white", alpha=0.8)
    ax_bot.axvline(0, color="black", linewidth=1.5)
    ax_bot.axvline(5, color="red", linestyle="--", linewidth=1, label="spike threshold ±5")
    ax_bot.axvline(-5, color="red", linestyle="--", linewidth=1)
    ax_bot.set_title(f"Distribution returns | std={np.std(returns):.2f}", fontsize=10)
    ax_bot.set_xlabel("Δmid_price")
    ax_bot.set_ylabel("Count")
    ax_bot.set_xlim(-25, 25)
    ax_bot.legend(fontsize=7)
    ax_bot.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(DATA_DIR / "plot2_ACO_spikes.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  → plot2_ACO_spikes.png saved | Total spikes: {total_spikes}")

# ─── PLOT 3 — ACO Post-Spike Mean Reversion ──────────────────────────────────

print("Generating Plot 3: ACO Post-spike Mean Reversion...")
LOOKAHEAD = 20
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
fig.suptitle("PLOT 3 — ACO: Mean Reversion POST-SPIKE (Round 2)\nRetour moyen t+k après spike ≥|5|", fontsize=13, fontweight="bold")

for ax, (spike_sign, label, color) in zip(axes, [
    (1,  "Après spike POSITIF ≥+5 → expected SHORT", "red"),
    (-1, "Après spike NÉGATIF ≤-5 → expected LONG", "blue"),
]):
    mean_returns = []
    std_returns = []
    counts = []

    for k in range(1, LOOKAHEAD + 1):
        all_returns = []
        for day in DAYS:
            df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
            df_d = df_d[df_d["mid_price"] > 100]
            mid = df_d["mid_price"].values
            returns = np.diff(mid)
            for i in range(len(returns)):
                if spike_sign == 1 and returns[i] >= 5:
                    if i + k < len(mid):
                        all_returns.append(mid[i + k] - mid[i + 1])
                elif spike_sign == -1 and returns[i] <= -5:
                    if i + k < len(mid):
                        all_returns.append(mid[i + k] - mid[i + 1])

        if all_returns:
            mean_returns.append(np.mean(all_returns))
            std_returns.append(np.std(all_returns))
            counts.append(len(all_returns))
        else:
            mean_returns.append(0)
            std_returns.append(0)
            counts.append(0)

    ks = np.arange(1, LOOKAHEAD + 1)
    mean_arr = np.array(mean_returns)
    std_arr = np.array(std_returns)
    n_arr = np.array(counts)
    sem_arr = std_arr / np.sqrt(np.maximum(n_arr, 1))

    ax.plot(ks, mean_arr, color=color, linewidth=2, marker="o", markersize=4, label=f"Mean return (n≈{counts[0]})")
    ax.fill_between(ks, mean_arr - sem_arr, mean_arr + sem_arr, color=color, alpha=0.2, label="±SEM")
    ax.fill_between(ks, mean_arr - std_arr, mean_arr + std_arr, color=color, alpha=0.07, label="±σ")
    ax.axhline(0, color="black", linewidth=1.5, linestyle="--")
    ax.set_title(label, fontsize=11)
    ax.set_xlabel("Timesteps après le spike (k)")
    ax.set_ylabel("Retour moyen (mid[t+k] - mid[t+1])")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Annotate t+1 value
    if mean_arr[0] != 0:
        ax.annotate(f"t+1: {mean_arr[0]:+.2f}",
                    xy=(1, mean_arr[0]), xytext=(3, mean_arr[0] + (0.5 if spike_sign==1 else -0.5)),
                    fontsize=10, fontweight="bold", color=color,
                    arrowprops=dict(arrowstyle="->", color=color))

plt.tight_layout()
plt.savefig(DATA_DIR / "plot3_ACO_postspike.png", dpi=150, bbox_inches="tight")
plt.close()
print("  → plot3_ACO_postspike.png saved")

# ─── PLOT 4 — Spreads ────────────────────────────────────────────────────────

print("Generating Plot 4: Spreads...")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("PLOT 4 — Distribution des Spreads L1 (Round 2)", fontsize=13, fontweight="bold")

for row, (product, df_p, label) in enumerate([
    ("ACO", aco, "ASH_COATED_OSMIUM"),
    ("IPR", ipr, "INTARIAN_PEPPER_ROOT"),
]):
    ax_left = axes[row, 0]
    ax_right = axes[row, 1]

    spreads = df_p["spread_l1"].dropna()
    spreads = spreads[(spreads > 0) & (spreads < 100)]

    # Per-day histogram
    for day in DAYS:
        s_d = df_p[df_p["day"] == day]["spread_l1"].dropna()
        s_d = s_d[(s_d > 0) & (s_d < 100)]
        ax_left.hist(s_d, bins=50, alpha=0.5, color=COLORS[day], label=f"Day {day} (mean={s_d.mean():.1f})")
    ax_left.set_title(f"{label} — Spread L1 par jour", fontsize=10)
    ax_left.set_xlabel("Spread (ask_price_1 - bid_price_1)")
    ax_left.set_ylabel("Count")
    ax_left.legend(fontsize=8)
    ax_left.grid(True, alpha=0.3)

    # Cumulative distribution
    sorted_s = np.sort(spreads)
    cdf = np.arange(1, len(sorted_s)+1) / len(sorted_s)
    ax_right.plot(sorted_s, cdf, color="navy", linewidth=2)
    p50 = np.percentile(spreads, 50)
    p90 = np.percentile(spreads, 90)
    ax_right.axvline(p50, color="orange", linestyle="--", linewidth=1.5, label=f"P50={p50:.1f}")
    ax_right.axvline(p90, color="red", linestyle="--", linewidth=1.5, label=f"P90={p90:.1f}")
    ax_right.set_title(f"{label} — CDF spread | avg={spreads.mean():.2f}", fontsize=10)
    ax_right.set_xlabel("Spread")
    ax_right.set_ylabel("CDF")
    ax_right.legend(fontsize=9)
    ax_right.grid(True, alpha=0.3)
    ax_right.text(0.6, 0.2, f"Mean: {spreads.mean():.2f}\nStd: {spreads.std():.2f}\nMin: {spreads.min():.0f}\nMax: {spreads.max():.0f}",
                  transform=ax_right.transAxes, fontsize=9,
                  bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))

plt.tight_layout()
plt.savefig(DATA_DIR / "plot4_spreads.png", dpi=150, bbox_inches="tight")
plt.close()
print("  → plot4_spreads.png saved")

# ─── PLOT 5 — Wall_mid stability during ACO spikes ───────────────────────────

print("Generating Plot 5: Wall_mid stability during spikes...")
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("PLOT 5 — ACO: Wall_mid vs Mid_price pendant les spikes (Round 2)\nClé pour notre stratégie: wall_mid bouge-t-il ?", fontsize=13, fontweight="bold")

for col, day in enumerate(DAYS):
    ax = axes[col]
    df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
    df_d = df_d[df_d["mid_price"] > 100]
    mid = df_d["mid_price"].values
    wm = df_d["wall_mid"].values
    t = df_d["timestamp"].values

    returns_mid = np.diff(mid)
    returns_wm = np.diff(wm)
    spike_mask = np.abs(returns_mid) >= 5

    wm_deltas = np.abs(returns_wm[spike_mask])
    pct_moved = 100 * np.mean(wm_deltas >= 1)
    avg_wm_delta = np.mean(wm_deltas)

    # Scatter: Δmid vs Δwall_mid at spike events
    ax.scatter(returns_mid[spike_mask], returns_wm[spike_mask],
               alpha=0.3, s=15, color=COLORS[day])
    ax.axhline(0, color="black", linewidth=1)
    ax.axvline(0, color="black", linewidth=1)

    # Diagonal line = wall follows mid perfectly
    lim = max(abs(returns_mid[spike_mask]).max(), abs(returns_wm[spike_mask]).max()) if spike_mask.sum() > 0 else 20
    ax.plot([-lim, lim], [-lim, lim], "r--", linewidth=1, alpha=0.5, label="wall = mid (perfect follow)")
    ax.plot([-lim, lim], [0, 0], "g-", linewidth=1, alpha=0.5, label="wall stable (ideal)")

    ax.set_title(f"Day {day} | {spike_mask.sum()} spikes\nWall moved ≥1: {pct_moved:.1f}% | avg Δwall={avg_wm_delta:.2f}", fontsize=10)
    ax.set_xlabel("Δmid_price (spike)")
    ax.set_ylabel("Δwall_mid")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    ax.text(0.05, 0.92, f"Si wall stable → on voit le mispricing\nSi wall suit → on rate",
            transform=ax.transAxes, fontsize=8, color="darkred",
            bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.7))

plt.tight_layout()
plt.savefig(DATA_DIR / "plot5_wallmid_spike.png", dpi=150, bbox_inches="tight")
plt.close()
print("  → plot5_wallmid_spike.png saved")

# ─── PLOT 6 — ACO Inventory Pressure ─────────────────────────────────────────

print("Generating Plot 6: ACO Inventory pressure...")
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("PLOT 6 — ACO: Pression d'Inventaire & Asymétrie du Book (Round 2)\nPourquoi finit-on net long ?", fontsize=13, fontweight="bold")

for col, day in enumerate(DAYS):
    ax_top = axes[0, col]
    ax_bot = axes[1, col]
    df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
    df_d = df_d[df_d["mid_price"] > 100]

    # Top: bid volume vs ask volume L1 over time
    bid_v1 = df_d["bid_volume_1"].fillna(0)
    ask_v1 = df_d["ask_volume_1"].fillna(0)
    imbalance = (bid_v1 - ask_v1) / (bid_v1 + ask_v1 + 1e-6)
    t = df_d["timestamp"].values
    mid = df_d["mid_price"].values

    ax_top.plot(t, imbalance.rolling(50, min_periods=1).mean(), color=COLORS[day], linewidth=1, label="Imbalance (bid-ask)/(bid+ask)")
    ax_top.axhline(0, color="black", linewidth=1)
    ax_top.fill_between(t, 0, imbalance.rolling(50, min_periods=1).mean(),
                        where=imbalance.rolling(50, min_periods=1).mean() > 0,
                        color="green", alpha=0.2, label="bid side dominates")
    ax_top.fill_between(t, 0, imbalance.rolling(50, min_periods=1).mean(),
                        where=imbalance.rolling(50, min_periods=1).mean() < 0,
                        color="red", alpha=0.2, label="ask side dominates")
    ax_top.set_title(f"Day {day} — Order Book Imbalance (50ts MA)", fontsize=10)
    ax_top.set_xlabel("Timestamp")
    ax_top.set_ylabel("Imbalance")
    ax_top.legend(fontsize=7)
    ax_top.grid(True, alpha=0.3)

    # Bottom: mid_price deviation from 10000 → shows where spikes go
    dev_from_fv = mid - 10000
    ax_bot.plot(t, dev_from_fv, color=COLORS[day], linewidth=0.5, alpha=0.6)
    ax_bot.axhline(0, color="black", linewidth=1.5, linestyle="--", label="FV=10000")
    # Highlight positive spikes (→ should SHORT) and negative (→ should LONG)
    pos_spike_mask = dev_from_fv > 5
    neg_spike_mask = dev_from_fv < -5
    ax_bot.fill_between(t, 0, dev_from_fv, where=pos_spike_mask, color="red", alpha=0.4, label=f"above FV+5 ({pos_spike_mask.sum()} ts → SHORT)")
    ax_bot.fill_between(t, 0, dev_from_fv, where=neg_spike_mask, color="blue", alpha=0.4, label=f"below FV-5 ({neg_spike_mask.sum()} ts → LONG)")
    ax_bot.set_title(f"Day {day} — mid_price - FV(10000) | mean={dev_from_fv.mean():.2f}", fontsize=10)
    ax_bot.set_xlabel("Timestamp")
    ax_bot.set_ylabel("Déviation vs FV")
    ax_bot.legend(fontsize=7)
    ax_bot.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(DATA_DIR / "plot6_ACO_inventory.png", dpi=150, bbox_inches="tight")
plt.close()
print("  → plot6_ACO_inventory.png saved")

# ─── Summary stats ────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("SUMMARY STATS — ROUND 2 DATA")
print("="*60)

print("\n--- IPR ---")
for day in DAYS:
    df_d = ipr[ipr["day"] == day].copy()
    wm = df_d["wall_mid"].dropna()
    t = df_d["timestamp"].values
    valid = df_d["wall_mid"].notna()
    if valid.sum() > 10:
        coeffs = np.polyfit(t[valid], wm.values, 1)
        print(f"  Day {day}: wall_mid range [{wm.min():.1f}, {wm.max():.1f}] | "
              f"FV théo start={10000+1000*(day+2):.0f} | "
              f"empirical slope={coeffs[0]:.5f} (expected 0.001) | "
              f"intercept={coeffs[1]:.1f}")

print("\n--- ACO ---")
spike_total = 0
for day in DAYS:
    df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
    df_d = df_d[df_d["mid_price"] > 100]
    mid = df_d["mid_price"].values
    returns = np.diff(mid)
    n_spikes = np.sum(np.abs(returns) >= 5)
    spike_total += n_spikes
    wm = df_d["wall_mid"].dropna()
    print(f"  Day {day}: mid mean={mid.mean():.2f} | spikes≥|5|: {n_spikes} ({n_spikes/100:.1f}/1000ts) | "
          f"wall_mid mean={wm.mean():.2f} | spread_l1 mean={df_d['spread_l1'].mean():.2f}")

print(f"\n  Total spikes (3 days): {spike_total} = ~{spike_total//3}/day")

print("\n--- POST-SPIKE REVERSION (Round 2) ---")
for spike_sign, label in [(1, "Pos spike ≥+5"), (-1, "Neg spike ≤-5")]:
    t1_returns = []
    for day in DAYS:
        df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
        df_d = df_d[df_d["mid_price"] > 100]
        mid = df_d["mid_price"].values
        returns = np.diff(mid)
        for i in range(len(returns)):
            if spike_sign == 1 and returns[i] >= 5:
                if i + 1 < len(mid):
                    t1_returns.append(mid[i+1] - mid[i+1-1])
            elif spike_sign == -1 and returns[i] <= -5:
                if i + 1 < len(mid):
                    t1_returns.append(mid[i+1] - mid[i+1-1])
    # actually compute t+1 return correctly
    t1_returns = []
    for day in DAYS:
        df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
        df_d = df_d[df_d["mid_price"] > 100]
        mid = df_d["mid_price"].values
        returns = np.diff(mid)
        for i in range(len(returns) - 1):
            if spike_sign == 1 and returns[i] >= 5:
                t1_returns.append(returns[i+1])
            elif spike_sign == -1 and returns[i] <= -5:
                t1_returns.append(returns[i+1])
    if t1_returns:
        arr = np.array(t1_returns)
        print(f"  {label}: t+1 mean={arr.mean():+.2f}, σ={arr.std():.2f}, n={len(arr)}")

print("\n--- WALL_MID DURING SPIKES (Round 2) ---")
for day in DAYS:
    df_d = aco[aco["day"] == day].copy().sort_values("timestamp")
    df_d = df_d[df_d["mid_price"] > 100]
    mid = df_d["mid_price"].values
    wm = df_d["wall_mid"].values
    returns_mid = np.diff(mid)
    returns_wm = np.diff(wm)
    spike_mask = np.abs(returns_mid) >= 5
    if spike_mask.sum() > 0:
        wm_d = np.abs(returns_wm[spike_mask])
        pct = 100 * np.mean(wm_d >= 1)
        print(f"  Day {day}: {spike_mask.sum()} spikes | wall moved ≥1: {pct:.1f}% | avg |Δwall|={wm_d.mean():.3f}")

print("\nAll plots saved to:", DATA_DIR)

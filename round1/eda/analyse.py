"""
╔══════════════════════════════════════════════════════════╗
║       PROSPERITY 4 — EDA ROUND 1  (v2 post-wiki)        ║
║       ASH_COATED_OSMIUM  &  INTARIAN_PEPPER_ROOT         ║
╚══════════════════════════════════════════════════════════╝

CE QU'ON SAIT DÉJÀ (analyse serveur) :
- IPR = random walk + drift EXACTE de +0.001/timestep (+1000/jour)
         Fair value = 10000 + 1000*(day+2) + 0.001*timestamp
- ACO = mean-reversion autour de 10000, spikes fréquents (±5 à ±16)
         "Hidden pattern" selon le wiki → à découvrir visuellement

OBJECTIF DES PLOTS :
1. Visualiser la tendance IPR et les déviations autour
2. Visualiser les spikes ACO et leur structure
3. Chercher le "hidden pattern" ACO (timing ? amplitude ? paires ?)
4. Calibrer les paramètres de market making
"""

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

plt.style.use('dark_background')
COLORS = {'ACO': '#00bfff', 'IPR': '#ff6b35'}

# ══════════════════════════════════════════════
# 1. CHARGEMENT
# ══════════════════════════════════════════════
# %%
DATA_DIR = "."  # Dossier où sont tes CSV

prices, trades = [], []
for day in [-2, -1, 0]:
    p = pd.read_csv(f"{DATA_DIR}/prices_round_1_day_{day}.csv", sep=";")
    p["day"] = day
    prices.append(p)
    t = pd.read_csv(f"{DATA_DIR}/trades_round_1_day_{day}.csv", sep=";")
    t["day"] = day
    trades.append(t)

df_p = pd.concat(prices).reset_index(drop=True)
df_t = pd.concat(trades).reset_index(drop=True)
df_p = df_p[df_p["mid_price"] > 0].copy()

ACO = df_p[df_p["product"] == "ASH_COATED_OSMIUM"].copy()
IPR = df_p[df_p["product"] == "INTARIAN_PEPPER_ROOT"].copy()
ACO_t = df_t[df_t["symbol"] == "ASH_COATED_OSMIUM"].copy()
IPR_t = df_t[df_t["symbol"] == "INTARIAN_PEPPER_ROOT"].copy()

# Fair value IPR = tendance linéaire parfaite
# Day offset : day -2 → 0, day -1 → 1000, day 0 → 2000
DAY_OFFSET = {-2: 0, -1: 1000, 0: 2000}
IPR["fair_value"] = IPR.apply(
    lambda r: 10000 + DAY_OFFSET[r["day"]] + 0.001 * r["timestamp"], axis=1
)
IPR["deviation"] = IPR["mid_price"] - IPR["fair_value"]

print("✅ Données chargées")
print(f"   ACO: {len(ACO)} rows | IPR: {len(IPR)} rows")

# ══════════════════════════════════════════════
# PLOT 1 — IPR : TENDANCE + DÉVIATIONS
# ══════════════════════════════════════════════
# %%
fig, axes = plt.subplots(2, 3, figsize=(18, 9))
fig.suptitle("INTARIAN_PEPPER_ROOT — Tendance linéaire et déviations", fontsize=14)

for col, day in enumerate([-2, -1, 0]):
    sub = IPR[IPR["day"] == day]
    fv = sub["fair_value"]

    # Haut : prix vs tendance
    ax = axes[0, col]
    ax.plot(sub["timestamp"], sub["mid_price"], color=COLORS["IPR"], lw=1, label="mid_price")
    ax.plot(sub["timestamp"], fv, color="yellow", lw=1.5, linestyle="--", label="fair_value")
    ax.fill_between(sub["timestamp"], sub["mid_price"], fv,
                    where=sub["mid_price"] > fv, alpha=0.3, color="green", label="above FV")
    ax.fill_between(sub["timestamp"], sub["mid_price"], fv,
                    where=sub["mid_price"] < fv, alpha=0.3, color="red", label="below FV")
    ax.set_title(f"Day {day} — prix vs tendance")
    ax.legend(fontsize=7)
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Price")

    # Bas : déviation autour de la tendance
    ax = axes[1, col]
    ax.plot(sub["timestamp"], sub["deviation"], color=COLORS["IPR"], lw=1)
    ax.axhline(0, color="white", lw=1, linestyle="--")
    dev_std = sub["deviation"].std()
    ax.axhline(dev_std, color="green", lw=0.8, linestyle=":", label=f"+1σ={dev_std:.1f}")
    ax.axhline(-dev_std, color="red", lw=0.8, linestyle=":", label=f"-1σ={dev_std:.1f}")
    ax.set_title(f"Day {day} — déviation (mid - fair_value)")
    ax.legend(fontsize=7)
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Déviation")

plt.tight_layout()
plt.savefig("plot1_IPR_tendance.png", dpi=150, bbox_inches="tight")
plt.show()
print("📊 Plot 1 sauvegardé : plot1_IPR_tendance.png")

# ══════════════════════════════════════════════
# PLOT 2 — ACO : PRIX + SPIKES
# ══════════════════════════════════════════════
# %%
fig, axes = plt.subplots(2, 3, figsize=(18, 9))
fig.suptitle("ASH_COATED_OSMIUM — Mean reversion autour de 10000 + spikes", fontsize=14)

ACO_FV = 10000  # fair value fixe

for col, day in enumerate([-2, -1, 0]):
    sub = ACO[ACO["day"] == day].copy()
    sub_t = ACO_t[ACO_t["day"] == day]
    ret = sub["mid_price"].diff()
    spikes = sub[abs(ret) >= 5]

    # Haut : prix + spikes marqués
    ax = axes[0, col]
    ax.plot(sub["timestamp"], sub["mid_price"], color=COLORS["ACO"], lw=0.8)
    ax.axhline(ACO_FV, color="yellow", lw=1, linestyle="--", label="FV=10000")
    ax.scatter(spikes["timestamp"], spikes["mid_price"],
               color="red", s=12, zorder=5, label=f"spikes (n={len(spikes)})")
    ax.set_title(f"Day {day} — prix + spikes ≥5pts")
    ax.legend(fontsize=7)
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Price")

    # Bas : returns — distribution
    ax = axes[1, col]
    ax.hist(ret.dropna(), bins=80, color=COLORS["ACO"], alpha=0.7)
    ax.axvline(0, color="white", lw=1)
    ax.axvline(5, color="red", lw=0.8, linestyle="--", label="±5 (spike)")
    ax.axvline(-5, color="red", lw=0.8, linestyle="--")
    n_spikes = (abs(ret) >= 5).sum()
    ax.set_title(f"Day {day} — distribution returns\n{n_spikes} spikes ≥5")
    ax.legend(fontsize=7)
    ax.set_xlabel("Return")
    ax.set_ylabel("Count")

plt.tight_layout()
plt.savefig("plot2_ACO_spikes.png", dpi=150, bbox_inches="tight")
plt.show()
print("📊 Plot 2 sauvegardé : plot2_ACO_spikes.png")

# ══════════════════════════════════════════════
# PLOT 3 — ACO : LE "HIDDEN PATTERN"
# Après un spike, que se passe-t-il ?
# ══════════════════════════════════════════════
# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("ACO — Hidden Pattern : comportement POST-SPIKE", fontsize=14)

SPIKE_THR = 5
WINDOW_AFTER = 20  # timesteps après le spike

post_spike_pos = []  # returns après un spike positif
post_spike_neg = []  # returns après un spike négatif

for day in [-2, -1, 0]:
    sub = ACO[ACO["day"] == day]["mid_price"].reset_index(drop=True)
    ret = sub.diff()
    for i in range(1, len(ret) - WINDOW_AFTER):
        if ret.iloc[i] >= SPIKE_THR:      # spike positif
            future = [sub.iloc[i+k] - sub.iloc[i] for k in range(1, WINDOW_AFTER+1)]
            post_spike_pos.append(future)
        elif ret.iloc[i] <= -SPIKE_THR:   # spike négatif
            future = [sub.iloc[i+k] - sub.iloc[i] for k in range(1, WINDOW_AFTER+1)]
            post_spike_neg.append(future)

# Moyenne des trajectoires post-spike
if post_spike_pos:
    mean_pos = np.mean(post_spike_pos, axis=0)
    std_pos = np.std(post_spike_pos, axis=0)
    ax = axes[0]
    ax.plot(range(1, WINDOW_AFTER+1), mean_pos, color="green", lw=2, label="moyenne")
    ax.fill_between(range(1, WINDOW_AFTER+1),
                    mean_pos - std_pos, mean_pos + std_pos,
                    alpha=0.3, color="green", label="±1σ")
    ax.axhline(0, color="white", lw=1, linestyle="--")
    ax.set_title(f"Après spike POSITIF ≥{SPIKE_THR}\n(n={len(post_spike_pos)} événements)")
    ax.set_xlabel("Timesteps après le spike")
    ax.set_ylabel("Prix relatif au spike")
    ax.legend()

if post_spike_neg:
    mean_neg = np.mean(post_spike_neg, axis=0)
    std_neg = np.std(post_spike_neg, axis=0)
    ax = axes[1]
    ax.plot(range(1, WINDOW_AFTER+1), mean_neg, color="red", lw=2, label="moyenne")
    ax.fill_between(range(1, WINDOW_AFTER+1),
                    mean_neg - std_neg, mean_neg + std_neg,
                    alpha=0.3, color="red", label="±1σ")
    ax.axhline(0, color="white", lw=1, linestyle="--")
    ax.set_title(f"Après spike NÉGATIF ≤-{SPIKE_THR}\n(n={len(post_spike_neg)} événements)")
    ax.set_xlabel("Timesteps après le spike")
    ax.set_ylabel("Prix relatif au spike")
    ax.legend()

plt.tight_layout()
plt.savefig("plot3_ACO_postspike.png", dpi=150, bbox_inches="tight")
plt.show()
print("📊 Plot 3 sauvegardé : plot3_ACO_postspike.png")
print(f"\n  → Après spike positif  : retour moyen à t+1 = {mean_pos[0]:.2f}")
print(f"  → Après spike négatif  : retour moyen à t+1 = {mean_neg[0]:.2f}")
print("  Si ces valeurs sont proches de 0 ou négatifs/positifs → mean reversion exploitable !")

# ══════════════════════════════════════════════
# PLOT 4 — SPREAD BID-ASK : COMBIEN ON PEUT GAGNER ?
# ══════════════════════════════════════════════
# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("SPREAD MOYEN — Potentiel de market making", fontsize=14)

for ax, (df_sub, name, color) in zip(axes, [
    (ACO, "ASH_COATED_OSMIUM", COLORS["ACO"]),
    (IPR, "INTARIAN_PEPPER_ROOT", COLORS["IPR"]),
]):
    spreads_by_day = []
    for day in [-2, -1, 0]:
        sub = df_sub[df_sub["day"] == day].copy()
        spread = sub["ask_price_1"] - sub["bid_price_1"]
        spreads_by_day.append(spread)
        ax.hist(spread.dropna(), bins=40, alpha=0.5, label=f"Day {day}")

    all_spreads = pd.concat(spreads_by_day)
    avg = all_spreads.mean()
    ax.axvline(avg, color="yellow", lw=2, linestyle="--", label=f"avg={avg:.2f}")
    ax.set_title(f"{name}\navg spread = {avg:.2f} → edge/fill ≈ {avg/2:.2f}")
    ax.set_xlabel("Spread (ask1 - bid1)")
    ax.set_ylabel("Count")
    ax.legend(fontsize=8)

plt.tight_layout()
plt.savefig("plot4_spreads.png", dpi=150, bbox_inches="tight")
plt.show()
print("📊 Plot 4 sauvegardé : plot4_spreads.png")

# ══════════════════════════════════════════════
# RÉSUMÉ FINAL
# ══════════════════════════════════════════════
# %%
print("\n" + "="*60)
print("📋 RÉSUMÉ — CE QU'ON SAIT MAINTENANT")
print("="*60)

# IPR stats
ipr_dev_std = IPR["deviation"].std()
print(f"""
INTARIAN_PEPPER_ROOT (= Kelp/Emerald type)
  ✅ Fair value = 10000 + 1000*(day+2) + 0.001*timestamp
  ✅ Drift exacte = +1 toutes les 100 steps (r²=1.0000)
  📊 Déviation autour de la tendance : std = {ipr_dev_std:.2f}
  🎯 Stratégie : market making autour de la fair value dynamique
  ⚠️  Position limit = 80
""")

# ACO stats
aco_std = ACO["mid_price"].std()
aco_returns = ACO["mid_price"].diff().dropna()
aco_ac1 = aco_returns.autocorr(1)
n_spikes_total = (abs(aco_returns) >= 5).sum()
print(f"""
ASH_COATED_OSMIUM (= Squid Ink type)
  ✅ Fair value fixe = 10000 (mean={ACO['mid_price'].mean():.1f})
  📊 Std = {aco_std:.2f}, autocorr lag1 = {aco_ac1:.3f}
  🔴 Spikes ≥5 : {n_spikes_total} sur 3 jours ({n_spikes_total/3:.0f}/jour)
  ❓ Hidden pattern : voir plot3 post-spike
  🎯 Stratégie : market making + détection spike → mean reversion
  ⚠️  Position limit = 80
""")

print("📁 Envoie les 4 plots à Claude pour calibrer les paramètres !")
print("="*60)
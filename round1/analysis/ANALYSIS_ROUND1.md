# Analyse Round 1 — Findings & Ce qu'on aurait pu faire mieux

---

## 1. IPR — Tendance linéaire (Plot 1)

### Ce que les graphiques montrent
- **Trend parfaite** : wall_mid suit FV = 10000 + 1000*(day+2) + 0.001*t avec R²=1.0000 sur les 3 jours
- **Déviation autour du trend** : std = 2.0 (day -2) → 2.2 (day -1) → 2.4 (day 0). Très serré.
- **Observation critique** : Les déviations sont majoritairement **négatives** (orange domine). Le mid_price est systématiquement légèrement en-dessous de la FV théorique. Pourquoi ? Le wall_mid capture le trend mais avec un léger lag, ou la FV réelle est légèrement différente de la formule.

### Ce que notre stratégie fait
- ✅ On utilise wall_mid comme FV dynamique → correct, pas besoin de hardcoder la formule
- ✅ IPR_LEAN = 70 pour capturer le drift (+70 × 0.001/step = 0.07 seashells/step = 70/jour capturés)
- ✅ Take à wall_mid quand pos < IPR_LEAN → accumuler la position lean rapidement

### Ce qu'on rate / pourrait améliorer
- Le spread moyen est **13 seashells** → edge/fill ≈ 6.5 seashells. C'est correct mais il y a des moments où le spread est plus large (queue de distribution jusqu'à 20). On pourrait adapter dynamiquement.
- La déviation std=2.2 est petite → nos ordres passifs à ±1 du wall_mid capturent bien la valeur. Pas grand chose à changer.

---

## 2. ACO — Mean reversion + spikes (Plot 2)

### Ce que les graphiques montrent
- **FV fixe = 10000** confirmé (mean = 10000.2 stable sur 3 jours)
- **~1739 spikes ≥5 par jour** — soit un spike toutes les ~575 timesteps (fréquent !)
- **Distribution bimodale** : la majorité des returns sont = 0 (pas de mouvement), mais les spikes font ±5 à ±20+
- Les spikes montent jusqu'à ±20 seashells (ce qui est 20% d'un spread)

### Ce que notre stratégie fait
- ✅ Take tous les asks < wall_mid et bids > wall_mid → capture les spikes APRÈS qu'ils ont eu lieu (on prend les mispricings)
- ✅ Making à penny-jump autour de wall_mid → passive fills quand le prix revient

### Ce qu'on rate / pourrait améliorer
- ❌ **On n'exploite pas le post-spike** directement (voir section 3 ci-dessous)
- **CONFIRMÉ PAR LES LOGS** : le wall_mid bouge pendant les spikes (voir section 9). Notre take logic est donc partiellement aveugle aux mispricings.

---

## 3. ACO — Hidden Pattern POST-SPIKE (Plot 3) ← LE PLUS IMPORTANT

### Ce que les graphiques montrent
```
Après spike POSITIF ≥+5 → retour moyen t+1 = -3.91 seashells (EDA)
Après spike NÉGATIF ≤-5 → retour moyen t+1 = +4.04 seashells (EDA)
```
- **Ce pattern persiste sur 20 timesteps** : la moyenne reste à -4 ou +4 sur tout le graphique
- La σ est large (~8 seashells) mais la **moyenne est très stable**
- Ce n'est PAS du bruit — c'est un signal exploitable sur 5217 événements (3 jours)

### Interprétation économique
Le wall_mid est stable (les walls bougent peu), mais le mid_price spike fortement à cause de penny-jumpers ou d'ordres market aggressifs. Ce spike est "faux" — la vraie FV reste à 10000. Donc après un spike positif, le prix revient vers 10000, et notre algo peut capturer ce retour.

### Ce que notre stratégie fait
- **Partiellement** : si l'ask est < wall_mid APRÈS le spike, on le prend. Mais on ne trade pas assez agressivement.
- ❌ On n'a pas de logique "si détecté spike → aller max short/long directionnellement"

### Stratégie supplémentaire à ajouter
```
Calculer mid_price au début du timestep
Si mid_price > wall_mid + 5 (spike positif) :
    → Mode directionnel SHORT : vendre agressivement à bid_wall (pas de making bid, only asks)
    → Tenir la position short jusqu'à ce que mid_price revienne à wall_mid
Si mid_price < wall_mid - 5 (spike négatif) :
    → Mode directionnel LONG : acheter agressivement à ask_wall
```

**Gain estimé :** ~1646 spikes/jour × 4.1 seashells de retour moyen × efficacité ~30% = ~2,000 seashells/jour additionnels sur ACO si bien calibré.

**Risque :** Le σ est large, certains spikes continuent dans la même direction. Threshold à ≥5, position directionnelle max 20-30 unités supplémentaires.

---

## 4. Spreads (Plot 4)

### Ce que les graphiques montrent
- **ACO spread L1** : avg = 16.18 seashells → edge/fill ≈ 8.09 seashells
- **IPR spread L1** : avg = 13.05 seashells → edge/fill ≈ 6.52 seashells
- Les deux distributions sont très concentrées (peu de variance) → les spreads sont **stables et prévisibles**

### Implication pour notre making
- ACO : on fait du penny-jump à l'intérieur du spread ~16. Si on se fait fill des deux côtés, on capture ~14 seashells par aller-retour. En pratique, on capture ~8 (fill d'un côté à la fois).
- IPR : idem, ~6.5 seashells/fill passif.
- La distribution ACO montre un pic net à 16. Ça veut dire que la structure du book ACO est très régulière. Notre making à bid_wall+1 et ask_wall-1 est proche optimal.

---

## 5. Comparaison avec la stratégie Frankfurt

### Ce que Frankfurt fait que nous faisons aussi ✅
- Wall_mid comme FV (StaticTrader pour ACO, DynamicTrader pour IPR)
- Take aggressif avant making
- Penny-jump avec filtre vol > 1
- Position tracking intra-timestep (buy_sent/sell_sent)
- IPR lean (Frankfurt ne l'a pas documenté mais la logique est identique à leur DynamicTrader)

### Ce que Frankfurt fait qu'on ne fait PAS ❌
1. **Signal Olivia / trader informé** : Frankfurt trackait les trades de quantité 15 aux extrêmes pour détecter un trader informé dès R1. Dans les trades_round_1, les colonnes buyer/seller sont VIDES → pas de signal disponible dans les données de pratique. MAIS dans le live round, ces colonnes pourraient être remplies.
   → **Action : implémenter le tracking dès maintenant**, même si c'est vide en pratique.

2. **Mode directionnel sur les spikes ACO** : Frankfurt utilisait une logique similaire sur Squid Ink (pas Resin). L'ACO ressemble plus à Resin (FV fixe) mais avec des spikes de Squid Ink. On pourrait hybrider.

3. **Robustesse des paramètres (zones plates)** : Frankfurt ne choisit jamais le pic mais la zone plate. On a choisi IPR_LEAN=70 car c'est "bien" mais on n'a pas fait de grid search. À faire si on a du temps.

---

## 6. Ce que les données Round 2 changent

Les données Round 2 (days -1, 0, 1) :
- IPR day -1 démarre à wall_mid ≈ 11001.5 → FV = 10000 + 1000*(1) = 11000 ✅ trend continue
- ACO day -1 : bid_wall = 9982, ask_wall = 10000-10003 → FV ≈ 9991? Ou wall_mid plus conservateur

**Observation ACO Round 2 data** : `9982;21;;;;;10000;13;10003;21` → worst_bid=9982, worst_ask=10003 → wall_mid = (9982+10003)/2 = 9992.5. Ce n'est pas 10000 ! Le wall_mid en Round 2 semble être légèrement différent de 10000 en début de journée.

→ **Notre stratégie v2 (wall_mid dynamique) gère ça correctement**, contrairement à la v1 hardcodée à 10000.

---

## 7. Ce qu'on cherchait dans les logs Round 1

Questions posées avant l'analyse :

1. **ACO PnL** : quelle est la ventilation take vs make ? → **Non disponible** (pas de print() dans le trader soumis, logs vides)
2. **IPR LEAN** : est-ce qu'on a atteint pos=70 ? → **OUI** (voir section 9)
3. **Spikes ACO** : est-ce qu'on rate des mispricings pendant les spikes ? → **OUI** (voir section 9)
4. **Position moyenne** : on est plutôt flat, long ou short en fin de journée ? → **Long sur les deux** (voir section 9)
5. **PnL total** : quelle part vient d'ACO vs IPR ? → **IPR 78.7%, ACO 21.3%** (voir section 9)

---

## 8. Résumé des améliorations à implémenter (par priorité)

| Priorité | Amélioration | Impact estimé | Risque |
|---|---|---|---|
| 🔴 HAUTE | ACO spike detection → mode directionnel | +2k/jour | Calibration difficile |
| 🔴 HAUTE | Ajouter print() statements dans trader.py pour logs futurs | Diagnostic seulement | Aucun |
| 🟡 MOYENNE | Olivia tracking dans market_trades | Variable (0 en pratique, potentiellement fort en live) | Aucun |
| 🟡 MOYENNE | ACO : bloquer les bids quand pos > +40 et spike positif détecté | Réduit inventory risk | Faible |
| 🟢 BASSE | Grid search sur IPR_LEAN (actuellement 70, position atteinte = 78) | Marginal | Faible |
| 🟢 BASSE | Adapter le making spread quand le L1 spread est plus large | Marginal | Faible |

---

## 9. Résultats logs Round 1 — Soumission 272806 (analyse du 2026-04-18)

**Fichier** : `272806.log` | **Produits** : ASH_COATED_OSMIUM (ACO), INTARIAN_PEPPER_ROOT (IPR) | **Jour** : 1 seul jour simulé

### PnL Split

| Produit | PnL Final | % du total |
|---|---|---|
| INTARIAN_PEPPER_ROOT (IPR) | **72,164.25** | 78.7% |
| ASH_COATED_OSMIUM (ACO) | **19,546.91** | 21.3% |
| **TOTAL** | **91,711.16** | 100% |

IPR domine largement. Le trend déterministe à +1/1000 steps est la source principale de profit.

### IPR LEAN — atteint ✅

Position finale IPR = **+78** (target = 70). Le lean a été dépassé légèrement.
- avg PnL delta/step = **7.22 seashells/step** (= making + trend capture combinés)
- Le lean seul contribuerait 0.07/step, le reste vient du making passif

### ACO Spikes — problème confirmé ❌

- **1646 spikes** détectés (|Δmid_price| ≥ 5) sur 10,000 timesteps
- **Wall_mid bouge dans 88.3% des spikes** avec Δwall_mid moyen = **6.75 seashells**
- Conséquence : notre signal de mispricing `mid_price - wall_mid` est réduit de ~6.75 sur chaque spike → on ne détecte que ~30% du mispricing réel
- **Post-spike mean reversion confirmée** :
  - Après spike positif ≥+5 : retour moyen t+1 = **-4.00** (n=818)
  - Après spike négatif ≤-5 : retour moyen t+1 = **+4.23** (n=826)
  - Signal robuste, cohérent avec l'EDA (-3.91 / +4.04 sur données historiques)

**ACO statistiques** :
- mid_price mean = 10000.18 (FV = 10000 confirmé)
- wall_mid mean = 10000.19

### Positions fin de journée

| Produit | Position finale | Statut |
|---|---|---|
| INTARIAN_PEPPER_ROOT (IPR) | **+78** | Long lean ✅ |
| ASH_COATED_OSMIUM (ACO) | **+39** | Net long (non voulu) ⚠️ |

ACO à +39 signifie qu'on a accumulé une position longue non intentionnelle. Probablement dû au fait qu'on prend les asks mispricés (spikes négatifs) plus souvent qu'on ne vend les bids mispricés (spikes positifs), ou que notre making est asymétrique.

### Logs sandbox/lambda

**Vides** — le trader soumis ne contient pas de `print()` statements. Impossible de décomposer take vs make PnL.
→ **Action Round 2** : ajouter des logs structurés dans trader.py (au moins par timestep : position, take_pnl, make_pnl).

### Nombre de trades

- **ACO** : 723 trades (buyer ou seller = SUBMISSION)
- **IPR** : 411 trades
- **Total** : 1304 trades sur le jour

---

## 10. Plan d'action Round 2

### Immédiat (avant soumission)
1. **ACO spike mode** : implémenter la logique directionnelle spike dans trader.py
   - Si `mid_price > wall_mid + 5` : sell agressif, bloquer les bids
   - Si `mid_price < wall_mid - 5` : buy agressif, bloquer les asks
   - Position directionnelle max = 20 unités additionnelles
2. **ACO inventory control** : position finale +39 est trop longue → ajouter un biais de making (élargir ask side, réduire bid side quand pos > 20)
3. **Print logs** : ajouter `print(f"[{product}] ts={ts} pos={pos} take={take_pnl:.1f} make={make_pnl:.1f}")` pour diagnostiquer les soumissions futures

### Si temps disponible
4. **MAF bid** : implémenter `bid()` function pour Market Access Fee (top 50% accepté)
5. **Grid search IPR_LEAN** : tester 60, 70, 80 sur les données Round 2
6. **Olivia tracking** : détecter les trades de taille 15 aux extrêmes du book

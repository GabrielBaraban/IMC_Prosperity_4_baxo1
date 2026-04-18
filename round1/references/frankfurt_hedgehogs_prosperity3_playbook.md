# 🦔 IMC Prosperity 3 — Playbook Frankfurt Hedgehogs (2e Mondial)

> **Équipe :** Timo Diehm, Arne Witt, Marvin Schuster — Frankfurt  
> **Résultat :** 1,433,876 SeaShells | #2 mondial (meneur de chaque round sauf le dernier)  
> **Code source complet :** [FrankfurtHedgehogs_polished.py](https://github.com/TimoDiehm/imc-prosperity-3/blob/main/FrankfurtHedgehogs_polished.py) (925 lignes)  
> **Blog post philosophie :** [How to (Almost) Win](https://medium.com/@td.timodiehm/how-to-almost-win-against-thousands-of-other-teams-in-competitive-environments-bc31387e4b26)

---

## 🧠 Philosophie — Ce qui les distingue vraiment

> *"Once you truly understand a problem, the solution becomes trivial."*

Frankfurt n'a pas cherché les meilleures stratégies. Ils ont cherché à **comprendre exactement comment l'environnement fonctionne**, puis les stratégies sont devenues évidentes.

**Leurs trois principes fondamentaux :**

**1. First-principles avant tout.** Avant d'implémenter quoi que ce soit, ils se demandent : *comment ces données ont-elles pu être générées ?* Si la réponse est "prix aléatoires avec bruit additionnel mean-reverting", alors la stratégie découle directement. Ne jamais partir d'une stratégie et chercher à la justifier après.

**2. Robustesse > performance.** Lors de l'optimisation des paramètres, ils choisissent les **zones plates** du landscape (là où la performance change peu autour de la valeur choisie), pas les pics. Un pic qui vaut 120k en backtest mais s'effondre à -20k avec ±5% de variation est inutilisable. Une zone plate à 80k qui reste entre 70-90k est fiable.

**3. Tests contrôlés de l'environnement.** Avant d'optimiser une stratégie, ils ont conçu des algorithmes spécialement pour *tester le comportement de la simulation*, pas pour trader. "Comment les ordres sont-ils matchés ? À quelle vitesse ? Y a-t-il une séquence ?" Ces tests leur ont révélé des informations que d'autres équipes n'ont jamais découvertes.

---

## 🏗️ Architecture du code

Le code est architecturé autour d'une classe de base `ProductTrader` que chaque stratégie hérite. C'est propre, modulaire, et chaque produit a sa propre logique isolée.

**Structure générale :**
```python
class ProductTrader:        # Base class — gestion position, orders, walls, logging
class StaticTrader(PT):     # Rainforest Resin
class DynamicTrader(PT):    # Kelp
class InkTrader(PT):        # Squid Ink
class EtfTrader:            # Baskets + Constituents (non-héritée, plusieurs PT internes)
class OptionTrader:         # Options + Underlying
class CommodityTrader(PT):  # Magnificent Macarons

class Trader:               # Point d'entrée — instancie tout, collecte les ordres
    def run(self, state):
        ...
```

**Pattern systématique dans chaque trader :**
1. Calculer le `wall_mid` (= vraie fair value)
2. Prendre les ordres favorables (taking)
3. Poster des ordres passifs améliorés (making)
4. Tracker les ordres envoyés dans le timestep pour ne pas dépasser les limits

**Gestion de la mémoire inter-timesteps via `traderData` :**
```python
# Lire la mémoire précédente
self.last_traderData = json.loads(state.traderData)

# Écrire la nouvelle mémoire
self.new_trader_data['MA_KEY'] = value
final_trader_data = json.dumps(new_trader_data)
return result, conversions, final_trader_data
```
Tout ce qui doit persister (EMAs, premiums, timestamps Olivia, historiques) est stocké dans ce dictionnaire JSON sérialisé.

---

## 🔵 ROUND 1 — Market Making

### Concept fondamental : le Wall Mid

**Insight clé de Frankfurt :** La "vraie" valeur d'un produit n'est PAS le mid classique (best_bid + best_ask) / 2. C'est le **Wall Mid** = (worst_bid + worst_ask) / 2.

**Pourquoi ?** Dans la simulation Prosperity, il y a des market makers persistants qui postent à des prix stables reflétant la vraie valeur interne. Ces ordres sont aux **niveaux les plus profonds** du book (worst bid, worst ask). Les ordres proches du mid sont ceux des autres bots qui penny-jump — ils ne reflètent pas la vraie valeur.

```python
def get_walls(self):
    bid_wall = min([x for x, _ in self.mkt_buy_orders.items()])   # prix le plus BAS côté bid
    ask_wall = max([x for x, _ in self.mkt_sell_orders.items()])  # prix le plus HAUT côté ask
    wall_mid = (bid_wall + ask_wall) / 2
    return bid_wall, wall_mid, ask_wall
```

**En pratique :** Si le book montre bids à 9997, 9998, 9999 et asks à 10001, 10002, 10003, le wall_mid = (9997 + 10003) / 2 = 10000. Beaucoup plus stable que (9999 + 10001) / 2 = 10000, mais plus résistant aux manipulations.

---

### Rainforest Resin — `StaticTrader`

**Nature :** Fair value fixe à 10,000. Position limit ±50. Le produit le plus simple.

**Logique en 2 étapes (voir [`StaticTrader.get_orders()`](https://github.com/TimoDiehm/imc-prosperity-3/blob/main/FrankfurtHedgehogs_polished.py)) :**

**Étape 1 — Taking (immédiat, prioritaire) :**
```python
for sp, sv in self.mkt_sell_orders.items():
    if sp <= self.wall_mid - 1:          # Ask SOUS la fair value → BUY immédiatement
        self.bid(sp, sv)
    elif sp <= self.wall_mid and self.initial_position < 0:   # Ask à fair value ET on est short
        volume = min(sv, abs(self.initial_position))          # → réduire la position
        self.bid(sp, volume)

for bp, bv in self.mkt_buy_orders.items():
    if bp >= self.wall_mid + 1:          # Bid AU-DESSUS de la fair value → SELL immédiatement
        self.ask(bp, bv)
    elif bp >= self.wall_mid and self.initial_position > 0:   # Bid à fair value ET on est long
        volume = min(bv, self.initial_position)               # → réduire la position
        self.ask(bp, volume)
```

**Étape 2 — Making (penny jumping) :**
```python
bid_price = int(self.bid_wall + 1)   # fallback : juste au-dessus du wall
ask_price = int(self.ask_wall - 1)   # fallback : juste en-dessous du wall

# Trouver le meilleur bid dans le book qui est encore SOUS le wall_mid
for bp, bv in self.mkt_buy_orders.items():
    overbidding_price = bp + 1
    if bv > 1 and overbidding_price < self.wall_mid:   # Volume suffisant = vrai MM
        bid_price = max(bid_price, overbidding_price)  # On surenchérit d'1 tick
        break
    elif bp < self.wall_mid:
        bid_price = max(bid_price, bp)
        break

# Idem côté ask
for sp, sv in self.mkt_sell_orders.items():
    underbidding_price = sp - 1
    if sv > 1 and underbidding_price > self.wall_mid:
        ask_price = min(ask_price, underbidding_price)
        break
    elif sp > self.wall_mid:
        ask_price = min(ask_price, sp)
        break

self.bid(bid_price, self.max_allowed_buy_volume)
self.ask(ask_price, self.max_allowed_sell_volume)
```

**Pourquoi `bv > 1` ?** Un ordre de volume 1 est probablement un artefact ou un testeur. Un vrai MM place plusieurs unités. En filtrant sur volume > 1, on évite de penny-jumper des ordres insignifiants.

**PnL :** ~39,000 seashells/round. Stable, quasi sans variance.

---

### Kelp — `DynamicTrader`

**Nature :** Random walk lent. Même logique que Resin mais fair value recalculée à chaque timestep.

**Même structure que Resin MAIS avec un twist Olivia :**

Frankfurt a détecté Olivia sur Kelp dès le Round 1 (sans connaître son nom). Quand Olivia a acheté récemment (dans les 500 derniers timesteps), ils se mettent agressivement long jusqu'à position 40 :

```python
if self.informed_bought_ts is not None and self.informed_bought_ts + 500 >= self.state.timestamp:
    if self.initial_position < 40:
        bid_price = self.ask_wall      # prendre agressivement à l'ask wall
        bid_volume = 40 - self.initial_position

# Guard : si on est SHORT et qu'Olivia est short, ne pas penny-jump côté bid
if self.wall_mid - bid_price < 1 and (self.informed_direction == SHORT and self.initial_position > -40):
    bid_price = self.bid_wall         # reculer au wall, pas de penny jump
```

**Intuition :** Si Olivia a acheté il y a moins de 500 timesteps, le prix est probablement encore en train de monter. On sort du mode "passif" (penny jump) pour aller en mode "directionnel" (prendre agressivement).

**PnL :** ~5,000 seashells/round sur le market making pur + extra du signal Olivia.

---

### Squid Ink — `InkTrader`

**Nature :** Volatile, spikes réguliers. Pas de market making ici.

**Stratégie Frankfurt : 100% basée sur Olivia, dès le Round 1.**

```python
def get_orders(self):
    expected_position = 0
    if self.informed_direction == LONG:
        expected_position = self.position_limit    # +50
    elif self.informed_direction == SHORT:
        expected_position = -self.position_limit   # -50

    remaining_volume = expected_position - self.initial_position

    if remaining_volume > 0 and self.ask_wall is not None:
        self.bid(self.ask_wall, remaining_volume)   # prendre à l'ask wall
    elif remaining_volume < 0 and self.bid_wall is not None:
        self.ask(self.bid_wall, -remaining_volume)  # prendre au bid wall
```

**C'est tout.** Pas de market making sur Squid Ink. Si Olivia a acheté → go max long à l'ask wall. Si Olivia a vendu → go max short au bid wall. Si pas de signal → position 0.

**Comment Olivia est détectée sans son nom (Rounds 1-4) :**

```python
def check_for_informed(self):
    # Lire les timestamps du dernier trade Olivia depuis la mémoire
    informed_bought_ts, informed_sold_ts = self.last_traderData.get(self.name, [None, None])

    trades = self.state.market_trades.get(self.name, []) + self.state.own_trades.get(self.name, [])
    for trade in trades:
        if trade.buyer == INFORMED_TRADER_ID:    # 'Olivia' — visible au R5
            informed_bought_ts = trade.timestamp
        if trade.seller == INFORMED_TRADER_ID:
            informed_sold_ts = trade.timestamp

    # Sauvegarder pour le prochain timestep
    self.new_trader_data[self.name] = [informed_bought_ts, informed_sold_ts]

    # Déterminer la direction
    if informed_bought and not informed_sold:     informed_direction = LONG
    elif informed_sold and not informed_bought:   informed_direction = SHORT
    elif informed_bought and informed_sold:
        if informed_sold_ts > informed_bought_ts: informed_direction = SHORT
        else:                                     informed_direction = LONG
    else:                                         informed_direction = NEUTRAL
```

**Avant Round 5 :** Ils trackaient les trades de quantité 15 aux extrêmes de journée. La détection était heuristique. Au Round 5, `INFORMED_TRADER_ID = 'Olivia'` est passé en dur et la détection devient exacte.

**PnL Squid Ink :** ~8,000 seashells/round en moyenne, avec très faible variance grâce au signal fiable.

---

## 🟡 ROUND 2 — ETF Statistical Arbitrage

### Principe de génération de données — La vraie question à se poser

Frankfurt ne s'est pas demandé "comment trader ce basket ?". Ils se sont demandés : **comment ces données ont-elles été générées ?**

Leur hypothèse : les prix des 3 composants sont générés indépendamment (random walk), puis un bruit mean-reverting est ajouté pour créer le prix du basket. Si c'est vrai, alors :
- Les **baskets** mean-révertent vers leur valeur synthétique
- Les **composants** ne réagissent PAS au basket

→ Conséquence directe : trader le basket vers la valeur synthétique, pas l'inverse. Le hedge avec les composants réduit la variance MAIS réduit aussi l'expected value (à cause des spreads), donc hedger partiellement est le bon compromis.

**Erreur à éviter :** Beaucoup d'équipes ont appliqué des z-scores ou des moving average crossovers sans réfléchir au mécanisme. Frankfurt explique : normaliser par la vol rolling n'a de sens que si la vol varie significativement dans le temps — ce qu'elle ne fait pas ici. Et un MA crossover suppose une tendance courte dans un mean-reverting long — incohérent.

---

### Architecture ETF — `EtfTrader`

Pas une classe héritée de `ProductTrader`, mais une classe qui **contient plusieurs** `ProductTrader` :

```python
class EtfTrader:
    def __init__(self, ...):
        self.baskets = [ProductTrader(s, ...) for s in ['PICNIC_BASKET1', 'PICNIC_BASKET2']]
        self.informed_constituent = ProductTrader('CROISSANTS', ...)  # = Croissants (Olivia joue dessus)
        self.hedging_constituents = [ProductTrader(s, ...) for s in ['JAMS', 'DJEMBES']]
```

---

### Calcul du spread — Running Premium

```python
# Pour chaque basket :
constituents_price = croissant_wall_mid * 6 + jam_wall_mid * 3 + djembe_wall_mid * 1  # pour B1
raw_spread = basket_wall_mid - constituents_price

# Mise à jour incrémentale de la premium moyenne (online mean)
old_mean, n = self.last_traderData.get('ETF_0_P', [INITIAL_ETF_PREMIUMS[0], 60_000])
n += 1
mean_premium = old_mean + (raw_spread - old_mean) / n    # Welford's online mean
self.new_trader_data['ETF_0_P'] = [mean_premium, n]

# Spread ajusté = ce qu'on trade réellement
spread = raw_spread - mean_premium
```

**Pourquoi une running premium ?** Les premiums ne sont pas centrées en zéro (B1 ≈ +5, B2 ≈ +53 d'après `INITIAL_ETF_PREMIUMS`). Si on ne soustrait pas la premium moyenne, on trade avec un biais. La running mean corrige ça dynamiquement en temps réel.

**`INITIAL_ETF_PREMIUMS = [5, 53]`** : valeurs hardcodées issues des données historiques, utilisées au démarrage avant que l'online mean ne converge.

---

### Logique de trading ETF

**Seuils fixes (pas de z-score) :**
```python
BASKET_THRESHOLDS = [80, 50]  # B1 : ±80, B2 : ±50
```

**Entrée en position :**
```python
if spread > (threshold + informed_thr_adj):      # basket trop cher → SHORT basket
    basket.ask(basket.bid_wall, max_volume)

elif spread < (-threshold + informed_thr_adj):   # basket trop pas cher → LONG basket
    basket.bid(basket.ask_wall, max_volume)
```

**Clôture à zero-crossing (ETF_CLOSE_AT_ZERO = True) :**
```python
elif ETF_CLOSE_AT_ZERO:
    if spread > informed_thr_adj and basket.initial_position > 0:   # spread revenu positif + on est long
        basket.ask(basket.bid_wall, basket.initial_position)         # → clôturer
    elif spread < informed_thr_adj and basket.initial_position < 0: # spread revenu négatif + on est short
        basket.bid(basket.ask_wall, -basket.initial_position)        # → clôturer
```

**Insight clé :** On ne attend pas que le spread traverse le seuil opposé pour sortir. Dès que le spread repasse à zéro (ajusté pour Olivia), on clôture. Ça réduit la variance et verrouille les profits plus tôt. L'espérance de valeur en sortant à zéro est neutre (pas de momentum à zero-crossing), donc aucun coût en expected value.

---

### Signal Olivia intégré dans les seuils ETF

```python
ETF_THR_INFORMED_ADJS = [90, 90]   # ajustement si Olivia est détectée

informed_thr_adj = {
    LONG:  +90,   # Olivia long Croissants → on biaise vers long basket
    SHORT: -90,   # Olivia short Croissants → on biaise vers short basket
}.get(self.informed_direction, 0)

# Si threshold = 80 et Olivia est SHORT :
# Entry long  : spread < -80 + (-90) = -170  (beaucoup plus difficile d'entrer long)
# Entry short : spread > +80 + (-90) = -10   (très facile d'entrer short)
```

**Intuition :** Si Olivia est short sur les Croissants, le prix des Croissants va baisser → la valeur synthétique du basket va baisser → le spread va augmenter → on veut être short le basket. Donc on abaisse massivement le seuil d'entrée short (-10 au lieu de +80) et on monte le seuil d'entrée long (-170 au lieu de -80).

**C'est la grande différence avec CMU :** Frankfurt utilisait Olivia pour biaiser ses baskets depuis le Round 2. CMU n'a utilisé Olivia que pour les produits individuels au Round 5.

---

### Hedge des composants — Facteur 0.5

```python
ETF_HEDGE_FACTOR = 0.5  # hedge à 50%

for hedging_constituent in self.hedging_constituents:   # Jams, Djembes (pas Croissants)
    expected_hedge_position = 0
    for b_idx, basket in enumerate(self.baskets):
        factor = ETF_CONSTITUENT_FACTORS[b_idx][constituent_idx]
        expected_hedge_position += -basket.expected_position * factor * ETF_HEDGE_FACTOR

    remaining_volume = round(expected_hedge_position - hedging_constituent.initial_position)
    if remaining_volume > 0:   hedging_constituent.bid(ask_wall, remaining_volume)
    elif remaining_volume < 0: hedging_constituent.ask(bid_wall, -remaining_volume)
```

**Pourquoi 50% ?** Frankfurt voit ça comme : toute stratégie = combinaison linéaire de "fully hedged" et "fully unhedged". 50% c'est le compromis équilibré. Le fully hedge réduit la variance mais réduit l'expected value (spreads des constituants à payer). Le unhedged maximise l'EV mais expose à plus de bruit. 50% = minimum de regret dans les deux scénarios.

**Note : Croissants est traité séparément** (c'est `informed_constituent`). Il est tradé directement sur signal Olivia, pas utilisé comme hedge des baskets.

---

### Sélection des paramètres — Landscape stability

Frankfurt ne choisit PAS le paramètre avec le PnL backtest maximal. Ils regardent la **carte 2D des PnL** en fonction des paramètres et choisissent une région plate (bonne performance sur une large zone). 

Si tu as un pic à (threshold=47, adj=92) qui performe à 120k mais que (46, 92) donne 30k et (48, 92) donne -10k → inutilisable. Une zone plate à 75k dans tout le voisinage est bien plus robuste en live.

**PnL Round 2 :** 40k-60k seashells/round sur les baskets + 20k/round sur Croissants direct = **60k-80k/round** total.

---

## 🔴 ROUND 3 — IV Scalping + Mean Reversion Hybride

### Vision générale : deux alpha sources indépendantes

Frankfurt a combiné deux stratégies indépendantes sur les options et l'underlying :
1. **IV Scalping** (stable, 100k-150k/round) — la source principale
2. **Mean Reversion** (volatile, +100k/-50k/-10k) — hedge relatif contre d'autres équipes

L'idée : deux flux d'alpha non-corrélés > un seul. Et si d'autres équipes ne trouvent pas le IV scalping, elles vont all-in sur la mean reversion → maintenir une position mean reversion est un hedge *relatif* contre elles.

---

### IV Scalping — `OptionTrader.get_iv_scalping_orders()`

**Étape 1 — Calculer la théoretical option value**

```python
def get_option_values(self, S, K, TTE):
    def get_iv(St, K, TTE):
        m_t_k = np.log(K/St) / TTE**0.5           # moneyness
        coeffs = [0.27362531, 0.01007566, 0.14876677]  # fitted parabole du smile
        iv = np.poly1d(coeffs)(m_t_k)
        return iv

    iv = get_iv(S, K, TTE)
    bs_call_value, delta = bs_call(S, K, TTE, iv)
    vega = bs_vega(S, K, TTE, iv)
    return bs_call_value, delta, vega
```

**Les coefficients `[0.27362531, 0.01007566, 0.14876677]`** sont hardcodés — ils ont fitté la parabole `v = a*m² + b*m + c` sur les données historiques avant la compétition. C'est la différence avec CMU qui refittait à chaque fois et dont le fit a divergé.

**Étape 2 — Calculer le theo_diff et son EMA**

```python
option_theo_diff = option.wall_mid - option_theo         # écart actuel prix marché vs théorique
new_mean_diff = calculate_ema(f'{option.name}_theo_diff', THEO_NORM_WINDOW=20, option_theo_diff)
new_mean_avg_dev = calculate_ema(f'{option.name}_avg_devs', IV_SCALPING_WINDOW=100, abs(option_theo_diff - new_mean_diff))
```

**`mean_theo_diff`** = EMA(20) de l'écart → donne le "biais moyen" de l'option par rapport au théorique.  
**`switch_mean`** = EMA(100) de |écart - biais| → mesure l'amplitude typique des fluctuations autour du biais.

**Étape 3 — Trading sur déviations**

```python
IV_SCALPING_THR = 0.7   # threshold pour activer le scalping

if switch_mean >= IV_SCALPING_THR:   # il y a assez de mouvement pour scalper
    # Calculer la déviation nette (normalisée par le mid)
    deviation = current_theo_diff - option.wall_mid + option.best_bid - mean_theo_diff

    if deviation >= THR_OPEN (0.5) + low_vega_adj:   # option trop chère → SHORT
        option.ask(option.best_bid, max_sell_volume)

    if deviation >= THR_CLOSE (0):    # spread revenu à zéro → fermer les longs
        option.ask(option.best_bid, initial_long_position)

    elif deviation <= -(THR_OPEN + low_vega_adj):    # option trop pas chère → LONG
        option.bid(option.best_ask, max_buy_volume)

    if deviation <= -THR_CLOSE:       # spread revenu à zéro → fermer les shorts
        option.bid(option.best_ask, -initial_short_position)
else:
    # Pas assez de signal → fermer toutes les positions existantes
    if option.initial_position > 0: option.ask(best_bid, initial_position)
    if option.initial_position < 0: option.bid(best_ask, -initial_position)
```

**Ajustement low vega :** Si la vega de l'option est ≤ 1 (options très deep OTM ou près de l'expiration), les prix fluctuent davantage pour des raisons techniques. On augmente le seuil d'entrée de `LOW_VEGA_THR_ADJ = 0.5` pour éviter les faux signaux.

**Quelles options sont scalpées ?** Tous les vouchers avec strike ≥ 9750 (les 4 moins profond ITM). Le voucher 9500 est réservé à la mean reversion (voir ci-dessous).

**PnL IV Scalping :** 100k-150k seashells/round. Très stable (PnL en quasi-ligne droite en backtest).

---

### Mean Reversion — Underlying + Options

**Mean reversion sur l'underlying (Volcanic Rock) :**

```python
# EMA court terme sur le prix de l'underlying
ema_u_dev = underlying.wall_mid - calculate_ema('ema_u', window=10, value=underlying.wall_mid)

# Si le prix a dévié de plus de 15 seashells de sa moyenne courte → MR
if ema_u_dev > 15:    # prix trop haut → SHORT underlying
    underlying.ask(bid_wall + 1, max_sell_volume)
elif ema_u_dev < -15: # prix trop bas → LONG underlying
    underlying.bid(ask_wall - 1, max_buy_volume)
```

**Mean reversion sur l'option deep ITM (voucher 9500) :**

```python
# EMA long terme sur l'underlying (window = 30)
ema_o_dev = underlying.wall_mid - calculate_ema('ema_o', window=30, value=underlying.wall_mid)

# Combiner avec la déviation IV de l'option 9500
iv_deviation = current_theo_diff_9500 - mean_theo_diff_9500
combined_deviation = ema_o_dev + iv_deviation

if combined_deviation > 5:    # prix combiné trop haut → SHORT call
    option_9500.ask(best_bid, max_sell_volume)
elif combined_deviation < -5: # prix combiné trop bas → LONG call
    option_9500.bid(best_ask, max_buy_volume)
```

**Pourquoi le voucher 9500 (deep ITM) pour la mean reversion ?** C'est l'option avec le delta le plus proche de 1 — elle se comporte quasi comme un "leveraged underlying". Quand on est convaincu que l'underlying va mean-revenir, prendre une position sur cet option donne plus d'exposition directionnelle que l'underlying lui-même (grâce au levier implicite), mais avec moins de capital immobilisé.

---

### Décision finale R5 — Garder la mean reversion comme hedge relatif

Après Round 4, la mean reversion avait perdu 50k. Frankfurt ne croyait plus à sa validité empirique. Mais ils ont quand même gardé une exposition réduite pour le Round 5. Leur raisonnement :

> "Les équipes qui faisaient uniquement de la mean reversion allaient sûrement continuer. Si on ne la fait plus et qu'elles gagnent à ce round, elles nous rattrapent. En maintenant une position partielle, on se hedge *relativement* contre elles. Notre VaR à 95% sur la MR est ~50k = 25% de notre avance de 190k. Acceptable."

C'est un exemple pur de **risk management relatif** (optimiser sa position dans le classement) vs **risk management absolu** (maximiser son PnL attendu).

---

## 🟢 ROUND 4 — Locational Arbitrage (Macarons)

### Mécanisme des Macarons — `CommodityTrader`

**Deux marchés :**
- **Local island** : order book standard
- **Pristine Island** : prix fixes `ex_bid`/`ex_ask` + frais à la conversion

**Frais de conversion :**
```python
ex_ask = ex_raw_ask + import_tariff + transport_fees   # coût d'import (couvrir une short)
ex_bid = ex_raw_bid - export_tariff - transport_fees   # revenu d'export (couvrir une long)
```

L'`import_tariff` est **négatif** (~-3). Donc `ex_ask` est plus BAS que `ex_raw_ask`. C'est la source de profit.

---

### Stratégie Frankfurt — Deux arbitrages + buyer caché

**Short arbitrage (le principal) :** Vendre localement, couvrir sur Pristine Island via import.

```python
local_sell_price = math.floor(ex_raw_bid + 0.5)   # prix auquel le buyer caché prend
ex_ask = ex_raw_ask + import_tariff + transport_fees  # coût de couverture

short_arbitrage = local_sell_price - ex_ask         # profit par macaron
```

**Long arbitrage (le secondaire) :** Acheter localement, exporter vers Pristine Island.

```python
local_buy_price = math.ceil(ex_raw_ask - 0.5)
ex_bid = ex_raw_bid - export_tariff - transport_fees  # revenu de l'export

long_arbitrage = ex_bid - local_buy_price - 0.1     # -0.1 pour le storage
```

**Filtre sur l'historique :** Avant de trader, vérifier que l'arb est rentable en moyenne sur les 10 derniers timesteps :
```python
short_arbs_hist = self.last_traderData.get('SA', [])[-10:]  # garder 10 dernières valeurs
mean_short_arb = np.mean(short_arbs_hist)

if short_arbitrage >= 0 and mean_short_arb > 0:   # arb rentable maintenant ET en moyenne
    # → trader
```

**Logique de pricing — le buyer caché :**

```python
remaining_volume = CONVERSION_LIMIT  # 10 unités

# D'abord essayer de vendre aux bids existants dans le book
# si le price discount est < 42% de l'arb total → profitable
for bp, bv in self.mkt_buy_orders.items():
    if (short_arbitrage - (local_sell_price - bp)) > (0.58 * short_arbitrage):
        v = min(remaining_volume, bv)
        self.ask(bp, v)
        remaining_volume -= v
    else:
        break

# Pour le reste, vendre au prix du buyer caché
if remaining_volume > 0:
    self.ask(local_sell_price, remaining_volume)
```

**Insight du `0.58 * short_arbitrage` :** Frankfurt tolère de vendre jusqu'à 42% moins bien que le prix optimal (`local_sell_price`) — tant que l'arb reste positif. Ça augmente les fills en allant chercher des ordres déjà dans le book, sans sacrifier la rentabilité.

**Gestion de la conversion :**
```python
self.conversions = max(min(-self.initial_position, CONVERSION_LIMIT), -CONVERSION_LIMIT)
```
On convertit max 10 unités par timestep pour annuler notre position short. Borné par ±10.

**PnL :** 80k-100k seashells/round (légèrement moins que le théorique de 130-160k à cause du sizing conservateur de 10 unités au lieu de 20-30).

---

## ⚪ ROUND 5 — Trader IDs (finalisation)

**Changement majeur :** `INFORMED_TRADER_ID = 'Olivia'` est maintenant utilisé directement dans `check_for_informed()` pour un matching exact au lieu de la détection heuristique.

**Ajustements Round 5 :**
- Remplacé la détection heuristique par check direct du `trade.buyer == 'Olivia'`
- Élimination des faux positifs → quelques centaines de seashells gagnés
- Hedging baskets à 50% maintenu (ETF_HEDGE_FACTOR = 0.5)
- Mean reversion maintenue à exposition réduite (hedge relatif vs autres équipes)
- Re-optimisation de tous les paramètres sur les données les plus récentes

---

## 📊 Manual — Approche par round

### Round 1 : FX Arbitrage
BFS sur le graphe de devises. Cycle optimal : SeaShells → Snowballs → Silicon Nuggets → Pizzas → Snowballs → SeaShells = **+8.87%**.

### Round 2 : Containers
Monte Carlo Nash → tous les conteneurs convergent vers ~7-9k EV. Ouverture d'un 2e conteneur toujours négatif. Choix : ×80 (chiffre "ennuyeux" → moins de biais cognitif).

### Round 3 : Reserve Price
Bid 1 = 240 (optimum analytique sur U[160,200]). Bid 2 = 303 — Frankfurt a **sur-estimé** la sophistication des joueurs. La moyenne réelle était 287 → ils se sont retrouvés au-dessus, donc zéro pénalité, mais marge plus faible.

### Round 4 : Suitcases
Nash EV ≈ 56k > coût du 2e (50k) → ouvrir 2 valises est marginalement positif. Priors mis à jour après les données Discord de R2. Résultat : ~85k.

### Round 5 : News Trading
Tableau produits / mouvements estimés / allocations. Résultat : 126k (vs optimum 194k). Principales erreurs : sous-estimation Red Flags (+50.9% vs +15% estimé) et Solar Panels.

---

## 🔑 Résumé des insights uniques Frankfurt

### 1. Backtesting — Deux outils, deux usages

Frankfurt avait une règle simple :
- Stratégies dépendant du comportement des bots (Resin, Kelp, Macarons) → valider sur le **site officiel Prosperity**
- Tout le reste → **backtester Jasper** (plus flexible, plus rapide, grid search facile)

**JAMAIS optimiser uniquement pour le score du site officiel** — trop sujet à l'overfitting sur la stochasticité de la simulation.

### 2. Leur dashboard custom

Ils ont construit un dashboard from scratch (pas le visualiseur Jasper) avec :
- Visualisation des niveaux bid/ask colorés (rouge/bleu) dans le temps
- Overlay d'indicateurs custom (WallMid, spread ETF, etc.)
- Normalisation par un indicateur → rend les séries stationnaires visuellement
- Filtrage des trades par trader ID, volume, type (maker/taker)

Ce dashboard leur a permis de détecter Olivia visuellement dès Round 1.

### 3. Test du random seed

Ils ont tenté de reverse-engineer le générateur aléatoire en comparant les premiers 100 returns observés aux séquences générées par tous les 4 milliards de seeds possibles. L'idée : si les données viennent d'un PRNG, connaître le seed = connaître le futur. Ils n'ont pas réussi à le faire fonctionner dans le temps imparti.

### 4. Hardcoding — La controverse et leur position

Dans les Rounds 1-2, ils ont **implémenté** le frontrunning des bots (comportements identiques à P2), mais avec un fallback automatique. Ils ont ensuite **signalé** l'exploit à IMC. IMC a banni la pratique à partir de R3 et relancé les rounds. Une des équipes qui les a dépassés à la fin avait aussi utilisé le hardcoding en R1-R2 — sans le signalement de Frankfurt, ces équipes auraient perdu leur avantage au re-run.

---

## 🏆 Résultats finaux

| Round | Classement | Notes |
|---|---|---|
| R1 | **1er** | Après re-run |
| R2 | **1er** | Après re-run |
| R3 | **1er** | ~100-150k IV scalping + ~100k MR |
| R4 | **1er** | ~80-100k macarons |
| R5 | **2e** | Heisenberg #1 avec +800k inexpliqué |
| **Final** | **2e mondial** | 1,433,876 seashells |

**PnL approximatif par produit/round :**
- Rainforest Resin : ~39k/round
- Kelp : ~5k/round
- Squid Ink (Olivia) : ~8k/round
- Baskets + Croissants : ~60-80k/round
- IV Scalping : ~100-150k/round
- Mean Reversion : +100k / -50k / -10k (R3/R4/R5)
- Macarons : ~80-100k/round

---

## ⚡ Ce qu'il faut retenir pour Prosperity 4

1. **Implémenter le Wall Mid immédiatement** — pas le mid classique. C'est la base de tout.

2. **Ne jamais appliquer un z-score ou une MA sans se demander pourquoi** — la justification théorique doit précéder l'implémentation, pas la suivre.

3. **Chercher Olivia (ou son équivalent) dès Round 1** — analyser les patterns de volume (quantité fixe, timing aux extrêmes) avant même que les IDs ne soient révélés.

4. **Choisir les paramètres dans les zones plates** — grid search + visualisation 2D de la heatmap de PnL. Ne jamais prendre le pic.

5. **La running premium** pour les ETF — le spread n'est pas centré en zéro. Calculer la moyenne online et soustraire dynamiquement.

6. **Macarons : chercher le buyer caché dès que le produit apparaît** — poser des orders à `floor(mid_pristine + 0.5)` et regarder s'ils se font fill.

7. **ETF close at zero** — ne pas attendre le seuil opposé pour sortir. Dès que le spread repasse zéro (ajusté), clôturer.

8. **Deux backtesting tools, deux usages** — site officiel pour les interactions bot, Jasper pour tout le reste.

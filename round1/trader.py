"""
Prosperity 4 — Round 1 Trader
Products: ASH_COATED_OSMIUM (ACO) + INTARIAN_PEPPER_ROOT (IPR)

Architecture: Frankfurt Hedgehogs (P3 #2 worldwide) — 3-step pattern per product.
  Step 1 — Fair Value Taker  : cross anything mispriced vs fair value
  Step 2 — Position Reducer  : close position when price returns to fair value
  Step 3 — Penny Jump Maker  : passive quotes at best_bid+1 / best_ask-1

Key insight: Wall Mid = (worst_bid + worst_ask) / 2 is the true fair value anchor.
The persistent market maker quotes at the walls — those are the "true" prices.
Near-mid orders are noise from other bots penny-jumping.

EDA findings:
  ACO: FV fixed at 10 000. Autocorr lag-1 = -0.495 (strong mean reversion).
       ~1745 spikes ≥5 pts/day. Post-spike: price stays -4 from peak for 20+ steps.
       Spread = 16 pts → walls at ≈FV±8. Taking captures spikes; making captures edges.
  IPR: FV = linear trend (+0.001/ts, +1000/day). Wall mid tracks it exactly.
       Spread = 13 pts. Standard Frankfurt MM around wall_mid.
"""

import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional

# ═══════════════════════════════════════════════════════════
# PARAMETERS
# ═══════════════════════════════════════════════════════════
POSITION_LIMITS = {
    "ASH_COATED_OSMIUM":    80,
    "INTARIAN_PEPPER_ROOT": 80,
}

ACO_FV         = 10000   # known fixed fair value
IPR_TAKE_WIDTH = 1.5     # take IPR asks/bids if they are ≥1.5 pts inside wall_mid


# ═══════════════════════════════════════════════════════════
# BASE CLASS
# ═══════════════════════════════════════════════════════════
class ProductTrader:
    """
    One instance per product per timestep.
    Tracks intra-timestep orders sent so bid() / ask() never breach position limits.
    """

    def __init__(self, symbol: str, state: TradingState):
        self.symbol   = symbol
        self.limit    = POSITION_LIMITS[symbol]
        self.position = state.position.get(symbol, 0)

        od: OrderDepth = state.order_depths.get(symbol, OrderDepth())
        self.bids = dict(sorted(od.buy_orders.items(),  reverse=True))  # high→low
        self.asks = dict(sorted(od.sell_orders.items()))                # low→high

        self.bid_wall:  Optional[int]   = None
        self.ask_wall:  Optional[int]   = None
        self.wall_mid:  Optional[float] = None
        self.best_bid:  Optional[int]   = None
        self.best_ask:  Optional[int]   = None

        self._buy_sent  = 0
        self._sell_sent = 0
        self._orders: List[Order] = []
        self._parse_book()

    def _parse_book(self):
        if self.bids:
            self.best_bid = max(self.bids.keys())
            self.bid_wall = min(self.bids.keys())   # worst (lowest) bid = wall
        if self.asks:
            self.best_ask = min(self.asks.keys())
            self.ask_wall = max(self.asks.keys())   # worst (highest) ask = wall
        if self.bid_wall is not None and self.ask_wall is not None:
            self.wall_mid = (self.bid_wall + self.ask_wall) / 2

    @property
    def max_buy(self) -> int:
        return max(0, self.limit - self.position - self._buy_sent)

    @property
    def max_sell(self) -> int:
        return max(0, self.limit + self.position - self._sell_sent)

    def bid(self, price: int, volume: int):
        v = min(volume, self.max_buy)
        if v > 0:
            self._orders.append(Order(self.symbol, int(price), v))
            self._buy_sent += v

    def ask(self, price: int, volume: int):
        v = min(volume, self.max_sell)
        if v > 0:
            self._orders.append(Order(self.symbol, int(price), -v))
            self._sell_sent += v

    def _passive_bid(self, fv: float) -> int:
        """
        Penny jump: find the highest resting bid strictly below fv, bid at +1.
        Frankfurt filter: skip volume-1 orders (likely test probes, not real MMs).
        Fallback: bid_wall + 1.
        """
        result = self.bid_wall + 1
        for bp, bv in sorted(self.bids.items(), reverse=True):
            jump = bp + 1
            if jump < fv:
                result = max(result, jump if bv > 1 else bp)
                break
            elif bp < fv:
                result = max(result, bp)
                break
        return result

    def _passive_ask(self, fv: float) -> int:
        """Mirror of _passive_bid for the ask side."""
        result = self.ask_wall - 1
        for sp, sq in sorted(self.asks.items()):
            sv = abs(sq)
            jump = sp - 1
            if jump > fv:
                result = min(result, jump if sv > 1 else sp)
                break
            elif sp > fv:
                result = min(result, sp)
                break
        return result

    def get_orders(self) -> List[Order]:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════
# ACO — STATIC FAIR VALUE  (Frankfurt StaticTrader equivalent)
# ═══════════════════════════════════════════════════════════
class ACOTrader(ProductTrader):
    """
    ASH_COATED_OSMIUM  |  Fair value = 10 000 (fixed, known).

    Book structure (EDA):
      - Walls at ≈ FV±8  (bid_wall ≈ 9992, ask_wall ≈ 10008)
      - Spread ≈ 16 pts, concentrated at that level across all 3 days
      - ~1745 spikes ≥5 pts/day → bids/asks cross the wall temporarily

    Hidden pattern: after a spike ≥5, price stays ≈ FV±4 for 20+ timesteps.
    This means spikes are profitable to fade and the elevated phase is also tradeable
    (bids stay above FV+1 for many steps → taking keeps selling).

    Order flow:
      [Step 1] Fair value taker  — sell bids > FV, buy asks < FV
      [Step 2] Position reducer  — close at FV if position is non-zero
      [Step 3] Penny jump maker  — passive quotes at FV±(1 to 7)
    """

    def __init__(self, state: TradingState):
        super().__init__("ASH_COATED_OSMIUM", state)

    def get_orders(self) -> List[Order]:
        if self.wall_mid is None:
            return []

        fv = float(ACO_FV)   # 10 000.0

        # ── STEP 1: FAIR VALUE TAKER ──────────────────────────────
        # Buy any ask that is STRICTLY BELOW fair value (mispriced too cheap)
        for sp, sq in sorted(self.asks.items()):
            sv = abs(sq)
            if sp < fv:
                self.bid(sp, sv)
            else:
                break   # sp ≥ fv — stop (asks only get more expensive from here)

        # Sell any bid that is STRICTLY ABOVE fair value (mispriced too expensive)
        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp > fv:
                self.ask(bp, bv)
            else:
                break   # bp ≤ fv — stop

        # ── STEP 2: POSITION REDUCER AT FAIR VALUE ────────────────
        # If we're short AND there's an ask exactly AT fair value → buy to reduce
        for sp, sq in sorted(self.asks.items()):
            sv = abs(sq)
            if sp == int(fv) and self.position < 0:
                reduce = min(sv, max(0, -self.position - self._buy_sent))
                if reduce > 0:
                    self.bid(sp, reduce)
            elif sp > int(fv):
                break

        # If we're long AND there's a bid exactly AT fair value → sell to reduce
        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp == int(fv) and self.position > 0:
                reduce = min(bv, max(0, self.position - self._sell_sent))
                if reduce > 0:
                    self.ask(bp, reduce)
            elif bp < int(fv):
                break

        # ── STEP 3: PENNY JUMP MAKER ──────────────────────────────
        # Post passive quotes one tick inside the best resting orders,
        # but never at or beyond fair value.
        bid_price = self._passive_bid(fv)
        ask_price = self._passive_ask(fv)

        # Hard guards: bid must be strictly below FV, ask strictly above FV
        bid_price = min(bid_price, int(fv) - 1)
        ask_price = max(ask_price, int(fv) + 1)

        if bid_price < ask_price:
            self.bid(bid_price, self.max_buy)
            self.ask(ask_price, self.max_sell)

        return self._orders


# ═══════════════════════════════════════════════════════════
# IPR — DYNAMIC FAIR VALUE  (Frankfurt DynamicTrader equivalent)
# ═══════════════════════════════════════════════════════════
class IPRTrader(ProductTrader):
    """
    INTARIAN_PEPPER_ROOT  |  Fair value = wall_mid (tracks trend perfectly).

    The fair value drifts at +0.001/timestep (+1000/day). The persistent market
    maker updates their wall quotes with the trend, so wall_mid = (bid_wall + ask_wall)/2
    is always the correct fair value anchor — no need to know which day it is.

    Book structure (EDA):
      - Spread ≈ 13 pts → walls ≈ FV±6.5
      - Deviation of mid around trend: std = 2.2 (very tight)
      - Pure random walk + drift; no spikes, no mean reversion

    Order flow: identical to ACO but with a moving fair value.
      [Step 1] Fair value taker  — sell bids > wall_mid, buy asks < wall_mid
      [Step 2] Position reducer  — close near wall_mid if position is non-zero
      [Step 3] Penny jump maker  — passive quotes at wall_mid ± (1 to 5)
    """

    def __init__(self, state: TradingState):
        super().__init__("INTARIAN_PEPPER_ROOT", state)

    def get_orders(self) -> List[Order]:
        if self.wall_mid is None:
            return []

        fv = self.wall_mid   # float, e.g. 12000.5

        # ── STEP 1: FAIR VALUE TAKER ──────────────────────────────
        for sp, sq in sorted(self.asks.items()):
            sv = abs(sq)
            if sp <= fv - IPR_TAKE_WIDTH:
                self.bid(sp, sv)
            else:
                break

        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp >= fv + IPR_TAKE_WIDTH:
                self.ask(bp, bv)
            else:
                break

        # ── STEP 2: POSITION REDUCER AT FAIR VALUE ────────────────
        for sp, sq in sorted(self.asks.items()):
            sv = abs(sq)
            if sp <= fv and self.position < 0:
                reduce = min(sv, max(0, -self.position - self._buy_sent))
                if reduce > 0:
                    self.bid(sp, reduce)
            elif sp > fv:
                break

        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp >= fv and self.position > 0:
                reduce = min(bv, max(0, self.position - self._sell_sent))
                if reduce > 0:
                    self.ask(bp, reduce)
            elif bp < fv:
                break

        # ── STEP 3: PENNY JUMP MAKER ──────────────────────────────
        bid_price = self._passive_bid(fv)
        ask_price = self._passive_ask(fv)

        # Largest int strictly below fv, smallest int strictly above fv
        bid_price = min(bid_price, math.ceil(fv) - 1)
        ask_price = max(ask_price, math.floor(fv) + 1)

        if bid_price < ask_price:
            self.bid(bid_price, self.max_buy)
            self.ask(ask_price, self.max_sell)

        return self._orders


# ═══════════════════════════════════════════════════════════
# MAIN TRADER — entry point called by the exchange each timestep
# ═══════════════════════════════════════════════════════════
class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = ACOTrader(state).get_orders()

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = IPRTrader(state).get_orders()

        return result, 0, json.dumps({})

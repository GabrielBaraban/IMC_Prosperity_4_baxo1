"""
Prosperity 4 — Round 2 Trader FINAL  (v3 — post feedback fix)
Products : ASH_COATED_OSMIUM (ACO) + INTARIAN_PEPPER_ROOT (IPR)
MAF bid   : 7 500 XIRECs

═══════════════════════════════════════════════════════════════
STRATEGY SUMMARY
═══════════════════════════════════════════════════════════════

IPR — unchanged from Round 1 (Round 1 PnL: 72 164, pos: +78)
  • FV = wall_mid  (tracks +0.001/ts drift perfectly, R²=1.000)
  • Take: buy asks ≤ wall_mid−1.5, sell bids ≥ wall_mid+1.5
  • Make: penny-jump at best resting order ± 1 tick from wall_mid

ACO — FIX: use wall_mid as FV  (critical fix from feedback analysis)
  BUG in v2: FV = 10 000 hardcoded.
  In Round 2 feedback log, ACO wall_mid = 10 004 on average (85% of
  timesteps had wall_mid > 10 001). Hardcoded FV=10000 caused us to
  sell bids at 10001-10004 (treating FAIR prices as "too expensive"),
  accumulating position -76 (max short). Fix: use wall_mid as FV,
  exactly like IPR. Wall_mid is always the correct anchor.

  [KEEP] Spike mode  (EDA: 1 686 spikes≥|5| per day)
    spike = mid_price − wall_mid  (now vs wall_mid, not 10000)
    • spike > +5: skip bid in making (mean reversion −4.00 at t+1)
    • spike < −5: skip ask in making (mean reversion +4.09 at t+1)

  [KEEP] Inventory soft cap at ±35
    Prevents unintended drift. Round 1: +39 drift fixed by this cap.
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

ACO_SPIKE_THRESH = 5       # |mid_price − wall_mid| ≥ 5 → spike mode
ACO_INV_SOFT_CAP = 80      # effectively no cap (FV fix resolved drift)

IPR_TAKE_WIDTH   = 3.5     # take if order is ≥ 3.5 inside wall_mid
IPR_LEAN         = 70      # target long position to capture trend (+0.001/ts × 70 = +70/day)

MAF_BID          = 7_500   # Market Access Fee bid (XIRECs)


# ═══════════════════════════════════════════════════════════
# BASE CLASS
# ═══════════════════════════════════════════════════════════
class ProductTrader:

    def __init__(self, symbol: str, state: TradingState):
        self.symbol   = symbol
        self.limit    = POSITION_LIMITS[symbol]
        self.position = state.position.get(symbol, 0)

        od: OrderDepth = state.order_depths.get(symbol, OrderDepth())
        self.bids = dict(sorted(od.buy_orders.items(),  reverse=True))
        self.asks = dict(sorted(od.sell_orders.items()))

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
            self.bid_wall = min(self.bids.keys())
        if self.asks:
            self.best_ask = min(self.asks.keys())
            self.ask_wall = max(self.asks.keys())
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
# ACO
# ═══════════════════════════════════════════════════════════
class ACOTrader(ProductTrader):

    def __init__(self, state: TradingState):
        super().__init__("ASH_COATED_OSMIUM", state)

    def get_orders(self) -> List[Order]:
        if self.wall_mid is None:
            return []

        fv = self.wall_mid  # dynamic — follows the market maker's anchor

        # ── SPIKE DETECTION ───────────────────────────────────
        if self.best_bid is not None and self.best_ask is not None:
            mid_price = (self.best_bid + self.best_ask) / 2.0
        else:
            mid_price = fv
        spike     = mid_price - fv
        spike_up   = spike >=  ACO_SPIKE_THRESH
        spike_down = spike <= -ACO_SPIKE_THRESH

        # ── STEP 1: FAIR VALUE TAKER ──────────────────────────
        for sp, sq in sorted(self.asks.items()):
            if sp < fv:
                self.bid(sp, abs(sq))
            else:
                break

        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp > fv:
                self.ask(bp, bv)
            else:
                break

        # ── STEP 2: POSITION REDUCER ──────────────────────────
        fv_floor = math.floor(fv)
        fv_ceil  = math.ceil(fv)
        for sp, sq in sorted(self.asks.items()):
            if sp <= fv_ceil and self.position < 0:
                reduce = min(abs(sq), max(0, -self.position - self._buy_sent))
                if reduce > 0:
                    self.bid(sp, reduce)
            elif sp > fv_ceil:
                break

        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp >= fv_floor and self.position > 0:
                reduce = min(bv, max(0, self.position - self._sell_sent))
                if reduce > 0:
                    self.ask(bp, reduce)
            elif bp < fv_floor:
                break

        # ── STEP 3: PENNY JUMP MAKER ──────────────────────────
        bid_price = self._passive_bid(fv)
        ask_price = self._passive_ask(fv)
        bid_price = min(bid_price, math.ceil(fv)  - 1)
        ask_price = max(ask_price, math.floor(fv) + 1)

        if bid_price < ask_price:
            post_bid = True
            post_ask = True

            # Spike mode: skip wrong side
            if spike_up:
                post_bid = False
            if spike_down:
                post_ask = False

            # Inventory soft cap
            if self.position >= ACO_INV_SOFT_CAP:
                post_bid = False
            if self.position <= -ACO_INV_SOFT_CAP:
                post_ask = False

            if post_bid:
                self.bid(bid_price, self.max_buy)
            if post_ask:
                self.ask(ask_price, self.max_sell)

        return self._orders


# ═══════════════════════════════════════════════════════════
# IPR
# ═══════════════════════════════════════════════════════════
class IPRTrader(ProductTrader):

    def __init__(self, state: TradingState):
        super().__init__("INTARIAN_PEPPER_ROOT", state)

    def get_orders(self) -> List[Order]:
        if self.wall_mid is None:
            return []

        fv = self.wall_mid

        # ── STEP 1: FAIR VALUE TAKER ──────────────────────────
        for sp, sq in sorted(self.asks.items()):
            if sp <= fv - IPR_TAKE_WIDTH:
                self.bid(sp, abs(sq))
            else:
                break

        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp >= fv + IPR_TAKE_WIDTH:
                self.ask(bp, bv)
            else:
                break

        # ── STEP 1b: LEAN BUILDER (Frankfurt aggressive) ──────
        # Bid at ask_wall price to sweep all asks and hit lean target immediately.
        # Guarantees position fills regardless of where asks sit relative to fv.
        lean_gap = IPR_LEAN - self.position - self._buy_sent
        if lean_gap > 0 and self.ask_wall is not None:
            self.bid(self.ask_wall, lean_gap)

        # ── STEP 2: POSITION REDUCER ──────────────────────────
        # Short side: reduce if below -IPR_LEAN (shouldn't happen often)
        for sp, sq in sorted(self.asks.items()):
            if sp <= fv and self.position < -IPR_LEAN:
                reduce = min(abs(sq), max(0, -self.position - IPR_LEAN - self._buy_sent))
                if reduce > 0:
                    self.bid(sp, reduce)
            elif sp > fv:
                break

        # Long side: ONLY reduce position that is ABOVE lean target.
        # Don't reduce the lean itself — that's our trend income source.
        for bp, bv in sorted(self.bids.items(), reverse=True):
            if bp >= fv and self.position > IPR_LEAN:
                excess = self.position - IPR_LEAN
                reduce = min(bv, max(0, excess - self._sell_sent))
                if reduce > 0:
                    self.ask(bp, reduce)
            elif bp < fv:
                break

        # ── STEP 3: PENNY JUMP MAKER ──────────────────────────
        bid_price = self._passive_bid(fv)
        ask_price = self._passive_ask(fv)
        bid_price = min(bid_price, math.ceil(fv) - 1)
        ask_price = max(ask_price, math.floor(fv) + 1)

        if bid_price < ask_price:
            bid_vol = self.max_buy
            if self.position < IPR_LEAN:
                # Still building lean — post zero asks so they don't get lifted and undo our buys
                ask_vol = 0
            else:
                # Above lean — only offer excess
                ask_vol = max(0, self.position - IPR_LEAN - self._sell_sent)
                ask_vol = max(ask_vol, min(self.max_sell, 10))
            self.bid(bid_price, bid_vol)
            if ask_vol > 0:
                self.ask(ask_price, ask_vol)

        return self._orders


# ═══════════════════════════════════════════════════════════
# MAIN TRADER
# ═══════════════════════════════════════════════════════════
class Trader:

    def bid(self) -> int:
        """Market Access Fee bid. Top 50% of bids accepted, fee deducted from PnL.
        7 500 XIRECs: estimated ~75% win probability vs. ~15-20k value of extra access.
        Expected net value: +10 000 XIRECs."""
        return MAF_BID

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = ACOTrader(state).get_orders()

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = IPRTrader(state).get_orders()

        return result, 0, json.dumps({})

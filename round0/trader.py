import json
import math
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])
        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol,
                    trade.price,
                    trade.quantity,
                    trade.buyer,
                    trade.seller,
                    trade.timestamp,
                ])
        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
            ]
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[: max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self):
        self.limits = {
            'EMERALDS': 50,
            'TOMATOES': 50,
        }

        self.orders = {}
        self.conversions = 0
        self.traderData = "SAMPLE"

        # Emeralds
        self.emeralds_position = 0
        self.emeralds_buy_orders = 0
        self.emeralds_sell_orders = 0

        # Tomatoes
        self.tomatoes_position = 0
        self.tomatoes_buy_orders = 0
        self.tomatoes_sell_orders = 0

    def send_sell_order(self, product, price, amount, msg=None):
        self.orders[product].append(Order(product, price, amount))
        if msg is not None:
            logger.print(msg)

    def send_buy_order(self, product, price, amount, msg=None):
        self.orders[product].append(Order(product, price, amount))
        if msg is not None:
            logger.print(msg)

    def printStuff(self, state):
        logger.print("traderData: " + state.traderData)
        logger.print("Observations: " + str(state.observations))

    def get_product_pos(self, state, product):
        if product == 'EMERALDS':
            return state.position.get('EMERALDS', 0)
        elif product == 'TOMATOES':
            return state.position.get('TOMATOES', 0)
        else:
            raise ValueError(f"Unknown product: {product}")

    def search_buys(self, state, product, acceptable_price, depth=1):
        order_depth = state.order_depths[product]
        if len(order_depth.sell_orders) != 0:
            orders = list(order_depth.sell_orders.items())
            for ask, amount in orders[0:max(len(orders), depth)]:
                pos = self.get_product_pos(state, product)
                if int(ask) < acceptable_price or (abs(ask - acceptable_price) < 1 and (pos < 0 and abs(pos - amount) < abs(pos))):
                    if product == 'EMERALDS':
                        size = min(50 - self.emeralds_position - self.emeralds_buy_orders, -amount)
                        self.emeralds_buy_orders += size
                        self.send_buy_order(product, ask, size, msg=f"TRADE BUY {str(size)} x @ {ask}")

                    elif product == 'TOMATOES':
                        size = min(50 - self.tomatoes_position - self.tomatoes_buy_orders, -amount)
                        self.tomatoes_buy_orders += size
                        self.send_buy_order(product, ask, size, msg=f"TRADE BUY {str(size)} x @ {ask}")

    def search_sells(self, state, product, acceptable_price, depth=1):
        order_depth = state.order_depths[product]
        if len(order_depth.buy_orders) != 0:
            orders = list(order_depth.buy_orders.items())
            for bid, amount in orders[0:max(len(orders), depth)]:
                pos = self.get_product_pos(state, product)
                if int(bid) > acceptable_price or (abs(bid - acceptable_price) < 1 and (pos > 0 and abs(pos - amount) < abs(pos))):
                    if product == 'EMERALDS':
                        size = min(self.emeralds_position + 50 - self.emeralds_sell_orders, amount)
                        self.emeralds_sell_orders += size
                        self.send_sell_order(product, bid, -size, msg=f"TRADE SELL {str(-size)} x @ {bid}")

                    elif product == 'TOMATOES':
                        size = min(self.tomatoes_position + 50 - self.tomatoes_sell_orders, amount)
                        self.tomatoes_sell_orders += size
                        self.send_sell_order(product, bid, -size, msg=f"TRADE SELL {str(-size)} x @ {bid}")

    def get_bid(self, state, product, price):
        order_depth = state.order_depths[product]
        if len(order_depth.buy_orders) != 0:
            orders = list(order_depth.buy_orders.items())
            for bid, _ in orders:
                if bid < price:
                    return bid
        return None

    def get_ask(self, state, product, price):
        order_depth = state.order_depths[product]
        if len(order_depth.sell_orders) != 0:
            orders = list(order_depth.sell_orders.items())
            for ask, _ in orders:
                if ask > price:
                    return ask
        return None

    def get_second_bid(self, state, product):
        order_depth = state.order_depths[product]
        if len(order_depth.buy_orders) != 0:
            orders = list(order_depth.buy_orders.items())
            if len(orders) < 2:
                return None
            bid, _ = orders[1]
            return bid
        return None

    def get_second_ask(self, state, product):
        order_depth = state.order_depths[product]
        if len(order_depth.sell_orders) != 0:
            orders = list(order_depth.sell_orders.items())
            if len(orders) < 2:
                return None
            ask, _ = orders[1]
            return ask
        return None

    def trade_emeralds(self, state):
        self.search_buys(state, 'EMERALDS', 10000, depth=3)
        self.search_sells(state, 'EMERALDS', 10000, depth=3)

        best_ask = self.get_ask(state, 'EMERALDS', 10000)
        best_bid = self.get_bid(state, 'EMERALDS', 10000)

        buy_price = 9996
        sell_price = 10004

        if best_ask is not None and best_bid is not None:
            sell_price = best_ask - 1
            buy_price = best_bid + 1

        max_buy = 50 - self.emeralds_position - self.emeralds_buy_orders
        max_sell = self.emeralds_position + 50 - self.emeralds_sell_orders

        self.send_sell_order('EMERALDS', sell_price, -max_sell, msg=f"EMERALDS: MARKET MADE Sell {max_sell} @ {sell_price}")
        self.send_buy_order('EMERALDS', buy_price, max_buy, msg=f"EMERALDS: MARKET MADE Buy {max_buy} @ {buy_price}")

    def trade_tomatoes(self, state):
        order_book = state.order_depths['TOMATOES']
        sell_orders = order_book.sell_orders
        buy_orders = order_book.buy_orders

        if len(sell_orders) != 0 and len(buy_orders) != 0:
            ask, _ = list(sell_orders.items())[-1]  # worst ask
            bid, _ = list(buy_orders.items())[-1]   # worst bid

            fair_price = int(math.ceil((ask + bid) / 2))
            decimal_fair_price = (ask + bid) / 2

            logger.print(f"TOMATOES FAIR PRICE: {decimal_fair_price}")
            self.search_buys(state, 'TOMATOES', decimal_fair_price, depth=3)
            self.search_sells(state, 'TOMATOES', decimal_fair_price, depth=3)

            best_ask = self.get_ask(state, 'TOMATOES', fair_price)
            best_bid = self.get_bid(state, 'TOMATOES', fair_price)

            buy_price = math.floor(decimal_fair_price) - 2
            sell_price = math.ceil(decimal_fair_price) + 2

            if best_ask is not None and best_bid is not None:
                sell_price = best_ask - 1
                buy_price = best_bid + 1

            max_buy = 50 - self.tomatoes_position - self.tomatoes_buy_orders
            max_sell = self.tomatoes_position + 50 - self.tomatoes_sell_orders

            self.send_buy_order('TOMATOES', buy_price, max_buy, msg=f"TOMATOES: MARKET MADE Buy {max_buy} @ {buy_price}")
            self.send_sell_order('TOMATOES', sell_price, -max_sell, msg=f"TOMATOES: MARKET MADE Sell {max_sell} @ {sell_price}")

    def reset_orders(self, state):
        self.orders = {}
        self.conversions = 0

        self.emeralds_position = self.get_product_pos(state, 'EMERALDS')
        self.emeralds_buy_orders = 0
        self.emeralds_sell_orders = 0

        self.tomatoes_position = self.get_product_pos(state, 'TOMATOES')
        self.tomatoes_buy_orders = 0
        self.tomatoes_sell_orders = 0

        for product in state.order_depths:
            self.orders[product] = []

    def run(self, state: TradingState):
        self.reset_orders(state)

        self.trade_emeralds(state)
        self.trade_tomatoes(state)

        logger.flush(state, self.orders, self.conversions, self.traderData)
        return self.orders, self.conversions, self.traderData

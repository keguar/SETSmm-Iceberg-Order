
from enum import Enum
import locale
import re
import sys

import linked_list


class OrderType(Enum):
    BUY = 'B'
    SELL = 'S'


class OrderEntry:
    def __init__(self, order_type, order_id, price, count, peak):
        self.order_type = order_type
        self.order_id = order_id
        self.price = price
        self.count = count
        self.peak = peak

    def __repr__(self):
        peak_repr = f' with peak {self.peak}' if self.peak else ''
        return f'OrderEntry(id={self.order_id} {self.order_type.name} {self.count} at limit {self.price}{peak_repr})'


class OrderStatus:
    def __init__(self, entry):
        self.order_type = entry.order_type
        self.order_id = entry.order_id
        self.price = entry.price
        if entry.peak:
            self.visible_volume = min(entry.count, entry.peak)
            self.hidden_tail = entry.count - self.visible_volume
        else:
            self.visible_volume = entry.count
            self.hidden_tail = 0
        self.peak = entry.peak
        self.tick = next(tick)


class TradeMessage:
    def __init__(self, book_node, order_entry):
        self.count = min(book_node.visible_volume, order_entry.count)
        self.price = book_node.price
        if book_node.order_type == OrderType.BUY:
            self.buy_order_id = book_node.order_id
            self.sell_order_id = order_entry.order_id
        elif book_node.order_type == OrderType.SELL:
            self.buy_order_id = order_entry.order_id
            self.sell_order_id = book_node.order_id


class OrderStackPriceLevelSublist:
    def __init__(self, entry):
        self.price = entry.price

        linked_list.init(self)
        self.put(entry)

    def exhaust(self, entry, trade_messages):
        node = linked_list.head(self)
        while node:
            if entry.count <= 0:
                return

            trade = TradeMessage(node, entry)
            trade_messages.append(trade)
            node.visible_volume -= trade.count
            entry.count -= trade.count

            if node.visible_volume > 0:
                return
            if node.hidden_tail > 0:
                new_peak = OrderEntry(
                    order_type=node.order_type,
                    order_id=node.order_id,
                    price=node.price,
                    count=node.hidden_tail,
                    peak=node.peak,
                )
                self.put(new_peak)

            node = node.next_node
            linked_list.set_head(self, node)

    def put(self, entry):
        print(f'StackListPriceLevelSublist(price={self.price}).put', file=sys.stderr)
        node = OrderStatus(entry)
        linked_list.insert_before(self, node, None)

    def is_empty(self):
        return linked_list.head(self) is None

    def __iter__(self):
        return self.__next__()

    def __next__(self):
        node = linked_list.head(self)
        while node:
            yield node
            node = node.next_node


class OrderStackList:
    def __init__(self, order_type):
        self.order_type = order_type

        linked_list.init(self)

        if order_type == OrderType.BUY:
            self.node_in_entry_limit = lambda node, entry: node.price >= entry.price
        elif order_type == OrderType.SELL:
            self.node_in_entry_limit = lambda node, entry: node.price <= entry.price

    def exhaust(self, entry, trade_messages):
        node = linked_list.head(self)
        while node:
            if entry.count <= 0:
                return
            if not self.node_in_entry_limit(node, entry):
                return
            node.exhaust(entry, trade_messages)
            if node.is_empty():
                node = linked_list.next(node)
                linked_list.set_head(self, node)
            else:
                return

    def put(self, entry):
        print('StackList.put', file=sys.stderr)
        node = linked_list.head(self)
        while node:
            print(f'StackList node.price={node.price}', file=sys.stderr)
            if self.node_in_entry_limit(node, entry):
                if node.price == entry.price:
                    return node.put(entry)
                else:
                    node = linked_list.next(node)
            else:
                break

        new_node = OrderStackPriceLevelSublist(entry)
        print(f'StackList.insert_before(node)', file=sys.stderr)
        linked_list.insert_before(self, new_node, node)

    def __iter__(self):
        return self.__next__()

    def __next__(self):
        node = linked_list.head(self)
        while node:
            for sub_node in node:
                yield sub_node
            node = node.next_node


class OrderBook:
    def __init__(self):
        self.buys = OrderStackList(OrderType.BUY)
        self.sells = OrderStackList(OrderType.SELL)
        self.entry_executor = {
            OrderType.BUY: {
                'exhaust': self.sells,
                'put': self.buys,
            },
            OrderType.SELL: {
                'exhaust': self.buys,
                'put': self.sells,
            }
        }

    def execute(self, entry):
        executor = self.entry_executor[entry.order_type]
        trade_messages = []
        executor['exhaust'].exhaust(entry, trade_messages)
        if entry.count > 0:
            executor['put'].put(entry)
        return self.deduplicate_trade(trade_messages)

    @staticmethod
    def deduplicate_trade(messages):
        result = []
        order_mapping = {}
        for msg in messages:
            key = (msg.buy_order_id, msg.sell_order_id)
            if key in order_mapping:
                index = order_mapping[key]
                result[index].count += msg.count
            else:
                index = len(result)
                result.append(msg)
                order_mapping[key] = index
        return result

    def print(self, output):
        old_locale = locale.getlocale(locale.LC_ALL)
        try:
            locale.setlocale(locale.LC_ALL, 'en_US')
            print("+-----------------------------------------------------------------+", file=output)
            print("| BUY                            | SELL                           |", file=output)
            print("| Id       | Volume      | Price | Price | Volume      | Id       |", file=output)
            print("+----------+-------------+-------+-------+-------------+----------+", file=output)
            buy_stack = list(self.buys)
            sell_stack = list(self.sells)
            line_count = max(len(buy_stack), len(sell_stack))
            for line_index in range(line_count):
                buy = buy_stack[line_index] if line_index < len(buy_stack) else None
                sell = sell_stack[line_index] if line_index < len(sell_stack) else None
                print(f"|{self.__format_buy_status(buy)}|{self.__format_sell_status(sell)}|", file=output)
            print("+-----------------------------------------------------------------+", file=output)
        finally:
            locale.setlocale(locale.LC_ALL, old_locale)

    @staticmethod
    def __format_buy_status(status):
        if status:
            volume_str = locale.format_string("%d", status.visible_volume, grouping=True)
            price_str = locale.format_string("%d", status.price, grouping=True)
            return f"{status.order_id:#10}|{volume_str:>13}|{price_str:>7}"
        else:
            return " " * 10 + "|" + " " * 13 + "|" + " " * 7

    @staticmethod
    def __format_sell_status(status):
        if status:
            volume_str = locale.format_string("%d", status.visible_volume, grouping=True)
            price_str = locale.format_string("%d", status.price, grouping=True)
            return f"{price_str:>7}|{volume_str:>13}|{status.order_id:#10}"
        else:
            return " " * 7 + "|" + " " * 13 + "|" + " " * 10


def ticks_generator():
    t = 1
    while True:
        yield t
        t += 1


tick = ticks_generator()


def read_entries(f):
    comment_expr = re.compile('^\s*(#.*)?$', re.ASCII)
    for line in f:
        if comment_expr.match(line):
            continue
        parts = line.split(',')
        yield OrderEntry(
            order_type=OrderType(parts[0]),
            order_id=int(parts[1]),
            price=int(parts[2]),
            count=int(parts[3]),
            peak=int(parts[4]) if len(parts) >= 5 else None,
        )


def write_trade_message(output, msg):
    print(f"{msg.buy_order_id},{msg.sell_order_id},{msg.price},{msg.count}", file=output)


def run(input, output):
    book = OrderBook()
    for entry in read_entries(input):
        print(repr(entry), file=sys.stderr)
        for trade_message in book.execute(entry):
            write_trade_message(output, trade_message)
        book.print(output)


if __name__ == "__main__":
    run(sys.stdin, sys.stdout)

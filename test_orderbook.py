import pytest

from orderbook import BookError, OrderBook


def make_book():
    book = OrderBook()
    book.add(1, "B", 1_000_000, 500, time=1)
    book.add(2, "B", 999_900, 300, time=2)
    book.add(3, "S", 1_000_100, 200, time=3)
    book.add(4, "S", 1_000_200, 400, time=4)
    return book


def test_top_of_book_uses_integer_prices():
    book = make_book()
    assert book.best_bid() == 1_000_000
    assert book.best_ask() == 1_000_100
    assert book.spread() == 100
    assert book.mid() == 1_000_050


def test_executions_and_cancels_reduce_orders_and_empty_levels_disappear():
    book = make_book()
    book.reduce(3, 150, time=5)
    assert book.levels["S"][1_000_100] == 50
    book.reduce(3, 50, time=6)
    assert 3 not in book.orders
    assert book.best_ask() == 1_000_200


def test_delete_removes_the_whole_order():
    book = make_book()
    book.delete(1, time=5)
    assert book.best_bid() == 999_900
    assert 1 not in book.orders


def test_replace_moves_the_order_and_loses_queue_priority():
    book = make_book()
    book.add(5, "B", 1_000_000, 100, time=5)
    assert book.queue_position(5) == 500
    book.replace(1, 6, 500, 1_000_000, time=6)
    assert 1 not in book.orders
    assert book.queue_position(5) == 0
    assert book.queue_position(6) == 100


def test_depth_microprice_and_imbalance():
    book = make_book()
    assert book.depth("B", 2) == [(1_000_000, 500), (999_900, 300)]
    assert book.depth("S", 1) == [(1_000_100, 200)]
    assert book.total_depth("S") == 600
    assert book.microprice() == pytest.approx((1_000_000 * 200 + 1_000_100 * 500) / 700)
    assert book.imbalance(1) == pytest.approx(300 / 700)
    assert book.imbalance(2) == pytest.approx(200 / 1400)


@pytest.mark.parametrize("action", [
    lambda b: b.add(1, "B", 1_000_000, 100, time=5),
    lambda b: b.reduce(99, 100, time=5),
    lambda b: b.reduce(3, 1_000, time=5),
    lambda b: b.add(9, "B", 1_000_000, 100, time=0),
    lambda b: b.add(9, "B", 1_000_100, 100, time=5),
])
def test_strict_mode_rejects_impossible_messages(action):
    with pytest.raises(BookError):
        action(make_book())


def test_lenient_mode_counts_problems_and_keeps_going():
    book = make_book()
    book.strict = False
    book.reduce(99, 100, time=5)
    book.add(1, "B", 1_000_000, 100, time=6)
    assert book.problems == {"unknown order": 1, "duplicate order": 1}
    assert book.best_bid() == 1_000_000


def test_apply_dispatches_itch_messages():
    book = OrderBook()
    book.apply({"type": "A", "time": 1, "order": 7, "side": "S", "shares": 300, "price": 500_000})
    book.apply({"type": "E", "time": 2, "order": 7, "shares": 100})
    book.apply({"type": "U", "time": 3, "order": 7, "new_order": 8, "shares": 200, "price": 499_900})
    book.apply({"type": "P", "time": 4, "side": "B", "shares": 50, "price": 499_950})
    assert book.depth("S", 1) == [(499_900, 200)]
    book.apply({"type": "D", "time": 5, "order": 8})
    assert book.best_ask() is None

import gzip

from itch import formats, messages, parse, raw_messages
from make_sample import (
    add,
    clock,
    delete,
    directory,
    execute,
    hidden_trade,
    replace,
    sample_day,
    system,
)
from replay import replay


def write(tmp_path, data, compressed=True):
    path = tmp_path / ("day.itch.gz" if compressed else "day.itch")
    if compressed:
        with gzip.open(path, "wb") as file:
            file.write(data)
    else:
        path.write_bytes(data)
    return path


def tiny_day():
    return b"".join([
        system(clock(4), "O"),
        directory(1, "AAPL"),
        directory(2, "MSFT"),
        system(clock(9, 30), "Q"),
        add(1, clock(9, 30, 1), 11, "B", 100, "AAPL", 1_500_000),
        add(2, clock(9, 30, 2), 12, "S", 100, "MSFT", 4_000_000),
        execute(1, clock(9, 30, 3), 11, 40, 1),
        replace(1, clock(9, 30, 4), 11, 13, 60, 1_499_900),
        hidden_trade(1, clock(9, 30, 5), "S", 25, "AAPL", 1_500_100, 2),
        delete(1, clock(10, 0, 1), 13),
        system(clock(16), "M"),
        system(clock(20), "C"),
    ])


def test_messages_keep_only_the_chosen_stock(tmp_path):
    found = list(messages(write(tmp_path, tiny_day()), "AAPL"))
    book = [m for m in found if m["type"] != "S"]
    assert [m["type"] for m in book] == ["A", "E", "U", "P", "D"]
    assert book[0] == {"type": "A", "time": clock(9, 30, 1), "order": 11, "side": "B", "shares": 100, "price": 1_500_000}
    assert book[2]["new_order"] == 13 and book[2]["price"] == 1_499_900


def test_messages_stop_at_the_cutoff_and_read_uncompressed_files(tmp_path):
    found = list(messages(write(tmp_path, tiny_day(), compressed=False), "aapl", until=clock(10)))
    assert found[-1]["type"] == "P"


def test_messages_split_across_read_chunks_are_reassembled(tmp_path):
    path = write(tmp_path, tiny_day())
    assert list(raw_messages(path, chunk_size=7)) == list(raw_messages(path))


def test_replaying_the_sample_day_gives_a_clean_book(tmp_path):
    book, counts, rows = replay(write(tmp_path, sample_day(minutes=5)), "DEMO")
    assert book.problems == {}
    assert counts["A"] > 0 and counts["E"] > 0 and counts["U"] > 0
    assert len(rows) > 250
    assert all(r["bid"] < r["ask"] for r in rows)

def test_execution_with_price_reads_the_price_field():
    raw = formats[b"C"].pack(b"C", 1, 0, (5).to_bytes(6, "big"), 42, 100, 7, b"Y", 3_243_200)
    assert parse(b"C", raw) == {"type": "C", "time": 5, "order": 42, "shares": 100, "price": 3_243_200}
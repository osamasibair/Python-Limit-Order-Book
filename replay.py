"""Replay one stocks trading day from a Nasdaq ITCH file through the order book, printing and saving the top of the book."""
import argparse
import csv
from collections import Counter
from itertools import pairwise

from itch import messages
from orderbook import OrderBook

second = 1_000_000_000


def clock_text(time):
    seconds = time // second
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def parse_clock(text):
    hours, minutes = map(int, text.split(":"))
    return (hours * 3600 + minutes * 60) * second


def snapshot(book, time):
    bid, ask = book.best_bid(), book.best_ask()
    return {
        "time": clock_text(time),
        "bid": bid / 10_000,
        "bid_size": book.levels["B"][bid],
        "ask": ask / 10_000,
        "ask_size": book.levels["S"][ask],
        "spread_cents": book.spread() / 100,
        "mid": book.mid() / 10_000,
        "microprice": round(book.microprice() / 10_000, 4),
        "imbalance_5": round(book.imbalance(5), 3),
        "resting_orders": len(book.orders),
    }


def imbalance_hit_rate(rows):
    hits = total = 0
    for now, later in pairwise(rows):
        move = later["mid"] - now["mid"]
        if move != 0 and now["imbalance_5"] != 0:
            total += 1
            hits += (move > 0) == (now["imbalance_5"] > 0)
    return hits / total if total else None


def replay(path, symbol, until=None, every=1, print_every=60):
    book = OrderBook(strict=False)
    counts, rows = Counter(), []
    trading, next_snapshot = False, None
    for message in messages(path, symbol, until):
        counts[message["type"]] += 1
        if message["type"] == "S":
            if message["event"] == "Q":
                trading, next_snapshot = True, message["time"]
            elif message["event"] == "M":
                trading = False
            continue
        book.apply(message)
        if trading and message["time"] >= next_snapshot and book.best_bid() and book.best_ask():
            row = snapshot(book, message["time"])
            rows.append(row)
            if (len(rows) - 1) % print_every == 0:
                print(f"{row['time']}  {row['bid_size']:>6} x {row['bid']:.2f}  |  {row['ask']:.2f} x {row['ask_size']:<6}"
                      f"  spread {row['spread_cents']:.0f}c  micro {row['microprice']:.4f}  imbalance {row['imbalance_5']:+.3f}")
            next_snapshot = message["time"] - message["time"] % (every * second) + every * second
    return book, counts, rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="ITCH 5.0 file, .gz or uncompressed")
    parser.add_argument("symbol", help="ticker, e.g. AAPL")
    parser.add_argument("--until", help="stop at this exchange time, HH:MM (US Eastern)")
    parser.add_argument("--every", type=int, default=1, help="seconds between saved snapshots")
    args = parser.parse_args()

    book, counts, rows = replay(args.path, args.symbol, parse_clock(args.until) if args.until else None, args.every)
    out = f"{args.symbol.lower()}_book.csv"
    if rows:
        with open(out, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    names = {"A": "adds", "E": "executions", "C": "executions at a different price", "X": "partial cancels",
             "D": "deletes", "U": "replaces", "P": "hidden-order trades", "S": "system events"}
    print("\n" + ", ".join(f"{counts[k]:,} {names[k]}" for k in names if counts[k]))
    print(f"problems: {book.problems or 'none'}")
    if rows:
        spreads = [r["spread_cents"] for r in rows]
        print(f"{len(rows):,} snapshots saved to {out}; average spread {sum(spreads) / len(spreads):.2f} cents")
        rate = imbalance_hit_rate(rows)
        if rate is not None:
            print(f"the next mid move went the way the 5-level imbalance pointed {rate:.0%} of the time")

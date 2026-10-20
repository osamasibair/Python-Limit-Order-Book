# Python Limit Order Book

A limit order book built from real Nasdaq market data. It reads a TotalView-ITCH 5.0 file, rebuilds one stocks order book message by message, and records the top of the book every second.

## What it does

- **Parses Nasdaq ITCH 5.0** binary files (`itch.py`): adds, executions, cancels, deletes, replaces and hidden trades for one stock.
- **Tracks every order** (an L3 book, in `orderbook.py`): order ids, price levels and queue position. Prices are stored as integers to avoid floating-point errors.
- **Calculates book metrics:** best bid and ask, spread, mid price, microprice, depth, total depth, order book imbalance and queue position.
- **Checks itself:** it counts any crossed book, unknown order or time going backwards. On real data it prints `problems: none`.
- **Replays a trading day** (`replay.py`): prints the book each minute, saves a snapshot every second to CSV, and tests whether imbalance predicts the next price move.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

## Usage

Try it on a small synthetic day first:

```bash
python make_sample.py
python replay.py data/sample.itch.gz DEMO
```

For real data, download a file from [emi.nasdaq.com/ITCH](https://emi.nasdaq.com/ITCH/) into `data/`, then:

```bash
python replay.py data/20200130.BX_ITCH_50 SPY --until XX:XX #insert timeframe
```

## Results

SPY on Nasdaq BX, 30 Jan 2020, 09:30–10:30:

- Average spread: **3.1 cents**
- **99% of orders were cancelled** rather than filled (165,868 adds, 164,442 deletes, about 1,800 executions), the high frequency market makers constantly requoting.
- Top 5 level imbalance predicted the next mid move **51%** of the time, so no edge. BX holds a small share of SPY's liquidity, and its book alone has little signal.

TSLA on the same day had a book too thin to analyse on BX (about a $10 spread, with most trades hidden).

## Files

| File | Purpose |
|---|---|
| `itch.py` | Reads ITCH 5.0 files and yields one stock's messages |
| `orderbook.py` | The order book and its metrics |
| `replay.py` | Replays a day, prints and saves snapshots |
| `make_sample.py` | Writes a small synthetic ITCH file for testing |
| `test_orderbook.py`, `test_itch.py` | 17 tests |

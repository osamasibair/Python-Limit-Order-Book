"""Count add orders per stock to find the busiest ones."""
import sys
from collections import Counter
from itertools import islice

from itch import formats, raw_messages

names, adds = {}, Counter()
for raw in islice(raw_messages(sys.argv[1]), 20_000_000):
    kind = raw[:1]
    if kind == b"R":
        fields = formats[b"R"].unpack(raw)
        names[fields[1]] = fields[4].decode().strip()
    elif kind in (b"A", b"F"):
        adds[int.from_bytes(raw[1:3], "big")] += 1

for locate, count in adds.most_common(10):
    print(f"{names.get(locate, locate):<8} {count:,}")
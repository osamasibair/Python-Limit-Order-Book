"""Read Nasdaq TotalView-ITCH 5.0 files and get the order book messages for one stock."""
import gzip
import struct

formats = {
    b"S": struct.Struct(">cHH6sc"),
    b"R": struct.Struct(">cHH6s8sccIcc2scccccIc"),
    b"A": struct.Struct(">cHH6sQcI8sI"),
    b"F": struct.Struct(">cHH6sQcI8sI4s"),
    b"E": struct.Struct(">cHH6sQIQ"),
    b"C": struct.Struct(">cHH6sQIQcI"),
    b"X": struct.Struct(">cHH6sQI"),
    b"D": struct.Struct(">cHH6sQ"),
    b"U": struct.Struct(">cHH6sQQII"),
    b"P": struct.Struct(">cHH6sQcI8sIQ"),
}
book_kinds = {b"A", b"F", b"E", b"C", b"X", b"D", b"U", b"P"}


def raw_messages(path, chunk_size=1 << 24):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as file:
        buffer = b""
        while chunk := file.read(chunk_size):
            buffer += chunk
            pos = 0
            while pos + 2 <= len(buffer):
                length = int.from_bytes(buffer[pos:pos + 2], "big")
                if pos + 2 + length > len(buffer):
                    break
                yield buffer[pos + 2:pos + 2 + length]
                pos += 2 + length
            buffer = buffer[pos:]


def parse(kind, raw):
    f = formats[kind].unpack(raw)
    time = int.from_bytes(f[3], "big")
    if kind in (b"A", b"F"):
        return {"type": "A", "time": time, "order": f[4], "side": f[5].decode(), "shares": f[6], "price": f[8]}
    if kind == b"E":
        return {"type": "E", "time": time, "order": f[4], "shares": f[5]}
    if kind == b"C":
        return {"type": "C", "time": time, "order": f[4], "shares": f[5], "price": f[8]}
    if kind == b"X":
        return {"type": "X", "time": time, "order": f[4], "shares": f[5]}
    if kind == b"D":
        return {"type": "D", "time": time, "order": f[4]}
    if kind == b"U":
        return {"type": "U", "time": time, "order": f[4], "new_order": f[5], "shares": f[6], "price": f[7]}
    return {"type": "P", "time": time, "side": f[5].decode(), "shares": f[6], "price": f[8]}


def messages(path, symbol, until=None, chunk_size=1 << 24):
    target = symbol.upper().ljust(8).encode()
    locate = None
    for raw in raw_messages(path, chunk_size):
        kind = raw[:1]
        if kind == b"R":
            fields = formats[b"R"].unpack(raw)
            if fields[4] == target:
                locate = fields[1]
        elif kind == b"S":
            fields = formats[b"S"].unpack(raw)
            yield {"type": "S", "time": int.from_bytes(fields[3], "big"), "event": fields[4].decode()}
            if fields[4] == b"C":
                return
        elif kind in book_kinds and locate is not None and int.from_bytes(raw[1:3], "big") == locate:
            message = parse(kind, raw)
            if until is not None and message["time"] > until:
                return
            yield message

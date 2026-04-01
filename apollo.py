"""Minimal WPILog (.wpilog) parser. Zero dependencies beyond stdlib."""

import bisect
import struct
import mmap
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("apollo-mcp-server")

DECODERS = {
    "double":    lambda d: struct.unpack("<d", d[:8])[0],
    "float":     lambda d: struct.unpack("<f", d[:4])[0],
    "int64":     lambda d: struct.unpack("<q", d[:8])[0],
    "boolean":   lambda d: d[0] != 0,
    "string":    lambda d: d.decode("utf-8", errors="replace"),
    "double[]":  lambda d: list(struct.unpack(f"<{len(d)//8}d", d[:len(d)//8*8])),
    "int64[]":   lambda d: list(struct.unpack(f"<{len(d)//8}q", d[:len(d)//8*8])),
    "float[]":   lambda d: list(struct.unpack(f"<{len(d)//4}f", d[:len(d)//4*4])),
    "boolean[]": lambda d: [b != 0 for b in d],
}

def _read_int(buf, offset, size):
    """Read a little-endian unsigned int of 1/2/4 bytes."""
    return int.from_bytes(buf[offset:offset + size], "little"), offset + size


def _read_lp_string(buf, offset):
    """Read a 4-byte-length-prefixed UTF-8 string."""
    slen = struct.unpack_from("<I", buf, offset)[0]
    offset += 4
    return buf[offset:offset + slen].decode("utf-8", errors="replace"), offset + slen


# _file_cache[path] = {
#   "entry_map":  {entry_id: (name, type_str)},
#   "records":    [(timestamp_us, name, type_str, value), ...],  # data records only, sorted by ts
#   "timestamps": [int, ...],  # parallel timestamp list for bisect
# }
_file_cache: dict[str, dict] = {}


def _load(path: str) -> dict:
    """Single-pass parse + decode. Results are cached."""
    if path in _file_cache:
        return _file_cache[path]

    with open(path, "rb") as f:
        buf = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    if buf[:6] != b"WPILOG":
        raise ValueError("Not a WPILog file")
    extra_len = struct.unpack_from("<I", buf, 8)[0]
    pos = 12 + extra_len

    entry_map: dict[int, tuple[str, str]] = {}
    # Accumulate data records after the first pass so we can resolve names.
    # Control records (entry_id 0) define names and may appear before or after
    # the data records that reference them, so we do two logical phases:
    # 1. collect raw data records as (entry_id, ts, payload_bytes)
    # 2. decode eagerly once all names are known
    raw: list[tuple[int, int, bytes]] = []

    while pos < len(buf):
        bitfield = buf[pos]; pos += 1
        id_size = (bitfield & 0x03) + 1
        ps_size = ((bitfield >> 2) & 0x03) + 1
        ts_size = ((bitfield >> 4) & 0x07) + 1

        entry_id, pos = _read_int(buf, pos, id_size)
        payload_sz, pos = _read_int(buf, pos, ps_size)
        timestamp, pos = _read_int(buf, pos, ts_size)

        payload = bytes(buf[pos:pos + payload_sz])
        pos += payload_sz

        if entry_id == 0:
            if len(payload) >= 1 and payload[0] == 0:
                # control-start: extract entry metadata
                off = 1
                target_id = struct.unpack_from("<I", payload, off)[0]; off += 4
                name, off = _read_lp_string(payload, off)
                type_str, off = _read_lp_string(payload, off)
                entry_map[target_id] = (name, type_str)
        else:
            raw.append((entry_id, timestamp, payload))

    buf.close()

    # Eager decode: resolve names and decode values in one pass
    records: list[tuple[int, str, str, object]] = []
    for entry_id, ts, payload in raw:
        meta = entry_map.get(entry_id)
        if meta is None:
            continue
        name, type_str = meta
        decoder = DECODERS.get(type_str)
        if decoder is None:
            continue
        try:
            value = decoder(payload)
        except (struct.error, IndexError, UnicodeDecodeError):
            continue
        records.append((ts, name, type_str, value))

    # wpilog is written in timestamp order; sorting is cheap insurance and
    # required for the bisect-based time_range fast-path below.
    records.sort(key=lambda r: r[0])
    timestamps = [r[0] for r in records]

    cached = {"entry_map": entry_map, "records": records, "timestamps": timestamps}
    _file_cache[path] = cached
    return cached


@mcp.tool()
def read_nt(path, prefix="/", quantize_level: int | None = None, time_range: tuple[int, int] | None = None):
    """
    Read NT entries from a wpilog file.

    Args:
        path:   Path to .wpilog file
        prefix: Only return entries whose name starts with this (default "/")
        quantize_level (optional): coarsity of signals, returns every quantize_levelth value per record name
        time_range (optional): tuple of form (min timestamp, max timestamp) to filter all returned records by

    Returns:
        List of {timestamp_us, name, type, value} dicts
    """
    data = _load(path)
    records = data["records"]
    timestamps = data["timestamps"]

    # Binary search to narrow the record slice when a time_range is given
    if time_range is not None:
        lo = bisect.bisect_left(timestamps, time_range[0])
        hi = bisect.bisect_right(timestamps, time_range[1])
        records = records[lo:hi]

    name_freq: dict[str, int] = {}
    result = []
    for ts, name, type_str, value in records:
        if not name.startswith(prefix):
            continue
        if quantize_level is not None:
            i = name_freq.get(name, 0)
            name_freq[name] = i + 1
            if i % quantize_level != 0:
                continue
        result.append({"timestamp_us": ts, "name": name, "type": type_str, "value": value})
    return result


@mcp.tool()
def list_entries(path):
    """Return [{name, type}] for all entries in the log."""
    return [{"name": n, "type": t} for n, t in _load(path)["entry_map"].values()]

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()

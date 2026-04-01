"""Minimal WPILog (.wpilog) parser. Zero dependencies beyond stdlib."""

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

# lazy parse entire file
log_cache: dict[str, list] = dict()
def parse(path):
    """Yield (entry_id, timestamp_us, payload_bytes) for every record."""
    global log_cache
    if path in log_cache:
        return log_cache[path]
    with open(path, "rb") as f:
        buf = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    # Header: 6-byte magic, 2-byte version, 4-byte extra header len
    if buf[:6] != b"WPILOG":
        raise ValueError("Not a WPILog file")
    extra_len = struct.unpack_from("<I", buf, 8)[0]
    pos = 12 + extra_len

    log = []
    while pos < len(buf):
        bitfield = buf[pos]; pos += 1
        id_size   = ((bitfield & 0x03) + 1)          # 1-4 bytes
        ps_size   = (((bitfield >> 2) & 0x03) + 1)   # 1-4 bytes
        ts_size   = (((bitfield >> 4) & 0x07) + 1)    # 1-8 bytes

        entry_id, pos = _read_int(buf, pos, id_size)
        payload_sz, pos = _read_int(buf, pos, ps_size)
        timestamp, pos = _read_int(buf, pos, ts_size)

        payload = buf[pos:pos + payload_sz]
        pos += payload_sz

        log.append((entry_id, timestamp, payload))
    log_cache[path]=log
    return log

entry_cache: dict[str, dict] = dict()
def entries(path):
    """Return {entry_id: (name, type_str)} from control-start records."""
    global entry_cache
    if path in entry_cache:
        return entry_cache[path]
    result = {}
    for entry_id, _, payload in parse(path):
        if entry_id != 0 or len(payload) < 1 or payload[0] != 0:
            continue
        # control start: 1-byte type (0), 4-byte target entry id, then name, type, metadata
        off = 1
        target_id = struct.unpack_from("<I", payload, off)[0]; off += 4
        name, off = _read_lp_string(payload, off)
        type_str, off = _read_lp_string(payload, off)
        result[target_id] = (name, type_str)
    entry_cache[path]=result
    return result


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
    entry_map = entries(path)
    records = []
    name_freq = {}

    for entry_id, ts, payload in parse(path):
        if time_range is not None and not (time_range[0] <= ts <= time_range[1]):
            continue
        if entry_id == 0 or entry_id not in entry_map:
            continue
        name, type_str = entry_map[entry_id]
        if not name.startswith(prefix):
            continue
        decoder = DECODERS.get(type_str)
        if decoder is None:
            continue
        try:
            value = decoder(payload)
        except (struct.error, IndexError, UnicodeDecodeError):
            continue
        r = {"timestamp_us": ts, "name": name, "type": type_str, "value": value}
        if quantize_level is not None:
            i = name_freq.get(name, 0)
            name_freq[name]=i+1
            if i % quantize_level != 0:
                continue
        records.append(r)
    return records


@mcp.tool()
def list_entries(path):
    """Return [{name, type}] for all entries in the log."""
    return [{"name": n, "type": t} for n, t in entries(path).values()]

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()

"""Decoder for raw Kaifa KFM_001 frames so the dashboard can enrich terse SNAP lines with per-phase detail."""

from __future__ import annotations

from typing import Any


def _read_be32(b: bytes) -> int:
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def parse_kfm001_frame(hex_payload: str) -> dict[str, Any] | None:
    try:
        buf = bytes.fromhex(hex_payload)
    except Exception:
        return None
    pattern = b"	KFM_001"
    pos = buf.find(pattern)
    if pos < 0:
        return None
    clock_tag = b"	"
    cpos = buf.find(clock_tag)
    if cpos < 0 or cpos + 14 > len(buf):
        return None
    t = buf[cpos + 2 : cpos + 14]
    year = (t[0] << 8) | t[1]
    month = t[2]
    day = t[3]
    hour = t[5]
    minute = t[6]
    second = t[7]
    meter_ts = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    p = pos + len(pattern)
    if p + 18 > len(buf) or buf[p] != 0x09 or buf[p + 1] != 0x10:
        return None
    meter_id = "".join(chr(c) for c in buf[p + 2 : p + 18] if 32 <= c <= 126)
    p += 18
    if p + 10 > len(buf) or buf[p] != 0x09 or buf[p + 1] != 0x08:
        return None
    meter_type = "".join(chr(c) for c in buf[p + 2 : p + 10] if 32 <= c <= 126)
    p += 10
    vals = []
    for _ in range(10):
        if p + 5 > len(buf) or buf[p] != 0x06:
            return None
        vals.append(_read_be32(buf[p + 1 : p + 5]))
        p += 5
    l1_v = vals[7] / 10.0
    l2_v = vals[8] / 10.0
    l3_v = vals[9] / 10.0
    voltages = [v for v in (l1_v, l2_v, l3_v) if v > 1.0]
    avg_v = sum(voltages) / len(voltages) if voltages else 0.0
    import_w = float(vals[0])
    export_w = float(vals[1])
    q_import = float(vals[2])
    q_export = float(vals[3])
    l1_a = vals[4] / 1000.0
    l2_a = vals[5] / 1000.0
    l3_a = vals[6] / 1000.0
    total_a = l1_a + l2_a + l3_a
    net_w = import_w - export_w
    apparent = sum(v * a for v, a in [(l1_v, l1_a), (l2_v, l2_a), (l3_v, l3_a)] if v > 1.0)
    pf = min(1.0, abs(net_w) / apparent) if apparent > 1.0 else 0.0
    return {
        "meter_timestamp": meter_ts,
        "meter_id": meter_id,
        "meter_type": meter_type,
        "import_w": import_w,
        "export_w": export_w,
        "q_import_var": q_import,
        "q_export_var": q_export,
        "l1_v": l1_v,
        "l2_v": l2_v,
        "l3_v": l3_v,
        "avg_voltage_v": avg_v,
        "l1_a": l1_a,
        "l2_a": l2_a,
        "l3_a": l3_a,
        "total_current_a": total_a,
        "net_power_w": net_w,
        "apparent_power_va": apparent,
        "estimated_power_factor": pf,
    }

"""Protocol helpers for the text-based link between the dashboard and the ESP32 gateway."""

from __future__ import annotations

from typing import Iterable

from .models import (
    DeviceInfo,
    FrameEvent,
    MqttStatus,
    ParsedLine,
    SnapshotEvent,
    StatusLine,
    WifiStatus,
)


SENSITIVE_INDEXES = {
    "SET_WIFI": {2},
    "SET_MQTT": {4},
}

GATEWAY_PROTOCOL_PREFIXES = (
    "RSP:",
    "STATUS,",
    "FRAME,",
    "SNAP,",
)


def escape_command_field(value: object) -> str:
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def split_escaped_fields(text: str) -> list[str]:
    fields: list[str] = []
    buf: list[str] = []
    escaping = False
    for ch in text:
        if escaping:
            if ch == "n":
                buf.append("\n")
            elif ch == "r":
                buf.append("\r")
            else:
                buf.append(ch)
            escaping = False
            continue
        if ch == "\\":
            escaping = True
            continue
        if ch == ",":
            fields.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if escaping:
        buf.append("\\")
    fields.append("".join(buf))
    return fields


def build_command(*parts: object) -> str:
    return ",".join(escape_command_field(part) for part in parts if part is not None)


def mask_sensitive_command(command: str) -> str:
    raw = command.strip()
    if not raw:
        return raw

    parts = split_escaped_fields(raw)
    if not parts:
        return raw

    indexes = SENSITIVE_INDEXES.get(parts[0])
    if not indexes:
        return raw

    for idx in indexes:
        if idx < len(parts):
            parts[idx] = "***"
    return build_command(*parts)


def is_gateway_protocol_line(line: str) -> bool:
    raw = line.rstrip("\r\n")
    return raw.startswith(GATEWAY_PROTOCOL_PREFIXES)


def list_supported_commands() -> Iterable[str]:
    return [
        "GET_INFO",
        "GET_STATUS",
        "SET_WIFI,<ssid>,<password>  # commas and backslashes are escaped automatically",
        "CLEAR_WIFI",
        "SET_MQTT,<host>,<port>,<user>,<password>,<topic_prefix>  # commas and backslashes are escaped automatically",
        "MQTT_ENABLE",
        "MQTT_DISABLE",
        "REPUBLISH_DISCOVERY",
        "START_PROVISIONING",
        "STOP_PROVISIONING",
        "REBOOT",
        "FACTORY_RESET",
    ]


def parse_line(line: str) -> ParsedLine:
    raw = line.rstrip("\r\n")
    if not raw:
        return ParsedLine(raw=raw, kind="empty")

    if raw.startswith("RSP:INFO,"):
        parts = split_escaped_fields(raw)
        if len(parts) == 4:
            return ParsedLine(
                raw=raw,
                kind="device_info",
                payload=DeviceInfo(
                    fw_version=parts[1],
                    device_id=parts[2],
                    mac=parts[3],
                ),
            )
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid RSP:INFO")

    if raw.startswith("RSP:WIFI,"):
        parts = split_escaped_fields(raw)
        if len(parts) >= 2:
            state = parts[1]
            ip = parts[2] if len(parts) > 2 else ""
            return ParsedLine(raw=raw, kind="wifi_status", payload=WifiStatus(state=state, ip=ip))
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid RSP:WIFI")

    if raw.startswith("RSP:MQTT,"):
        parts = split_escaped_fields(raw)
        if len(parts) == 2:
            return ParsedLine(raw=raw, kind="mqtt_status", payload=MqttStatus(state=parts[1]))
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid RSP:MQTT")

    if raw.startswith("RSP:OK"):
        return ParsedLine(raw=raw, kind="ok")

    if raw.startswith("RSP:ERROR,"):
        parts = split_escaped_fields(raw)
        return ParsedLine(raw=raw, kind="error", error=parts[1] if len(parts) > 1 else "unknown")

    if raw.startswith("STATUS,"):
        parts = split_escaped_fields(raw)
        if len(parts) >= 3:
            category = parts[1]
            state = parts[2]
            extra = parts[3] if len(parts) == 4 else ""
            return ParsedLine(raw=raw, kind="status", payload=StatusLine(category, state, extra))
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid STATUS line")

    if raw.startswith("FRAME,"):
        parts = split_escaped_fields(raw)
        if len(parts) == 4:
            try:
                payload = FrameEvent(
                    sequence=int(parts[1]),
                    length=int(parts[2]),
                    hex_payload=parts[3],
                )
                return ParsedLine(raw=raw, kind="frame", payload=payload)
            except ValueError as exc:
                return ParsedLine(raw=raw, kind="parse_error", error=str(exc))
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid FRAME line")

    if raw.startswith("SNAP,"):
        parts = split_escaped_fields(raw)
        if len(parts) >= 21:
            try:
                payload = SnapshotEvent(
                    sequence=int(parts[1]),
                    meter_id=parts[2],
                    meter_type=parts[3],
                    timestamp=parts[4],
                    import_w=float(parts[5]),
                    export_w=float(parts[6]),
                    q_import_var=float(parts[7]),
                    q_export_var=float(parts[8]),
                    avg_voltage_v=float(parts[9]),
                    phase_imbalance_a=float(parts[10]),
                    l1_a=float(parts[11]),
                    l2_a=float(parts[12]),
                    l3_a=float(parts[13]),
                    net_power_w=float(parts[14]),
                    estimated_power_factor=float(parts[15]),
                    total_current_a=float(parts[16]),
                    apparent_power_va=float(parts[17]),
                    rolling_samples=int(parts[18]),
                    frames_rx=int(parts[19]),
                    frames_bad=int(parts[20]),
                )
                return ParsedLine(raw=raw, kind="snapshot", payload=payload)
            except ValueError as exc:
                return ParsedLine(raw=raw, kind="parse_error", error=f"Invalid SNAP numeric field: {exc}")
        return ParsedLine(raw=raw, kind="parse_error", error="Invalid SNAP line")

    return ParsedLine(raw=raw, kind="raw")

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class DeviceInfo:
    fw_version: str
    device_id: str
    mac: str


@dataclass(slots=True)
class WifiStatus:
    state: str
    ip: str = ""


@dataclass(slots=True)
class MqttStatus:
    state: str


@dataclass(slots=True)
class StatusLine:
    category: str
    state: str
    extra: str = ""


@dataclass(slots=True)
class FrameEvent:
    sequence: int
    length: int
    hex_payload: str


@dataclass(slots=True)
class SnapshotEvent:
    sequence: int
    meter_id: str
    meter_type: str
    timestamp: str
    import_w: float
    export_w: float
    q_import_var: float
    q_export_var: float
    avg_voltage_v: float
    phase_imbalance_a: float
    l1_a: float
    l2_a: float
    l3_a: float
    net_power_w: float
    estimated_power_factor: float
    total_current_a: float
    apparent_power_va: float
    rolling_samples: int
    frames_rx: int
    frames_bad: int


@dataclass(slots=True)
class ParsedLine:
    raw: str
    kind: str
    payload: object | None = None
    error: Optional[str] = None


@dataclass(slots=True)
class HistoryRecord:
    row_id: int
    received_at: str
    snapshot: SnapshotEvent


@dataclass(slots=True)
class HistorySummary:
    count: int = 0
    avg_import_w: float = 0.0
    avg_net_w: float = 0.0
    max_import_w: float = 0.0
    min_net_w: float = 0.0
    max_net_w: float = 0.0
    latest_received_at: str = "-"

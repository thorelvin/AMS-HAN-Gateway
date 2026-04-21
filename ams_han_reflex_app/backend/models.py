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


@dataclass(slots=True)
class PortOption:
    port: str
    description: str = ""

    @property
    def label(self) -> str:
        return f"{self.port} - {self.description}" if self.description else self.port

    def matches_display(self, raw: str) -> bool:
        text = str(raw or "").strip()
        return text in {self.port, self.label}


@dataclass(slots=True)
class IntegratedInterval:
    start: object
    end: object
    hours: float
    import_kw: float
    export_kw: float


@dataclass(slots=True)
class CostRow:
    hour: str
    day: str
    spot_nok_kwh: float
    grid_nok_kwh: float
    total_nok_kwh: float
    import_kw: float
    export_kw: float
    import_cost_nok: float
    export_value_nok: float
    net_cost_nok: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "hour": self.hour,
            "day": self.day,
            "spot_nok_kwh": self.spot_nok_kwh,
            "grid_nok_kwh": self.grid_nok_kwh,
            "total_nok_kwh": self.total_nok_kwh,
            "import_kw": self.import_kw,
            "export_kw": self.export_kw,
            "import_cost_nok": self.import_cost_nok,
            "export_value_nok": self.export_value_nok,
            "net_cost_nok": self.net_cost_nok,
        }


@dataclass(slots=True)
class CostSummaryData:
    source_text: str
    spot_now_text: str
    grid_now_text: str
    total_now_text: str
    warning_text: str
    import_cost_now_text: str
    export_value_now_text: str
    daily_import_cost_text: str
    daily_export_value_text: str
    daily_net_cost_text: str
    current_hour_cost_text: str
    capacity_step_text: str
    capacity_price_text: str
    capacity_basis_text: str
    capacity_warning_text: str
    rows: list[CostRow]

    def as_dict(self) -> dict[str, object]:
        return {
            "source_text": self.source_text,
            "spot_now_text": self.spot_now_text,
            "grid_now_text": self.grid_now_text,
            "total_now_text": self.total_now_text,
            "warning_text": self.warning_text,
            "import_cost_now_text": self.import_cost_now_text,
            "export_value_now_text": self.export_value_now_text,
            "daily_import_cost_text": self.daily_import_cost_text,
            "daily_export_value_text": self.daily_export_value_text,
            "daily_net_cost_text": self.daily_net_cost_text,
            "current_hour_cost_text": self.current_hour_cost_text,
            "capacity_step_text": self.capacity_step_text,
            "capacity_price_text": self.capacity_price_text,
            "capacity_basis_text": self.capacity_basis_text,
            "capacity_warning_text": self.capacity_warning_text,
            "rows": [row.as_dict() for row in self.rows],
        }

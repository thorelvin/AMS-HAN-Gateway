from __future__ import annotations

from dataclasses import dataclass, field
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
class CapacityStepVisual:
    label: str
    price_text: str
    limit_text: str
    fill_percent: str = "0%"
    status: str = "future"


@dataclass(slots=True)
class CapacityEstimateData:
    step_label: str = "-"
    step_price_text: str = "-"
    basis_kw_text: str = "0.00 kW basis"
    basis_text: str = "-"
    warning_text: str = "-"
    steps: list[CapacityStepVisual] = field(default_factory=list)


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


@dataclass(slots=True)
class GatewaySettings:
    last_port: str = ""
    baudrate: int = 115200
    auto_connect: bool = True
    show_advanced: bool = False
    db_path: str = ""
    price_area: str = "NO3"
    grid_day_rate: float = 0.4254
    grid_night_rate: float = 0.2642
    event_filter: str = "all"
    replay_path: str = ""
    replay_lines_per_tick: int = 4
    heatmap_switch_threshold: int = 300
    mains_network_type: str = "TN"

    @classmethod
    def from_dict(cls, raw: dict[str, object] | None = None) -> "GatewaySettings":
        merged = dict(raw or {})
        def as_int(name: str, default: int) -> int:
            try:
                return int(merged.get(name, default) or default)
            except (TypeError, ValueError):
                return default

        def as_float(name: str, default: float) -> float:
            try:
                return float(merged.get(name, default) or default)
            except (TypeError, ValueError):
                return default

        return cls(
            last_port=str(merged.get("last_port", "")),
            baudrate=as_int("baudrate", 115200),
            auto_connect=bool(merged.get("auto_connect", True)),
            show_advanced=bool(merged.get("show_advanced", False)),
            db_path=str(merged.get("db_path", "")),
            price_area=str(merged.get("price_area", "NO3")),
            grid_day_rate=as_float("grid_day_rate", 0.4254),
            grid_night_rate=as_float("grid_night_rate", 0.2642),
            event_filter=str(merged.get("event_filter", "all")),
            replay_path=str(merged.get("replay_path", "")),
            replay_lines_per_tick=as_int("replay_lines_per_tick", 4),
            heatmap_switch_threshold=as_int("heatmap_switch_threshold", 300),
            mains_network_type=str(merged.get("mains_network_type", "TN")),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "last_port": self.last_port,
            "baudrate": self.baudrate,
            "auto_connect": self.auto_connect,
            "show_advanced": self.show_advanced,
            "db_path": self.db_path,
            "price_area": self.price_area,
            "grid_day_rate": self.grid_day_rate,
            "grid_night_rate": self.grid_night_rate,
            "event_filter": self.event_filter,
            "replay_path": self.replay_path,
            "replay_lines_per_tick": self.replay_lines_per_tick,
            "heatmap_switch_threshold": self.heatmap_switch_threshold,
            "mains_network_type": self.mains_network_type,
        }


@dataclass(slots=True)
class DashboardSyncData:
    connection_status: str = "Searching for gateway"
    mains_network_type: str = "TN"
    show_advanced: bool = False
    baudrate: int = 115200
    replay_path: str = ""
    db_path: str = ""
    price_area: str = "NO3"
    grid_day_rate: float = 0.4254
    grid_night_rate: float = 0.2642
    heatmap_switch_threshold: int = 300
    preferred_port_label: str = ""
    device_id: str = "-"
    firmware: str = "-"
    mac: str = "-"
    wifi_state: str = "DISCONNECTED"
    wifi_ip: str = ""
    mqtt_state: str = "IDLE"
    last_frame: str = "seq=0, len=0"
    snapshot_meter: str = "-"
    snapshot_meter_time: str = "-"
    snapshot_power: str = "-"
    snapshot_grid_flow: str = "-"
    snapshot_reactive: str = "-"
    snapshot_voltage: str = "-"
    snapshot_current: str = "-"
    snapshot_power_factor: str = "-"
    snapshot_counters: str = "-"
    snapshot_stats: str = "-"
    overview_title: str = "Waiting for live data"
    overview_value: str = "-"
    overview_subtitle: str = "No valid HAN snapshot yet"
    overview_accent: str = "blue"
    import_bar_width: str = "0%"
    export_bar_width: str = "0%"
    import_bar_text: str = "Import 0.0 W"
    export_bar_text: str = "Export 0.0 W"
    bar_scale_text: str = "No recent peak yet"
    stale_snapshot: bool = False
    replay_loaded: bool = False
    replay_active: bool = False
    replay_paused: bool = False
    replay_status_text: str = "Idle"
    replay_progress_text: str = "No replay loaded"
    replay_source_text: str = "-"
    auto_connect_message: str = "Searching for gateway..."
    logs: list[str] = field(default_factory=list)

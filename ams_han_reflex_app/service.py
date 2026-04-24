"""High-level gateway coordinator that glues serial IO, history, analysis, pricing, and replay together."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .backend.models import (
    CostSummaryData,
    DashboardSyncData,
    DeviceInfo,
    GatewaySettings,
    HistoryRecord,
    HistorySummary,
    MqttStatus,
    ParsedLine,
    SnapshotEvent,
    StatusLine,
    WifiStatus,
)
from .backend.protocol import build_command, mask_sensitive_command
from .backend.serial_worker import SerialManager
from .backend.storage import SnapshotStore
from .domain.analysis import (
    import_export_bar,
    parse_meter_dt,
    signed_grid_w,
    unified_overview,
)
from .domain.mains import DEFAULT_MAINS_NETWORK_TYPE, normalize_mains_network_type
from .domain.pricing import GRID_DAY_RATE_NOK_PER_KWH, GRID_NIGHT_RATE_NOK_PER_KWH, PriceProvider
from .services import (
    AnalysisService,
    ConnectionService,
    CostService,
    HistoryService,
    ReplayService,
    RuntimeService,
    SettingsService,
)
from .support.event_log_store import EventLogStore
from .support.replay_player import ReplayPlayer
from .support.settings_store import SettingsStore

DEFAULT_SETTINGS: dict[str, Any] = GatewaySettings(
    grid_day_rate=GRID_DAY_RATE_NOK_PER_KWH,
    grid_night_rate=GRID_NIGHT_RATE_NOK_PER_KWH,
    mains_network_type=DEFAULT_MAINS_NETWORK_TYPE,
).as_dict()


class GatewayService:
    """Compatibility facade used by the UI while the internals stay split by responsibility."""

    def __init__(
        self,
        db_path: Path,
        *,
        settings_store: SettingsStore | None = None,
        event_log_store: EventLogStore | None = None,
        snapshot_store: SnapshotStore | None = None,
        serial_manager: SerialManager | None = None,
        price_provider: PriceProvider | None = None,
        replay_player: ReplayPlayer | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.settings_service = SettingsService(
            settings_store or SettingsStore(default_settings_path(), DEFAULT_SETTINGS)
        )
        self.settings = self.settings_service.settings
        self.event_log_store = event_log_store or EventLogStore(self.settings_service.directory / "event_log.json")
        # Runtime state, storage, replay, pricing, and connection handling are split
        # into focused services. This coordinator keeps the UI API stable.
        self.runtime_service = RuntimeService(
            self.event_log_store,
            mains_network_type=self.settings.mains_network_type,
            selected_port=str(self.settings.last_port),
            event_rows=self.event_log_store.load(),
        )
        self.db_path = Path(self.settings.db_path or db_path)
        self.history_service = HistoryService(self.db_path, snapshot_store=snapshot_store)
        self.store = self.history_service.store
        self.serial = serial_manager or SerialManager(on_line=self._on_line, on_state=self._on_state)
        self.connection_service = ConnectionService(self.serial)
        self.analysis_service = AnalysisService()
        self.cost_service = CostService(self.history_service, price_provider=price_provider)
        self.price_provider = self.cost_service.price_provider
        self.replay_service = ReplayService(replay_player or ReplayPlayer())
        self.replay_player = self.replay_service.player
        self.replay_records = self.history_service.replay_records
        self._last_probe_attempt = 0.0
        self._reconnect_interval_s = 4.0
        self._data_epoch = 0
        self._event_epoch = 0
        self._settings_epoch = 0
        self._cache = {}

    def _timestamp(self) -> str:
        return self.runtime_service._timestamp()

    def _append_log(self, level: str, line: str) -> None:
        self.runtime_service.append_log(level, line)

    @property
    def mains_network_type(self) -> str:
        return self.runtime_service.state.mains_network_type

    @mains_network_type.setter
    def mains_network_type(self, value: str) -> None:
        self.runtime_service.state.mains_network_type = value

    @property
    def connection_status(self) -> str:
        return self.runtime_service.state.connection_status

    @connection_status.setter
    def connection_status(self, value: str) -> None:
        self.runtime_service.state.connection_status = value

    @property
    def selected_port(self) -> str:
        return self.runtime_service.state.selected_port

    @selected_port.setter
    def selected_port(self, value: str) -> None:
        self.runtime_service.state.selected_port = str(value)

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.runtime_service.state.device_info

    @device_info.setter
    def device_info(self, value: DeviceInfo | None) -> None:
        self.runtime_service.state.device_info = value

    @property
    def wifi_status(self) -> WifiStatus:
        return self.runtime_service.state.wifi_status

    @wifi_status.setter
    def wifi_status(self, value: WifiStatus) -> None:
        self.runtime_service.state.wifi_status = value

    @property
    def mqtt_status(self) -> MqttStatus:
        return self.runtime_service.state.mqtt_status

    @mqtt_status.setter
    def mqtt_status(self, value: MqttStatus) -> None:
        self.runtime_service.state.mqtt_status = value

    @property
    def latest_snapshot(self) -> SnapshotEvent | None:
        return self.runtime_service.state.latest_snapshot

    @latest_snapshot.setter
    def latest_snapshot(self, value: SnapshotEvent | None) -> None:
        self.runtime_service.state.latest_snapshot = value

    @property
    def last_frame_seq(self) -> int:
        return self.runtime_service.state.last_frame_seq

    @last_frame_seq.setter
    def last_frame_seq(self, value: int) -> None:
        self.runtime_service.state.last_frame_seq = int(value)

    @property
    def last_frame_len(self) -> int:
        return self.runtime_service.state.last_frame_len

    @last_frame_len.setter
    def last_frame_len(self, value: int) -> None:
        self.runtime_service.state.last_frame_len = int(value)

    @property
    def latest_kfm_detail(self) -> dict[str, Any] | None:
        return self.runtime_service.state.latest_kfm_detail

    @latest_kfm_detail.setter
    def latest_kfm_detail(self, value: dict[str, Any] | None) -> None:
        self.runtime_service.state.latest_kfm_detail = value

    @property
    def recent_phase_samples(self) -> deque[dict[str, Any]]:
        return self.runtime_service.state.recent_phase_samples

    @recent_phase_samples.setter
    def recent_phase_samples(self, value: deque[dict[str, Any]]) -> None:
        self.runtime_service.state.recent_phase_samples = value

    @property
    def logs(self) -> deque[str]:
        return self.runtime_service.state.logs

    @logs.setter
    def logs(self, value: deque[str]) -> None:
        self.runtime_service.state.logs = value

    @property
    def event_log(self) -> deque[dict[str, str]]:
        return self.runtime_service.state.event_log

    @event_log.setter
    def event_log(self, value: deque[dict[str, str]]) -> None:
        self.runtime_service.state.event_log = value

    @property
    def event_engine(self):
        return self.runtime_service.event_engine

    @event_engine.setter
    def event_engine(self, value) -> None:
        self.runtime_service.event_engine = value

    def _cache_key(self, name: str, *parts: Any) -> tuple[Any, ...]:
        return (name, self._data_epoch, self._event_epoch, self._settings_epoch, *parts)

    def _cache_get_or_set(self, key, builder):
        if key in self._cache:
            return self._cache[key]
        value = builder()
        self._cache[key] = value
        return value

    def _invalidate_data_cache(self):
        self._data_epoch += 1
        self._cache.clear()

    def _invalidate_event_cache(self):
        self._event_epoch += 1
        self._cache.clear()

    def _invalidate_settings_cache(self):
        self._settings_epoch += 1
        self._cache.clear()

    def _save_settings(self):
        self.settings.db_path = str(self.db_path)
        self.settings_service.save()
        self._invalidate_settings_cache()

    def _save_event_log(self, force: bool = False):
        self.runtime_service.save_event_log(force=force)

    @staticmethod
    def _parse_event_delta_w(event: dict[str, Any]) -> float | None:
        return RuntimeService.parse_event_delta_w(event)

    @staticmethod
    def _port_from_label(label: str) -> str:
        return ConnectionService.extract_port_name(label)

    def _reclassify_event_log_for_mains(self) -> None:
        self.runtime_service._reclassify_event_log_for_mains()

    def set_mains_network_type(self, mains_network_type: str) -> None:
        normalized = normalize_mains_network_type(mains_network_type)
        if normalized == self.mains_network_type:
            return
        self.runtime_service.set_mains_network_type(normalized)
        self.settings.mains_network_type = normalized
        self._save_settings()
        self._save_event_log(force=True)
        self._invalidate_data_cache()
        self._invalidate_event_cache()

    def set_heatmap_switch_threshold(self, threshold: int) -> int:
        cleaned = max(100, min(1500, int(threshold)))
        self.settings.heatmap_switch_threshold = cleaned
        self._save_settings()
        return cleaned

    def set_show_advanced(self, show_advanced: bool) -> bool:
        self.settings.show_advanced = bool(show_advanced)
        self._save_settings()
        return bool(self.settings.show_advanced)

    def set_baudrate(self, baudrate: int) -> int:
        cleaned = max(1200, int(baudrate))
        self.settings.baudrate = cleaned
        self._save_settings()
        return cleaned

    def set_replay_path(self, replay_path: str) -> str:
        self.settings.replay_path = str(replay_path)
        self._save_settings()
        return str(self.settings.replay_path)

    def list_ports(self) -> list[str]:
        return self.connection_service.list_port_labels()

    def preferred_port_label(self) -> str:
        target = self.selected_port or self.settings.last_port
        if not target:
            return ""
        return self.connection_service.preferred_port_label(target)

    def _ordered_candidates(self):
        preferred = str(self.settings.last_port)
        return self.connection_service.ordered_candidates(preferred)

    def _probe_port(self, port: str, baudrate: int) -> bool:
        return self.connection_service.probe_port(port, baudrate)

    def auto_connect(self, baudrate: int) -> str:
        if self.replay_service.summary().loaded:
            return "Replay loaded. Stop replay before hardware auto-connect."
        if self.serial.connected:
            current_port = self._port_from_label(self.selected_port) if self.selected_port else self.settings.last_port
            self.connection_status = f"Connected to {current_port}" if current_port else "Connected"
            return self.connection_status
        for option in self._ordered_candidates():
            if self._probe_port(option.port, baudrate):
                self.connect(option.label, baudrate)
                if not self.connection_status.startswith("Connected to"):
                    self.connection_status = f"Connected to {option.port}"
                return self.connection_status
        self.connection_status = "No gateway found"
        return self.connection_status

    def auto_reconnect_if_needed(self, baudrate: int):
        if self.serial.connected or self.replay_service.summary().loaded:
            return
        import time

        now = time.time()
        if now - self._last_probe_attempt < self._reconnect_interval_s:
            return
        self._last_probe_attempt = now
        self.auto_connect(baudrate)

    def tick_runtime(self, baudrate: int) -> None:
        if self.replay_service.summary().active:
            self.advance_replay()
        else:
            self.auto_reconnect_if_needed(baudrate)

    def connect(self, port_label: str, baudrate: int):
        result = self.connection_service.connect(port_label, baudrate)
        self.connection_status = f"Connected to {result.option.port}"
        self.selected_port = result.option.label
        self.settings.last_port = result.option.port
        self.settings.baudrate = result.baudrate
        self._save_settings()
        self._invalidate_data_cache()
        self.request_info()
        self.request_status()

    def disconnect(self):
        if self.serial.connected:
            self.connection_service.disconnect()
        self.connection_status = "Disconnected"

    def send_command(self, cmd: str):
        if self.serial.connected:
            self._append_log("TX", mask_sensitive_command(cmd))
            self.connection_service.send(cmd)

    def request_info(self) -> None:
        self.send_command("GET_INFO")

    def request_status(self) -> None:
        self.send_command("GET_STATUS")

    def set_wifi_config(self, ssid: str, password: str) -> None:
        self.send_command(build_command("SET_WIFI", ssid, password))

    def clear_wifi_config(self) -> None:
        self.send_command("CLEAR_WIFI")

    def set_mqtt_config(self, host: str, port: str | int, user: str = "", password: str = "", prefix: str = "") -> None:
        self.send_command(build_command("SET_MQTT", host, port, user, password, prefix))

    def enable_mqtt(self) -> None:
        self.send_command("MQTT_ENABLE")

    def disable_mqtt(self) -> None:
        self.send_command("MQTT_DISABLE")

    def republish_discovery(self) -> None:
        self.send_command("REPUBLISH_DISCOVERY")

    def _on_state(self, connected: bool, message: str):
        with self._lock:
            self.runtime_service.update_connection_state(
                message,
                invalidate_data_cache=self._invalidate_data_cache,
            )

    def _history_records_desc(self, limit: int = 500):
        return self.history_service.records_desc(limit)

    def _all_records_desc(self):
        return self.history_service.all_records_desc()

    def _derive_baseline(self, current_ts: str, lookback_records: list[HistoryRecord]) -> dict[str, Any] | None:
        vals = []
        curdt = parse_meter_dt(current_ts)
        for r in lookback_records[:12]:
            dt = parse_meter_dt(r.snapshot.timestamp)
            if curdt and dt and abs((curdt - dt).total_seconds()) > 120:
                continue
            vals.append(signed_grid_w(r.snapshot))
        if not vals:
            return None
        vals_sorted = sorted(vals)
        med = vals_sorted[len(vals_sorted) // 2]
        return {"signed_grid_w": med}

    def _record_history(self, snap: SnapshotEvent):
        self.history_service.record_snapshot(snap, replay_mode=self.replay_service.summary().loaded)

    def _snapshot_sample(self, snap: SnapshotEvent) -> dict[str, Any]:
        return self.runtime_service._snapshot_sample(snap)

    def _apply_parsed(self, parsed: ParsedLine):
        self.runtime_service.apply_parsed(
            parsed,
            history_records_desc=self._history_records_desc,
            record_history=self._record_history,
            derive_baseline=self._derive_baseline,
            invalidate_data_cache=self._invalidate_data_cache,
            invalidate_event_cache=self._invalidate_event_cache,
        )

    def _on_line(self, raw: str):
        with self._lock:
            # Live serial traffic and replay traffic both flow through this one ingest
            # path so parsing, history, event detection, and UI state stay in sync.
            self.runtime_service.ingest_raw_line(
                raw,
                history_records_desc=self._history_records_desc,
                record_history=self._record_history,
                derive_baseline=self._derive_baseline,
                invalidate_data_cache=self._invalidate_data_cache,
                invalidate_event_cache=self._invalidate_event_cache,
            )

    # Replay methods
    def _reset_live_buffers(self):
        self.runtime_service.reset_live_buffers(
            invalidate_data_cache=self._invalidate_data_cache,
            invalidate_event_cache=self._invalidate_event_cache,
        )

    def _clear_replay_runtime(self):
        self.runtime_service.clear_replay_runtime(
            self.history_service.clear_replay,
            invalidate_data_cache=self._invalidate_data_cache,
            invalidate_event_cache=self._invalidate_event_cache,
        )

    def load_replay_file(self, path: str) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            msg = f"Replay file not found: {p}"
            self._append_log("WARN", msg)
            return msg
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_file(p)
        self.set_replay_path(str(p))
        self._clear_replay_runtime()
        self.connection_status = f"Replay loaded: {p.name}"
        self._append_log("INFO", self.connection_status)
        return self.connection_status

    def load_replay_lines(self, lines: list[str], source_name: str = "uploaded.log") -> str:
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_lines(lines, source_name)
        self._clear_replay_runtime()
        self.connection_status = f"Replay loaded: {source_name}"
        self._append_log("INFO", self.connection_status)
        return self.connection_status

    def load_demo_replay(self) -> str:
        demo_path = default_demo_replay_path()
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_file(demo_path, demo=True)
        self._clear_replay_runtime()
        self.connection_status = f"Demo replay loaded: {demo_path.name}"
        self._append_log("INFO", self.connection_status)
        return self.connection_status

    def start_replay(self) -> str:
        summary = self.replay_service.summary()
        if not summary.loaded:
            return "No replay loaded"
        self.replay_service.start()
        self.connection_status = f"Replay playing: {summary.source_name}"
        self._append_log("INFO", self.connection_status)
        return self.connection_status

    def pause_or_resume_replay(self) -> str:
        summary = self.replay_service.summary()
        if not summary.loaded:
            return "No replay loaded"
        if summary.active:
            self.replay_service.pause()
            self.connection_status = f"Replay paused: {summary.source_name}"
        else:
            self.replay_service.resume()
            self.connection_status = f"Replay playing: {summary.source_name}"
        self._append_log("INFO", self.connection_status)
        return self.connection_status

    def stop_replay(self) -> str:
        summary = self.replay_service.summary()
        name = summary.source_name or "replay"
        self.replay_service.stop(unload=True)
        self._clear_replay_runtime()
        self.connection_status = "Replay stopped"
        self._append_log("INFO", f"Stopped {name}")
        return self.connection_status

    def advance_replay(self, max_lines: int | None = None) -> int:
        summary = self.replay_service.summary()
        if not summary.loaded:
            return 0
        line_budget = max_lines or int(self.settings.replay_lines_per_tick or 4)
        emitted = 0
        for raw in self.replay_service.advance(line_budget):
            self._on_line(raw)
            emitted += 1
        new_summary = self.replay_service.summary()
        if summary.active and not new_summary.active and new_summary.position >= new_summary.total:
            self.connection_status = f"Replay finished: {new_summary.source_name}"
            self._append_log("INFO", self.connection_status)
        return emitted

    def replay_summary(self) -> dict[str, Any]:
        summary = self.replay_service.summary()
        return {
            "loaded": summary.loaded,
            "active": summary.active,
            "paused": summary.paused,
            "demo": summary.demo,
            "source_name": summary.source_name,
            "status_text": summary.status_text,
            "progress_text": summary.progress_text,
        }

    def dashboard_sync_data(self) -> DashboardSyncData:
        replay = self.replay_summary()
        snapshot = self.snapshot_dict()
        overview = self.unified_overview()
        bars = self.import_export_bar()
        preferred = self.preferred_port_label()
        auto_connect_message = "Searching for gateway..."
        if self.serial.connected:
            auto_connect_message = self.connection_status
        elif replay["loaded"]:
            auto_connect_message = "Replay loaded"
        device_info = self.device_info
        return DashboardSyncData(
            connection_status=self.connection_status,
            mains_network_type=self.mains_network_type,
            show_advanced=bool(self.settings.show_advanced),
            baudrate=int(self.settings.baudrate),
            replay_path=str(self.settings.replay_path),
            db_path=str(self.db_path),
            price_area=str(self.settings.price_area),
            grid_day_rate=float(self.settings.grid_day_rate),
            grid_night_rate=float(self.settings.grid_night_rate),
            heatmap_switch_threshold=int(self.settings.heatmap_switch_threshold),
            preferred_port_label=preferred,
            device_id=device_info.device_id if device_info is not None else "-",
            firmware=device_info.fw_version if device_info is not None else "-",
            mac=device_info.mac if device_info is not None else "-",
            wifi_state=self.wifi_status.state,
            wifi_ip=self.wifi_status.ip,
            mqtt_state=self.mqtt_status.state,
            last_frame=f"seq={self.last_frame_seq}, len={self.last_frame_len}",
            snapshot_meter=snapshot["meter"],
            snapshot_meter_time=snapshot["meter_time"],
            snapshot_power=snapshot["power"],
            snapshot_grid_flow=snapshot["grid_flow"],
            snapshot_reactive=snapshot["reactive"],
            snapshot_voltage=snapshot["voltage"],
            snapshot_current=snapshot["current"],
            snapshot_power_factor=snapshot["power_factor"],
            snapshot_counters=snapshot["counters"],
            snapshot_stats=snapshot["stats"],
            overview_title=overview["title"],
            overview_value=overview["value"],
            overview_subtitle=overview["subtitle"],
            overview_accent=overview["accent"],
            import_bar_width=bars["import_width"],
            export_bar_width=bars["export_width"],
            import_bar_text=bars["import_text"],
            export_bar_text=bars["export_text"],
            bar_scale_text=bars["scale_text"],
            stale_snapshot=(self.has_cached_snapshot() and not self.serial.connected and not bool(replay["loaded"])),
            replay_loaded=bool(replay["loaded"]),
            replay_active=bool(replay["active"]),
            replay_paused=bool(replay["paused"]),
            replay_status_text=str(replay["status_text"]),
            replay_progress_text=str(replay["progress_text"]),
            replay_source_text=str(replay["source_name"] or "-"),
            auto_connect_message=auto_connect_message,
            logs=self.logs_list(),
        )

    # Data accessors
    def logs_list(self, limit: int = 300) -> list[str]:
        return list(self.logs)[:limit]

    def has_cached_snapshot(self) -> bool:
        return (
            self.latest_snapshot is not None and not self.serial.connected and not self.replay_service.summary().active
        )

    def snapshot_dict(self) -> dict[str, Any]:
        from .domain.analysis import signed_grid_w

        s = self.latest_snapshot
        d = self.latest_kfm_detail
        if s is None:
            return {
                "meter": "-",
                "meter_time": "-",
                "power": "-",
                "grid_flow": "-",
                "reactive": "-",
                "voltage": "-",
                "current": "-",
                "power_factor": "-",
                "counters": "-",
                "stats": f"Frames: seq={self.last_frame_seq}, len={self.last_frame_len}",
            }
        signed = s.export_w - s.import_w
        voltage_text = f"Average voltage {s.avg_voltage_v:.1f} V"
        if d is not None:
            voltage_text = (
                f"L1 {d['l1_v']:.1f} V | L2 {d['l2_v']:.1f} V | L3 {d['l3_v']:.1f} V | Avg {d['avg_voltage_v']:.1f} V"
            )
        return {
            "meter": f"{s.meter_id} ({s.meter_type})",
            "meter_time": s.timestamp,
            "power": f"Import {s.import_w:.1f} W | Export {s.export_w:.1f} W | Net {s.net_power_w:.1f} W",
            "grid_flow": f"Signed grid flow {signed:.1f} W (export positive, import negative)",
            "reactive": f"Q+ {s.q_import_var:.1f} var | Q- {s.q_export_var:.1f} var",
            "voltage": voltage_text,
            "current": f"L1 {s.l1_a:.3f} A | L2 {s.l2_a:.3f} A | L3 {s.l3_a:.3f} A | Total {s.total_current_a:.3f} A",
            "power_factor": f"PF {s.estimated_power_factor:.2f} | Apparent {s.apparent_power_va:.1f} VA",
            "counters": f"Rolling {s.rolling_samples} | RX {s.frames_rx} | Bad {s.frames_bad}",
            "stats": f"Frames: seq={self.last_frame_seq}, len={self.last_frame_len}",
        }

    def unified_overview(self):
        return unified_overview(self.latest_snapshot)

    def import_export_bar(self, limit: int = 500):
        return import_export_bar(self.latest_snapshot, self._history_records_desc(limit))

    def get_history_rows(self, limit: int = 200):
        return self.analysis_service.history_rows(self._history_records_desc(limit))

    def get_summary(self, limit: int = 500) -> HistorySummary:
        return self.history_service.summary(limit)

    def analysis_summary(self, limit: int = 1000):
        key = self._cache_key("analysis_summary", limit)

        def _build():
            recent_records = self._history_records_desc(limit)
            latest_dt = parse_meter_dt(recent_records[0].snapshot.timestamp) if recent_records else None
            energy_records = recent_records
            if latest_dt is not None:
                day_start = latest_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                week_start = day_start - timedelta(days=latest_dt.weekday())
                energy_records = self.history_service.records_since_meter_time(week_start)
            return self.analysis_service.analysis_summary(recent_records, energy_records=energy_records)

        return self._cache_get_or_set(key, _build)

    def phase_analysis(self, limit: int = 300):
        return self.analysis_service.phase_analysis(
            list(self.recent_phase_samples)[-limit:],
            self._history_records_desc(limit),
            mains_network_type=self.mains_network_type,
        )

    def top_hour_rows(self, limit: int = 2000, top_n: int = 8):
        return self.analysis_service.top_hour_rows(self._all_records_desc()[:limit], top_n=top_n)

    def event_tracker_rows(self, limit: int = 80, event_filter: str = "all"):
        return self.analysis_service.diagnostics_summary(
            recent_phase_samples=list(self.recent_phase_samples),
            history_records=self._history_records_desc(max(limit, 300)),
            connection_status=self.connection_status,
            wifi_state=self.wifi_status.state,
            mqtt_state=self.mqtt_status.state,
            last_frame_seq=self.last_frame_seq,
            last_frame_len=self.last_frame_len,
            latest_snapshot=self.latest_snapshot,
            event_log=list(self.event_log),
            event_filter=event_filter,
            limit=limit,
            mains_network_type=self.mains_network_type,
        )["events"]

    def daily_graph_data(self, limit: int = 6000):
        return self.analysis_service.daily_graph_data(self._all_records_desc()[:limit])

    def load_heatmaps(self, limit: int = 6000, switch_threshold_w: float = 300.0):
        return self.analysis_service.load_heatmaps(
            self._all_records_desc()[:limit],
            switch_threshold_w=switch_threshold_w,
            mains_network_type=self.mains_network_type,
        )

    def diagnostics_summary(self, limit: int = 80, event_filter: str = "all"):
        return self.analysis_service.diagnostics_summary(
            recent_phase_samples=list(self.recent_phase_samples),
            history_records=self._history_records_desc(max(limit, 300)),
            connection_status=self.connection_status,
            wifi_state=self.wifi_status.state,
            mqtt_state=self.mqtt_status.state,
            last_frame_seq=self.last_frame_seq,
            last_frame_len=self.last_frame_len,
            latest_snapshot=self.latest_snapshot,
            event_log=list(self.event_log),
            event_filter=event_filter,
            limit=limit,
            mains_network_type=self.mains_network_type,
        )

    def _signature_observed_dates(self, limit: int = 6000) -> list[str]:
        observed: list[str] = []
        seen: set[str] = set()
        for record in self._all_records_desc()[:limit]:
            ts = str(record.snapshot.timestamp or "")
            day_text = ts[:10] if len(ts) >= 10 else ""
            if day_text and day_text not in seen:
                seen.add(day_text)
                observed.append(day_text)
        return observed

    def signature_rows(self, limit: int = 12, coverage_limit: int = 6000):
        key = self._cache_key("signature_rows", limit, coverage_limit)
        return self._cache_get_or_set(
            key,
            lambda: self.analysis_service.signature_rows(
                list(self.event_log),
                limit=limit,
                observed_dates=self._signature_observed_dates(coverage_limit),
            ),
        )

    # Cost integration
    def save_cost_settings(self, *, price_area: str, grid_day_rate: float, grid_night_rate: float):
        self.settings.price_area = price_area
        self.settings.grid_day_rate = grid_day_rate
        self.settings.grid_night_rate = grid_night_rate
        self._save_settings()

    def cost_summary(self, limit: int = 8000) -> CostSummaryData:
        area = str(self.settings.price_area)
        day = float(self.settings.grid_day_rate)
        night = float(self.settings.grid_night_rate)
        return self.cost_service.build_summary(
            latest_snapshot=self.latest_snapshot,
            area=area,
            day_rate=day,
            night_rate=night,
            limit=limit,
        )

    def capacity_estimate(self, limit: int = 12000):
        key = self._cache_key("capacity_estimate", limit)
        return self._cache_get_or_set(key, lambda: self.cost_service.capacity_estimate(limit))

    def clear_history(self):
        with self._lock:
            self.history_service.clear_history()
            self.store = self.history_service.store
            self._append_log("INFO", "Snapshot history cleared")
            self._invalidate_data_cache()
            self._invalidate_event_cache()

    def set_db_path(self, path: str):
        self.db_path = Path(path)
        self.history_service.set_db_path(self.db_path)
        self.store = self.history_service.store
        self.settings.db_path = str(self.db_path)
        self._save_settings()
        self._invalidate_data_cache()


def default_db_path() -> Path:
    return Path.home() / ".ams_han_gateway_tool" / "snapshot_history.sqlite3"


def default_settings_path() -> Path:
    return Path.home() / ".ams_han_gateway_tool" / "settings.json"


def default_demo_replay_path() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "demo_session.log"

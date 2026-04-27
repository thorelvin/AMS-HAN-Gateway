"""Live runtime state manager that applies parsed gateway lines to device status, history, and event state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from ..backend.models import DeviceInfo, MqttStatus, ParsedLine, SnapshotEvent, StatusLine, WifiStatus
from ..backend.protocol import parse_line
from ..domain.analysis import signed_grid_w
from ..domain.event_engine import EventEngineV2
from ..domain.frame_parser import parse_kfm001_frame
from ..domain.mains import classify_phase_delta, normalize_mains_network_type, parse_phase_delta_text
from ..domain.signatures import likely_device_hint
from ..support.event_log_store import EventLogStore


HistoryRecordsProvider = Callable[[int], list[Any]]
RecordHistoryCallback = Callable[[SnapshotEvent], None]
DeriveBaselineCallback = Callable[[str, list[Any]], dict[str, Any] | None]
InvalidateCallback = Callable[[], None]
ClearReplayCallback = Callable[[], None]


@dataclass(slots=True)
class RuntimeState:
    mains_network_type: str
    connection_status: str = "Searching for gateway"
    selected_port: str = ""
    device_info: DeviceInfo | None = None
    wifi_status: WifiStatus = field(default_factory=lambda: WifiStatus(state="DISCONNECTED", ip=""))
    mqtt_status: MqttStatus = field(default_factory=lambda: MqttStatus(state="IDLE"))
    latest_snapshot: SnapshotEvent | None = None
    last_frame_seq: int = 0
    last_frame_len: int = 0
    latest_kfm_detail: dict[str, Any] | None = None
    recent_phase_samples: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=1200))
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=1800))
    event_log: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=1200))


class RuntimeService:
    """Applies parsed gateway lines to the mutable live state used by the dashboard."""

    def __init__(
        self,
        event_log_store: EventLogStore,
        *,
        mains_network_type: str,
        selected_port: str = "",
        event_rows: list[dict[str, str]] | None = None,
    ) -> None:
        normalized = normalize_mains_network_type(mains_network_type)
        self.event_log_store = event_log_store
        self.state = RuntimeState(
            mains_network_type=normalized,
            selected_port=str(selected_port),
            event_log=deque(event_rows or [], maxlen=event_log_store.max_items),
        )
        self.event_engine = EventEngineV2(mains_network_type=normalized)

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def append_log(self, level: str, line: str) -> None:
        self.state.logs.appendleft(f"[{self._timestamp()}] {level}: {line}")

    def save_event_log(self, force: bool = False) -> None:
        rows = list(self.state.event_log)
        if force:
            self.event_log_store.flush(rows)
        else:
            self.event_log_store.flush_if_needed(rows)

    @staticmethod
    def parse_event_delta_w(event: dict[str, Any]) -> float | None:
        raw = event.get("dW", event.get("delta_signed"))
        if raw in (None, "", "-"):
            return None
        try:
            return float(str(raw).replace("W", "").strip())
        except ValueError:
            return None

    def set_mains_network_type(self, mains_network_type: str) -> str:
        normalized = normalize_mains_network_type(mains_network_type)
        self.state.mains_network_type = normalized
        self.event_engine = EventEngineV2(mains_network_type=normalized)
        self._reclassify_event_log_for_mains()
        return normalized

    def _reclassify_event_log_for_mains(self) -> None:
        # Existing power events are re-labeled when the user switches between TN and IT
        # so signatures, heatmaps, and diagnostics stay consistent with the chosen model.
        session_start_info: dict[str, tuple[str, str]] = {}
        for event in self.state.event_log:
            if str(event.get("category", "") or "") != "power":
                continue
            if str(event.get("type", event.get("event_type", "")) or "") != "load_session_start":
                continue
            parsed = parse_phase_delta_text(event.get("phase_delta"))
            if parsed is None:
                continue
            phase = classify_phase_delta(parsed[0], parsed[1], parsed[2], self.state.mains_network_type)
            delta_w = self.parse_event_delta_w(event) or 0.0
            note = likely_device_hint(
                delta_w,
                phase,
                sustained=True,
                mains_network_type=self.state.mains_network_type,
            )
            event["phase"] = phase
            event["summary"] = f"Load session start {delta_w:+.0f} W on {phase}"
            event["note"] = note
            session_start_info[str(event.get("time", "-") or "-")] = (phase, note)

        for event in self.state.event_log:
            category = str(event.get("category", "") or "")
            parsed = parse_phase_delta_text(event.get("phase_delta"))
            if parsed is None or category not in ("power", "phase"):
                continue
            phase = classify_phase_delta(parsed[0], parsed[1], parsed[2], self.state.mains_network_type)
            event["phase"] = phase
            if category != "power":
                continue
            event_type = str(event.get("type", event.get("event_type", "")) or "")
            delta_w = self.parse_event_delta_w(event) or 0.0
            if event_type == "load_session_start":
                continue
            if event_type == "load_session_end":
                start_text = str(event.get("note", "") or "")
                start_text = (
                    start_text[16:35] if start_text.startswith("Session started ") and len(start_text) >= 35 else "-"
                )
                event["summary"] = f"Load session ended on {phase}"
                signature_note = session_start_info.get(
                    start_text,
                    (phase, likely_device_hint(delta_w, phase, mains_network_type=self.state.mains_network_type)),
                )[1]
                event["note"] = f"Session started {start_text} ({signature_note})"
            elif event_type == "power_step":
                direction = "Export step" if delta_w > 0 else "Import step"
                event["summary"] = f"{direction} {delta_w:+.0f} W on {phase}"
                event["note"] = likely_device_hint(delta_w, phase, mains_network_type=self.state.mains_network_type)

    def update_connection_state(self, message: str, *, invalidate_data_cache: InvalidateCallback) -> None:
        self.state.connection_status = message
        self.append_log("INFO", message)
        invalidate_data_cache()

    def _snapshot_sample(self, snap: SnapshotEvent) -> dict[str, Any]:
        detail = self.state.latest_kfm_detail or {}
        # Event rules operate on a compact, normalized sample shape rather than the
        # raw protocol models. That keeps the event engine independent of serial details.
        return {
            "timestamp": snap.timestamp,
            "import_w": snap.import_w,
            "export_w": snap.export_w,
            "signed_grid_w": signed_grid_w(snap),
            "l1_a": snap.l1_a,
            "l2_a": snap.l2_a,
            "l3_a": snap.l3_a,
            "l1_v": float(detail.get("l1_v", snap.avg_voltage_v)),
            "l2_v": float(detail.get("l2_v", 0.0)),
            "l3_v": float(detail.get("l3_v", snap.avg_voltage_v)),
        }

    def apply_parsed(
        self,
        parsed: ParsedLine,
        *,
        history_records_desc: HistoryRecordsProvider,
        record_history: RecordHistoryCallback,
        derive_baseline: DeriveBaselineCallback,
        invalidate_data_cache: InvalidateCallback,
        invalidate_event_cache: InvalidateCallback,
    ) -> None:
        if parsed.kind == "device_info":
            self.state.device_info = parsed.payload
        elif parsed.kind == "wifi_status":
            self.state.wifi_status = parsed.payload
        elif parsed.kind == "mqtt_status":
            self.state.mqtt_status = parsed.payload
        elif parsed.kind == "status":
            status = parsed.payload
            if isinstance(status, StatusLine):
                if status.category == "WIFI":
                    self.state.wifi_status = WifiStatus(state=status.state, ip=status.extra)
                elif status.category == "MQTT":
                    self.state.mqtt_status = MqttStatus(state=status.state)
                elif status.category == "HAN" and status.extra:
                    self.append_log("INFO", f"HAN status: {status.state} ({status.extra})")
                elif status.category == "HAN":
                    self.append_log("INFO", f"HAN status: {status.state}")
        elif parsed.kind == "frame":
            self.state.last_frame_seq = parsed.payload.sequence
            self.state.last_frame_len = parsed.payload.length
            # FRAME lines carry richer raw meter data than SNAP. When they decode
            # cleanly, the dashboard can show per-phase voltages and extra detail.
            detail = parse_kfm001_frame(parsed.payload.hex_payload)
            if detail:
                self.state.latest_kfm_detail = detail
        elif parsed.kind == "snapshot":
            snap = parsed.payload
            if self.state.latest_kfm_detail and self.state.latest_kfm_detail.get("meter_timestamp") == snap.timestamp:
                snap.avg_voltage_v = float(self.state.latest_kfm_detail.get("avg_voltage_v", snap.avg_voltage_v))
                snap.apparent_power_va = float(
                    self.state.latest_kfm_detail.get("apparent_power_va", snap.apparent_power_va)
                )
                snap.estimated_power_factor = float(
                    self.state.latest_kfm_detail.get("estimated_power_factor", snap.estimated_power_factor)
                )
                snap.total_current_a = float(self.state.latest_kfm_detail.get("total_current_a", snap.total_current_a))
            self.state.latest_snapshot = snap
            record_history(snap)
            sample = self._snapshot_sample(snap)
            previous = self.state.recent_phase_samples[-1] if self.state.recent_phase_samples else None
            # Baselines come from slightly older history so we can classify changes as
            # "normal background" versus "notable event" without relying on one sample.
            baseline = derive_baseline(snap.timestamp, history_records_desc(30)[1:])
            self.state.recent_phase_samples.append(sample)
            for event in self.event_engine.process_sample(sample, previous, baseline):
                row = event.as_row()
                self.state.event_log.appendleft(row)
                self.event_log_store.mark_dirty()
            self.save_event_log(False)
        elif parsed.kind == "parse_error":
            self.append_log("WARN", parsed.error or f"Parse error: {parsed.raw}")
        elif parsed.kind == "error":
            self.append_log("ERR", parsed.error or "Protocol error")
        invalidate_data_cache()
        invalidate_event_cache()

    def ingest_raw_line(
        self,
        raw: str,
        *,
        history_records_desc: HistoryRecordsProvider,
        record_history: RecordHistoryCallback,
        derive_baseline: DeriveBaselineCallback,
        invalidate_data_cache: InvalidateCallback,
        invalidate_event_cache: InvalidateCallback,
    ) -> None:
        parsed = parse_line(raw)
        self.append_log("RX", raw)
        self.apply_parsed(
            parsed,
            history_records_desc=history_records_desc,
            record_history=record_history,
            derive_baseline=derive_baseline,
            invalidate_data_cache=invalidate_data_cache,
            invalidate_event_cache=invalidate_event_cache,
        )

    def reset_live_buffers(
        self,
        *,
        invalidate_data_cache: InvalidateCallback,
        invalidate_event_cache: InvalidateCallback,
    ) -> None:
        self.state.device_info = None
        self.state.wifi_status = WifiStatus(state="DISCONNECTED", ip="")
        self.state.mqtt_status = MqttStatus(state="IDLE")
        self.state.latest_snapshot = None
        self.state.last_frame_seq = 0
        self.state.last_frame_len = 0
        self.state.latest_kfm_detail = None
        self.state.recent_phase_samples.clear()
        self.event_engine = EventEngineV2(mains_network_type=self.state.mains_network_type)
        invalidate_data_cache()
        invalidate_event_cache()

    def clear_replay_runtime(
        self,
        clear_replay: ClearReplayCallback,
        *,
        invalidate_data_cache: InvalidateCallback,
        invalidate_event_cache: InvalidateCallback,
    ) -> None:
        clear_replay()
        self.reset_live_buffers(
            invalidate_data_cache=invalidate_data_cache,
            invalidate_event_cache=invalidate_event_cache,
        )

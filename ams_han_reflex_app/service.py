from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .backend.models import CostSummaryData, DeviceInfo, GatewaySettings, HistorySummary, MqttStatus, ParsedLine, SnapshotEvent, StatusLine, WifiStatus
from .backend.protocol import build_command, mask_sensitive_command, parse_line
from .backend.serial_worker import SerialManager
from .backend.storage import SnapshotStore
from .domain.analysis import (
    import_export_bar, parse_meter_dt, signed_grid_w, unified_overview,
)
from .domain.event_engine import EventEngineV2
from .domain.frame_parser import parse_kfm001_frame
from .domain.mains import DEFAULT_MAINS_NETWORK_TYPE, classify_phase_delta, normalize_mains_network_type, parse_phase_delta_text
from .domain.pricing import GRID_DAY_RATE_NOK_PER_KWH, GRID_NIGHT_RATE_NOK_PER_KWH, PRICE_AREAS, PriceProvider
from .domain.signatures import build_signature_rows, likely_device_hint
from .services import AnalysisService, ConnectionService, CostService, HistoryService, ReplayService, SettingsService
from .support.event_log_store import EventLogStore
from .support.replay_player import ReplayPlayer
from .support.settings_store import SettingsStore

DEFAULT_SETTINGS: dict[str, Any] = GatewaySettings(
    grid_day_rate=GRID_DAY_RATE_NOK_PER_KWH,
    grid_night_rate=GRID_NIGHT_RATE_NOK_PER_KWH,
    mains_network_type=DEFAULT_MAINS_NETWORK_TYPE,
).as_dict()

class GatewayService:
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
        self.settings_service = SettingsService(settings_store or SettingsStore(default_settings_path(), DEFAULT_SETTINGS))
        self.settings = self.settings_service.settings
        self.event_log_store = event_log_store or EventLogStore(self.settings_service.directory/'event_log.json')
        self.db_path = Path(self.settings.db_path or db_path)
        self.history_service = HistoryService(self.db_path, snapshot_store=snapshot_store)
        self.store = self.history_service.store
        self.serial = serial_manager or SerialManager(on_line=self._on_line, on_state=self._on_state)
        self.connection_service = ConnectionService(self.serial)
        self.mains_network_type = normalize_mains_network_type(self.settings.mains_network_type)
        self.connection_status='Searching for gateway'
        self.selected_port=str(self.settings.last_port)
        self.device_info: DeviceInfo | None = None
        self.wifi_status = WifiStatus(state='DISCONNECTED', ip='')
        self.mqtt_status = MqttStatus(state='IDLE')
        self.latest_snapshot: SnapshotEvent | None = None
        self.last_frame_seq = 0
        self.last_frame_len = 0
        self.latest_kfm_detail: dict[str, Any] | None = None
        self.recent_phase_samples: deque[dict[str, Any]] = deque(maxlen=1200)
        self.logs: deque[str] = deque(maxlen=1800)
        self.event_log: deque[dict[str, str]] = deque(self.event_log_store.load(), maxlen=1200)
        self.event_engine = EventEngineV2(mains_network_type=self.mains_network_type)
        self.analysis_service = AnalysisService()
        self.cost_service = CostService(self.history_service, price_provider=price_provider)
        self.price_provider = self.cost_service.price_provider
        self.replay_service = ReplayService(replay_player or ReplayPlayer())
        self.replay_player = self.replay_service.player
        self.replay_records = self.history_service.replay_records
        self._last_probe_attempt=0.0
        self._reconnect_interval_s=4.0
        self._data_epoch=0; self._event_epoch=0; self._settings_epoch=0; self._cache={}

    def _timestamp(self) -> str:
        return datetime.now().strftime('%H:%M:%S')

    def _append_log(self, level: str, line: str) -> None:
        self.logs.appendleft(f'[{self._timestamp()}] {level}: {line}')

    def _cache_key(self, name: str, *parts: Any) -> tuple[Any,...]:
        return (name, self._data_epoch, self._event_epoch, self._settings_epoch, *parts)

    def _cache_get_or_set(self, key, builder):
        if key in self._cache:
            return self._cache[key]
        value = builder()
        self._cache[key]=value
        return value

    def _invalidate_data_cache(self):
        self._data_epoch +=1; self._cache.clear()
    def _invalidate_event_cache(self):
        self._event_epoch +=1; self._cache.clear()
    def _invalidate_settings_cache(self):
        self._settings_epoch +=1; self._cache.clear()

    def _save_settings(self):
        self.settings.db_path = str(self.db_path)
        self.settings_service.save()
        self._invalidate_settings_cache()

    def _save_event_log(self, force: bool=False):
        if force: self.event_log_store.flush(list(self.event_log))
        else: self.event_log_store.flush_if_needed(list(self.event_log))

    @staticmethod
    def _parse_event_delta_w(event: dict[str, Any]) -> float | None:
        raw = event.get('dW', event.get('delta_signed'))
        if raw in (None, '', '-'):
            return None
        try:
            return float(str(raw).replace('W', '').strip())
        except ValueError:
            return None

    @staticmethod
    def _port_from_label(label: str) -> str:
        return ConnectionService.extract_port_name(label)

    def _reclassify_event_log_for_mains(self) -> None:
        session_start_info: dict[str, tuple[str, str]] = {}
        for event in self.event_log:
            if str(event.get('category', '') or '') != 'power':
                continue
            if str(event.get('type', event.get('event_type', '')) or '') != 'load_session_start':
                continue
            parsed = parse_phase_delta_text(event.get('phase_delta'))
            if parsed is None:
                continue
            phase = classify_phase_delta(parsed[0], parsed[1], parsed[2], self.mains_network_type)
            delta_w = self._parse_event_delta_w(event) or 0.0
            note = likely_device_hint(delta_w, phase, sustained=True, mains_network_type=self.mains_network_type)
            event['phase'] = phase
            event['summary'] = f'Load session start {delta_w:+.0f} W on {phase}'
            event['note'] = note
            session_start_info[str(event.get('time', '-') or '-')] = (phase, note)

        for event in self.event_log:
            category = str(event.get('category', '') or '')
            parsed = parse_phase_delta_text(event.get('phase_delta'))
            if parsed is None or category not in ('power', 'phase'):
                continue
            phase = classify_phase_delta(parsed[0], parsed[1], parsed[2], self.mains_network_type)
            event['phase'] = phase
            if category != 'power':
                continue
            event_type = str(event.get('type', event.get('event_type', '')) or '')
            delta_w = self._parse_event_delta_w(event) or 0.0
            if event_type == 'load_session_start':
                continue
            elif event_type == 'load_session_end':
                start_text = str(event.get('note', '') or '')
                start_text = start_text[16:35] if start_text.startswith('Session started ') and len(start_text) >= 35 else '-'
                event['summary'] = f'Load session ended on {phase}'
                signature_note = session_start_info.get(start_text, (phase, likely_device_hint(delta_w, phase, mains_network_type=self.mains_network_type)))[1]
                event['note'] = f'Session started {start_text} ({signature_note})'
            elif event_type == 'power_step':
                direction = 'Export step' if delta_w > 0 else 'Import step'
                event['summary'] = f'{direction} {delta_w:+.0f} W on {phase}'
                event['note'] = likely_device_hint(delta_w, phase, mains_network_type=self.mains_network_type)

    def set_mains_network_type(self, mains_network_type: str) -> None:
        normalized = normalize_mains_network_type(mains_network_type)
        if normalized == self.mains_network_type:
            return
        self.mains_network_type = normalized
        self.settings.mains_network_type = normalized
        self._save_settings()
        self.event_engine = EventEngineV2(mains_network_type=normalized)
        self._reclassify_event_log_for_mains()
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
            return ''
        return self.connection_service.preferred_port_label(target)

    def _ordered_candidates(self):
        preferred = str(self.settings.last_port)
        return self.connection_service.ordered_candidates(preferred)

    def _probe_port(self, port: str, baudrate: int) -> bool:
        return self.connection_service.probe_port(port, baudrate)

    def auto_connect(self, baudrate: int) -> str:
        if self.replay_service.summary().loaded:
            return 'Replay loaded. Stop replay before hardware auto-connect.'
        if self.serial.connected:
            current_port = self._port_from_label(self.selected_port) if self.selected_port else self.settings.last_port
            self.connection_status = f'Connected to {current_port}' if current_port else 'Connected'
            return self.connection_status
        for option in self._ordered_candidates():
            if self._probe_port(option.port, baudrate):
                self.connect(option.label, baudrate)
                if not self.connection_status.startswith('Connected to'):
                    self.connection_status = f'Connected to {option.port}'
                return self.connection_status
        self.connection_status='No gateway found'
        return self.connection_status

    def auto_reconnect_if_needed(self, baudrate: int):
        if self.serial.connected or self.replay_service.summary().loaded:
            return
        import time
        now=time.time()
        if now - self._last_probe_attempt < self._reconnect_interval_s:
            return
        self._last_probe_attempt = now
        self.auto_connect(baudrate)

    def connect(self, port_label: str, baudrate: int):
        result = self.connection_service.connect(port_label, baudrate)
        self.connection_status = f'Connected to {result.option.port}'
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
        self.connection_status='Disconnected'

    def send_command(self, cmd: str):
        if self.serial.connected:
            self._append_log('TX', mask_sensitive_command(cmd))
            self.connection_service.send(cmd)

    def request_info(self) -> None:
        self.send_command('GET_INFO')

    def request_status(self) -> None:
        self.send_command('GET_STATUS')

    def set_wifi_config(self, ssid: str, password: str) -> None:
        self.send_command(build_command('SET_WIFI', ssid, password))

    def clear_wifi_config(self) -> None:
        self.send_command('CLEAR_WIFI')

    def set_mqtt_config(self, host: str, port: str | int, user: str = '', password: str = '', prefix: str = '') -> None:
        self.send_command(build_command('SET_MQTT', host, port, user, password, prefix))

    def enable_mqtt(self) -> None:
        self.send_command('MQTT_ENABLE')

    def disable_mqtt(self) -> None:
        self.send_command('MQTT_DISABLE')

    def republish_discovery(self) -> None:
        self.send_command('REPUBLISH_DISCOVERY')

    def _on_state(self, connected: bool, message: str):
        with self._lock:
            self.connection_status = message
            self._append_log('INFO', message)
            self._invalidate_data_cache()

    def _history_records_desc(self, limit: int = 500):
        return self.history_service.records_desc(limit)

    def _all_records_desc(self):
        return self.history_service.all_records_desc()

    def _derive_baseline(self, current_ts: str, lookback_records: list[HistoryRecord]) -> dict[str, Any] | None:
        vals=[]
        curdt = parse_meter_dt(current_ts)
        for r in lookback_records[:12]:
            dt=parse_meter_dt(r.snapshot.timestamp)
            if curdt and dt and abs((curdt-dt).total_seconds())>120:
                continue
            vals.append(signed_grid_w(r.snapshot))
        if not vals: return None
        vals_sorted=sorted(vals)
        med = vals_sorted[len(vals_sorted)//2]
        return {'signed_grid_w': med}

    def _record_history(self, snap: SnapshotEvent):
        self.history_service.record_snapshot(snap, replay_mode=self.replay_service.summary().loaded)

    def _snapshot_sample(self, snap: SnapshotEvent) -> dict[str, Any]:
        detail = self.latest_kfm_detail or {}
        return {
            'timestamp': snap.timestamp,
            'import_w': snap.import_w,
            'export_w': snap.export_w,
            'signed_grid_w': snap.export_w - snap.import_w,
            'l1_a': snap.l1_a,
            'l2_a': snap.l2_a,
            'l3_a': snap.l3_a,
            'l1_v': float(detail.get('l1_v', snap.avg_voltage_v)),
            'l2_v': float(detail.get('l2_v', 0.0)),
            'l3_v': float(detail.get('l3_v', snap.avg_voltage_v)),
        }

    def _apply_parsed(self, parsed: ParsedLine):
        if parsed.kind == 'device_info':
            self.device_info = parsed.payload
        elif parsed.kind == 'wifi_status':
            self.wifi_status = parsed.payload
        elif parsed.kind == 'mqtt_status':
            self.mqtt_status = parsed.payload
        elif parsed.kind == 'status':
            status = parsed.payload
            if isinstance(status, StatusLine):
                if status.category == 'WIFI':
                    self.wifi_status = WifiStatus(state=status.state, ip=status.extra)
                elif status.category == 'MQTT':
                    self.mqtt_status = MqttStatus(state=status.state)
                elif status.category == 'HAN' and status.extra:
                    self._append_log('INFO', f'HAN status: {status.state} ({status.extra})')
                elif status.category == 'HAN':
                    self._append_log('INFO', f'HAN status: {status.state}')
        elif parsed.kind == 'frame':
            self.last_frame_seq = parsed.payload.sequence
            self.last_frame_len = parsed.payload.length
            detail = parse_kfm001_frame(parsed.payload.hex_payload)
            if detail:
                self.latest_kfm_detail = detail
        elif parsed.kind == 'snapshot':
            snap = parsed.payload
            if self.latest_kfm_detail and self.latest_kfm_detail.get('meter_timestamp') == snap.timestamp:
                # enrich avg voltage if better
                snap.avg_voltage_v = float(self.latest_kfm_detail.get('avg_voltage_v', snap.avg_voltage_v))
            self.latest_snapshot = snap
            self._record_history(snap)
            sample = self._snapshot_sample(snap)
            previous = self.recent_phase_samples[-1] if self.recent_phase_samples else None
            baseline = self._derive_baseline(snap.timestamp, self._history_records_desc(30)[1:])
            self.recent_phase_samples.append(sample)
            for event in self.event_engine.process_sample(sample, previous, baseline):
                row = event.as_row()
                self.event_log.appendleft(row)
                self.event_log_store.mark_dirty()
            self._save_event_log(False)
        elif parsed.kind == 'parse_error':
            self._append_log('WARN', parsed.error or f'Parse error: {parsed.raw}')
        elif parsed.kind == 'error':
            self._append_log('ERR', parsed.error or 'Protocol error')
        self._invalidate_data_cache(); self._invalidate_event_cache()

    def _on_line(self, raw: str):
        parsed = parse_line(raw)
        with self._lock:
            self._append_log('RX', raw)
            self._apply_parsed(parsed)

    # Replay methods
    def _reset_live_buffers(self):
        self.device_info=None; self.wifi_status=WifiStatus(state='DISCONNECTED',ip=''); self.mqtt_status=MqttStatus(state='IDLE')
        self.latest_snapshot=None; self.last_frame_seq=0; self.last_frame_len=0; self.latest_kfm_detail=None
        self.recent_phase_samples.clear(); self.event_engine=EventEngineV2(mains_network_type=self.mains_network_type); self._invalidate_data_cache(); self._invalidate_event_cache()

    def _clear_replay_runtime(self):
        self.history_service.clear_replay()
        self._reset_live_buffers()

    def load_replay_file(self, path: str) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            msg = f'Replay file not found: {p}'
            self._append_log('WARN', msg)
            return msg
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_file(p)
        self.set_replay_path(str(p))
        self._clear_replay_runtime()
        self.connection_status = f'Replay loaded: {p.name}'
        self._append_log('INFO', self.connection_status)
        return self.connection_status

    def load_replay_lines(self, lines: list[str], source_name: str = 'uploaded.log') -> str:
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_lines(lines, source_name)
        self._clear_replay_runtime()
        self.connection_status = f'Replay loaded: {source_name}'
        self._append_log('INFO', self.connection_status)
        return self.connection_status

    def load_demo_replay(self) -> str:
        demo_path = default_demo_replay_path()
        if self.serial.connected:
            self.connection_service.disconnect()
        self.replay_service.load_file(demo_path, demo=True)
        self._clear_replay_runtime()
        self.connection_status = f'Demo replay loaded: {demo_path.name}'
        self._append_log('INFO', self.connection_status)
        return self.connection_status

    def start_replay(self) -> str:
        summary = self.replay_service.summary()
        if not summary.loaded:
            return 'No replay loaded'
        self.replay_service.start()
        self.connection_status = f'Replay playing: {summary.source_name}'
        self._append_log('INFO', self.connection_status)
        return self.connection_status

    def pause_or_resume_replay(self) -> str:
        summary = self.replay_service.summary()
        if not summary.loaded:
            return 'No replay loaded'
        if summary.active:
            self.replay_service.pause()
            self.connection_status = f'Replay paused: {summary.source_name}'
        else:
            self.replay_service.resume()
            self.connection_status = f'Replay playing: {summary.source_name}'
        self._append_log('INFO', self.connection_status)
        return self.connection_status

    def stop_replay(self) -> str:
        summary = self.replay_service.summary()
        name = summary.source_name or 'replay'
        self.replay_service.stop(unload=True)
        self._clear_replay_runtime()
        self.connection_status = 'Replay stopped'
        self._append_log('INFO', f'Stopped {name}')
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
            self.connection_status = f'Replay finished: {new_summary.source_name}'
            self._append_log('INFO', self.connection_status)
        return emitted

    def replay_summary(self) -> dict[str, Any]:
        summary = self.replay_service.summary()
        return {
            'loaded': summary.loaded,
            'active': summary.active,
            'paused': summary.paused,
            'demo': summary.demo,
            'source_name': summary.source_name,
            'status_text': summary.status_text,
            'progress_text': summary.progress_text,
        }

    # Data accessors
    def logs_list(self, limit: int = 300) -> list[str]:
        return list(self.logs)[:limit]
    def has_cached_snapshot(self) -> bool:
        return self.latest_snapshot is not None and not self.serial.connected and not self.replay_service.summary().active
    def snapshot_dict(self) -> dict[str, Any]:
        from .domain.analysis import signed_grid_w
        s=self.latest_snapshot; d=self.latest_kfm_detail
        if s is None:
            return {'meter':'-','meter_time':'-','power':'-','grid_flow':'-','reactive':'-','voltage':'-','current':'-','power_factor':'-','counters':'-','stats':f'Frames: seq={self.last_frame_seq}, len={self.last_frame_len}'}
        signed=s.export_w - s.import_w
        voltage_text=f'Average voltage {s.avg_voltage_v:.1f} V'
        if d is not None:
            voltage_text=f"L1 {d['l1_v']:.1f} V | L2 {d['l2_v']:.1f} V | L3 {d['l3_v']:.1f} V | Avg {d['avg_voltage_v']:.1f} V"
        return {'meter':f'{s.meter_id} ({s.meter_type})','meter_time':s.timestamp,'power':f'Import {s.import_w:.1f} W | Export {s.export_w:.1f} W | Net {s.net_power_w:.1f} W','grid_flow':f'Signed grid flow {signed:.1f} W (export positive, import negative)','reactive':f'Q+ {s.q_import_var:.1f} var | Q- {s.q_export_var:.1f} var','voltage':voltage_text,'current':f'L1 {s.l1_a:.3f} A | L2 {s.l2_a:.3f} A | L3 {s.l3_a:.3f} A | Total {s.total_current_a:.3f} A','power_factor':f'PF {s.estimated_power_factor:.2f} | Apparent {s.apparent_power_va:.1f} VA','counters':f'Rolling {s.rolling_samples} | RX {s.frames_rx} | Bad {s.frames_bad}','stats':f'Frames: seq={self.last_frame_seq}, len={self.last_frame_len}'}
    def unified_overview(self): return unified_overview(self.latest_snapshot)
    def import_export_bar(self, limit: int=500):
        return import_export_bar(self.latest_snapshot, self._history_records_desc(limit))
    def get_history_rows(self, limit: int = 200):
        return self.analysis_service.history_rows(self._history_records_desc(limit))

    def get_summary(self, limit: int = 500) -> HistorySummary:
        return self.history_service.summary(limit)

    def analysis_summary(self, limit: int = 1000):
        return self.analysis_service.analysis_summary(self._history_records_desc(limit))

    def phase_analysis(self, limit: int = 300):
        return self.analysis_service.phase_analysis(
            list(self.recent_phase_samples)[-limit:],
            self._history_records_desc(limit),
            mains_network_type=self.mains_network_type,
        )

    def top_hour_rows(self, limit: int = 2000, top_n: int = 8):
        return self.analysis_service.top_hour_rows(self._all_records_desc()[:limit], top_n=top_n)

    def event_tracker_rows(self, limit: int = 80, event_filter: str = 'all'):
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
        )['events']

    def daily_graph_data(self, limit: int = 6000):
        return self.analysis_service.daily_graph_data(self._all_records_desc()[:limit])

    def load_heatmaps(self, limit: int = 6000, switch_threshold_w: float = 300.0):
        return self.analysis_service.load_heatmaps(
            self._all_records_desc()[:limit],
            switch_threshold_w=switch_threshold_w,
            mains_network_type=self.mains_network_type,
        )

    def diagnostics_summary(self, limit: int = 80, event_filter: str = 'all'):
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
            ts = str(record.snapshot.timestamp or '')
            day_text = ts[:10] if len(ts) >= 10 else ''
            if day_text and day_text not in seen:
                seen.add(day_text)
                observed.append(day_text)
        return observed

    def signature_rows(self, limit: int = 12, coverage_limit: int = 6000):
        key = self._cache_key('signature_rows', limit, coverage_limit)
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

    def clear_history(self):
        with self._lock:
            self.history_service.clear_history()
            self.store = self.history_service.store
            self._append_log('INFO', 'Snapshot history cleared')
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
    return Path.home()/'.ams_han_gateway_tool'/'snapshot_history.sqlite3'

def default_settings_path() -> Path:
    return Path.home()/'.ams_han_gateway_tool'/'settings.json'

def default_demo_replay_path() -> Path:
    return Path(__file__).resolve().parent.parent/'fixtures'/'demo_session.log'


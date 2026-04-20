from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from .backend.models import DeviceInfo, HistoryRecord, MqttStatus, ParsedLine, SnapshotEvent, StatusLine, WifiStatus
from .backend.protocol import is_gateway_protocol_line, mask_sensitive_command, parse_line
from .backend.serial_worker import SerialConfig, SerialManager
from .backend.storage import SnapshotStore
from .domain.analysis import (
    analysis_summary, build_load_heatmaps, daily_graph_data, diagnose_issues, health_rows, history_rows,
    import_export_bar, parse_meter_dt, phase_analysis, signed_grid_w,
    top_hour_rows, unified_overview, what_changed,
)
from .domain.event_engine import EventEngineV2
from .domain.frame_parser import parse_kfm001_frame
from .domain.pricing import GRID_DAY_RATE_NOK_PER_KWH, GRID_NIGHT_RATE_NOK_PER_KWH, PRICE_AREAS, PriceProvider, estimate_capacity
from .domain.signatures import build_signature_rows
from .support.event_log_store import EventLogStore
from .support.replay_player import ReplayPlayer
from .support.settings_store import SettingsStore

DEFAULT_SETTINGS: dict[str, Any] = {
    'last_port':'', 'baudrate':115200, 'auto_connect':True, 'show_advanced':False, 'db_path':'',
    'price_area':'NO3', 'grid_day_rate':GRID_DAY_RATE_NOK_PER_KWH, 'grid_night_rate':GRID_NIGHT_RATE_NOK_PER_KWH,
    'event_filter':'all', 'replay_path':'', 'replay_lines_per_tick':4,
}

PROBE_TIMEOUT_S = 2.6
PROBE_RETRY_INTERVAL_S = 0.45

class GatewayService:
    def __init__(self, db_path: Path) -> None:
        self._lock = threading.RLock()
        self.settings_store = SettingsStore(default_settings_path(), DEFAULT_SETTINGS)
        self.settings = self.settings_store.load()
        self.event_log_store = EventLogStore(self.settings_store.directory/'event_log.json')
        self.db_path = Path(self.settings.get('db_path') or db_path)
        self.store = SnapshotStore(self.db_path)
        self.serial = SerialManager(on_line=self._on_line, on_state=self._on_state)
        self.connection_status='Searching for gateway'
        self.selected_port=str(self.settings.get('last_port',''))
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
        self.event_engine = EventEngineV2()
        self.price_provider = PriceProvider()
        self.replay_player = ReplayPlayer()
        self.replay_records: deque[HistoryRecord] = deque(maxlen=12000)
        self._replay_row_id = 0
        self._last_ports_cache: list[tuple[str,str]]=[]
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
        self.settings['db_path']=str(self.db_path)
        self.settings_store.save(self.settings)
        self._invalidate_settings_cache()

    def _save_event_log(self, force: bool=False):
        if force: self.event_log_store.flush(list(self.event_log))
        else: self.event_log_store.flush_if_needed(list(self.event_log))

    def list_ports(self) -> list[str]:
        self._last_ports_cache = SerialManager.list_ports()
        return [f"{p} — {d}" if d else p for p,d in self._last_ports_cache]

    def preferred_port_label(self) -> str:
        target = self.selected_port or self.settings.get('last_port','')
        if not target:
            return ''
        for p,d in self._last_ports_cache:
            label=f"{p} — {d}" if d else p
            if p==target or label==target:
                return label
        return target

    def _ordered_candidates(self) -> list[tuple[str,str]]:
        ports = SerialManager.list_ports()
        self._last_ports_cache = ports
        preferred = self.settings.get('last_port','')
        ports = sorted(ports, key=lambda pd: 0 if pd[0]==preferred else 1)
        return ports

    def _probe_port(self, port: str, baudrate: int) -> bool:
        try:
            import serial as pyserial
            with pyserial.Serial(port, baudrate, timeout=0.25, write_timeout=0.25) as ser:
                SerialManager._stabilize_port(ser)
                end = time.monotonic() + PROBE_TIMEOUT_S
                next_probe = 0.0
                while time.monotonic() < end:
                    now = time.monotonic()
                    if now >= next_probe:
                        for cmd in (b'GET_INFO\n', b'GET_STATUS\n'):
                            ser.write(cmd)
                        ser.flush()
                        next_probe = now + PROBE_RETRY_INTERVAL_S
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line and is_gateway_protocol_line(line):
                        return True
            return False
        except Exception:
            return False

    def auto_connect(self, baudrate: int) -> str:
        if self.replay_player.summary().loaded:
            return 'Replay loaded. Stop replay before hardware auto-connect.'
        if self.serial.connected:
            current_port = self.selected_port.split(' â€” ', 1)[0] if self.selected_port else self.settings.get('last_port', '')
            self.connection_status = f'Connected to {current_port}' if current_port else 'Connected'
            return self.connection_status
        for port, _desc in self._ordered_candidates():
            if self._probe_port(port, baudrate):
                self.connect(port, baudrate)
                if not self.connection_status.startswith('Connected to'):
                    self.connection_status = f'Connected to {port}'
                return self.connection_status
        self.connection_status='No gateway found'
        return self.connection_status

    def auto_reconnect_if_needed(self, baudrate: int):
        if self.serial.connected or self.replay_player.summary().loaded:
            return
        import time
        now=time.time()
        if now - self._last_probe_attempt < self._reconnect_interval_s:
            return
        self._last_probe_attempt = now
        self.auto_connect(baudrate)

    def connect(self, port_label: str, baudrate: int):
        port = port_label.split(' — ',1)[0]
        self.serial.connect(SerialConfig(port=port, baudrate=baudrate))
        # Update immediately so the UI reflects auto-connect before the next callback/poll.
        self.connection_status = f'Connected to {port}'
        label = port_label
        for p, d in (self._last_ports_cache or SerialManager.list_ports()):
            candidate = f"{p} — {d}" if d else p
            if p == port or candidate == port_label:
                label = candidate
                break
        self.selected_port = label
        self.settings['last_port']=port
        self.settings['baudrate']=baudrate
        self._save_settings()
        self._invalidate_data_cache()
        self.send_command('GET_INFO')
        self.send_command('GET_STATUS')

    def disconnect(self):
        if self.serial.connected:
            self.serial.disconnect()
        self.connection_status='Disconnected'

    def send_command(self, cmd: str):
        if self.serial.connected:
            self._append_log('TX', mask_sensitive_command(cmd))
            self.serial.send(cmd)

    def _on_state(self, connected: bool, message: str):
        with self._lock:
            self.connection_status = message
            self._append_log('INFO', message)
            self._invalidate_data_cache()

    def _history_records_desc(self, limit: int = 500) -> list[HistoryRecord]:
        if self.replay_records:
            return list(self.replay_records)[:limit]
        return self.store.get_recent(limit)

    def _all_records_desc(self) -> list[HistoryRecord]:
        if self.replay_records:
            return list(self.replay_records)
        return self.store.get_all()

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
        if self.replay_player.summary().loaded:
            self._replay_row_id +=1
            self.replay_records.appendleft(HistoryRecord(row_id=self._replay_row_id, received_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), snapshot=snap))
        else:
            self.store.save_snapshot(snap)

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
        self.recent_phase_samples.clear(); self.event_engine=EventEngineV2(); self._invalidate_data_cache(); self._invalidate_event_cache()

    def _clear_replay_runtime(self):
        self.replay_records.clear(); self._replay_row_id=0; self._reset_live_buffers()

    def load_replay_file(self, path: str) -> str:
        p=Path(path).expanduser()
        if not p.exists():
            msg=f'Replay file not found: {p}'; self._append_log('WARN', msg); return msg
        if self.serial.connected: self.serial.disconnect()
        self.replay_player.load_file(p)
        self.settings['replay_path']=str(p); self._save_settings(); self._clear_replay_runtime(); self.connection_status=f'Replay loaded: {p.name}'; self._append_log('INFO', self.connection_status); return self.connection_status

    def load_replay_lines(self, lines: list[str], source_name: str = 'uploaded.log') -> str:
        if self.serial.connected: self.serial.disconnect()
        self.replay_player.load_lines(lines, source_name)
        self._clear_replay_runtime(); self.connection_status=f'Replay loaded: {source_name}'; self._append_log('INFO', self.connection_status); return self.connection_status

    def load_demo_replay(self) -> str:
        demo_path=default_demo_replay_path()
        if self.serial.connected: self.serial.disconnect()
        self.replay_player.load_file(demo_path, demo=True)
        self._clear_replay_runtime(); self.connection_status=f'Demo replay loaded: {demo_path.name}'; self._append_log('INFO', self.connection_status); return self.connection_status

    def start_replay(self) -> str:
        summary=self.replay_player.summary()
        if not summary.loaded: return 'No replay loaded'
        self.replay_player.start(); self.connection_status=f'Replay playing: {summary.source_name}'; self._append_log('INFO', self.connection_status); return self.connection_status
    def pause_or_resume_replay(self) -> str:
        summary=self.replay_player.summary()
        if not summary.loaded: return 'No replay loaded'
        if summary.active:
            self.replay_player.pause(); self.connection_status=f'Replay paused: {summary.source_name}'
        else:
            self.replay_player.resume(); self.connection_status=f'Replay playing: {summary.source_name}'
        self._append_log('INFO', self.connection_status); return self.connection_status
    def stop_replay(self) -> str:
        summary=self.replay_player.summary(); name=summary.source_name or 'replay'
        self.replay_player.stop(unload=True); self._clear_replay_runtime(); self.connection_status='Replay stopped'; self._append_log('INFO', f'Stopped {name}'); return self.connection_status
    def advance_replay(self, max_lines: int | None = None) -> int:
        summary=self.replay_player.summary()
        if not summary.loaded: return 0
        line_budget=max_lines or int(self.settings.get('replay_lines_per_tick',4) or 4)
        emitted=0
        for raw in self.replay_player.advance(line_budget):
            self._on_line(raw); emitted +=1
        new_summary=self.replay_player.summary()
        if summary.active and not new_summary.active and new_summary.position >= new_summary.total:
            self.connection_status=f'Replay finished: {new_summary.source_name}'; self._append_log('INFO', self.connection_status)
        return emitted
    def replay_summary(self)->dict[str,Any]:
        s=self.replay_player.summary()
        return {'loaded':s.loaded,'active':s.active,'paused':s.paused,'demo':s.demo,'source_name':s.source_name,'status_text':s.status_text,'progress_text':s.progress_text}

    # Data accessors
    def logs_list(self, limit: int = 300) -> list[str]:
        return list(self.logs)[:limit]
    def has_cached_snapshot(self) -> bool:
        return self.latest_snapshot is not None and not self.serial.connected and not self.replay_player.summary().active
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
    def get_history_rows(self, limit: int=200): return history_rows(self._history_records_desc(limit))
    def get_summary(self, limit: int=500):
        if self.replay_records:
            recs=self._history_records_desc(limit)
            if not recs: return {'count':0,'avg_import_w':0.0,'avg_net_w':0.0,'max_import_w':0.0,'min_net_w':0.0,'max_net_w':0.0,'latest_received_at':'-'}
            avg_import=mean([r.snapshot.import_w for r in recs]); avg_net=mean([r.snapshot.net_power_w for r in recs]); max_import=max(r.snapshot.import_w for r in recs); min_net=min(r.snapshot.net_power_w for r in recs); max_net=max(r.snapshot.net_power_w for r in recs); latest=recs[0].received_at
            return {'count':len(recs),'avg_import_w':avg_import,'avg_net_w':avg_net,'max_import_w':max_import,'min_net_w':min_net,'max_net_w':max_net,'latest_received_at':latest}
        s=self.store.get_summary(limit)
        return {'count':s.count,'avg_import_w':s.avg_import_w,'avg_net_w':s.avg_net_w,'max_import_w':s.max_import_w,'min_net_w':s.min_net_w,'max_net_w':s.max_net_w,'latest_received_at':s.latest_received_at}
    def analysis_summary(self, limit: int=1000): return analysis_summary(self._history_records_desc(limit))
    def phase_analysis(self, limit: int=300): return phase_analysis(list(self.recent_phase_samples)[-limit:], self._history_records_desc(limit))
    def top_hour_rows(self, limit: int=2000, top_n: int=8): return top_hour_rows(self._all_records_desc()[:limit], top_n)
    def event_tracker_rows(self, limit: int=80, event_filter: str='all'):
        rows=[]
        for event in list(self.event_log):
            if event_filter=='open' and event.get('status')!='open': continue
            if event_filter=='resolved' and event.get('status')!='resolved': continue
            if event_filter=='severe' and event.get('severity') not in ('high','critical'): continue
            if event_filter in ('power','voltage','phase','connectivity','data_quality') and event.get('category') != event_filter: continue
            rows.append({
                'time':event.get('time','-'),'type':event.get('type', event.get('event_type','-')),'status':event.get('status','-'),'severity':event.get('severity','-'),'confidence':event.get('conf', event.get('confidence','-')),
                'delta_signed':event.get('dW', event.get('delta_signed','-')),'phase':event.get('phase','-'),'voltages':event.get('voltages','-'),'phase_delta':event.get('phase_delta','-'),'note':event.get('note','-'),'summary':event.get('summary','-'),'category':event.get('category','-')
            })
            if len(rows)>=limit: break
        return rows
    def daily_graph_data(self, limit: int=6000): return daily_graph_data(self._all_records_desc()[:limit])
    def load_heatmaps(self, limit: int=6000): return build_load_heatmaps(self._all_records_desc()[:limit])
    def diagnostics_summary(self, limit:int=80, event_filter:str='all'):
        phase=self.phase_analysis(); events=self.event_tracker_rows(limit,event_filter); issues=diagnose_issues(events, phase, self.connection_status, self.wifi_status.state); health=health_rows(self.connection_status, self.wifi_status.state, self.mqtt_status.state, self.last_frame_seq, self.last_frame_len, self.latest_snapshot, len(self.event_log)); return {'issues':issues,'health':health,'phase':phase,'what_changed':what_changed(self.latest_snapshot, events)}
    def signature_rows(self, limit:int=12): return build_signature_rows(list(self.event_log), limit)

    # Cost integration
    def save_cost_settings(self, *, price_area:str, grid_day_rate:float, grid_night_rate:float):
        self.settings['price_area']=price_area; self.settings['grid_day_rate']=grid_day_rate; self.settings['grid_night_rate']=grid_night_rate; self._save_settings()

    def _integrated_intervals(self, limit:int=8000):
        recs = list(reversed(self._all_records_desc()[:limit]))  # oldest -> newest
        rows=[]
        prev_dt=None; prev_snap=None
        for rec in recs:
            dt=parse_meter_dt(rec.snapshot.timestamp)
            if dt is None: continue
            if prev_dt is not None and prev_snap is not None:
                delta_h=max(0.0,(dt-prev_dt).total_seconds()/3600.0)
                if 0 < delta_h < 0.5:
                    rows.append({'start':prev_dt,'end':dt,'hours':delta_h,'import_kw':prev_snap.import_w/1000.0,'export_kw':prev_snap.export_w/1000.0})
            prev_dt=dt; prev_snap=rec.snapshot
        return rows

    def cost_summary(self, limit:int=8000):
        area=str(self.settings.get('price_area','NO3')); day=float(self.settings.get('grid_day_rate',GRID_DAY_RATE_NOK_PER_KWH)); night=float(self.settings.get('grid_night_rate',GRID_NIGHT_RATE_NOK_PER_KWH))
        now=datetime.now().astimezone(); price_data=self.price_provider.get_price_data(area, now); spot=float(price_data['current_price']); grid=self.price_provider.current_grid_rate(now.hour, day, night); total=spot+grid
        snap=self.latest_snapshot
        import_cost_now=((snap.import_w/1000.0)*total) if snap else 0.0
        export_value_now=((snap.export_w/1000.0)*spot) if snap else 0.0
        intervals=self._integrated_intervals(limit)
        daily_import=daily_export=current_hour_import=0.0
        latest_day=max((i['start'].date() for i in intervals), default=None)
        current_hour = now.strftime('%Y-%m-%d %H')
        hour_buckets=[]
        bucket_map={}
        for i in intervals:
            st=i['start'].astimezone(); spot_h=self.price_provider.price_for_hour(area, st.astimezone()); grid_h=self.price_provider.current_grid_rate(st.hour, day, night); total_h=spot_h+grid_h
            imp_cost=i['import_kw']*i['hours']*total_h
            exp_val=i['export_kw']*i['hours']*spot_h
            if latest_day and st.date()==latest_day:
                daily_import += imp_cost; daily_export += exp_val
                key=st.strftime('%Y-%m-%d %H')
                b=bucket_map.setdefault(key, {'day':st.strftime('%Y-%m-%d'),'hour':st.strftime('%H'),'import_kwh':0.0,'export_kwh':0.0,'import_cost_nok':0.0,'export_value_nok':0.0,'spot_nok_kwh':spot_h,'grid_nok_kwh':grid_h,'total_nok_kwh':total_h,'duration_h':0.0})
                b['import_kwh'] += i['import_kw']*i['hours']; b['export_kwh'] += i['export_kw']*i['hours']; b['import_cost_nok'] += imp_cost; b['export_value_nok'] += exp_val; b['duration_h'] += i['hours']
                if key == current_hour:
                    current_hour_import += imp_cost
        rows=[]
        for key in sorted(bucket_map.keys()):
            b=bucket_map[key]
            dur=max(b['duration_h'],1e-6)
            rows.append({'hour':b['hour'],'day':b['day'],'spot_nok_kwh':round(b['spot_nok_kwh'],3),'grid_nok_kwh':round(b['grid_nok_kwh'],3),'total_nok_kwh':round(b['total_nok_kwh'],3),'import_kw':round(b['import_kwh']/dur,3),'export_kw':round(b['export_kwh']/dur,3),'import_cost_nok':round(b['import_cost_nok'],3),'export_value_nok':round(b['export_value_nok'],3),'net_cost_nok':round(b['import_cost_nok']-b['export_value_nok'],3)})
        # basis from top 3 hourly avg import on different days in current month
        hourly_for_capacity=[]
        month = latest_day.strftime('%Y-%m') if latest_day else ''
        for r in rows:
            if month and r['day'].startswith(month):
                hourly_for_capacity.append({'day':r['day'],'hour':r['hour'],'avg_import_kw':r['import_kw']})
        cap = estimate_capacity(hourly_for_capacity)
        return {'source_text':f"{price_data['source_name']} · {area} · {price_data['source_note']}",'spot_now_text':f'{spot:.3f} NOK/kWh spot','grid_now_text':f"{grid:.3f} NOK/kWh {self.price_provider.current_grid_rate_label(now.hour)}",'total_now_text':f'{total:.3f} NOK/kWh total','import_cost_now_text':f'{import_cost_now:.2f} NOK/h current import cost','export_value_now_text':f'{export_value_now:.2f} NOK/h current export value','daily_import_cost_text':f'{daily_import:.2f} NOK daily import cost','daily_export_value_text':f'{daily_export:.2f} NOK daily export value','daily_net_cost_text':f'{daily_import-daily_export:.2f} NOK daily net cost','current_hour_cost_text':f'{current_hour_import:.2f} NOK current hour import est.','capacity_step_text':cap['step_label'],'capacity_price_text':cap['step_price_text'],'capacity_basis_text':cap['basis_text'],'capacity_warning_text':cap['warning_text'],'rows':rows}

    def set_db_path(self, path: str):
        self.db_path=Path(path); self.store=SnapshotStore(self.db_path); self.settings['db_path']=str(self.db_path); self._save_settings(); self._invalidate_data_cache();


def default_db_path() -> Path:
    return Path.home()/'.ams_han_gateway_tool'/'snapshot_history.sqlite3'

def default_settings_path() -> Path:
    return Path.home()/'.ams_han_gateway_tool'/'settings.json'

def default_demo_replay_path() -> Path:
    return Path(__file__).resolve().parent.parent/'fixtures'/'demo_session.log'

gateway_service = GatewayService(default_db_path())

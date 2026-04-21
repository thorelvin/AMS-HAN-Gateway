from __future__ import annotations

import reflex as rx

from .domain.analysis import HeatmapRow
from .service import gateway_service

class DashboardState(rx.State):
    ports: list[str] = []
    selected_port: str = ''
    baudrate: str = str(gateway_service.settings.get('baudrate', 115200))
    connection_status: str = 'Searching for gateway'

    wifi_ssid: str = ''
    wifi_password: str = ''
    wifi_state: str = 'DISCONNECTED'
    wifi_ip: str = ''

    mqtt_host: str = ''
    mqtt_port: str = '1883'
    mqtt_user: str = ''
    mqtt_password: str = ''
    mqtt_prefix: str = 'amshan'
    mqtt_state: str = 'IDLE'

    price_area: str = str(gateway_service.settings.get('price_area', 'NO3'))
    grid_day_rate: str = str(gateway_service.settings.get('grid_day_rate', 0.4254))
    grid_night_rate: str = str(gateway_service.settings.get('grid_night_rate', 0.2642))
    cost_source_text: str = '-'
    spot_now_text: str = '-'
    grid_now_text: str = '-'
    total_now_text: str = '-'
    import_cost_now_text: str = '-'
    export_value_now_text: str = '-'
    daily_import_cost_text: str = '-'
    daily_export_value_text: str = '-'
    daily_net_cost_text: str = '-'
    current_hour_cost_text: str = '-'
    capacity_step_text: str = '-'
    capacity_price_text: str = '-'
    capacity_basis_text: str = '-'
    capacity_warning_text: str = '-'
    cost_rows: list[dict[str, float | str]] = []

    replay_path: str = str(gateway_service.settings.get('replay_path', ''))
    replay_status_text: str = 'Idle'
    replay_progress_text: str = 'No replay loaded'
    replay_source_text: str = '-'

    device_id: str = '-'
    firmware: str = '-'
    mac: str = '-'
    last_frame: str = 'seq=0, len=0'

    snapshot_meter: str = '-'
    snapshot_meter_time: str = '-'
    snapshot_power: str = '-'
    snapshot_grid_flow: str = '-'
    snapshot_reactive: str = '-'
    snapshot_voltage: str = '-'
    snapshot_current: str = '-'
    snapshot_power_factor: str = '-'
    snapshot_counters: str = '-'
    snapshot_stats: str = '-'

    overview_title: str = 'Waiting for live data'
    overview_value: str = '-'
    overview_subtitle: str = 'No valid HAN snapshot yet'
    overview_accent: str = 'blue'

    import_bar_width: str = '0%'
    export_bar_width: str = '0%'
    import_bar_text: str = 'Import 0.0 W'
    export_bar_text: str = 'Export 0.0 W'
    bar_scale_text: str = 'No recent peak yet'

    history_limit: str = '200'
    db_path: str = str(gateway_service.db_path)
    history_rows: list[dict[str, str]] = []
    top_hour_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    signature_rows: list[dict[str, str]] = []
    diagnostics_issues: list[str] = []
    health_rows: list[dict[str, str]] = []
    daily_graph_rows: list[dict[str, float | str]] = []
    heatmap_recent_rows: list[HeatmapRow] = []
    heatmap_weekday_rows: list[HeatmapRow] = []
    daily_date_text: str = 'No daily data'
    daily_peak_text: str = 'No daily peak yet'
    daily_hours_text: str = '0 populated hours'
    heatmap_days_text: str = '0 days in heatmap'
    heatmap_peak_text: str = 'No hourly load peak yet'
    heatmap_change_text: str = 'No load-change spikes yet'
    heatmap_weekday_text: str = 'No weekday pattern yet'
    current_tab: str = 'live'
    db_count: int = 0
    avg_import_text: str = '0.0 W avg import'
    avg_net_text: str = '0.0 W avg net'
    peak_text: str = '0.0 W max import | 0.0/0.0 W net'
    latest_history_text: str = '-'

    signed_avg_text: str = '0.0 W signed avg'
    current_hour_text: str = '0.0 W current hour avg'
    projected_hour_text: str = '0.00 kWh projected hour'
    import_peak_text: str = '0.0 W peak import'
    export_peak_text: str = '0.0 W peak export'
    import_samples_text: str = '0 import samples'
    export_samples_text: str = '0 export samples'

    phase_latest_text: str = 'No phase data'
    phase_avg_text: str = 'No averages yet'
    phase_dominant_text: str = '-'
    phase_imbalance_text: str = '0.000 A recent max imbalance'
    voltage_latest_text: str = 'No voltage frame yet'
    voltage_avg_text: str = 'No voltage averages yet'
    voltage_min_text: str = 'No voltage minimums yet'
    voltage_spread_text: str = '0.0 V worst phase spread'
    heatmap_switch_threshold: str = str(gateway_service.settings.get('heatmap_switch_threshold', 300))

    event_filter: str = str(gateway_service.settings.get('event_filter', 'all'))
    logs: list[str] = []
    show_advanced: bool = bool(gateway_service.settings.get('show_advanced', False))
    auto_connect_message: str = 'Searching for gateway...'
    stale_snapshot: bool = False
    _slow_counter: int = 0

    def on_load(self):
        self._slow_counter = 0
        self.refresh_ports()
        self.sync_from_service(force_heavy=False)
        self.refresh_live_metrics()
        self.refresh_tab_data()
        if gateway_service.serial.connected:
            self.auto_connect_message = gateway_service.connection_status
        elif gateway_service.replay_summary().get('loaded'):
            self.auto_connect_message = 'Replay loaded'
        else:
            self.auto_connect_message = 'Searching for gateway...'

    def live_tick(self, _moment_value: str = ''):
        if gateway_service.replay_summary().get('active'):
            gateway_service.advance_replay()
        else:
            gateway_service.auto_reconnect_if_needed(int(self.baudrate or '115200'))
        self._slow_counter += 1
        if self._slow_counter % 9 == 0:
            self.refresh_ports()
        self.sync_from_service(force_heavy=False)
        if self._slow_counter % 3 == 0:
            self.refresh_live_metrics()
        if self.current_tab in ('analysis', 'daily', 'heatmap', 'diagnostics', 'history', 'cost') and self._slow_counter % 6 == 0:
            self.refresh_tab_data()

    def sync_from_service(self, force_heavy: bool = False):
        self.connection_status = gateway_service.connection_status
        preferred = gateway_service.preferred_port_label()
        if preferred:
            self.selected_port = preferred
        if gateway_service.device_info is not None:
            self.device_id = gateway_service.device_info.device_id
            self.firmware = gateway_service.device_info.fw_version
            self.mac = gateway_service.device_info.mac
        self.wifi_state = gateway_service.wifi_status.state
        self.wifi_ip = gateway_service.wifi_status.ip
        self.mqtt_state = gateway_service.mqtt_status.state
        self.last_frame = f"seq={gateway_service.last_frame_seq}, len={gateway_service.last_frame_len}"

        snap = gateway_service.snapshot_dict()
        self.snapshot_meter = snap['meter']; self.snapshot_meter_time = snap['meter_time']; self.snapshot_power = snap['power']; self.snapshot_grid_flow = snap['grid_flow']; self.snapshot_reactive = snap['reactive']; self.snapshot_voltage = snap['voltage']; self.snapshot_current = snap['current']; self.snapshot_power_factor = snap['power_factor']; self.snapshot_counters = snap['counters']; self.snapshot_stats = snap['stats']
        overview = gateway_service.unified_overview(); self.overview_title = overview['title']; self.overview_value = overview['value']; self.overview_subtitle = overview['subtitle']; self.overview_accent = overview['accent']
        bars = gateway_service.import_export_bar(); self.import_bar_width=bars['import_width']; self.export_bar_width=bars['export_width']; self.import_bar_text=bars['import_text']; self.export_bar_text=bars['export_text']; self.bar_scale_text=bars['scale_text']
        self.stale_snapshot = gateway_service.has_cached_snapshot() and not gateway_service.serial.connected and not gateway_service.replay_summary().get('loaded')
        replay = gateway_service.replay_summary(); self.replay_status_text=str(replay['status_text']); self.replay_progress_text=str(replay['progress_text']); self.replay_source_text=str(replay['source_name'] or '-')
        self.logs = gateway_service.logs_list()
        if force_heavy:
            self.refresh_live_metrics()
            self.refresh_tab_data()

    def refresh_ports(self):
        self.ports = gateway_service.list_ports(); preferred = gateway_service.preferred_port_label();
        if preferred and preferred in self.ports: self.selected_port = preferred
        elif self.selected_port and self.selected_port in self.ports: pass
        elif self.ports: self.selected_port = self.ports[0]
        else: self.selected_port = ''

    def set_selected_port(self, value:str): self.selected_port=value
    def set_wifi_ssid(self, value:str): self.wifi_ssid=value
    def set_wifi_password(self, value:str): self.wifi_password=value
    def set_mqtt_host(self, value:str): self.mqtt_host=value
    def set_mqtt_port(self, value:str): self.mqtt_port=value
    def set_mqtt_user(self, value:str): self.mqtt_user=value
    def set_mqtt_password(self, value:str): self.mqtt_password=value
    def set_mqtt_prefix(self, value:str): self.mqtt_prefix=value
    def set_price_area(self, value:str): self.price_area=value
    def set_grid_day_rate(self, value:str): self.grid_day_rate=value
    def set_grid_night_rate(self, value:str): self.grid_night_rate=value
    def set_history_limit(self, value:str): self.history_limit=value
    def set_db_path(self, value:str): self.db_path=value
    def set_event_filter(self, value:str):
        self.event_filter = value
        self.refresh_diagnostics()
    def set_heatmap_switch_threshold(self, value:str):
        cleaned = ''.join(ch for ch in str(value) if ch.isdigit())
        threshold = int(cleaned) if cleaned else 300
        threshold = max(100, min(1500, threshold))
        self.heatmap_switch_threshold = str(threshold)
        gateway_service.settings['heatmap_switch_threshold'] = threshold
        gateway_service._save_settings()
        self.refresh_analysis()
    def set_current_tab(self, value: str):
        self.current_tab = value
        self.refresh_tab_data()
    def set_replay_path(self, value:str): self.replay_path=value

    def toggle_advanced(self):
        self.show_advanced = not self.show_advanced
        gateway_service.settings['show_advanced']=self.show_advanced
        gateway_service.settings['baudrate']=int(self.baudrate or '115200')
        gateway_service._save_settings()

    def connect(self):
        if self.selected_port:
            gateway_service.connect(self.selected_port, int(self.baudrate or '115200')); self.sync_from_service(force_heavy=True)
    def auto_connect_now(self):
        self.auto_connect_message = gateway_service.auto_connect(int(self.baudrate or '115200')); self.sync_from_service(force_heavy=True)
    def disconnect(self):
        gateway_service.disconnect(); self.sync_from_service(force_heavy=True)
    def send_get_info(self): gateway_service.send_command('GET_INFO'); self.sync_from_service()
    def send_get_status(self): gateway_service.send_command('GET_STATUS'); self.sync_from_service()
    def send_set_wifi(self):
        if self.wifi_ssid and self.wifi_password: gateway_service.send_command(f'SET_WIFI,{self.wifi_ssid},{self.wifi_password}'); self.sync_from_service()
    def send_clear_wifi(self): gateway_service.send_command('CLEAR_WIFI'); self.sync_from_service()
    def send_set_mqtt(self):
        if self.mqtt_host and self.mqtt_port:
            gateway_service.send_command(f'SET_MQTT,{self.mqtt_host},{self.mqtt_port},{self.mqtt_user},{self.mqtt_password},{self.mqtt_prefix}'); self.sync_from_service()
    def mqtt_enable(self): gateway_service.send_command('MQTT_ENABLE'); self.sync_from_service()
    def mqtt_disable(self): gateway_service.send_command('MQTT_DISABLE'); self.sync_from_service()
    def republish_discovery(self): gateway_service.send_command('REPUBLISH_DISCOVERY'); self.sync_from_service()

    def refresh_history_summary(self):
        limit=int(self.history_limit or '200') if (self.history_limit or '200').isdigit() else 200
        s = gateway_service.get_summary(max(limit,1))
        self.db_count=s['count']; self.avg_import_text=f"{s['avg_import_w']:.1f} W avg import"; self.avg_net_text=f"{s['avg_net_w']:.1f} W avg net"; self.peak_text=f"{s['max_import_w']:.1f} W max import | {s['min_net_w']:.1f}/{s['max_net_w']:.1f} W net"; self.latest_history_text=s['latest_received_at']
    def refresh_history(self):
        limit=int(self.history_limit or '200') if (self.history_limit or '200').isdigit() else 200
        self.history_rows = gateway_service.get_history_rows(limit)
        self.refresh_history_summary()
    def refresh_live_metrics(self):
        limit=int(self.history_limit or '200') if (self.history_limit or '200').isdigit() else 200
        self.refresh_history_summary()
        a = gateway_service.analysis_summary(max(limit,1)*5); self.signed_avg_text=a['signed_avg_text']; self.current_hour_text=a['current_hour_text']; self.projected_hour_text=a['projected_hour_text']; self.import_peak_text=a['import_peak_text']; self.export_peak_text=a['export_peak_text']; self.import_samples_text=a['import_samples_text']; self.export_samples_text=a['export_samples_text']
    def refresh_analysis(self):
        limit=int(self.history_limit or '200') if (self.history_limit or '200').isdigit() else 200
        self.refresh_live_metrics()
        p = gateway_service.phase_analysis(max(limit,1)); self.phase_latest_text=p['phase_latest_text']; self.phase_avg_text=p['phase_avg_text']; self.phase_dominant_text=p['phase_dominant_text']; self.phase_imbalance_text=p['phase_imbalance_text']; self.voltage_latest_text=p['voltage_latest_text']; self.voltage_avg_text=p['voltage_avg_text']; self.voltage_min_text=p['voltage_min_text']; self.voltage_spread_text=p['voltage_spread_text']
        self.top_hour_rows = gateway_service.top_hour_rows(max(limit,1)*10, top_n=8)
        d = gateway_service.daily_graph_data(max(limit,1)*20); self.daily_graph_rows=d['rows']; self.daily_date_text=d['date_text']; self.daily_hours_text=d['hours_text']; self.daily_peak_text=d['peak_text']
        threshold = int(self.heatmap_switch_threshold or '300') if (self.heatmap_switch_threshold or '300').isdigit() else 300
        h = gateway_service.load_heatmaps(max(limit,1)*20, switch_threshold_w=threshold); self.heatmap_recent_rows=h['recent_rows']; self.heatmap_weekday_rows=h['weekday_rows']; self.heatmap_days_text=h['day_count_text']; self.heatmap_peak_text=h['peak_hour_text']; self.heatmap_change_text=h['change_peak_text']; self.heatmap_weekday_text=h['weekday_focus_text']
        self.signature_rows = gateway_service.signature_rows(12, coverage_limit=max(limit,1)*20)
    def refresh_diagnostics(self):
        diag = gateway_service.diagnostics_summary(80, self.event_filter)
        self.diagnostics_issues = diag['issues']; self.health_rows = diag['health']; self.event_rows = gateway_service.event_tracker_rows(120, self.event_filter)
    def refresh_cost(self):
        c = gateway_service.cost_summary(12000); self.cost_source_text=c['source_text']; self.spot_now_text=c['spot_now_text']; self.grid_now_text=c['grid_now_text']; self.total_now_text=c['total_now_text']; self.import_cost_now_text=c['import_cost_now_text']; self.export_value_now_text=c['export_value_now_text']; self.daily_import_cost_text=c['daily_import_cost_text']; self.daily_export_value_text=c['daily_export_value_text']; self.daily_net_cost_text=c['daily_net_cost_text']; self.current_hour_cost_text=c['current_hour_cost_text']; self.capacity_step_text=c['capacity_step_text']; self.capacity_price_text=c['capacity_price_text']; self.capacity_basis_text=c['capacity_basis_text']; self.capacity_warning_text=c['capacity_warning_text']; self.cost_rows=c['rows']
    def refresh_tab_data(self):
        if self.current_tab == 'history':
            self.refresh_history()
        elif self.current_tab == 'diagnostics':
            self.refresh_diagnostics()
        elif self.current_tab == 'cost':
            self.refresh_cost()
        elif self.current_tab in ('analysis', 'daily', 'heatmap'):
            self.refresh_analysis()
    def apply_cost_settings(self):
        try: day=float(self.grid_day_rate or '0')
        except ValueError: day=0.4254; self.grid_day_rate=str(day)
        try: night=float(self.grid_night_rate or '0')
        except ValueError: night=0.2642; self.grid_night_rate=str(night)
        gateway_service.save_cost_settings(price_area=self.price_area, grid_day_rate=day, grid_night_rate=night); self.refresh_cost()
    def clear_history(self): gateway_service.clear_history(); self.sync_from_service(force_heavy=True)
    def apply_db_path(self): gateway_service.set_db_path(self.db_path); self.refresh_history(); self.refresh_analysis(); self.refresh_cost(); self.sync_from_service()

    # replay actions
    def load_demo_replay(self):
        self.auto_connect_message = gateway_service.load_demo_replay(); self.sync_from_service(force_heavy=True)
    def load_replay(self):
        self.auto_connect_message = gateway_service.load_replay_file(self.replay_path); self.sync_from_service(force_heavy=True)
    def start_replay(self): gateway_service.start_replay(); self.sync_from_service(force_heavy=True)
    def pause_or_resume_replay(self): gateway_service.pause_or_resume_replay(); self.sync_from_service(force_heavy=True)
    def stop_replay(self): gateway_service.stop_replay(); self.sync_from_service(force_heavy=True)
    async def handle_replay_upload(self, files: list[rx.UploadFile]):
        if not files: return
        f = files[0]
        data = await f.read()
        text = data.decode('utf-8', errors='replace')
        self.auto_connect_message = gateway_service.load_replay_lines(text.splitlines(), f.filename or 'uploaded.log')
        self.replay_path = f.filename or 'uploaded.log'
        self.sync_from_service(force_heavy=True)

    @rx.var(cache=False)
    def wifi_summary(self) -> str: return f"{self.wifi_state} • {self.wifi_ip}" if self.wifi_ip else self.wifi_state
    @rx.var(cache=False)
    def db_summary(self) -> str: return f"{self.db_count} snapshots"
    @rx.var(cache=False)
    def has_diagnostics_issues(self) -> bool:
        return len(self.diagnostics_issues) > 0
    @rx.var(cache=False)
    def has_snapshot(self) -> bool: return self.snapshot_meter != '-'
    @rx.var(cache=False)
    def show_cached_banner(self) -> bool: return self.stale_snapshot
    @rx.var(cache=False)
    def live_opacity(self) -> str: return '0.58' if self.stale_snapshot else '1.0'
    @rx.var(cache=False)
    def onboarding_message(self) -> str:
        replay = gateway_service.replay_summary()
        if replay.get('loaded'):
            return f"Replay mode active: {replay.get('source_name')} · {replay.get('status_text')} · {replay.get('progress_text')}"
        if self.stale_snapshot:
            return 'Disconnected from gateway. Showing last cached snapshot while auto-reconnect runs in the background.'
        if self.connection_status.startswith('Connected to') and not self.has_snapshot:
            return 'Gateway connected. Waiting for HAN frames...'
        if self.connection_status == 'No gateway found':
            return 'No gateway found. Plug in the ESP gateway or open Advanced to choose a port.'
        if self.has_snapshot:
            return 'Live HAN data active. Front page shows unified house flow; Analysis gives deeper phase, voltage and event insight.'
        return self.auto_connect_message

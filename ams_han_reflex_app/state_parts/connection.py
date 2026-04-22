from __future__ import annotations

from .common import _service


class DashboardConnectionState:
    ports: list[str] = []
    selected_port: str = ""
    baudrate: str = "115200"
    connection_status: str = "Searching for gateway"

    wifi_ssid: str = ""
    wifi_password: str = ""
    wifi_state: str = "DISCONNECTED"
    wifi_ip: str = ""

    mqtt_host: str = ""
    mqtt_port: str = "1883"
    mqtt_user: str = ""
    mqtt_password: str = ""
    mqtt_prefix: str = "amshan"
    mqtt_state: str = "IDLE"

    device_id: str = "-"
    firmware: str = "-"
    mac: str = "-"
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

    logs: list[str] = []
    show_advanced: bool = False
    auto_connect_message: str = "Searching for gateway..."
    stale_snapshot: bool = False
    replay_loaded: bool = False
    replay_active: bool = False
    replay_paused: bool = False
    _slow_counter: int = 0

    def on_load(self):
        self._slow_counter = 0
        self.refresh_ports()
        self.sync_from_service(force_heavy=False)
        self.refresh_live_metrics()
        self.refresh_tab_data()

    def live_tick(self, _moment_value: str = ""):
        _service().tick_runtime(int(self.baudrate or "115200"))
        self._slow_counter += 1
        if self._slow_counter % 9 == 0:
            self.refresh_ports()
        self.sync_from_service(force_heavy=False)
        if self._slow_counter % 3 == 0:
            self.refresh_live_metrics()
        if self.current_tab in ("analysis", "daily", "heatmap", "diagnostics", "history", "cost") and self._slow_counter % 6 == 0:
            self.refresh_tab_data()

    def sync_from_service(self, force_heavy: bool = False):
        snapshot = _service().dashboard_sync_data()
        self.connection_status = snapshot.connection_status
        self.mains_network_type = snapshot.mains_network_type
        self.show_advanced = snapshot.show_advanced
        self.baudrate = str(snapshot.baudrate)
        self.replay_path = snapshot.replay_path
        self.db_path = snapshot.db_path
        self.price_area = str(snapshot.price_area)
        self.grid_day_rate = str(snapshot.grid_day_rate)
        self.grid_night_rate = str(snapshot.grid_night_rate)
        self.heatmap_switch_threshold = str(snapshot.heatmap_switch_threshold)
        if snapshot.preferred_port_label:
            self.selected_port = snapshot.preferred_port_label
        self.device_id = snapshot.device_id
        self.firmware = snapshot.firmware
        self.mac = snapshot.mac
        self.wifi_state = snapshot.wifi_state
        self.wifi_ip = snapshot.wifi_ip
        self.mqtt_state = snapshot.mqtt_state
        self.last_frame = snapshot.last_frame
        self.snapshot_meter = snapshot.snapshot_meter
        self.snapshot_meter_time = snapshot.snapshot_meter_time
        self.snapshot_power = snapshot.snapshot_power
        self.snapshot_grid_flow = snapshot.snapshot_grid_flow
        self.snapshot_reactive = snapshot.snapshot_reactive
        self.snapshot_voltage = snapshot.snapshot_voltage
        self.snapshot_current = snapshot.snapshot_current
        self.snapshot_power_factor = snapshot.snapshot_power_factor
        self.snapshot_counters = snapshot.snapshot_counters
        self.snapshot_stats = snapshot.snapshot_stats
        self.overview_title = snapshot.overview_title
        self.overview_value = snapshot.overview_value
        self.overview_subtitle = snapshot.overview_subtitle
        self.overview_accent = snapshot.overview_accent
        self.import_bar_width = snapshot.import_bar_width
        self.export_bar_width = snapshot.export_bar_width
        self.import_bar_text = snapshot.import_bar_text
        self.export_bar_text = snapshot.export_bar_text
        self.bar_scale_text = snapshot.bar_scale_text
        self.stale_snapshot = snapshot.stale_snapshot
        self.replay_loaded = snapshot.replay_loaded
        self.replay_active = snapshot.replay_active
        self.replay_paused = snapshot.replay_paused
        self.replay_status_text = snapshot.replay_status_text
        self.replay_progress_text = snapshot.replay_progress_text
        self.replay_source_text = snapshot.replay_source_text
        self.auto_connect_message = snapshot.auto_connect_message
        self.logs = snapshot.logs
        if force_heavy:
            self.refresh_live_metrics()
            self.refresh_tab_data()

    def refresh_ports(self):
        self.ports = _service().list_ports()
        preferred = _service().preferred_port_label()
        if preferred and preferred in self.ports:
            self.selected_port = preferred
        elif self.selected_port and self.selected_port in self.ports:
            pass
        elif self.ports:
            self.selected_port = self.ports[0]
        else:
            self.selected_port = ""

    def set_selected_port(self, value: str):
        self.selected_port = value

    def set_wifi_ssid(self, value: str):
        self.wifi_ssid = value

    def set_wifi_password(self, value: str):
        self.wifi_password = value

    def set_mqtt_host(self, value: str):
        self.mqtt_host = value

    def set_mqtt_port(self, value: str):
        self.mqtt_port = value

    def set_mqtt_user(self, value: str):
        self.mqtt_user = value

    def set_mqtt_password(self, value: str):
        self.mqtt_password = value

    def set_mqtt_prefix(self, value: str):
        self.mqtt_prefix = value

    def toggle_advanced(self):
        self.show_advanced = not self.show_advanced
        _service().set_show_advanced(self.show_advanced)
        _service().set_baudrate(int(self.baudrate or "115200"))

    def connect(self):
        if self.selected_port:
            _service().connect(self.selected_port, int(self.baudrate or "115200"))
            self.sync_from_service(force_heavy=True)

    def auto_connect_now(self):
        self.auto_connect_message = _service().auto_connect(int(self.baudrate or "115200"))
        self.sync_from_service(force_heavy=True)

    def disconnect(self):
        _service().disconnect()
        self.sync_from_service(force_heavy=True)

    def send_get_info(self):
        _service().request_info()
        self.sync_from_service()

    def send_get_status(self):
        _service().request_status()
        self.sync_from_service()

    def send_set_wifi(self):
        if self.wifi_ssid and self.wifi_password:
            _service().set_wifi_config(self.wifi_ssid, self.wifi_password)
            self.sync_from_service()

    def send_clear_wifi(self):
        _service().clear_wifi_config()
        self.sync_from_service()

    def send_set_mqtt(self):
        if self.mqtt_host and self.mqtt_port:
            _service().set_mqtt_config(
                self.mqtt_host,
                self.mqtt_port,
                self.mqtt_user,
                self.mqtt_password,
                self.mqtt_prefix,
            )
            self.sync_from_service()

    def mqtt_enable(self):
        _service().enable_mqtt()
        self.sync_from_service()

    def mqtt_disable(self):
        _service().disable_mqtt()
        self.sync_from_service()

    def republish_discovery(self):
        _service().republish_discovery()
        self.sync_from_service()

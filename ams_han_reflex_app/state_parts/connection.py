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
        if _service().serial.connected:
            self.auto_connect_message = _service().connection_status
        elif _service().replay_summary().get("loaded"):
            self.auto_connect_message = "Replay loaded"
        else:
            self.auto_connect_message = "Searching for gateway..."

    def live_tick(self, _moment_value: str = ""):
        if _service().replay_summary().get("active"):
            _service().advance_replay()
        else:
            _service().auto_reconnect_if_needed(int(self.baudrate or "115200"))
        self._slow_counter += 1
        if self._slow_counter % 9 == 0:
            self.refresh_ports()
        self.sync_from_service(force_heavy=False)
        if self._slow_counter % 3 == 0:
            self.refresh_live_metrics()
        if self.current_tab in ("analysis", "daily", "heatmap", "diagnostics", "history", "cost") and self._slow_counter % 6 == 0:
            self.refresh_tab_data()

    def sync_from_service(self, force_heavy: bool = False):
        service = _service()
        self.connection_status = service.connection_status
        self.mains_network_type = service.mains_network_type
        self.show_advanced = bool(service.settings.show_advanced)
        self.baudrate = str(service.settings.baudrate)
        self.replay_path = str(service.settings.replay_path)
        self.db_path = str(service.db_path)
        self.price_area = str(service.settings.price_area)
        self.grid_day_rate = str(service.settings.grid_day_rate)
        self.grid_night_rate = str(service.settings.grid_night_rate)
        self.heatmap_switch_threshold = str(service.settings.heatmap_switch_threshold)
        preferred = service.preferred_port_label()
        if preferred:
            self.selected_port = preferred
        if service.device_info is not None:
            self.device_id = service.device_info.device_id
            self.firmware = service.device_info.fw_version
            self.mac = service.device_info.mac
        self.wifi_state = service.wifi_status.state
        self.wifi_ip = service.wifi_status.ip
        self.mqtt_state = service.mqtt_status.state
        self.last_frame = f"seq={service.last_frame_seq}, len={service.last_frame_len}"

        snap = service.snapshot_dict()
        self.snapshot_meter = snap["meter"]
        self.snapshot_meter_time = snap["meter_time"]
        self.snapshot_power = snap["power"]
        self.snapshot_grid_flow = snap["grid_flow"]
        self.snapshot_reactive = snap["reactive"]
        self.snapshot_voltage = snap["voltage"]
        self.snapshot_current = snap["current"]
        self.snapshot_power_factor = snap["power_factor"]
        self.snapshot_counters = snap["counters"]
        self.snapshot_stats = snap["stats"]

        overview = service.unified_overview()
        self.overview_title = overview["title"]
        self.overview_value = overview["value"]
        self.overview_subtitle = overview["subtitle"]
        self.overview_accent = overview["accent"]

        bars = service.import_export_bar()
        self.import_bar_width = bars["import_width"]
        self.export_bar_width = bars["export_width"]
        self.import_bar_text = bars["import_text"]
        self.export_bar_text = bars["export_text"]
        self.bar_scale_text = bars["scale_text"]

        self.stale_snapshot = (
            service.has_cached_snapshot()
            and not service.serial.connected
            and not service.replay_summary().get("loaded")
        )
        replay = service.replay_summary()
        self.replay_loaded = bool(replay["loaded"])
        self.replay_active = bool(replay["active"])
        self.replay_paused = bool(replay["paused"])
        self.replay_status_text = str(replay["status_text"])
        self.replay_progress_text = str(replay["progress_text"])
        self.replay_source_text = str(replay["source_name"] or "-")
        self.logs = service.logs_list()
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

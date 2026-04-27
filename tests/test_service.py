import sys
import tempfile
from collections import deque
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app import service as service_module
from ams_han_reflex_app.domain.pricing import PriceQuote
from ams_han_reflex_app.support.replay_player import normalize_replay_line


class _ConnectedSerial:
    connected = True


class _CaptureConnectionService:
    def __init__(self, sent: list[str]) -> None:
        self._sent = sent

    def send(self, command: str) -> None:
        self._sent.append(command)


class _FixedPriceProvider:
    def quote_for_hour(self, area, dt):
        return PriceQuote(nok_per_kwh=0.875, source_name="Test price feed", source_note=f"{area} fixed test price")

    @staticmethod
    def current_grid_rate(hour, day_rate, night_rate):
        return night_rate if (hour >= 22 or hour < 6) else day_rate

    @staticmethod
    def current_grid_rate_label(hour):
        return "Night (22-06)" if (hour >= 22 or hour < 6) else "Day (06-22)"


class _FallbackPriceProvider(_FixedPriceProvider):
    def quote_for_hour(self, area, dt):
        return PriceQuote(
            nok_per_kwh=1.0,
            source_name="Fallback spot estimate",
            source_note=f"{area} live spot price unavailable",
            fallback_used=True,
            warning_text="Live spot price unavailable. Using explicit fallback estimate 1.000 NOK/kWh.",
        )


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _play_replay_fixture(
    svc: service_module.GatewayService, fixture_name: str, *, chunk_size: int = 16
) -> tuple[str, str]:
    fixture_lines = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8").splitlines()
    load_message = svc.load_replay_lines(fixture_lines, source_name=fixture_name)
    start_message = svc.start_replay()
    while svc.advance_replay(chunk_size):
        pass
    return load_message, start_message


def _ingest_live_fixture(svc: service_module.GatewayService, fixture_name: str) -> None:
    fixture_path = FIXTURE_DIR / fixture_name
    for raw_line in fixture_path.read_text(encoding="utf-8").splitlines():
        line = normalize_replay_line(raw_line)
        if line is not None:
            svc._on_line(line)


class GatewayServiceTest(unittest.TestCase):
    def test_dashboard_sync_data_can_skip_log_payload_for_regular_live_ticks(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            for idx in range(12):
                svc.logs.appendleft(f"[12:00:{idx:02d}] RX: FRAME,{idx},39,ABCDEF")

            without_logs = svc.dashboard_sync_data(include_logs=False)
            with_logs = svc.dashboard_sync_data(include_logs=True, log_limit=5)

            self.assertEqual(without_logs.logs, [])
            self.assertEqual(len(with_logs.logs), 5)
            self.assertTrue(with_logs.logs[0].startswith("[12:00:11]"))

    def test_bounded_recent_queries_do_not_need_full_history_scan(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(
                Path(temp_dir) / "history.sqlite3",
                price_provider=_FixedPriceProvider(),
            )
            svc._on_state(True, "Connected to COM4")
            _ingest_live_fixture(svc, "demo_session.log")

            with patch.object(svc.history_service.store, "get_all", side_effect=AssertionError("full scan used")):
                heatmaps = svc.load_heatmaps(100, switch_threshold_w=300.0)
                daily = svc.daily_graph_data(100)
                top_hours = svc.top_hour_rows(100, top_n=3)

            self.assertTrue(heatmaps.recent_rows)
            self.assertTrue(daily.rows)
            self.assertGreaterEqual(len(top_hours), 1)

    def test_auto_connect_is_noop_when_serial_is_already_connected(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            svc.serial = _ConnectedSerial()
            svc.selected_port = "COM4 - USB Bridge"
            svc.connection_status = "Connected to COM4"

            with patch.object(svc, "_probe_port") as probe_mock, patch.object(svc, "connect") as connect_mock:
                message = svc.auto_connect(115200)

            self.assertEqual(message, "Connected to COM4")
            probe_mock.assert_not_called()
            connect_mock.assert_not_called()

    def test_set_mains_network_type_reclassifies_existing_power_events(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            svc.event_log = deque(
                [
                    {
                        "category": "power",
                        "type": "load_session_end",
                        "time": "2026-04-21 09:20:00",
                        "phase": "L1",
                        "phase_delta": "L1 +3.000 | L2 +3.100 | L3 +0.050",
                        "dW": "-50.0",
                        "note": "Session started 2026-04-21 09:00:00 (Likely single-phase appliance step)",
                        "summary": "Load session ended on L1",
                    },
                    {
                        "category": "power",
                        "type": "load_session_start",
                        "time": "2026-04-21 09:00:00",
                        "phase": "L1",
                        "phase_delta": "L1 +3.000 | L2 +3.100 | L3 +0.050",
                        "dW": "-2300.0",
                        "note": "Likely single-phase appliance step",
                        "summary": "Load session start -2300 W on L1",
                    },
                ],
                maxlen=1200,
            )

            svc.set_mains_network_type("IT")

            self.assertEqual(svc.mains_network_type, "IT")
            self.assertEqual(svc.event_log[0]["phase"], "L1-L2")
            self.assertEqual(svc.event_log[1]["phase"], "L1-L2")
            self.assertIn("Likely phase-to-phase appliance step", svc.event_log[1]["note"])
            self.assertIn("(Likely phase-to-phase appliance step)", svc.event_log[0]["note"])

    def test_clear_history_removes_persisted_rows(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(
                Path(temp_dir) / "history.sqlite3",
                price_provider=_FixedPriceProvider(),
            )
            _play_replay_fixture(svc, "demo_session.log")

            self.assertGreater(svc.get_summary(100).count, 0)

            svc.clear_history()

            self.assertEqual(svc.get_summary(100).count, 0)

    def test_cost_summary_surfaces_fallback_warning(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(
                Path(temp_dir) / "history.sqlite3",
                price_provider=_FallbackPriceProvider(),
            )

            summary = svc.cost_summary()

            self.assertIn("estimated spot", summary.spot_now_text)
            self.assertIn("fallback estimate", summary.warning_text.lower())

    def test_set_heatmap_threshold_uses_service_boundary_and_clamps(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")

            stored = svc.set_heatmap_switch_threshold(50)

            self.assertEqual(stored, 100)
            self.assertEqual(svc.settings.heatmap_switch_threshold, 100)

    def test_dashboard_sync_data_exposes_ui_facing_snapshot_without_direct_state_access(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            svc.connection_status = "Connected to COM4"
            svc.set_show_advanced(True)
            svc.set_baudrate(9600)

            snapshot = svc.dashboard_sync_data()

            self.assertEqual(snapshot.connection_status, "Connected to COM4")
            self.assertTrue(snapshot.show_advanced)
            self.assertEqual(snapshot.baudrate, 9600)
            self.assertEqual(snapshot.device_id, "-")
            self.assertEqual(snapshot.snapshot_meter, "-")
            self.assertEqual(snapshot.auto_connect_message, "Searching for gateway...")

    def test_wifi_and_mqtt_commands_use_escaped_protocol(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            sent: list[str] = []
            svc.serial = _ConnectedSerial()
            svc.connection_service = _CaptureConnectionService(sent)

            svc.set_wifi_config("My,SSID", r"pa\ss,word")
            svc.set_mqtt_config("broker,internal", 1883, "u,ser", r"se\cret", "ams,han")

            self.assertEqual(sent[0], r"SET_WIFI,My\,SSID,pa\\ss\,word")
            self.assertEqual(sent[1], r"SET_MQTT,broker\,internal,1883,u\,ser,se\\cret,ams\,han")

    def test_demo_replay_workflow_builds_history_cost_and_heatmap_views(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(
                Path(temp_dir) / "history.sqlite3",
                price_provider=_FixedPriceProvider(),
            )
            load_message, start_message = _play_replay_fixture(svc, "demo_session.log")

            summary = svc.get_summary(200)
            cost = svc.cost_summary(12000)
            heatmaps = svc.load_heatmaps(4000, switch_threshold_w=300.0)

            self.assertEqual(load_message, "Replay loaded: demo_session.log")
            self.assertEqual(start_message, "Replay playing: demo_session.log")
            self.assertEqual(svc.wifi_status.state, "CONNECTED")
            self.assertEqual(svc.mqtt_status.state, "IDLE")
            self.assertIsNotNone(svc.device_info)
            self.assertEqual(svc.replay_summary()["status_text"], "Finished")
            self.assertGreater(summary.count, 0)
            self.assertEqual(cost.warning_text, "")
            self.assertTrue(isinstance(cost.rows, list))
            self.assertTrue(heatmaps.recent_rows)

    def test_live_demo_session_fixture_drives_public_runtime_callback_and_sync_snapshot(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")

            svc._on_state(True, "Connected to COM4")
            _ingest_live_fixture(svc, "demo_session.log")

            sync = svc.dashboard_sync_data()
            snapshot = svc.snapshot_dict()
            summary = svc.get_summary(100)

            self.assertEqual(summary.count, 2)
            self.assertEqual(sync.connection_status, "Connected to COM4")
            self.assertEqual(sync.device_id, "esp32-21C9C4")
            self.assertEqual(sync.firmware, "0.2.0-wroom32d")
            self.assertEqual(sync.wifi_state, "CONNECTED")
            self.assertEqual(sync.wifi_ip, "192.168.1.191")
            self.assertEqual(sync.mqtt_state, "IDLE")
            self.assertEqual(sync.last_frame, "seq=58, len=121")
            self.assertEqual(sync.snapshot_meter_time, "2026-04-16 23:50:50")
            self.assertEqual(sync.snapshot_meter, "6970631408353607 (MA304H3E)")
            self.assertIn("Import 1273.0 W | Export 0.0 W | Net 1273.0 W", sync.snapshot_power)
            self.assertIn("L1 233.5 V | L2 0.0 V | L3 232.8 V | Avg 233.2 V", sync.snapshot_voltage)
            self.assertIn("L1 2.843 A | L2 3.787 A | L3 4.235 A | Total 10.865 A", sync.snapshot_current)
            self.assertIn("Rolling 6 | RX 58 | Bad 0", sync.snapshot_counters)
            self.assertEqual(snapshot["meter_time"], "2026-04-16 23:50:50")
            self.assertIn("Signed grid flow -1273.0 W", snapshot["grid_flow"])
            self.assertIsNotNone(svc.latest_kfm_detail)
            self.assertEqual(svc.latest_kfm_detail["meter_timestamp"], "2026-04-16 23:50:50")
            self.assertEqual(svc.latest_kfm_detail["meter_id"], "6970631408353607")
            self.assertTrue(any("RX: FRAME,58,121" in line for line in svc.logs))

    def test_firmware_contract_fixture_updates_status_lines_live_sync_and_han_log(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")

            for line in (FIXTURE_DIR / "firmware_protocol_contract.log").read_text(encoding="utf-8").splitlines():
                svc._on_line(line)

            sync = svc.dashboard_sync_data()

            self.assertEqual(sync.device_id, "esp32-21C9C4")
            self.assertEqual(sync.wifi_state, "CONNECTED")
            self.assertEqual(sync.wifi_ip, "192.168.1.191")
            self.assertEqual(sync.mqtt_state, "IDLE")
            self.assertEqual(sync.last_frame, "seq=241, len=39")
            self.assertEqual(sync.snapshot_meter_time, "2026-04-20 22:37:20")
            self.assertEqual(sync.snapshot_counters, "Rolling 6 | RX 332 | Bad 0")
            self.assertIn("Import 1978.0 W | Export 0.0 W | Net -1978.0 W", sync.snapshot_power)
            self.assertIn("HAN status: CONNECTED", "\n".join(svc.logs))


if __name__ == "__main__":
    unittest.main()

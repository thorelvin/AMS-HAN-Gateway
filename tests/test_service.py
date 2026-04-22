import sys
import tempfile
from collections import deque
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app import service as service_module
from ams_han_reflex_app.domain.pricing import PriceQuote


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
        return 'Night (22-06)' if (hour >= 22 or hour < 6) else 'Day (06-22)'


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


def _play_replay_fixture(svc: service_module.GatewayService, fixture_name: str, *, chunk_size: int = 16) -> tuple[str, str]:
    fixture_lines = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8").splitlines()
    load_message = svc.load_replay_lines(fixture_lines, source_name=fixture_name)
    start_message = svc.start_replay()
    while svc.advance_replay(chunk_size):
        pass
    return load_message, start_message


class GatewayServiceTest(unittest.TestCase):
    def test_auto_connect_is_noop_when_serial_is_already_connected(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
        ):
            svc = service_module.GatewayService(
                Path(temp_dir) / "history.sqlite3",
                price_provider=_FallbackPriceProvider(),
            )

            summary = svc.cost_summary()

            self.assertIn("estimated spot", summary.spot_now_text)
            self.assertIn("fallback estimate", summary.warning_text.lower())

    def test_set_heatmap_threshold_uses_service_boundary_and_clamps(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")

            stored = svc.set_heatmap_switch_threshold(50)

            self.assertEqual(stored, 100)
            self.assertEqual(svc.settings.heatmap_switch_threshold, 100)

    def test_dashboard_sync_data_exposes_ui_facing_snapshot_without_direct_state_access(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
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


if __name__ == "__main__":
    unittest.main()

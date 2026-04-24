import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app import service as service_module
from ams_han_reflex_app.domain.pricing import PriceQuote


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class _FixedPriceProvider:
    def quote_for_hour(self, area, dt):
        return PriceQuote(nok_per_kwh=0.875, source_name="Test price feed", source_note=f"{area} fixed test price")

    @staticmethod
    def current_grid_rate(hour, day_rate, night_rate):
        return night_rate if (hour >= 22 or hour < 6) else day_rate

    @staticmethod
    def current_grid_rate_label(hour):
        return "Night (22-06)" if (hour >= 22 or hour < 6) else "Day (06-22)"


def _fixture_lines(name: str) -> list[str]:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()


def _build_service(temp_dir: str) -> service_module.GatewayService:
    return service_module.GatewayService(
        Path(temp_dir) / "history.sqlite3",
        price_provider=_FixedPriceProvider(),
    )


def _run_replay_fixture(
    svc: service_module.GatewayService, fixture_name: str, *, chunk_size: int = 16
) -> tuple[str, str, int]:
    load_message = svc.load_replay_lines(_fixture_lines(fixture_name), source_name=fixture_name)
    start_message = svc.start_replay()
    emitted_total = 0
    while True:
        emitted = svc.advance_replay(chunk_size)
        if emitted == 0:
            break
        emitted_total += emitted
    return load_message, start_message, emitted_total


class EndToEndReplayTest(unittest.TestCase):
    def test_firmware_protocol_fixture_populates_state_via_public_replay_api(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = _build_service(temp_dir)

            load_message, start_message, emitted_total = _run_replay_fixture(svc, "firmware_protocol_contract.log")
            replay = svc.replay_summary()
            history = svc.get_summary(100)
            analysis = svc.analysis_summary(100)
            diagnostics = svc.diagnostics_summary(20)
            snapshot = svc.snapshot_dict()

            self.assertEqual(load_message, "Replay loaded: firmware_protocol_contract.log")
            self.assertEqual(start_message, "Replay playing: firmware_protocol_contract.log")
            self.assertEqual(emitted_total, 8)
            self.assertEqual(replay["status_text"], "Finished")
            self.assertEqual(replay["progress_text"], "8/8 lines (100%)")
            self.assertEqual(svc.connection_status, "Replay finished: firmware_protocol_contract.log")
            self.assertIsNotNone(svc.device_info)
            self.assertEqual(svc.device_info.fw_version, "0.2.0-wroom32d")
            self.assertEqual(svc.device_info.device_id, "esp32-21C9C4")
            self.assertEqual(svc.device_info.mac, "08:A6:F7:21:C9:C4")
            self.assertEqual(svc.wifi_status.state, "CONNECTED")
            self.assertEqual(svc.wifi_status.ip, "192.168.1.191")
            self.assertEqual(svc.mqtt_status.state, "IDLE")
            self.assertIsNotNone(svc.latest_snapshot)
            self.assertEqual(svc.latest_snapshot.timestamp, "2026-04-20 22:37:20")
            self.assertEqual(svc.last_frame_seq, 241)
            self.assertEqual(svc.last_frame_len, 39)
            self.assertEqual(history.count, 1)
            self.assertEqual(analysis.signed_avg_text, "1.98 kW avg import")
            self.assertEqual(diagnostics["issues"], [])
            self.assertEqual(len(diagnostics["events"]), 0)
            self.assertEqual(snapshot["meter_time"], "2026-04-20 22:37:20")
            self.assertIn("6970631408353607", snapshot["meter"])
            self.assertIn("Import 1978.0 W", snapshot["power"])
            self.assertIn("Frames: seq=241, len=39", snapshot["stats"])

    def test_demo_replay_lifecycle_updates_progress_pause_resume_and_finish(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"),
        ):
            svc = _build_service(temp_dir)

            load_message = svc.load_replay_lines(_fixture_lines("demo_session.log"), source_name="demo_session.log")
            initial = svc.replay_summary()
            start_message = svc.start_replay()
            emitted = svc.advance_replay(2)
            mid = svc.replay_summary()
            pause_message = svc.pause_or_resume_replay()
            paused = svc.replay_summary()
            resume_message = svc.pause_or_resume_replay()
            while svc.advance_replay(16):
                pass
            final = svc.replay_summary()

            self.assertEqual(load_message, "Replay loaded: demo_session.log")
            self.assertEqual(initial["status_text"], "Loaded")
            self.assertEqual(initial["progress_text"], "0/9 lines (0%)")
            self.assertEqual(start_message, "Replay playing: demo_session.log")
            self.assertEqual(emitted, 2)
            self.assertTrue(mid["active"])
            self.assertEqual(mid["progress_text"], "2/9 lines (22%)")
            self.assertEqual(pause_message, "Replay paused: demo_session.log")
            self.assertEqual(paused["status_text"], "Paused")
            self.assertEqual(resume_message, "Replay playing: demo_session.log")
            self.assertEqual(final["status_text"], "Finished")
            self.assertEqual(final["progress_text"], "9/9 lines (100%)")
            self.assertEqual(svc.connection_status, "Replay finished: demo_session.log")
            self.assertEqual(svc.get_summary(100).count, 2)

    def test_replay_scenarios_surface_expected_diagnostics_and_heatmap_signals(self):
        expectations = {
            "replay_load_switching.log": {
                "history_count": 7,
                "signed_avg_text": "1.98 kW avg import",
                "issue_contains": "Export step +6340 W on 3-phase",
                "event_contains": "Load session start -6580 W on 3-phase",
                "signature": ("Likely EV charger / large 3-phase load", "3-phase"),
                "heatmap_change_text": "6 switches >= 300 W",
            },
            "replay_phase_loss_l2.log": {
                "history_count": 6,
                "signed_avg_text": "0.99 kW avg import",
                "issue_contains": "L2 voltage missing/invalid",
                "event_contains": "L2 voltage channel recovered",
                "signature": None,
                "heatmap_change_text": "0 switches >= 300 W",
            },
            "replay_solar_export_cycle.log": {
                "history_count": 5,
                "signed_avg_text": "0.28 kW avg export",
                "issue_contains": None,
                "event_contains": "Export step +2210 W on L3",
                "signature": ("Likely single-phase appliance step", "L3"),
                "heatmap_change_text": "4 switches >= 300 W",
            },
            "replay_voltage_sag.log": {
                "history_count": 5,
                "signed_avg_text": "3.28 kW avg import",
                "issue_contains": "Phase voltage spread 15.6 V",
                "event_contains": "L1 sagged by 18.1 V",
                "signature": ("Likely heater / water heater / kitchen load", "L1"),
                "heatmap_change_text": "2 switches >= 300 W",
            },
        }

        for fixture_name, expected in expectations.items():
            with self.subTest(fixture_name=fixture_name):
                with (
                    tempfile.TemporaryDirectory() as temp_dir,
                    patch.object(
                        service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
                    ),
                ):
                    svc = _build_service(temp_dir)
                    _run_replay_fixture(svc, fixture_name)

                    history = svc.get_summary(1000)
                    analysis = svc.analysis_summary(2000)
                    diagnostics = svc.diagnostics_summary(50)
                    signatures = svc.signature_rows(10, 6000)
                    heatmaps = svc.load_heatmaps(6000, switch_threshold_w=300)

                    self.assertEqual(history.count, expected["history_count"])
                    self.assertEqual(analysis.signed_avg_text, expected["signed_avg_text"])
                    if expected["issue_contains"] is None:
                        self.assertEqual(diagnostics["issues"], [])
                    else:
                        self.assertTrue(
                            any(expected["issue_contains"] in issue for issue in diagnostics["issues"]),
                            msg=f"Missing issue '{expected['issue_contains']}' in {diagnostics['issues']}",
                        )
                    self.assertTrue(
                        any(expected["event_contains"] in row.summary for row in diagnostics["events"]),
                        msg=f"Missing event '{expected['event_contains']}' in {[row.summary for row in diagnostics['events']]}",
                    )
                    if expected["signature"] is None:
                        self.assertEqual(signatures, [])
                    else:
                        self.assertTrue(
                            any(
                                row.signature == expected["signature"][0] and row.phase == expected["signature"][1]
                                for row in signatures
                            ),
                            msg=f"Missing signature {expected['signature']} in {[(row.signature, row.phase) for row in signatures]}",
                        )
                    self.assertTrue(heatmaps.recent_rows)
                    self.assertEqual(heatmaps.recent_rows[0].change_text, expected["heatmap_change_text"])


if __name__ == "__main__":
    unittest.main()

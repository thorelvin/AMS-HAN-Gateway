import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.services.runtime_service import RuntimeService
from ams_han_reflex_app.support.event_log_store import EventLogStore


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class RuntimeServiceTest(unittest.TestCase):
    def test_set_mains_network_type_reclassifies_existing_power_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = RuntimeService(
                EventLogStore(Path(temp_dir) / "event_log.json"),
                mains_network_type="TN",
                event_rows=[
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
            )

            normalized = runtime.set_mains_network_type("IT")

            self.assertEqual(normalized, "IT")
            self.assertEqual(runtime.state.event_log[0]["phase"], "L1-L2")
            self.assertEqual(runtime.state.event_log[1]["phase"], "L1-L2")
            self.assertIn("Likely phase-to-phase appliance step", runtime.state.event_log[1]["note"])
            self.assertIn("(Likely phase-to-phase appliance step)", runtime.state.event_log[0]["note"])

    def test_ingest_raw_line_updates_runtime_state_from_firmware_fixture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = RuntimeService(
                EventLogStore(Path(temp_dir) / "event_log.json"),
                mains_network_type="TN",
            )
            fixture_lines = (FIXTURE_DIR / "firmware_protocol_contract.log").read_text(encoding="utf-8").splitlines()
            recorded: list[object] = []
            invalidate_data_calls = 0
            invalidate_event_calls = 0

            def record_history(snapshot):
                recorded.append(snapshot)

            def history_records_desc(limit: int):
                return []

            def derive_baseline(_ts: str, _rows: list[object]):
                return None

            def invalidate_data():
                nonlocal invalidate_data_calls
                invalidate_data_calls += 1

            def invalidate_event():
                nonlocal invalidate_event_calls
                invalidate_event_calls += 1

            for line in fixture_lines:
                runtime.ingest_raw_line(
                    line,
                    history_records_desc=history_records_desc,
                    record_history=record_history,
                    derive_baseline=derive_baseline,
                    invalidate_data_cache=invalidate_data,
                    invalidate_event_cache=invalidate_event,
                )

            self.assertIsNotNone(runtime.state.device_info)
            self.assertEqual(runtime.state.device_info.device_id, "esp32-21C9C4")
            self.assertEqual(runtime.state.wifi_status.state, "CONNECTED")
            self.assertEqual(runtime.state.wifi_status.ip, "192.168.1.191")
            self.assertEqual(runtime.state.mqtt_status.state, "IDLE")
            self.assertIsNotNone(runtime.state.latest_snapshot)
            self.assertEqual(runtime.state.latest_snapshot.timestamp, "2026-04-20 22:37:20")
            self.assertEqual(runtime.state.last_frame_seq, 241)
            self.assertEqual(runtime.state.last_frame_len, 39)
            self.assertEqual(len(recorded), 1)
            self.assertGreaterEqual(invalidate_data_calls, len(fixture_lines))
            self.assertGreaterEqual(invalidate_event_calls, len(fixture_lines))
            self.assertTrue(runtime.state.logs)
            self.assertIn("RX: SNAP,241", runtime.state.logs[0])


if __name__ == "__main__":
    unittest.main()

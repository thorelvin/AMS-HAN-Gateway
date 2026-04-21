import sys
import tempfile
from collections import deque
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app import service as service_module


class _ConnectedSerial:
    connected = True


class GatewayServiceTest(unittest.TestCase):
    def test_auto_connect_is_noop_when_serial_is_already_connected(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            service_module, "default_settings_path", return_value=Path(temp_dir) / "settings.json"
        ):
            svc = service_module.GatewayService(Path(temp_dir) / "history.sqlite3")
            svc.serial = _ConnectedSerial()
            svc.selected_port = "COM4 â€” USB Bridge"
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


if __name__ == "__main__":
    unittest.main()

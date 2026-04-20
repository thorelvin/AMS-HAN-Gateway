import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()

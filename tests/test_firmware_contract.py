import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.backend.protocol import GATEWAY_PROTOCOL_PREFIXES, build_command, list_supported_commands, parse_line
from ams_han_reflex_app.support.replay_player import normalize_replay_line


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures"
SERIAL_LINK_PATH = ROOT / "firmware" / "esp_idf_ams_han_gateway_wroom32d" / "main" / "serial_link.c"


def _firmware_split_fields(text: str) -> list[str]:
    fields: list[str] = [""]
    escaping = False
    for ch in text:
        if escaping:
            if ch == "n":
                fields[-1] += "\n"
            elif ch == "r":
                fields[-1] += "\r"
            else:
                fields[-1] += ch
            escaping = False
            continue
        if ch == "\\":
            escaping = True
            continue
        if ch == ",":
            fields.append("")
            continue
        fields[-1] += ch
    if escaping:
        fields[-1] += "\\"
    return fields


class FirmwareProtocolContractTest(unittest.TestCase):
    def test_python_build_command_round_trips_through_firmware_field_parser(self):
        wifi_password = "line1\r\nline2,secure"
        wifi_command = build_command("SET_WIFI", r"Cabin,Loft\LAN", wifi_password)
        mqtt_command = build_command("SET_MQTT", "broker,internal", 1883, r"user\name", "pa,ss", r"ams\han,raw")

        self.assertEqual(
            _firmware_split_fields(wifi_command),
            ["SET_WIFI", r"Cabin,Loft\LAN", wifi_password],
        )
        self.assertEqual(
            _firmware_split_fields(mqtt_command),
            ["SET_MQTT", "broker,internal", "1883", r"user\name", "pa,ss", r"ams\han,raw"],
        )

    def test_python_supported_commands_cover_firmware_dispatch_commands(self):
        firmware_path = (
            ROOT
            / "firmware"
            / "esp_idf_ams_han_gateway_wroom32d"
            / "main"
            / "app_main.c"
        )
        source = firmware_path.read_text(encoding="utf-8")
        firmware_commands = set(re.findall(r'strcmp\(command,\s+"([^"]+)"\)\s*==\s*0', source))
        python_commands = {entry.split(",", 1)[0].strip() for entry in list_supported_commands()}

        self.assertTrue(firmware_commands)
        self.assertTrue(firmware_commands.issubset(python_commands))

    def test_firmware_contract_fixture_lines_parse_cleanly(self):
        fixture_path = FIXTURE_DIR / "firmware_protocol_contract.log"
        parsed_kinds: set[str] = set()

        for raw_line in fixture_path.read_text(encoding="utf-8").splitlines():
            parsed = parse_line(raw_line)
            self.assertNotEqual(parsed.kind, "parse_error", raw_line)
            self.assertNotEqual(parsed.kind, "error", raw_line)
            parsed_kinds.add(parsed.kind)

        self.assertTrue({"device_info", "wifi_status", "mqtt_status", "status", "frame", "snapshot"}.issubset(parsed_kinds))

    def test_python_protocol_prefixes_cover_every_live_prefix_emitted_by_firmware_serial_link(self):
        source = SERIAL_LINK_PATH.read_text(encoding="utf-8")

        for token in ("RSP:INFO,", "RSP:WIFI,", "RSP:MQTT,", "STATUS,", "FRAME,", "SNAP,"):
            self.assertIn(token, source)

        self.assertEqual(set(GATEWAY_PROTOCOL_PREFIXES), {"RSP:", "STATUS,", "FRAME,", "SNAP,"})

    def test_raw_demo_session_fixture_normalizes_and_parses_in_firmware_message_order(self):
        fixture_path = FIXTURE_DIR / "demo_session.log"
        normalized_lines = [
            normalized
            for raw_line in fixture_path.read_text(encoding="utf-8").splitlines()
            if (normalized := normalize_replay_line(raw_line)) is not None
        ]

        self.assertEqual(
            [parse_line(line).kind for line in normalized_lines],
            [
                "device_info",
                "wifi_status",
                "mqtt_status",
                "frame",
                "snapshot",
                "frame",
                "snapshot",
                "wifi_status",
                "mqtt_status",
            ],
        )


if __name__ == "__main__":
    unittest.main()

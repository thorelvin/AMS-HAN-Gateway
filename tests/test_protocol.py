import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.backend.protocol import (
    build_command,
    is_gateway_protocol_line,
    mask_sensitive_command,
    parse_line,
    split_escaped_fields,
)
from ams_han_reflex_app.support.replay_player import normalize_replay_line


class ProtocolTest(unittest.TestCase):
    def test_is_gateway_protocol_line_matches_known_prefixes(self):
        self.assertTrue(is_gateway_protocol_line("RSP:INFO,0.2.0,amshan-01,AA:BB:CC:DD:EE:FF"))
        self.assertTrue(is_gateway_protocol_line("STATUS,HAN,CONNECTED"))
        self.assertTrue(is_gateway_protocol_line("FRAME,1,10,AA55"))
        self.assertTrue(
            is_gateway_protocol_line("SNAP,1,meter,type,2026-04-20 12:00:00,1,0,0,0,230,0,1,1,1,-1,0.99,3,690,1,1,0")
        )
        self.assertFalse(is_gateway_protocol_line("hello from another serial device"))

    def test_parse_status_line(self):
        parsed = parse_line("STATUS,WIFI,CONNECTED,192.168.1.20")
        self.assertEqual(parsed.kind, "status")
        self.assertEqual(parsed.payload.category, "WIFI")
        self.assertEqual(parsed.payload.state, "CONNECTED")
        self.assertEqual(parsed.payload.extra, "192.168.1.20")

    def test_build_command_escapes_commas_and_backslashes(self):
        command = build_command(
            "SET_MQTT",
            "broker,internal",
            1883,
            r"user\name",
            "pa,ss",
            r"ams\han,raw",
        )

        self.assertEqual(
            command,
            r"SET_MQTT,broker\,internal,1883,user\\name,pa\,ss,ams\\han\,raw",
        )
        self.assertEqual(
            split_escaped_fields(command),
            ["SET_MQTT", "broker,internal", "1883", r"user\name", "pa,ss", r"ams\han,raw"],
        )
        self.assertEqual(
            mask_sensitive_command(command),
            r"SET_MQTT,broker\,internal,1883,user\\name,***,ams\\han\,raw",
        )

    def test_demo_fixture_protocol_lines_parse_without_errors(self):
        fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "demo_session.log"
        parsed_kinds: set[str] = set()

        for raw_line in fixture_path.read_text(encoding="utf-8").splitlines():
            normalized = normalize_replay_line(raw_line)
            if normalized is None:
                continue
            parsed = parse_line(normalized)
            self.assertNotEqual(parsed.kind, "parse_error", normalized)
            self.assertNotEqual(parsed.kind, "error", normalized)
            parsed_kinds.add(parsed.kind)

        self.assertTrue({"device_info", "wifi_status", "mqtt_status", "frame", "snapshot"}.issubset(parsed_kinds))


if __name__ == "__main__":
    unittest.main()

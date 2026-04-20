import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.backend.protocol import is_gateway_protocol_line, parse_line


class ProtocolTest(unittest.TestCase):
    def test_is_gateway_protocol_line_matches_known_prefixes(self):
        self.assertTrue(is_gateway_protocol_line("RSP:INFO,0.2.0,amshan-01,AA:BB:CC:DD:EE:FF"))
        self.assertTrue(is_gateway_protocol_line("STATUS,HAN,CONNECTED"))
        self.assertTrue(is_gateway_protocol_line("FRAME,1,10,AA55"))
        self.assertTrue(is_gateway_protocol_line("SNAP,1,meter,type,2026-04-20 12:00:00,1,0,0,0,230,0,1,1,1,-1,0.99,3,690,1,1,0"))
        self.assertFalse(is_gateway_protocol_line("hello from another serial device"))

    def test_parse_status_line(self):
        parsed = parse_line("STATUS,WIFI,CONNECTED,192.168.1.20")
        self.assertEqual(parsed.kind, "status")
        self.assertEqual(parsed.payload.category, "WIFI")
        self.assertEqual(parsed.payload.state, "CONNECTED")
        self.assertEqual(parsed.payload.extra, "192.168.1.20")


if __name__ == "__main__":
    unittest.main()

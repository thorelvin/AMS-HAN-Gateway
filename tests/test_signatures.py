import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.domain.signatures import build_signature_rows


class SignatureRowsTest(unittest.TestCase):
    def test_build_signature_rows_includes_typical_watt(self):
        events = [
            {
                "category": "power",
                "phase": "L1",
                "note": "Likely heater / water heater / kitchen load",
                "dW": "-3300.0",
                "time": "2026-04-20 12:10:00",
                "conf": "0.95",
            },
            {
                "category": "power",
                "phase": "L1",
                "note": "Likely heater / water heater / kitchen load",
                "dW": "-3500.0",
                "time": "2026-04-20 12:00:00",
                "conf": "0.95",
            },
            {
                "category": "data_quality",
                "phase": "L2",
                "note": "Voltage channel below 80 V",
                "dW": "-",
                "time": "2026-04-20 11:00:00",
                "conf": "0.98",
            },
        ]

        rows = build_signature_rows(events)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signature"], "Likely heater / water heater / kitchen load")
        self.assertEqual(rows[0]["phase"], "L1")
        self.assertEqual(rows[0]["typical_w"], "3400 W")
        self.assertEqual(rows[0]["events"], "2")


if __name__ == "__main__":
    unittest.main()

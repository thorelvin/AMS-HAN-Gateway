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

    def test_build_signature_rows_adds_duty_cycle_metrics(self):
        signature = "Likely heater / water heater / kitchen load"
        events = [
            {
                "category": "power",
                "type": "load_session_end",
                "phase": "L1",
                "note": f"Session started 2026-04-21 18:05:00 ({signature})",
                "dW": "-110.0",
                "time": "2026-04-21 18:50:00",
                "conf": "0.85",
            },
            {
                "category": "power",
                "type": "load_session_start",
                "phase": "L1",
                "note": signature,
                "dW": "-3200.0",
                "time": "2026-04-21 18:05:00",
                "conf": "0.95",
            },
            {
                "category": "power",
                "type": "load_session_end",
                "phase": "L1",
                "note": f"Session started 2026-04-21 06:10:00 ({signature})",
                "dW": "-90.0",
                "time": "2026-04-21 07:40:00",
                "conf": "0.85",
            },
            {
                "category": "power",
                "type": "load_session_start",
                "phase": "L1",
                "note": signature,
                "dW": "-3400.0",
                "time": "2026-04-21 06:10:00",
                "conf": "0.95",
            },
            {
                "category": "power",
                "type": "load_session_start",
                "phase": "L1",
                "note": signature,
                "dW": "-3300.0",
                "time": "2026-04-19 06:20:00",
                "conf": "0.95",
            },
        ]

        rows = build_signature_rows(
            events,
            observed_dates=["2026-04-18", "2026-04-19", "2026-04-20", "2026-04-21"],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signature"], signature)
        self.assertEqual(rows[0]["events"], "3")
        self.assertEqual(rows[0]["avg_runtime"], "1h 8m")
        self.assertEqual(rows[0]["starts_per_day"], "0.8/d")
        self.assertEqual(rows[0]["common_start_hour"], "06:00")
        self.assertEqual(rows[0]["weekday_weekend"], "WD 1.0/d | WE 0.5/d")
        self.assertTrue(all("Session started" not in row["signature"] for row in rows))


if __name__ == "__main__":
    unittest.main()

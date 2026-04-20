import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.backend.models import HistoryRecord, SnapshotEvent
from ams_han_reflex_app.domain.analysis import build_load_heatmaps


def _record(row_id: int, ts: str, import_w: float, export_w: float) -> HistoryRecord:
    return HistoryRecord(
        row_id=row_id,
        received_at=ts,
        snapshot=SnapshotEvent(
            sequence=row_id,
            meter_id="meter-1",
            meter_type="type-a",
            timestamp=ts,
            import_w=import_w,
            export_w=export_w,
            q_import_var=0.0,
            q_export_var=0.0,
            avg_voltage_v=230.0,
            phase_imbalance_a=0.0,
            l1_a=1.0,
            l2_a=1.0,
            l3_a=1.0,
            net_power_w=export_w - import_w,
            estimated_power_factor=0.98,
            total_current_a=3.0,
            apparent_power_va=max(import_w, export_w),
            rolling_samples=1,
            frames_rx=1,
            frames_bad=0,
        ),
    )


class HeatmapAnalysisTest(unittest.TestCase):
    def test_build_load_heatmaps_returns_recent_and_weekday_rows(self):
        records_desc = [
            _record(6, "2026-04-21 09:00:00", 1800.0, 0.0),
            _record(5, "2026-04-21 08:50:00", 1500.0, 0.0),
            _record(4, "2026-04-20 09:00:00", 0.0, 1000.0),
            _record(3, "2026-04-20 08:50:00", 2000.0, 0.0),
            _record(2, "2026-04-20 08:40:00", 2100.0, 0.0),
            _record(1, "2026-04-20 08:30:00", 1900.0, 0.0),
        ]

        heatmaps = build_load_heatmaps(records_desc, recent_days=7)

        self.assertEqual(heatmaps["day_count_text"], "2 days in heatmap")
        self.assertEqual(heatmaps["recent_rows"][0].label, "2026-04-21")
        self.assertEqual(heatmaps["recent_rows"][1].label, "2026-04-20")
        self.assertEqual(len(heatmaps["recent_rows"][0].cells), 24)
        self.assertEqual(len(heatmaps["weekday_rows"]), 7)
        self.assertEqual(heatmaps["recent_rows"][0].cells[8].primary, "-1.5 kW")
        self.assertIn("Use", heatmaps["recent_rows"][0].cells[8].secondary)


if __name__ == "__main__":
    unittest.main()

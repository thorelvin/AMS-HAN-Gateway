import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.backend.models import HistoryRecord, SnapshotEvent
from ams_han_reflex_app.domain.analysis import build_load_heatmaps, phase_analysis


def _record(
    row_id: int,
    ts: str,
    import_w: float,
    export_w: float,
    l1_a: float = 1.0,
    l2_a: float = 1.0,
    l3_a: float = 1.0,
) -> HistoryRecord:
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
            l1_a=l1_a,
            l2_a=l2_a,
            l3_a=l3_a,
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
    def test_build_load_heatmaps_returns_phase_switch_counts(self):
        records_desc = [
            _record(8, "2026-04-21 09:10:00", 0.0, 900.0, 1.0, 1.0, 1.0),
            _record(7, "2026-04-21 09:00:00", 1800.0, 0.0, 4.0, 1.2, 1.1),
            _record(6, "2026-04-21 08:50:00", 1500.0, 0.0, 1.0, 1.0, 1.0),
            _record(5, "2026-04-20 09:10:00", 0.0, 1100.0, 2.1, 2.2, 2.1),
            _record(4, "2026-04-20 09:00:00", 0.0, 1000.0, 2.0, 2.1, 2.0),
            _record(3, "2026-04-20 08:50:00", 2000.0, 0.0, 1.0, 1.0, 1.0),
            _record(2, "2026-04-20 08:40:00", 2100.0, 0.0, 1.0, 1.0, 1.0),
            _record(1, "2026-04-20 08:30:00", 1900.0, 0.0, 1.0, 1.0, 1.0),
        ]

        heatmaps = build_load_heatmaps(records_desc, recent_days=7, switch_threshold_w=300.0)

        self.assertEqual(heatmaps.day_count_text, "2 days in heatmap")
        self.assertEqual(heatmaps.recent_rows[0].label, "2026-04-21")
        self.assertEqual(heatmaps.recent_rows[1].label, "2026-04-20")
        self.assertEqual(len(heatmaps.recent_rows[0].cells), 24)
        self.assertEqual(len(heatmaps.weekday_rows), 7)
        self.assertEqual(heatmaps.recent_rows[0].cells[9].secondary, "L 2/0/0")
        self.assertEqual(heatmaps.recent_rows[0].cells[9].tertiary, "3P 0")
        self.assertEqual(heatmaps.recent_rows[1].cells[9].secondary, "L 0/0/0")
        self.assertEqual(heatmaps.recent_rows[1].cells[9].tertiary, "3P 1")
        self.assertIn("Threshold 300 W", heatmaps.recent_rows[1].cells[9].tooltip)

    def test_build_load_heatmaps_uses_phase_pairs_in_it_mode(self):
        records_desc = [
            _record(4, "2026-04-21 09:10:00", 0.0, 900.0, 4.0, 4.1, 1.0),
            _record(3, "2026-04-21 09:00:00", 1800.0, 0.0, 1.0, 1.0, 1.0),
            _record(2, "2026-04-21 08:50:00", 1500.0, 0.0, 1.0, 1.0, 1.0),
            _record(1, "2026-04-21 08:40:00", 1400.0, 0.0, 1.0, 1.0, 1.0),
        ]

        heatmaps = build_load_heatmaps(records_desc, recent_days=7, switch_threshold_w=300.0, mains_network_type="IT")

        self.assertEqual(heatmaps.recent_rows[0].cells[9].secondary, "IT 1/0/0")
        self.assertIn("L1-L2/L1-L3/L2-L3 switches 1/0/0", heatmaps.recent_rows[0].cells[9].tooltip)

    def test_phase_analysis_uses_it_wording(self):
        phase = phase_analysis(
            [{"l1_a": 4.2, "l2_a": 4.4, "l3_a": 1.1, "l1_v": 230.0, "l2_v": 231.0, "l3_v": 229.0}],
            [],
            mains_network_type="IT",
        )

        self.assertIn("Dominant conductor recently", phase.phase_dominant_text)
        self.assertIn("conductor imbalance", phase.phase_imbalance_text)


if __name__ == "__main__":
    unittest.main()

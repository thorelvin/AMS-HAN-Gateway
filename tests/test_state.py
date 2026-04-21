import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.state import DashboardState


class DashboardStateCompositionTest(unittest.TestCase):
    def test_live_tick_keeps_reflex_temporal_event_handler(self):
        self.assertTrue(hasattr(DashboardState.live_tick, "temporal"))

    def test_split_state_keeps_derived_properties(self):
        self.assertTrue(hasattr(DashboardState, "wifi_summary"))
        self.assertTrue(hasattr(DashboardState, "signature_assignment_text"))


if __name__ == "__main__":
    unittest.main()

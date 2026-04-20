import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from ams_han_reflex_app.support.replay_player import ReplayPlayer

class ReplayTest(unittest.TestCase):
    def test_load_lines(self):
        rp=ReplayPlayer(); rp.load_lines(['RX: FRAME,1,10,AA', 'junk', 'SNAP,1,a,b,2026-01-01 00:00:00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0'], 'x.log')
        self.assertTrue(rp.summary().loaded)
        self.assertEqual(rp.summary().total, 2)

if __name__=='__main__':
    unittest.main()

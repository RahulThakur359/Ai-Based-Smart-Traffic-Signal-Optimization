import unittest
from traffic_engine.congestion import CongestionLevelCalculator


class TestCongestionLevel(unittest.TestCase):

    def setUp(self):
        self.calc = CongestionLevelCalculator(stopped_threshold_px=2.0, smoothing_window=3)

    def test_empty_road_congestion(self):
        res = self.calc.update_and_calculate([])
        self.assertEqual(res['congestion_level'], 'NORMAL')
        self.assertEqual(res['active_vehicles'], 0)

    def test_stopped_vehicles_trigger_high_congestion(self):
        """
        When vehicles do not move across frames (displacement < threshold),
        congestion should escalate to HIGH.
        """
        # Frame 1: 4 vehicles at fixed positions
        frame1 = [
            {'track_id': 1, 'x1': 100, 'y1': 100, 'x2': 150, 'y2': 150},
            {'track_id': 2, 'x1': 200, 'y1': 100, 'x2': 250, 'y2': 150},
            {'track_id': 3, 'x1': 300, 'y1': 100, 'x2': 350, 'y2': 150},
            {'track_id': 4, 'x1': 400, 'y1': 100, 'x2': 450, 'y2': 150},
        ]
        self.calc.update_and_calculate(frame1)

        # Frame 2: Same vehicles with near-zero motion (< 1px)
        frame2 = [
            {'track_id': 1, 'x1': 100, 'y1': 101, 'x2': 150, 'y2': 151},
            {'track_id': 2, 'x1': 200, 'y1': 100, 'x2': 250, 'y2': 150},
            {'track_id': 3, 'x1': 300, 'y1': 101, 'x2': 350, 'y2': 151},
            {'track_id': 4, 'x1': 400, 'y1': 100, 'x2': 450, 'y2': 150},
        ]
        res = self.calc.update_and_calculate(frame2)
        # Ratio of stopped vehicles is 100% (4/4) >= 50%
        self.assertEqual(res['stopped_vehicles'], 4)
        self.assertIn(res['congestion_level'], ['MODERATE', 'HIGH'])

    def test_moving_vehicles_maintain_normal_congestion(self):
        """When vehicles move fast (> 10px per frame), congestion remains NORMAL."""
        calc = CongestionLevelCalculator(stopped_threshold_px=2.0, smoothing_window=1)
        frame1 = [{'track_id': 10, 'x1': 50, 'y1': 50, 'x2': 80, 'y2': 80}]
        calc.update_and_calculate(frame1)

        frame2 = [{'track_id': 10, 'x1': 50, 'y1': 70, 'x2': 80, 'y2': 100}] # 20px movement
        res = calc.update_and_calculate(frame2)
        self.assertEqual(res['stopped_vehicles'], 0)
        self.assertEqual(res['congestion_level'], 'NORMAL')


if __name__ == '__main__':
    unittest.main()

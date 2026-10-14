import unittest
from config import Config
from optimization.optimizer import IntersectionSignalManager
from optimization.timing import DynamicTimingCalculator
from optimization.priority import RoadPriorityCalculator


class TestSignalOptimization(unittest.TestCase):

    def setUp(self):
        self.manager = IntersectionSignalManager()
        self.timing_calc = DynamicTimingCalculator()
        self.priority_calc = RoadPriorityCalculator()

    def test_green_duration_bounds(self):
        """Green duration must stay strictly between MIN_GREEN_TIME and MAX_GREEN_TIME."""
        min_g = Config.MIN_GREEN_TIME
        max_g = Config.MAX_GREEN_TIME

        # 0% density
        t_low = self.timing_calc.calculate_green_time(density_pct=0.0, congestion_level="NORMAL")
        self.assertGreaterEqual(t_low, min_g)
        self.assertLessEqual(t_low, max_g)

        # 100% density with HIGH congestion
        t_high = self.timing_calc.calculate_green_time(density_pct=100.0, congestion_level="HIGH")
        self.assertLessEqual(t_high, max_g)
        self.assertGreaterEqual(t_high, min_g)

        # Moderate density
        t_med = self.timing_calc.calculate_green_time(density_pct=50.0, congestion_level="MODERATE")
        self.assertTrue(min_g <= t_med <= max_g)

    def test_higher_density_receives_longer_green(self):
        """A road with 70% density must receive more green duration than one with 10% density."""
        t1 = self.timing_calc.calculate_green_time(density_pct=10.0, congestion_level="NORMAL")
        t2 = self.timing_calc.calculate_green_time(density_pct=70.0, congestion_level="HIGH")
        self.assertGreater(t2, t1)

    def test_starvation_fairness_prevents_indefinite_waiting(self):
        """
        If a low-traffic road waits for 3 cycles, its starvation counter increases
        its score so it is eventually granted green.
        """
        score_normal, _ = self.priority_calc.calculate_priority_score(
            density_pct=5.0, active_vehicles=1, congestion_level="NORMAL", starvation_cycles=0
        )
        score_starved, reason = self.priority_calc.calculate_priority_score(
            density_pct=5.0, active_vehicles=1, congestion_level="NORMAL", starvation_cycles=3
        )
        self.assertGreater(score_starved, score_normal)
        self.assertIn("Starvation", reason)

    def test_safety_interlocking(self):
        """
        At any moment, exactly one road can be active (GREEN or YELLOW),
        while all other 3 roads must be RED.
        """
        status = self.manager.get_status()
        active_states = []
        for rid in ['road1', 'road2', 'road3', 'road4']:
            state = status[rid]['state']
            if state in ['GREEN', 'YELLOW']:
                active_states.append(rid)

        self.assertEqual(len(active_states), 1, "Conflict: More or less than 1 road is active GREEN/YELLOW")
        inactive = [rid for rid in ['road1', 'road2', 'road3', 'road4'] if rid not in active_states]
        for rid in inactive:
            self.assertEqual(status[rid]['state'], 'RED')

    def test_fewer_vehicles_shorter_green_duration(self):
        """A road with fewer vehicles must receive a shorter green signal duration."""
        # 2 vehicles vs 22 vehicles
        t_few = self.timing_calc.calculate_green_time(vehicle_count=2, density_pct=10.0, congestion_level="NORMAL")
        t_many = self.timing_calc.calculate_green_time(vehicle_count=22, density_pct=60.0, congestion_level="HIGH")
        self.assertLess(t_few, t_many, "Fewer vehicles must receive a shorter green duration")
        self.assertGreaterEqual(t_few, Config.MIN_GREEN_TIME)
        self.assertLessEqual(t_many, Config.MAX_GREEN_TIME)

    def test_sequential_order_road1_first(self):
        """Green signal must be given to Road 1 first, then Road 2, Road 3, Road 4 sequentially."""
        mgr = IntersectionSignalManager(auto_activate=False)
        mgr.activate()
        # Initial active road must be road1
        self.assertEqual(mgr.active_road, 'road1')

        # Next sequential phases
        p2 = mgr.optimize_cycle(advance_sequence=True)
        self.assertEqual(p2['selected_road'], 'road2')

        p3 = mgr.optimize_cycle(advance_sequence=True)
        self.assertEqual(p3['selected_road'], 'road3')

        p4 = mgr.optimize_cycle(advance_sequence=True)
        self.assertEqual(p4['selected_road'], 'road4')

        # Cycle repeats to road1
        p1 = mgr.optimize_cycle(advance_sequence=True)
        self.assertEqual(p1['selected_road'], 'road1')

    def test_red_countdown_timer_synchronized(self):
        """If Road 1 has 20s green remaining, Road 2 must display RED with a 20s countdown timer."""
        mgr = IntersectionSignalManager(auto_activate=True)
        mgr.active_road = 'road1'
        mgr.active_state = mgr.active_state.GREEN
        mgr.allocated_green = 20
        mgr.remaining_time = 20

        status = mgr.get_status()
        self.assertEqual(status['road1']['state'], 'GREEN')
        self.assertEqual(status['road1']['remaining_time'], 20)

        # Road 2 is next in sequence: must show RED with countdown 20
        self.assertEqual(status['road2']['state'], 'RED')
        self.assertEqual(status['road2']['remaining_time'], 20)


if __name__ == '__main__':
    unittest.main()

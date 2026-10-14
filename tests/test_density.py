import unittest
from config import Config
from traffic_engine.density import TrafficDensityCalculator


class TestTrafficDensity(unittest.TestCase):

    def setUp(self):
        self.calc = TrafficDensityCalculator(road_id="road1", road_area_m2=350.0)

    def test_vehicle_area_values(self):
        """Verifies required physical area constants."""
        self.assertEqual(Config.VEHICLE_AREAS['motorcycle'], 1.33)
        self.assertEqual(Config.VEHICLE_AREAS['car'], 5.74)
        self.assertEqual(Config.VEHICLE_AREAS['bus'], 14.41)
        self.assertEqual(Config.VEHICLE_AREAS['truck'], 10.76)

    def test_density_formula(self):
        """
        Formula: (Occupied Area / Road Area) * 100
        Test with 2 cars (2 * 5.74 = 11.48 m²) on 350 m² road.
        Expected: (11.48 / 350.0) * 100 = 3.28%
        """
        detections = [
            {'class_name': 'car'},
            {'class_name': 'car'}
        ]
        res = self.calc.compute_density(detections)
        self.assertEqual(res['occupied_area_m2'], 11.48)
        self.assertAlmostEqual(res['density_percentage'], 3.28, places=1)
        self.assertEqual(res['density_category'], 'LOW')

    def test_density_threshold_classification(self):
        """Tests classification into LOW, MEDIUM, HIGH, and VERY HIGH."""
        self.assertEqual(self.calc.classify_density(10.0), 'LOW')
        self.assertEqual(self.calc.classify_density(35.0), 'MEDIUM')
        self.assertEqual(self.calc.classify_density(60.0), 'HIGH')
        self.assertEqual(self.calc.classify_density(85.0), 'VERY HIGH')

    def test_empty_road_density(self):
        """Empty detections should produce 0.0% density and LOW category."""
        res = self.calc.compute_density([])
        self.assertEqual(res['occupied_area_m2'], 0.0)
        self.assertEqual(res['density_percentage'], 0.0)
        self.assertEqual(res['density_category'], 'LOW')


if __name__ == '__main__':
    unittest.main()

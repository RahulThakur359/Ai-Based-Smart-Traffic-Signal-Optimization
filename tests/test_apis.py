import unittest
from app import create_app


class TestTrafficAPIs(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_get_traffic_status_returns_200_and_all_roads(self):
        """Checks GET /api/traffic/status contains all 4 roads and expected fields."""
        res = self.client.get('/api/traffic/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        for rid in ['road1', 'road2', 'road3', 'road4']:
            self.assertIn(rid, data)
            self.assertIn('density_percentage', data[rid])
            self.assertIn('congestion', data[rid])
            self.assertIn('signal', data[rid])

    def test_get_individual_road_status(self):
        """Checks GET /api/traffic/road/road1."""
        res = self.client.get('/api/traffic/road/road1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['road_id'], 'road1')
        self.assertIn('road_area_m2', data['data'])

    def test_get_signal_status(self):
        """Checks GET /api/signal/status returns real simulated signal states."""
        res = self.client.get('/api/signal/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('meta', data)
        self.assertIn(data['meta']['active_road'], ['road1', 'road2', 'road3', 'road4'])

    def test_upload_invalid_road_returns_400(self):
        """Uploading to an invalid road ID like 'road99' should return 400 Bad Request."""
        res = self.client.post('/upload/road99')
        self.assertEqual(res.status_code, 400)

    def test_upload_missing_file_returns_400(self):
        """Uploading without 'video' file part should return 400."""
        res = self.client.post('/upload/road1', data={})
        self.assertEqual(res.status_code, 400)


if __name__ == '__main__':
    unittest.main()

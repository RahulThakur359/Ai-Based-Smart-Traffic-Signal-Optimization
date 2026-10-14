import unittest
from traffic_engine.vehicle_counter import VehicleCounter


class TestVehicleCounter(unittest.TestCase):

    def setUp(self):
        # 640x360 frame with counting line at y=180
        self.counter = VehicleCounter(
            entry_line=[(0, 180), (640, 180)],
            frame_width=640,
            frame_height=360
        )

    def test_roi_membership(self):
        """Points well inside frame should be inside default ROI."""
        self.assertTrue(self.counter.is_inside_roi(320, 180))
        # Points far outside frame boundary should fail
        self.assertFalse(self.counter.is_inside_roi(-50, -50))

    def test_virtual_line_crossing_counts_once(self):
        """
        A tracked vehicle moving from y=160 to y=200 crosses line y=180.
        Subsequent frames should not increment the count for the same vehicle ID.
        """
        # Frame 1: Vehicle above line
        f1 = [{'track_id': 1, 'class_name': 'car', 'x1': 100, 'y1': 150, 'x2': 140, 'y2': 170}] # centroid cy=160
        self.counter.process_frame_tracks(f1)
        self.assertEqual(self.counter.get_line_count(), 0)

        # Frame 2: Vehicle crosses line (centroid cy=200)
        f2 = [{'track_id': 1, 'class_name': 'car', 'x1': 100, 'y1': 190, 'x2': 140, 'y2': 210}]
        self.counter.process_frame_tracks(f2)
        self.assertEqual(self.counter.get_line_count(), 1)

        # Frame 3: Vehicle continues down (centroid cy=240) - MUST NOT count again
        f3 = [{'track_id': 1, 'class_name': 'car', 'x1': 100, 'y1': 230, 'x2': 140, 'y2': 250}]
        self.counter.process_frame_tracks(f3)
        self.assertEqual(self.counter.get_line_count(), 1, "Duplicate counting occurred for same track ID")

    def test_unique_tracked_count(self):
        """Unique tracked vehicles should account for all distinct IDs seen."""
        f1 = [
            {'track_id': 1, 'class_name': 'car', 'x1': 10, 'y1': 10, 'x2': 50, 'y2': 50},
            {'track_id': 2, 'class_name': 'truck', 'x1': 100, 'y1': 10, 'x2': 160, 'y2': 80}
        ]
        self.counter.process_frame_tracks(f1)
        self.assertEqual(self.counter.get_unique_tracked_count(), 2)

        # Second frame adds vehicle 3
        f2 = [
            {'track_id': 1, 'class_name': 'car', 'x1': 10, 'y1': 15, 'x2': 50, 'y2': 55},
            {'track_id': 3, 'class_name': 'motorcycle', 'x1': 200, 'y1': 20, 'x2': 230, 'y2': 50}
        ]
        self.counter.process_frame_tracks(f2)
        self.assertEqual(self.counter.get_unique_tracked_count(), 3)

    def test_min_hits_filtering(self):
        """When min_hits=3, a 1-frame transient flicker must NOT be counted as unique vehicle."""
        counter = VehicleCounter(frame_width=640, frame_height=360, min_hits=3)
        # Frame 1: 1-frame noise appears
        counter.process_frame_tracks([
            {'track_id': 99, 'class_name': 'car', 'x1': 100, 'y1': 100, 'x2': 140, 'y2': 140}
        ])
        self.assertEqual(counter.get_unique_tracked_count(), 0, "1-frame noise should not be counted with min_hits=3")

        # Frame 2: Seen 2nd time
        counter.process_frame_tracks([
            {'track_id': 99, 'class_name': 'car', 'x1': 100, 'y1': 105, 'x2': 140, 'y2': 145}
        ])
        self.assertEqual(counter.get_unique_tracked_count(), 0)

        # Frame 3: Seen 3rd time -> confirmed
        counter.process_frame_tracks([
            {'track_id': 99, 'class_name': 'car', 'x1': 100, 'y1': 110, 'x2': 140, 'y2': 150}
        ])
        self.assertEqual(counter.get_unique_tracked_count(), 1, "Track must be confirmed after min_hits reached")

    def test_track_stitching_prevents_inflation(self):
        """A vehicle that suffers an ID switch due to brief occlusion must be stitched to same canonical ID."""
        counter = VehicleCounter(frame_width=640, frame_height=360, min_hits=1)
        # Frame 1: Car tracked with ID 10
        counter.process_frame_tracks([
            {'track_id': 10, 'class_name': 'car', 'x1': 200, 'y1': 200, 'x2': 250, 'y2': 250}
        ])
        self.assertEqual(counter.get_unique_tracked_count(), 1)

        # Frame 2: Car is temporarily occluded / not detected
        counter.process_frame_tracks([])

        # Frame 3: Car reappears slightly moved, but tracker assigned brand-new ID 55
        res = counter.process_frame_tracks([
            {'track_id': 55, 'class_name': 'car', 'x1': 205, 'y1': 210, 'x2': 255, 'y2': 260}
        ])
        # Track 55 should be stitched to canonical track 10
        self.assertEqual(res[0]['track_id'], 10, "Raw track 55 should be stitched to canonical track 10")
        self.assertEqual(counter.get_unique_tracked_count(), 1, "Stitched track must not increment unique count")

    def test_out_of_roi_not_counted(self):
        """Vehicles outside the configured ROI should not be counted in unique vehicles."""
        counter = VehicleCounter(frame_width=640, frame_height=360, min_hits=1)
        # Bounding box completely outside frame/ROI
        counter.process_frame_tracks([
            {'track_id': 88, 'class_name': 'car', 'x1': -100, 'y1': -100, 'x2': -50, 'y2': -50}
        ])
        self.assertEqual(counter.get_unique_tracked_count(), 0)
        self.assertEqual(counter.get_current_roi_count(), 0)


if __name__ == '__main__':
    unittest.main()

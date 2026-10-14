class WaitingTimeEstimator:
    """
    Estimates vehicle waiting times by tracking stationary tracked IDs.
    """
    def __init__(self, speed_threshold=1.0):
        """
        Args:
            speed_threshold (float): Movement speed (px/frame) below which a vehicle is considered waiting.
        """
        self.speed_threshold = speed_threshold
        self.stopped_vehicles = {}  # track_id -> frames_stopped

    def update_waiting_times(self, tracks, fps=30):
        """
        Updates and sums the waiting time for stopped vehicles.
        Args:
            tracks (list): List of tracked objects [x1, y1, x2, y2, track_id, class_id]
            fps (int): Frames per second of the video source to convert frames to time.
        """
        # Real implementation:
        # Measure displacement of centroids. If displacement < threshold, increment waiting frames.
        pass

    def get_average_waiting_time(self):
        """
        Returns:
            float: Average waiting time in seconds.
        """
        if not self.stopped_vehicles:
            return 0.0
        return sum(self.stopped_vehicles.values()) / len(self.stopped_vehicles)

import math
import logging
from collections import deque
from config import Config

logger = logging.getLogger(__name__)


class CongestionLevelCalculator:
    """
    Calculates traffic congestion from actual vehicle movement observations
    across consecutive video frames, combined with current vehicle occupancy.
    
    Metrics used:
        - Active vehicle count in the frame / ROI
        - Inter-frame centroid displacement (movement proxy in px/frame)
        - Movement state per vehicle (STOPPED, SLOW, MOVING)
        - Ratio of stopped/crawling vehicles to total active vehicles
        - Temporal smoothing window to prevent rapid status oscillations
        
    Classification:
        - NORMAL: Free-flowing traffic, low stopped ratio (< 25%)
        - MODERATE: Slower movement, queuing developing (25% - 50% stopped)
        - HIGH: Severe queue, stalled flow, majority stopped (>= 50% stopped or high density with halted flow)
    """

    def __init__(self, stopped_threshold_px=None, smoothing_window=None):
        settings = getattr(Config, 'CONGESTION_SETTINGS', {})
        self.stopped_thresh = stopped_threshold_px or settings.get('STOPPED_SPEED_THRESHOLD_PX', 2.0)
        self.high_ratio = settings.get('HIGH_STOPPED_RATIO', 0.50)
        self.mod_ratio = settings.get('MODERATE_STOPPED_RATIO', 0.25)
        self.window_size = smoothing_window or settings.get('SMOOTHING_WINDOW', 5)

        # Persistent state for inter-frame motion analysis
        self.prev_centroids = {}  # track_id -> (cx, cy)
        self.history_window = deque(maxlen=self.window_size)

    def reset(self):
        """Resets tracking state for a new video session."""
        self.prev_centroids.clear()
        self.history_window.clear()

    def update_and_calculate(self, detections):
        """
        Calculates congestion for current frame detections with temporal smoothing.
        
        Args:
            detections (list of dict): Detections containing x1, y1, x2, y2, and track_id.
            
        Returns:
            dict containing:
                - congestion_level: str ("NORMAL", "MODERATE", "HIGH")
                - active_vehicles: int
                - stopped_vehicles: int
                - moving_vehicles: int
                - stopped_ratio: float
                - avg_displacement_px: float
                - movement_summary: str
        """
        if not detections:
            self.history_window.append("NORMAL")
            return {
                "congestion_level": "NORMAL",
                "active_vehicles": 0,
                "stopped_vehicles": 0,
                "moving_vehicles": 0,
                "stopped_ratio": 0.0,
                "avg_displacement_px": 0.0,
                "movement_summary": "No vehicles present on road."
            }

        active_count = len(detections)
        stopped_count = 0
        moving_count = 0
        displacements = []
        current_centroids = {}

        for det in detections:
            x1, y1, x2, y2 = det.get('x1', 0), det.get('y1', 0), det.get('x2', 0), det.get('y2', 0)
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            track_id = det.get('track_id')

            if track_id is not None:
                current_centroids[track_id] = (cx, cy)
                if track_id in self.prev_centroids:
                    px_prev, py_prev = self.prev_centroids[track_id]
                    dist = math.hypot(cx - px_prev, cy - py_prev)
                    displacements.append(dist)

                    if dist < self.stopped_thresh:
                        stopped_count += 1
                    else:
                        moving_count += 1
                else:
                    # Brand-new track, assume moving unless detected otherwise
                    moving_count += 1

        # Update previous centroids for active tracks
        self.prev_centroids = current_centroids

        # Calculate average displacement across observed moving tracks
        avg_disp = float(sum(displacements) / len(displacements)) if displacements else 0.0
        stopped_ratio = stopped_count / max(1, active_count)

        # Raw classification before temporal smoothing
        if active_count == 0:
            raw_level = "NORMAL"
            summary = "Clear road."
        elif active_count >= 3 and stopped_ratio >= self.high_ratio:
            raw_level = "HIGH"
            summary = f"Heavy congestion: {stopped_count}/{active_count} vehicles queued/stopped (avg motion: {avg_disp:.1f}px)."
        elif active_count >= 2 and (stopped_ratio >= self.mod_ratio or avg_disp < 4.0):
            raw_level = "MODERATE"
            summary = f"Moderate congestion: {stopped_count} stopped, flow slowing down (avg motion: {avg_disp:.1f}px)."
        else:
            raw_level = "NORMAL"
            summary = f"Free flowing: majority moving smoothly (avg motion: {avg_disp:.1f}px)."

        # Temporal smoothing: avoid single-frame sudden fluctuations
        self.history_window.append(raw_level)
        smoothed_level = self._get_smoothed_level()

        return {
            "congestion_level": smoothed_level,
            "active_vehicles": active_count,
            "stopped_vehicles": stopped_count,
            "moving_vehicles": moving_count,
            "stopped_ratio": round(stopped_ratio, 2),
            "avg_displacement_px": round(avg_disp, 2),
            "movement_summary": summary
        }

    def _get_smoothed_level(self):
        """Calculates smoothed level via priority voting across window."""
        if not self.history_window:
            return "NORMAL"
        counts = {"HIGH": 0, "MODERATE": 0, "NORMAL": 0}
        for item in self.history_window:
            if item in counts:
                counts[item] += 1

        total = len(self.history_window)
        # If at least 40% of recent frames show HIGH, signal HIGH for safety
        if counts["HIGH"] / total >= 0.40:
            return "HIGH"
        elif (counts["HIGH"] + counts["MODERATE"]) / total >= 0.50:
            return "MODERATE"
        else:
            return "NORMAL"

    def determine_congestion(self, density=None, avg_speed=None, waiting_time=None):
        """Legacy helper for simple queries."""
        smoothed = self._get_smoothed_level()
        return smoothed

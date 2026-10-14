import logging
from config import Config

logger = logging.getLogger(__name__)


class DynamicTimingCalculator:
    """
    Calculates dynamic green signal duration based on measured area-based density,
    congestion level, and safety boundary constraints (MIN_GREEN and MAX_GREEN).
    """

    def __init__(self):
        self.min_green = Config.MIN_GREEN_TIME
        self.max_green = Config.MAX_GREEN_TIME

    def calculate_green_time(self, density_pct=0.0, congestion_level="NORMAL", priority_score=0.0, vehicle_count=None):
        """
        Calculates green duration in seconds.
        - Directly incorporates physical vehicle count: roads with fewer vehicles receive
          shorter green durations, while roads with more vehicles receive proportionally longer green times.
        - Area-based surface density and motion congestion levels provide fine-grained scaling.
        - Strictly bounded within safety limits [MIN_GREEN_TIME, MAX_GREEN_TIME].
        
        Args:
            density_pct (float): Area-based density percentage (0.0 to 100.0).
            congestion_level (str): "NORMAL", "MODERATE", or "HIGH".
            priority_score (float): Calculated priority score or emergency flag.
            vehicle_count (int, optional): Number of vehicles detected on this road.
            
        Returns:
            int: Green signal duration in seconds.
        """
        # If emergency override
        if priority_score >= 9000.0:
            return self.max_green

        span = float(self.max_green - self.min_green)

        # Scale traffic load using vehicle count and density percentage
        if vehicle_count is not None:
            v_cnt = max(0, int(vehicle_count))
            # Standard saturation volume: ~25 queued vehicles clears across a max green window
            norm_count = min(1.0, float(v_cnt) / 25.0)
            norm_density = min(1.0, float(density_pct) / 80.0)
            # Weighted vehicle volume (70%) and surface occupancy (30%)
            traffic_factor = 0.70 * norm_count + 0.30 * norm_density
        else:
            traffic_factor = min(1.0, float(density_pct) / 100.0)

        scaled_green = self.min_green + traffic_factor * span

        # Congestion adjustments (queue clearance headroom)
        cong_str = str(congestion_level).upper()
        if cong_str == "HIGH":
            scaled_green += 5.0
        elif cong_str == "MODERATE":
            scaled_green += 2.5

        green_time = int(round(scaled_green))
        # Ensure safety constraints [MIN_GREEN_TIME, MAX_GREEN_TIME]
        final_green = max(self.min_green, min(self.max_green, green_time))
        return final_green

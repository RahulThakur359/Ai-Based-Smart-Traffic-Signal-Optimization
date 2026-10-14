import logging

logger = logging.getLogger(__name__)


class RoadPriorityCalculator:
    """
    Calculates traffic priority using area-based density, queue congestion,
    active vehicle count, and starvation counters for fairness.
    """

    def __init__(self, weights=None):
        self.weights = weights or {
            'density': 0.55,       # Area-based density is primary input
            'vehicles': 0.25,      # Current vehicles inside ROI
            'congestion': 0.20     # Movement/queue status
        }

    def calculate_priority_score(self, density_pct=0.0, active_vehicles=0, 
                                 congestion_level="NORMAL", starvation_cycles=0, 
                                 has_emergency=False):
        """
        Computes numeric priority score and detailed decision rationale.
        
        Args:
            density_pct (float): Area-based traffic density percentage (0.0 to 100.0).
            active_vehicles (int): Number of vehicles currently visible inside ROI.
            congestion_level (str): "NORMAL", "MODERATE", or "HIGH".
            starvation_cycles (int): Number of cycles this road has waited in RED.
            has_emergency (bool): Whether a verified emergency vehicle is detected.
            
        Returns:
            tuple: (priority_score, decision_reason)
        """
        # Verified emergency override
        if has_emergency:
            return 9999.0, "EMERGENCY OVERRIDE: Emergency vehicle detected. Priority green granted."

        # Congestion multiplier
        cong_bonus = {
            'HIGH': 25.0,
            'MODERATE': 12.0,
            'NORMAL': 0.0
        }.get(str(congestion_level).upper(), 0.0)

        # Base score from traffic demand
        demand_score = (density_pct * self.weights['density']) + \
                       (active_vehicles * 2.0 * self.weights['vehicles']) + \
                       (cong_bonus * self.weights['congestion'])

        # Fairness: Starvation prevention boost
        starvation_bonus = starvation_cycles * 15.0
        total_score = demand_score + starvation_bonus

        # Formulate human-readable decision reason
        if starvation_cycles >= 3:
            reason = f"Starvation fairness policy triggered after waiting {starvation_cycles} consecutive phases."
        elif density_pct >= 50.0:
            reason = f"High traffic density ({density_pct:.1f}%) with {active_vehicles} queued vehicles ({congestion_level} congestion)."
        elif congestion_level == "HIGH":
            reason = f"Severe queue congestion ({congestion_level}) requiring intersection clearance."
        elif active_vehicles > 0:
            reason = f"Active traffic demand: {density_pct:.1f}% density, {active_vehicles} vehicles present."
        else:
            reason = f"Routine phase rotation (Low demand, {density_pct:.1f}% density)."

        return float(total_score), reason

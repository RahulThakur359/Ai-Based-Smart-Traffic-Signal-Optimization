import logging
from config import Config

logger = logging.getLogger(__name__)


class TrafficDensityCalculator:
    """
    Calculates physical area-based traffic density using vehicle surface area estimates
    and configured physical road lane dimensions.
    
    Formula:
        Traffic Density (%) = (Total Estimated Vehicle-Occupied Area / Total Defined Road Area) * 100
    
    Area Standards:
        - Motorcycle: 1.33 m²
        - Car: 5.74 m²
        - Bus: 14.41 m²
        - Truck: 10.76 m²
        - Bicycle: 1.10 m²
    """

    def __init__(self, road_id="road1", road_area_m2=None, roi=None):
        self.road_id = road_id
        if road_area_m2 is not None and road_area_m2 > 0:
            self.road_area_m2 = float(road_area_m2)
        else:
            self.road_area_m2 = float(Config.ROAD_AREAS.get(road_id, 350.0))
            
        self.vehicle_areas = Config.VEHICLE_AREAS
        self.thresholds = Config.DENSITY_THRESHOLDS
        self.roi = roi

    def calculate_occupied_area(self, detections):
        """
        Calculates the total physical surface area (m²) occupied by vehicles
        currently present in the given detections.
        
        Args:
            detections (list): List of detection dictionaries, each with 'class_name'.
            
        Returns:
            tuple: (total_occupied_area_m2, class_counts)
        """
        total_area = 0.0
        class_counts = {}

        for det in detections:
            class_name = det.get('class_name', 'car').lower()
            area = self.vehicle_areas.get(class_name, self.vehicle_areas.get('car', 5.74))
            total_area += area
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

        return round(total_area, 2), class_counts

    def classify_density(self, density_percentage):
        """
        Classifies the area-based density percentage into:
        LOW (< 25%), MEDIUM (25% - 50%), HIGH (50% - 75%), VERY HIGH (>= 75%).
        """
        low_t = self.thresholds.get('LOW', 25.0)
        med_t = self.thresholds.get('MEDIUM', 50.0)
        high_t = self.thresholds.get('HIGH', 75.0)

        if density_percentage < low_t:
            return "LOW"
        elif density_percentage < med_t:
            return "MEDIUM"
        elif density_percentage < high_t:
            return "HIGH"
        else:
            return "VERY HIGH"

    def compute_density(self, detections):
        """
        Computes the complete area-based density metrics for the current frame detections.
        
        Args:
            detections (list of dict): Vehicles currently present in the frame/ROI.
            
        Returns:
            dict containing:
                - occupied_area_m2: float
                - road_area_m2: float
                - density_percentage: float (0.0 to 100.0)
                - density_category: str ("LOW", "MEDIUM", "HIGH", "VERY HIGH")
                - current_vehicle_count: int
                - class_breakdown: dict
        """
        active_count = len(detections) if detections else 0
        if not detections or self.road_area_m2 <= 0:
            return {
                "occupied_area_m2": 0.0,
                "road_area_m2": self.road_area_m2,
                "density_percentage": 0.0,
                "density_category": "LOW",
                "current_vehicle_count": 0,
                "class_breakdown": {}
            }

        occupied_area, class_counts = self.calculate_occupied_area(detections)
        density_pct = min(100.0, max(0.0, (occupied_area / self.road_area_m2) * 100.0))
        density_pct = round(density_pct, 2)
        category = self.classify_density(density_pct)

        return {
            "occupied_area_m2": occupied_area,
            "road_area_m2": self.road_area_m2,
            "density_percentage": density_pct,
            "density_category": category,
            "current_vehicle_count": active_count,
            "class_breakdown": class_counts
        }

    # Backward compatibility method
    def calculate_density(self, detections, frame_area=None):
        if isinstance(detections, (int, float)):
            # If called with integer count, estimate area using average car size
            occupied = detections * self.vehicle_areas.get('car', 5.74)
            pct = min(100.0, (occupied / self.road_area_m2) * 100.0)
            return self.classify_density(pct)
        res = self.compute_density(detections)
        return res["density_category"]

import os
import logging
from config import Config

logger = logging.getLogger(__name__)


class EmergencyVehicleDetector:
    """
    Emergency vehicle detection module.
    
    Architectural Policy:
    - If a verified, specialized emergency model (e.g., fine-tuned YOLO for ambulances)
      is placed in `models/ambulance_best.pt`, it inspects model classes and runs inference.
    - If the model is not found or not configured, this module explicitly reports
      status as 'NOT CONFIGURED' to avoid producing fake or hardcoded detections.
    
    Priority Scheduling Rules (when configured):
    - Grants top priority override to the emergency branch.
    - Preserves safety: if conflicting lane is GREEN, it transitions through YELLOW (4s)
      to clear the junction before granting GREEN to the emergency vehicle.
    """

    def __init__(self, model_name='ambulance_best.pt'):
        self.model_path = os.path.join(Config.MODEL_FOLDER, model_name)
        self.model = None
        self.is_configured = False

        if os.path.exists(self.model_path):
            self.load_model()
        else:
            logger.info(
                f"Emergency vehicle model not found at {self.model_path}. "
                "Feature marked as NOT CONFIGURED."
            )

    def load_model(self):
        try:
            from ultralytics import YOLO
            loaded = YOLO(self.model_path)
            # Inspect class names to ensure ambulance is actually recognized
            class_names = [name.lower() for name in loaded.names.values()]
            if any('ambulance' in name or 'emergency' in name for name in class_names):
                self.model = loaded
                self.is_configured = True
                logger.info(f"Verified emergency vehicle detector loaded: {self.model_path}")
            else:
                logger.warning(
                    f"Model at {self.model_path} does not contain ambulance classes: {class_names}. "
                    "Feature remains NOT CONFIGURED."
                )
                self.model = None
                self.is_configured = False
        except Exception as e:
            logger.error(f"Failed to load emergency YOLO model: {e}")
            self.model = None
            self.is_configured = False

    def get_status_label(self):
        """Returns feature status string for dashboard presentation."""
        return "CONFIGURED (ACTIVE)" if self.is_configured else "NOT CONFIGURED"

    def is_emergency_present(self, frame):
        """
        Runs inference if model is configured.
        Returns False and never invents fake emergency detections if unconfigured.
        """
        if not self.is_configured or self.model is None or frame is None:
            return False

        try:
            results = self.model(frame, conf=0.45, verbose=False)
            for r in results:
                if len(r.boxes) > 0:
                    return True
        except Exception as err:
            logger.error(f"Emergency detection inference error: {err}")
        return False

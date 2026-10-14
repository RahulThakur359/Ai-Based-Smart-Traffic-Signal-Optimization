import os
import logging
import threading

from config import Config

logger = logging.getLogger(__name__)


class VehicleDetector:

    def __init__(self, model_name='yolov8n.pt'):
        self._lock = threading.Lock()

        # Check in Config.MODEL_FOLDER first
        self.model_path = os.path.join(
            Config.MODEL_FOLDER,
            model_name
        )

        # Fallback to root directory if missing in Config.MODEL_FOLDER
        if not os.path.exists(self.model_path):
            root_model_path = os.path.join(Config.BASE_DIR, model_name)
            if os.path.exists(root_model_path):
                self.model_path = root_model_path
            else:
                self.model_path = model_name

        self.model = None
        self.load_model()
        from traffic_engine.tracker import VehicleTracker
        self.tracker = VehicleTracker()

    def load_model(self):
        try:
            from ultralytics import YOLO
            import numpy as np

            self.model = YOLO(self.model_path)

            # Warmup inference to eliminate initial latency
            try:
                dummy = np.zeros((480, 480, 3), dtype=np.uint8)
                self.model(dummy, imgsz=480, verbose=False)
                logger.info("YOLO model pre-warmed successfully (imgsz=480)")
            except Exception as warmup_err:
                logger.warning(f"YOLO warmup skipped: {warmup_err}")

            logger.info(
                f"YOLO model loaded successfully: "
                f"{self.model_path}"
            )

        except Exception as e:
            logger.error(
                f"Failed to load YOLO model: {e}"
            )
            self.model = None

    def detect(self, frame, imgsz=480):
        if self.model is None or frame is None:
            return []

        h, w = frame.shape[:2]

        with self._lock:
            results = self.model(
                frame,
                conf=0.25,
                iou=0.45,
                imgsz=imgsz,
                verbose=False
            )

        detections = []


        # =====================================================
        # COCO VEHICLE CLASSES REQUIREMENT:
        # 1 = bicycle
        # 2 = car
        # 3 = motorcycle
        # 5 = bus
        # 7 = truck
        # =====================================================

        vehicle_classes = {
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }


        for result in results:

            boxes = result.boxes

            if boxes is None:
                continue


            for box in boxes:

                class_id = int(
                    box.cls[0].item()
                )


                confidence = float(
                    box.conf[0].item()
                )


                # Filter strictly for required vehicle classes
                if class_id not in vehicle_classes:
                    continue


                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                # Clamp coordinates to frame boundaries
                x1 = max(0, min(w - 1, x1))
                y1 = max(0, min(h - 1, y1))
                x2 = max(0, min(w - 1, x2))
                y2 = max(0, min(h - 1, y2))

                # Ignore invalid bounding boxes
                if x2 <= x1 or y2 <= y1:
                    continue

                detections.append({

                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,

                    "confidence": confidence,

                    "class_id": class_id,

                    "class_name":
                        vehicle_classes[class_id],

                    "track_id": None

                })


        return detections

    def track(self, frame, persist=True, imgsz=480):
        """
        Runs YOLOv8 object detection with ByteTrack persistent ID tracking.
        Returns list of detections with unique track_id for each vehicle.
        """
        if self.model is None or frame is None:
            return []

        h, w = frame.shape[:2]

        try:
            with self._lock:
                results = self.model.track(
                    frame,
                    tracker="bytetrack.yaml",
                    persist=persist,
                    conf=0.25,
                    iou=0.45,
                    imgsz=imgsz,
                    verbose=False
                )
        except Exception as e:
            logger.warning(f"ByteTrack tracker failed, falling back to detect: {e}")
            return self.detect(frame, imgsz=imgsz)

        vehicle_classes = {
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }

        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())

                if class_id not in vehicle_classes:
                    continue

                track_id = None
                if box.id is not None:
                    try:
                        track_id = int(box.id[0].item())
                    except Exception:
                        track_id = None

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                x1 = max(0, min(w - 1, x1))
                y1 = max(0, min(h - 1, y1))
                x2 = max(0, min(w - 1, x2))
                y2 = max(0, min(h - 1, y2))

                if x2 <= x1 or y2 <= y1:
                    continue

                detections.append({
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": vehicle_classes[class_id],
                    "track_id": track_id
                })

        # Preserve ByteTrack Kalman-filter track IDs directly without destructive re-matching
        has_bytetrack_ids = any(d.get("track_id") is not None for d in detections)
        if not has_bytetrack_ids:
            detections = self.tracker.update(detections, frame.shape)
        return detections

    def reset_tracker(self):
        """
        Resets ByteTrack tracking state for clean tracking on a new video stream.
        """
        self.tracker.reset()
        try:
            if hasattr(self.model, 'predictor') and self.model.predictor is not None:
                if hasattr(self.model.predictor, 'trackers') and len(self.model.predictor.trackers) > 0:
                    self.model.predictor.trackers[0].reset()
                    logger.info("ByteTrack tracker reset successfully.")
        except Exception as e:
            logger.warning(f"Could not reset ByteTrack tracker: {e}")


_shared_detector = None


def get_shared_detector(model_name='yolov8n.pt'):
    global _shared_detector
    if _shared_detector is None:
        _shared_detector = VehicleDetector(model_name)
    return _shared_detector
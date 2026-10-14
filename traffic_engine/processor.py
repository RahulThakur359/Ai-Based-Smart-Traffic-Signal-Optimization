import cv2
import os
import logging

from traffic_engine.detector import VehicleDetector
from traffic_engine.vehicle_counter import VehicleCounter
from traffic_engine.density import TrafficDensityCalculator
from traffic_engine.congestion import CongestionLevelCalculator
from config import Config

logger = logging.getLogger(__name__)


class TrafficProcessor:
    """
    Video processor for traffic feeds. Detects vehicles, tracks persistent IDs via ByteTrack,
    filters ROI membership, counts virtual line crossings, and computes real area-based
    density (%) and motion-based congestion levels.
    """

    def __init__(self, detector=None):
        if detector is not None:
            self.detector = detector
        else:
            from traffic_engine.detector import VehicleDetector
            self.detector = VehicleDetector()

    def process_video(self, video_path, road_id=None, max_frames=None):
        r_id = road_id or "road1"

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open video: {video_path}")

        # Video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 25.0

        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Standardize resolution (640 width)
        target_width = 640
        if orig_width > 0 and orig_height > 0:
            target_height = int(orig_height * (640 / orig_width))
        else:
            target_height = 360

        target_width = target_width - (target_width % 2)
        target_height = target_height - (target_height % 2)

        # Output directory and paths
        output_dir = os.path.join(Config.UPLOAD_FOLDER, r_id)
        os.makedirs(output_dir, exist_ok=True)

        input_name = os.path.splitext(os.path.basename(video_path))[0]
        output_filename = f"{input_name}_detected.mp4"
        output_path = os.path.join(output_dir, output_filename)

        frame_skip = 2
        writer_fps = max(1.0, fps / frame_skip)

        writer = self._create_video_writer(output_path, writer_fps, target_width, target_height)
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(f"Unable to create processed video writer for {output_path}")

        # Initialize road-specific independent analytics components (min_hits=3 requires multi-frame confirmation)
        counter = VehicleCounter(frame_width=target_width, frame_height=target_height, min_hits=3)
        density_calc = TrafficDensityCalculator(road_id=r_id)
        congestion_calc = CongestionLevelCalculator()

        if hasattr(self.detector, 'reset_tracker'):
            self.detector.reset_tracker()

        frame_count = 0
        processed_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = None

        logger.info(
            f"Starting video processing for {r_id}: {video_path} "
            f"(target={target_width}x{target_height}, max_frames={max_frames or 'ALL'})"
        )

        class_colors = {
            "car": (0, 255, 255),         # Yellow
            "motorcycle": (255, 191, 0),  # Cyan
            "bus": (203, 192, 255),       # Lavender
            "truck": (0, 165, 255),       # Orange
            "bicycle": (0, 255, 128),     # Emerald Green
        }
        default_color = (0, 255, 0)

        # Retain latest metrics for final reporting
        telemetry_timeline = []
        fps_val = float(fps) if fps and fps > 0 else 25.0

        latest_density = {
            "occupied_area_m2": 0.0,
            "road_area_m2": density_calc.road_area_m2,
            "density_percentage": 0.0,
            "density_category": "LOW",
            "current_vehicle_count": 0
        }
        latest_congestion = {
            "congestion_level": "NORMAL",
            "stopped_vehicles": 0,
            "active_vehicles": 0,
            "avg_displacement_px": 0.0
        }

        import time

        while True:
            if max_frames is not None and max_frames > 0 and frame_count >= max_frames:
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % frame_skip != 0:
                continue

            processed_count += 1
            time.sleep(0.003)  # Yield CPU so live API requests never lag

            frame = cv2.resize(frame, (target_width, target_height))
            height, width = target_height, target_width

            # 1. YOLOv8 + ByteTrack persistent tracking
            raw_detections = self.detector.track(frame, persist=True, imgsz=480)

            # Filter tiny noise boxes and low-confidence transient false positives
            min_box_area = 350
            min_conf = 0.30
            detections = [
                d for d in raw_detections
                if (d['x2'] - d['x1']) * (d['y2'] - d['y1']) >= min_box_area
                and d.get('confidence', 0.0) >= min_conf
            ]

            # 2. Update VehicleCounter and isolate vehicles inside road ROI
            roi_detections = counter.process_frame_tracks(detections)

            current_roi_count = counter.get_current_roi_count()
            line_crossed_count = counter.get_line_count()
            unique_vehicle_count = counter.get_unique_tracked_count()

            # 3. Compute real physical area-based density on ROI vehicles
            latest_density = density_calc.compute_density(roi_detections)

            # 4. Compute real movement-based congestion on ROI vehicles
            latest_congestion = congestion_calc.update_and_calculate(roi_detections)

            # 5. Render Bounding Boxes & persistent labels
            for det in detections:
                try:
                    x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
                    confidence = det["confidence"]
                    class_name = det["class_name"]
                    track_id = det.get("track_id")

                    if track_id is not None and track_id in counter.counted_ids:
                        color = (0, 255, 128)
                    else:
                        color = class_colors.get(class_name.lower(), default_color)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                    if track_id is not None:
                        label = f"#{track_id} {class_name.upper()} {confidence * 100:.0f}%"
                    else:
                        label = f"{class_name.upper()} {confidence * 100:.0f}%"

                    font_scale = 0.45
                    font_thickness = 1
                    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
                    label_pad = 4
                    label_h = th + baseline + label_pad * 2

                    if y1 - label_h >= 0:
                        bg_y1, bg_y2 = y1 - label_h, y1
                        text_y = y1 - baseline - label_pad
                    else:
                        bg_y1, bg_y2 = y1, y1 + label_h
                        text_y = y1 + th + label_pad

                    label_x1 = max(0, x1)
                    label_x2 = min(label_x1 + tw + label_pad * 2, width - 1)

                    cv2.rectangle(frame, (label_x1, bg_y1), (label_x2, bg_y2), color, -1)
                    cv2.putText(frame, label, (label_x1 + label_pad, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), font_thickness, cv2.LINE_AA)

                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    cv2.circle(frame, (cx, cy), 3, color, -1)
                except Exception as e:
                    logger.debug(f"Box draw error: {e}")
                    continue

            # 6. Draw Virtual Counting Line & ROI boundary
            counter.draw_on_frame(frame)

            # 7. Draw HUD telemetry bar at top of video frame
            hud_bg = frame[:32, :].copy()
            cv2.rectangle(frame, (0, 0), (width, 32), (20, 20, 20), -1)
            cv2.addWeighted(hud_bg, 0.3, frame[:32, :], 0.7, 0, frame[:32, :])

            hud_text = (
                f"{r_id.upper()} | ROI: {current_roi_count} | Crossed: {line_crossed_count} | "
                f"Area: {latest_density['occupied_area_m2']:.1f}/{latest_density['road_area_m2']:.0f}m2 | "
                f"Density: {latest_density['density_percentage']:.1f}% ({latest_density['density_category']}) | "
                f"Congestion: {latest_congestion['congestion_level']}"
            )
            cv2.putText(frame, hud_text, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)

            writer.write(frame)

            # Record time-indexed snapshot for continuous synchronized playback
            sec = round(frame_count / fps_val, 2)
            telemetry_timeline.append({
                "t": sec,
                "current_vehicles": current_roi_count,
                "active_vehicles": current_roi_count,
                "line_crossed_count": line_crossed_count,
                "unique_vehicle_count": unique_vehicle_count,
                "occupied_area_m2": latest_density["occupied_area_m2"],
                "road_area_m2": latest_density["road_area_m2"],
                "density_percentage": latest_density["density_percentage"],
                "density": latest_density["density_category"],
                "congestion": latest_congestion["congestion_level"],
                "stopped_vehicles": latest_congestion["stopped_vehicles"]
            })

            # 8. While processing, maintain PROCESSING status without displaying premature counts/density
            if r_id:
                try:
                    from routes.traffic_api import traffic_state
                    traffic_state[r_id].update({
                        "status": "PROCESSING",
                        "processed_video": None
                    })
                except Exception as err:
                    logger.debug(f"Live state update failed: {err}")

            if processed_count % 20 == 0:
                logger.info(
                    f"[{r_id}] Frame {frame_count}/{total_frames or '?'} (proc={processed_count}): "
                    f"Analyzing video stream..."
                )

        cap.release()
        writer.release()

        final_count = counter.get_unique_tracked_count()
        final_roi_count = counter.get_current_roi_count()
        final_line_count = counter.get_line_count()
        processed_video_url = f"/uploads/{r_id}/{output_filename}"

        result = {
            "status": "COMPLETED",
            "road_id": r_id,
            "frames_processed": frame_count,
            "frames_analyzed": processed_count,
            "vehicle_count": final_count,
            "unique_vehicle_count": final_count,
            "current_vehicles": final_roi_count,
            "active_vehicles": final_roi_count,
            "line_crossed_count": final_line_count,
            "occupied_area_m2": latest_density["occupied_area_m2"],
            "road_area_m2": latest_density["road_area_m2"],
            "density_percentage": latest_density["density_percentage"],
            "density": latest_density["density_category"],
            "density_category": latest_density["density_category"],
            "congestion": latest_congestion["congestion_level"],
            "congestion_level": latest_congestion["congestion_level"],
            "telemetry_timeline": telemetry_timeline,
            "class_counts": counter.class_counts,
            "processed_video": processed_video_url
        }

        # Final persistent update with completed calculations
        if r_id:
            try:
                from routes.traffic_api import traffic_state
                traffic_state[r_id].update({
                    "vehicle_count": final_count,
                    "unique_vehicle_count": final_count,
                    "current_vehicles": final_roi_count,
                    "active_vehicles": final_roi_count,
                    "line_crossed_count": final_line_count,
                    "occupied_area_m2": latest_density["occupied_area_m2"],
                    "road_area_m2": latest_density["road_area_m2"],
                    "density_percentage": latest_density["density_percentage"],
                    "density": latest_density["density_category"],
                    "density_category": latest_density["density_category"],
                    "congestion": latest_congestion["congestion_level"],
                    "congestion_level": latest_congestion["congestion_level"],
                    "telemetry_timeline": telemetry_timeline,
                    "status": "COMPLETED",
                    "processed_video": processed_video_url,
                    "emergency": "NOT CONFIGURED"
                })
                # Trigger signal timing and light switching now that calculations are finished
                from optimization.optimizer import get_signal_manager
                get_signal_manager().on_road_completed(r_id)

                # Persist completed traffic record to analytics database
                try:
                    from database.queries import insert_traffic_record
                    insert_traffic_record(
                        road_id=r_id,
                        vehicle_count=final_count,
                        density=latest_density["density_percentage"],
                        congestion_level=latest_congestion["congestion_level"],
                        emergency_detected=False
                    )
                except Exception as log_err:
                    logger.debug(f"DB record logging notice: {log_err}")
            except Exception as e:
                logger.error(f"Final state update failed: {e}")

        logger.info(f"Processing complete for {r_id}: {output_path}")
        return result

    def _create_video_writer(self, output_path, fps, width, height):
        # 1. MSMF H264 for Windows/HTML5 playback
        try:
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            writer = cv2.VideoWriter(output_path, cv2.CAP_MSMF, fourcc, fps, (width, height))
            if writer.isOpened():
                return writer
        except Exception:
            pass

        # 2. FFMPEG avc1
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if writer.isOpened():
                return writer
        except Exception:
            pass

        # 3. Fallback mp4v
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        return cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    def calculate_density(self, count):
        calc = TrafficDensityCalculator()
        return calc.calculate_density(count)

    def calculate_congestion(self, count):
        if count <= 5:
            return "NORMAL"
        elif count <= 12:
            return "MODERATE"
        return "HIGH"


RoadVideoProcessor = TrafficProcessor
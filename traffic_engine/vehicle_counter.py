import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _ccw(A, B, C):
    """Checks if points A, B, C are in counter-clockwise order."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def _segments_intersect(A, B, C, D):
    """Determines whether line segment AB intersects line segment CD."""
    return _ccw(A, C, D) != _ccw(B, C, D) and _ccw(A, B, C) != _ccw(A, B, D)


class VehicleCounter:
    """
    Maintains independent tracking state and vehicle counting metrics for a specific road:
    1. Current Vehicles: Number of vehicles currently visible inside the road's ROI.
    2. Total Vehicles Counted: Number of unique vehicles that have crossed the virtual counting line.
    """

    def __init__(self, entry_line=None, roi_polygon=None, frame_width=640, frame_height=360, min_hits=1):
        self.width = frame_width
        self.height = frame_height
        self.min_hits = max(1, int(min_hits))

        # Virtual counting line (horizontal line at 55% of frame height by default)
        if entry_line is not None:
            self.entry_line = entry_line
        else:
            line_y = int(frame_height * 0.55)
            self.entry_line = [(0, line_y), (frame_width, line_y)]

        # Road ROI polygon (default is 95% of active road frame)
        if roi_polygon is not None:
            self.roi_polygon = np.array(roi_polygon, dtype=np.int32)
        else:
            margin_x = int(frame_width * 0.02)
            margin_y = int(frame_height * 0.05)
            self.roi_polygon = np.array([
                [margin_x, margin_y],
                [frame_width - margin_x, margin_y],
                [frame_width - margin_x, frame_height - margin_y],
                [margin_x, frame_height - margin_y]
            ], dtype=np.int32)

        self.frame_index = 0
        self.counted_ids = set()
        self.unique_tracked_ids = set()
        self.prev_centroids = {}        # canonical_id -> (cx, cy)
        self.track_history = {}         # canonical_id -> list of (cx, cy)
        self.class_counts = {}          # class_name -> total counted
        self.current_roi_tracks = []    # Tracks inside ROI in current frame
        self.just_crossed_ids = set()

        # Spatial-temporal re-identification & stitching state
        self.id_aliases = {}            # raw_track_id -> canonical_id
        self.track_frame_counts = {}    # canonical_id -> total frames confirmed
        self.active_tracks = {}         # canonical_id -> dict(centroid, class_name, box, last_seen)
        self.lost_tracks = {}           # canonical_id -> dict(centroid, class_name, box, last_seen)

    def update_resolution(self, width, height):
        """Adapts line and ROI dimensions when video resolution changes."""
        self.width = width
        self.height = height
        line_y = int(height * 0.55)
        self.entry_line = [(0, line_y), (width, line_y)]
        margin_x = int(width * 0.02)
        margin_y = int(height * 0.05)
        self.roi_polygon = np.array([
            [margin_x, margin_y],
            [width - margin_x, margin_y],
            [width - margin_x, height - margin_y],
            [margin_x, height - margin_y]
        ], dtype=np.int32)

    def is_inside_roi(self, cx, cy):
        """Checks if point (cx, cy) is inside the configured road ROI."""
        if self.roi_polygon is None or len(self.roi_polygon) < 3:
            return True
        pt = (float(cx), float(cy))
        return cv2.pointPolygonTest(self.roi_polygon, pt, False) >= 0

    def process_frame_tracks(self, tracks):
        """
        Updates tracking, separates ROI-resident vehicles, performs spatial-temporal
        track stitching to eliminate duplicate counts from ID switches, and checks
        counting-line crossing.
        
        Args:
            tracks (list of dict): Detections with x1, y1, x2, y2, class_name, track_id.
            
        Returns:
            list of dict: Filtered tracks that are currently inside the ROI with canonical track_ids.
        """
        self.frame_index += 1
        self.just_crossed_ids.clear()
        self.current_roi_tracks = []
        p1, p2 = self.entry_line[0], self.entry_line[1]

        current_frame_canonical_ids = set()

        for det in (tracks or []):
            raw_track_id = det.get("track_id")
            class_name = det.get("class_name", "car")
            x1, y1, x2, y2 = det.get("x1", 0), det.get("y1", 0), det.get("x2", 0), det.get("y2", 0)

            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            curr_pt = (cx, cy)

            # Strictly require vehicle to be within road ROI boundary
            in_roi = self.is_inside_roi(cx, cy)
            if not in_roi:
                continue

            # Resolve canonical ID with spatial-temporal stitching
            canonical_id = raw_track_id
            if raw_track_id is not None:
                if raw_track_id in self.id_aliases:
                    canonical_id = self.id_aliases[raw_track_id]
                else:
                    # Check if this new track matches a recently lost track of same vehicle class
                    best_stitched_id = None
                    best_dist = float("inf")
                    for lost_id, lost_info in list(self.lost_tracks.items()):
                        if lost_info["class_name"] != class_name:
                            continue
                        elapsed = self.frame_index - lost_info["last_seen"]
                        if elapsed > 45:  # ~1.5 to 2 seconds at 25-30fps
                            continue
                        lcx, lcy = lost_info["centroid"]
                        dist = np.hypot(cx - lcx, cy - lcy)
                        # Dynamic distance threshold based on frames elapsed
                        max_allowed_dist = min(120.0, 45.0 + 3.0 * elapsed)
                        if dist < max_allowed_dist and dist < best_dist:
                            best_dist = dist
                            best_stitched_id = lost_id

                    if best_stitched_id is not None:
                        canonical_id = best_stitched_id
                        self.id_aliases[raw_track_id] = canonical_id
                        if canonical_id in self.lost_tracks:
                            del self.lost_tracks[canonical_id]
                        logger.debug(
                            f"[VehicleCounter] Stitched raw ID #{raw_track_id} -> canonical ID #{canonical_id} "
                            f"(dist={best_dist:.1f}px)"
                        )
                    else:
                        canonical_id = raw_track_id
                        self.id_aliases[raw_track_id] = canonical_id

                # Update det with the unified canonical track_id
                det["track_id"] = canonical_id
                current_frame_canonical_ids.add(canonical_id)

                # Track confirmation count
                self.track_frame_counts[canonical_id] = self.track_frame_counts.get(canonical_id, 0) + 1

                # Only register as confirmed unique vehicle if seen for min_hits
                if self.track_frame_counts[canonical_id] >= self.min_hits:
                    self.unique_tracked_ids.add(canonical_id)

                # Record active track position
                self.active_tracks[canonical_id] = {
                    "centroid": curr_pt,
                    "class_name": class_name,
                    "box": (x1, y1, x2, y2),
                    "last_seen": self.frame_index
                }

                # Update trajectory history
                if canonical_id not in self.track_history:
                    self.track_history[canonical_id] = []
                self.track_history[canonical_id].append(curr_pt)
                if len(self.track_history[canonical_id]) > 30:
                    self.track_history[canonical_id].pop(0)

                # Check virtual counting line crossing
                if canonical_id in self.prev_centroids:
                    prev_pt = self.prev_centroids[canonical_id]

                    crossed = _segments_intersect(prev_pt, curr_pt, p1, p2)
                    if not crossed and p1[1] == p2[1]:
                        line_y = p1[1]
                        if (prev_pt[1] < line_y <= curr_pt[1]) or (prev_pt[1] > line_y >= curr_pt[1]):
                            min_x = min(p1[0], p2[0])
                            max_x = max(p1[0], p2[0])
                            if min(prev_pt[0], curr_pt[0]) <= max_x and max(prev_pt[0], curr_pt[0]) >= min_x:
                                crossed = True

                    if crossed and canonical_id not in self.counted_ids:
                        self.counted_ids.add(canonical_id)
                        self.just_crossed_ids.add(canonical_id)
                        self.class_counts[class_name] = self.class_counts.get(class_name, 0) + 1
                        logger.info(
                            f"[TrafficCounter] Track #{canonical_id} ({class_name}) crossed virtual line. "
                            f"Total line crossed: {len(self.counted_ids)}"
                        )

                self.prev_centroids[canonical_id] = curr_pt

            self.current_roi_tracks.append(det)

        # Move unobserved active tracks to lost_tracks for re-identification
        for cid in list(self.active_tracks.keys()):
            if cid not in current_frame_canonical_ids:
                track_info = self.active_tracks.pop(cid)
                self.lost_tracks[cid] = track_info

        # Prune stale lost tracks (>60 frames)
        for cid in list(self.lost_tracks.keys()):
            if self.frame_index - self.lost_tracks[cid]["last_seen"] > 60:
                del self.lost_tracks[cid]

        return self.current_roi_tracks

    def get_current_roi_count(self):
        """Returns number of vehicles currently visible inside ROI right now."""
        return len(self.current_roi_tracks)

    def get_line_count(self):
        """Returns cumulative total vehicles that crossed virtual counting line."""
        return len(self.counted_ids)

    def get_unique_tracked_count(self):
        """Returns total distinct vehicle IDs seen over entire stream."""
        return len(self.unique_tracked_ids)

    def reset(self):
        """Resets all metrics for a fresh video."""
        self.frame_index = 0
        self.counted_ids.clear()
        self.unique_tracked_ids.clear()
        self.prev_centroids.clear()
        self.track_history.clear()
        self.class_counts.clear()
        self.current_roi_tracks.clear()
        self.just_crossed_ids.clear()
        self.id_aliases.clear()
        self.track_frame_counts.clear()
        self.active_tracks.clear()
        self.lost_tracks.clear()
        self.current_roi_tracks.clear()
        self.just_crossed_ids.clear()

    def draw_on_frame(self, frame):
        """Draws ROI boundary, virtual counting line, and trajectory history trails."""
        # 1. Draw ROI polygon boundary
        if self.roi_polygon is not None and len(self.roi_polygon) >= 3:
            cv2.polylines(frame, [self.roi_polygon], True, (255, 128, 0), 1, cv2.LINE_AA)

        # 2. Draw virtual counting line
        p1, p2 = self.entry_line[0], self.entry_line[1]
        line_color = (0, 255, 0) if len(self.just_crossed_ids) > 0 else (0, 255, 255)
        cv2.line(frame, p1, p2, line_color, 2, cv2.LINE_AA)

        # Label
        label = f"COUNT LINE [{len(self.counted_ids)}]"
        cv2.putText(frame, label, (p1[0] + 12, p1[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_color, 1, cv2.LINE_AA)

        # 3. Draw trajectory history trails
        for det in self.current_roi_tracks:
            track_id = det.get("track_id")
            if track_id and track_id in self.track_history:
                history = self.track_history[track_id]
                for i in range(1, len(history)):
                    cv2.line(frame, history[i - 1], history[i], (0, 215, 255), 1, cv2.LINE_AA)

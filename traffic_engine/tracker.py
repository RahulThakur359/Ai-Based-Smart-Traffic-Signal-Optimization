import logging
import numpy as np

logger = logging.getLogger(__name__)


def compute_iou(boxA, boxB):
    """
    Computes Intersection-over-Union (IoU) between two bounding boxes [x1, y1, x2, y2].
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    inter_area = inter_width * inter_height

    boxA_area = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxB_area = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])

    union_area = boxA_area + boxB_area - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class VehicleTracker:
    """
    Reliable multi-object vehicle tracker that maintains persistent IDs across
    sequential video frames using IoU matching and centroid proximity.
    """

    def __init__(self, max_lost=30, iou_thresh=0.25, max_dist=80):
        self.max_lost = max_lost
        self.iou_thresh = iou_thresh
        self.max_dist = max_dist
        self.next_id = 1
        self.tracks = {}  # track_id -> dict(box, centroid, class_name, confidence, lost)
        self.unique_ids = set()

    def reset(self):
        """
        Resets all active tracks and unique ID sets for a fresh video stream.
        """
        self.tracks.clear()
        self.unique_ids.clear()
        self.next_id = 1
        logger.info("VehicleTracker reset.")

    def get_unique_count(self):
        """
        Returns total number of unique vehicles tracked so far across the video.
        """
        return len(self.unique_ids)

    def update(self, detections, frame_shape=None):
        """
        Updates tracks with new detections from the current frame.

        Args:
            detections (list of dict): Detections containing x1, y1, x2, y2, confidence, class_name, class_id
            frame_shape (tuple, optional): (height, width) of the frame

        Returns:
            list of dict: Detections with guaranteed persistent 'track_id' field.
        """
        if not detections:
            dead_ids = []
            for tid, track in self.tracks.items():
                track["lost"] += 1
                if track["lost"] > self.max_lost:
                    dead_ids.append(tid)
            for tid in dead_ids:
                del self.tracks[tid]
            return []

        det_boxes = []
        det_centroids = []
        for det in detections:
            box = [det["x1"], det["y1"], det["x2"], det["y2"]]
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            det_boxes.append(box)
            det_centroids.append((cx, cy))

        active_track_ids = list(self.tracks.keys())
        matched_tracks = set()
        matched_dets = set()

        if active_track_ids:
            # 1. IoU Matching matrix
            iou_matrix = np.zeros((len(active_track_ids), len(detections)), dtype=np.float32)
            for i, tid in enumerate(active_track_ids):
                track_box = self.tracks[tid]["box"]
                for j, det_box in enumerate(det_boxes):
                    iou_matrix[i, j] = compute_iou(track_box, det_box)

            # Greedy matching for highest IoU >= iou_thresh
            while True:
                max_val = np.max(iou_matrix)
                if max_val < self.iou_thresh:
                    break
                i, j = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                tid = active_track_ids[i]
                if tid not in matched_tracks and j not in matched_dets:
                    matched_tracks.add(tid)
                    matched_dets.add(j)
                    self.tracks[tid]["box"] = det_boxes[j]
                    self.tracks[tid]["centroid"] = det_centroids[j]
                    self.tracks[tid]["lost"] = 0
                    if detections[j].get("track_id") is None:
                        detections[j]["track_id"] = tid
                iou_matrix[i, :] = -1.0
                iou_matrix[:, j] = -1.0

            # 2. Centroid distance matching for remaining unmatched detections of same class
            unmatched_tracks = [tid for tid in active_track_ids if tid not in matched_tracks]
            unmatched_dets = [j for j in range(len(detections)) if j not in matched_dets]

            for j in unmatched_dets:
                best_tid = None
                best_dist = float("inf")
                det_c = det_centroids[j]
                det_class = detections[j].get("class_name")

                for tid in unmatched_tracks:
                    track = self.tracks[tid]
                    if track["class_name"] != det_class:
                        continue
                    track_c = track["centroid"]
                    dist = np.hypot(det_c[0] - track_c[0], det_c[1] - track_c[1])
                    if dist < self.max_dist and dist < best_dist:
                        best_dist = dist
                        best_tid = tid

                if best_tid is not None:
                    matched_tracks.add(best_tid)
                    matched_dets.add(j)
                    unmatched_tracks.remove(best_tid)
                    self.tracks[best_tid]["box"] = det_boxes[j]
                    self.tracks[best_tid]["centroid"] = det_centroids[j]
                    self.tracks[best_tid]["lost"] = 0
                    self.tracks[best_tid]["confidence"] = detections[j].get("confidence", 0.0)
                    if detections[j].get("track_id") is None:
                        detections[j]["track_id"] = best_tid

        # 3. Create or assign new tracks for unmatched detections
        for j, det in enumerate(detections):
            if j not in matched_dets:
                existing_tid = det.get("track_id")
                if existing_tid is not None and isinstance(existing_tid, int) and existing_tid > 0:
                    tid = existing_tid
                    if tid >= self.next_id:
                        self.next_id = tid + 1
                else:
                    tid = self.next_id
                    self.next_id += 1

                if det.get("track_id") is None:
                    det["track_id"] = tid
                self.unique_ids.add(det["track_id"])
                self.tracks[tid] = {
                    "box": det_boxes[j],
                    "centroid": det_centroids[j],
                    "class_name": det.get("class_name", "car"),
                    "confidence": det.get("confidence", 0.0),
                    "lost": 0
                }
            else:
                self.unique_ids.add(detections[j]["track_id"])

        # 4. Age out dead tracks
        dead_ids = []
        for tid in active_track_ids:
            if tid not in matched_tracks:
                self.tracks[tid]["lost"] += 1
                if self.tracks[tid]["lost"] > self.max_lost:
                    dead_ids.append(tid)

        for tid in dead_ids:
            del self.tracks[tid]

        return detections

import copy
from flask import Blueprint, jsonify, request
from config import Config
from optimization.optimizer import get_signal_manager

traffic_api_bp = Blueprint(
    'traffic_api',
    __name__,
    url_prefix='/api/traffic'
)

def _build_initial_road_state(road_id):
    road_area = Config.ROAD_AREAS.get(road_id, 350.0)
    return {
        "road_id": road_id,
        "vehicle_count": 0,
        "unique_vehicle_count": 0,
        "current_vehicles": 0,
        "active_vehicles": 0,
        "line_crossed_count": 0,
        "occupied_area_m2": 0.0,
        "road_area_m2": road_area,
        "density_percentage": 0.0,
        "density": "LOW",
        "density_category": "LOW",
        "congestion": "NORMAL",
        "congestion_level": "NORMAL",
        "emergency": "NOT CONFIGURED",
        "status": "IDLE",
        "processed_video": None,
        "original_video": None
    }

traffic_state = {
    "road1": _build_initial_road_state("road1"),
    "road2": _build_initial_road_state("road2"),
    "road3": _build_initial_road_state("road3"),
    "road4": _build_initial_road_state("road4")
}


@traffic_api_bp.route('/status', methods=['GET'])
def get_traffic_status():
    """
    Returns complete real-time traffic intelligence and synchronized
    simulated signal light states for all four intersection branches.
    """
    try:
        manager = get_signal_manager()
        signal_data = manager.get_status()
    except Exception:
        signal_data = {}

    response_data = copy.deepcopy(traffic_state)
    for rid in ['road1', 'road2', 'road3', 'road4']:
        if rid in response_data and rid in signal_data:
            sig = signal_data[rid]
            response_data[rid]['signal'] = sig.get('state', 'RED')
            response_data[rid]['remaining_time'] = sig.get('remaining_time')
            response_data[rid]['optimized_green'] = sig.get('optimized_green')
            response_data[rid]['decision_reason'] = sig.get('decision_reason')
            response_data[rid]['starvation_count'] = sig.get('starvation_count', 0)

    if 'meta' in signal_data:
        response_data['meta'] = signal_data['meta']

    return jsonify(response_data)


@traffic_api_bp.route('/road/<road_id>', methods=['GET'])
def get_individual_road_status(road_id):
    """Returns granular metrics for a single designated road branch."""
    if road_id not in traffic_state:
        return jsonify({'success': False, 'error': f'Invalid road identifier {road_id}'}), 404

    try:
        manager = get_signal_manager()
        signal_data = manager.get_status().get(road_id, {})
    except Exception:
        signal_data = {}

    data = copy.deepcopy(traffic_state[road_id])
    data['signal'] = signal_data.get('state', 'RED')
    data['remaining_time'] = signal_data.get('remaining_time')
    data['optimized_green'] = signal_data.get('optimized_green')
    data['decision_reason'] = signal_data.get('decision_reason')

    return jsonify({
        'success': True,
        'road_id': road_id,
        'data': data
    })


@traffic_api_bp.route('/status/<road_id>', methods=['GET'])
def get_processing_status(road_id):
    """Returns video processing status for a designated road."""
    if road_id not in traffic_state:
        return jsonify({'success': False, 'error': 'Invalid road ID'}), 404

    st = traffic_state[road_id]
    return jsonify({
        'success': True,
        'road_id': road_id,
        'status': st.get('status', 'IDLE'),
        'processed_video': st.get('processed_video'),
        'current_vehicles': st.get('current_vehicles', 0),
        'line_crossed_count': st.get('line_crossed_count', 0)
    })


@traffic_api_bp.route('/update/<road_id>', methods=['POST'])
def update_traffic_status(road_id):
    if road_id not in traffic_state:
        return jsonify({"success": False, "error": "Invalid road ID"}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400

    traffic_state[road_id].update(data)
    return jsonify({
        "success": True,
        "road_id": road_id,
        "data": traffic_state[road_id]
    })


# Persistent live analyzers for instant canvas detections
_live_congestion_calcs = {}
_live_counters = {}


@traffic_api_bp.route('/detect_frame', methods=['POST'])
def detect_single_frame():
    """
    Real-time frame detection endpoint.
    Performs fast YOLOv8 inference with tracking on video frame, computes occupied physical area,
    density percentage, and movement-based congestion, updating road state immediately.
    """
    try:
        import base64
        import numpy as np
        import cv2
        from traffic_engine.detector import get_shared_detector
        from traffic_engine.density import TrafficDensityCalculator
        from traffic_engine.congestion import CongestionLevelCalculator
        from traffic_engine.vehicle_counter import VehicleCounter

        payload = request.get_json(silent=True)
        if not payload or 'image' not in payload:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        image_data = payload['image']
        road_id = payload.get('road_id', 'road1')
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]

        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'success': False, 'error': 'Image decode failed'}), 400

        h, w = frame.shape[:2]

        if road_id not in _live_congestion_calcs:
            _live_congestion_calcs[road_id] = CongestionLevelCalculator()
        if road_id not in _live_counters:
            _live_counters[road_id] = VehicleCounter(frame_width=w, frame_height=h)

        counter = _live_counters[road_id]
        cong_calc = _live_congestion_calcs[road_id]

        detector = get_shared_detector()
        # Fast inference (imgsz=480) with persistent ID tracking
        detections = detector.track(frame, persist=True, imgsz=480)

        # Filter noise and check ROI membership
        min_box_area = 300
        valid_dets = [
            d for d in detections
            if (d['x2'] - d['x1']) * (d['y2'] - d['y1']) >= min_box_area
        ]
        roi_detections = counter.process_frame_tracks(valid_dets)

        current_roi_count = counter.get_current_roi_count()
        line_crossed_count = counter.get_line_count()
        unique_vehicle_count = counter.get_unique_tracked_count()

        # Compute physical area density
        density_calc = TrafficDensityCalculator(road_id=road_id)
        density_info = density_calc.compute_density(roi_detections)

        # Compute real motion-based congestion
        cong_info = cong_calc.update_and_calculate(roi_detections)

        # Immediately update live traffic state in shared memory
        traffic_state[road_id].update({
            "current_vehicles": current_roi_count,
            "active_vehicles": current_roi_count,
            "vehicle_count": unique_vehicle_count,
            "unique_vehicle_count": unique_vehicle_count,
            "line_crossed_count": line_crossed_count,
            "occupied_area_m2": density_info['occupied_area_m2'],
            "road_area_m2": density_info['road_area_m2'],
            "density_percentage": density_info['density_percentage'],
            "density": density_info['density_category'],
            "density_category": density_info['density_category'],
            "congestion": cong_info['congestion_level'],
            "congestion_level": cong_info['congestion_level'],
            "stopped_vehicles": cong_info['stopped_vehicles']
        })

        return jsonify({
            'success': True,
            'road_id': road_id,
            'detections': valid_dets,
            'count': len(valid_dets),
            'current_vehicles': current_roi_count,
            'line_crossed_count': line_crossed_count,
            'unique_vehicle_count': unique_vehicle_count,
            'occupied_area_m2': density_info['occupied_area_m2'],
            'road_area_m2': density_info['road_area_m2'],
            'density_percentage': density_info['density_percentage'],
            'density_category': density_info['density_category'],
            'congestion': cong_info['congestion_level'],
            'stopped_vehicles': cong_info['stopped_vehicles'],
            'frame_width': w,
            'frame_height': h
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
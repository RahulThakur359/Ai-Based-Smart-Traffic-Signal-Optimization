import os
import logging
import threading

from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from config import Config
from traffic_engine.processor import TrafficProcessor
from traffic_engine.detector import get_shared_detector
from routes.traffic_api import traffic_state


logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)


# ======================================================
# Allowed video file check
# ======================================================

def allowed_file(filename):
    """
    Check whether uploaded file has a supported
    video extension.
    """

    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in Config.ALLOWED_EXTENSIONS
    )


# ======================================================
# Upload video
# ======================================================

@upload_bp.route('/upload/<road_id>', methods=['POST'])
def upload_video(road_id):
    """
    Upload video for Road 1 to Road 4.

    Flow:
        Upload
        -> Save video
        -> Async YOLOv8 processing in background thread
        -> Update traffic_state live
        -> Return processed video URL immediately to dashboard
    """

    # --------------------------------------------------
    # 1. Validate road ID
    # --------------------------------------------------

    if road_id not in [
        'road1',
        'road2',
        'road3',
        'road4'
    ]:

        return jsonify({
            'success': False,
            'error': 'Invalid road identifier'
        }), 400


    # --------------------------------------------------
    # 2. Check video file
    # --------------------------------------------------

    if 'video' not in request.files:

        return jsonify({
            'success': False,
            'error': 'No video file part in request'
        }), 400


    file = request.files['video']


    if file.filename == '':

        return jsonify({
            'success': False,
            'error': 'No file selected'
        }), 400


    # --------------------------------------------------
    # 3. Validate file extension
    # --------------------------------------------------

    if not allowed_file(file.filename):

        return jsonify({
            'success': False,
            'error': (
                'Unsupported file format. '
                'Supported: mp4, avi, mov, mkv'
            )
        }), 400


    # --------------------------------------------------
    # 4. Secure filename
    # --------------------------------------------------

    filename = secure_filename(file.filename)


    # --------------------------------------------------
    # 5. Create road folder
    # --------------------------------------------------

    road_dir = os.path.join(
        Config.UPLOAD_FOLDER,
        road_id
    )

    os.makedirs(
        road_dir,
        exist_ok=True
    )


    # --------------------------------------------------
    # 6. Save video
    # --------------------------------------------------

    target_path = os.path.join(
        road_dir,
        filename
    )


    try:

        file.save(target_path)

        logger.info(
            f"Video uploaded successfully for "
            f"{road_id}: {filename}"
        )

    except Exception as e:

        logger.exception(
            f"Failed to save video for "
            f"{road_id}: {e}"
        )

        return jsonify({
            'success': False,
            'error': 'Failed to save uploaded video'
        }), 500


    # --------------------------------------------------
    # 7. Output video URLs
    # --------------------------------------------------

    input_name = os.path.splitext(filename)[0]
    output_filename = f"{input_name}_detected.mp4"

    video_url = f"/uploads/{road_id}/{filename}"
    processed_video_url = f"/uploads/{road_id}/{output_filename}"


    # --------------------------------------------------
    # 8. Background processing for entire video
    # --------------------------------------------------

    traffic_state[road_id].update({
        'status': 'PROCESSING',
        'vehicle_count': 0,
        'unique_vehicle_count': 0,
        'current_vehicles': 0,
        'active_vehicles': 0,
        'line_crossed_count': 0,
        'occupied_area_m2': 0.0,
        'density_percentage': 0.0,
        'density': 'LOW',
        'density_category': 'LOW',
        'congestion': 'NORMAL',
        'congestion_level': 'NORMAL',
        'original_video': video_url,
        'processed_video': None,
        'telemetry_timeline': []
    })

    # Optional max_frames override if requested via query parameter
    max_frames_arg = request.args.get('max_frames', default=None)
    try:
        max_frames = int(max_frames_arg) if max_frames_arg is not None else None
    except (ValueError, TypeError):
        max_frames = None

    def run_background_processing(target_file, r_id, frames_limit):
        try:
            logger.info(
                f"Starting background processing for {r_id} (frames_limit={frames_limit or 'ALL'})..."
            )
            # Reuse the pre-loaded shared detector (loaded once at app startup)
            # to avoid the ~2 min YOLO model load penalty on every upload.
            shared_detector = get_shared_detector()
            processor = TrafficProcessor(detector=shared_detector)
            ai_res = processor.process_video(
                target_file,
                r_id,
                max_frames=frames_limit
            )
            logger.info(
                f"Full video processing completed for {r_id}: {ai_res.get('processed_video')}"
            )
        except Exception as e:
            logger.exception(f"Background processing failed for {r_id}: {e}")
            traffic_state[r_id].update({
                'status': 'ERROR'
            })

    processing_thread = threading.Thread(
        target=run_background_processing,
        args=(target_path, road_id, max_frames),
        daemon=True,
        name=f"Processor-{road_id}"
    )
    processing_thread.start()

    logger.info(
        f"Video uploaded for {road_id}. Spawned background processor for full duration."
    )

    return jsonify({
        "success": True,
        "message": "Video uploaded successfully. AI is processing the entire video in the background.",
        "filename": filename,
        "url": video_url,
        "road_id": road_id,
        "processed_video": None,
        "status": "PROCESSING"
    })


# ======================================================
# Serve uploaded video
# ======================================================

@upload_bp.route(
    '/uploads/<road_id>/<filename>'
)
def serve_uploaded_video(
    road_id,
    filename
):
    """
    Serve uploaded video so that the dashboard
    can play the video preview.
    """

    road_dir = os.path.join(
        Config.UPLOAD_FOLDER,
        road_id
    )

    return send_from_directory(
        road_dir,
        filename
    )
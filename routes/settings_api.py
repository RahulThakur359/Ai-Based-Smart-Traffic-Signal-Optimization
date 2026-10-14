import logging
from flask import Blueprint, jsonify, request
from config import Config
from optimization.optimizer import get_signal_manager
from database.db import get_db_connection

logger = logging.getLogger(__name__)

settings_api_bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')


@settings_api_bp.route('', methods=['GET'])
@settings_api_bp.route('/get', methods=['GET'])
def get_settings():
    """
    Returns current active system settings and algorithmic constraints.
    """
    manager = get_signal_manager()
    db_conn = get_db_connection()
    db_status = "CONNECTED (MySQL)" if db_conn else "STANDALONE (Built-in SQLite Storage Engine)"
    if db_conn and db_conn.is_connected():
        db_conn.close()

    return jsonify({
        'success': True,
        'settings': {
            'min_green': Config.MIN_GREEN_TIME,
            'max_green': Config.MAX_GREEN_TIME,
            'yellow_time': Config.YELLOW_TIME,
            'starvation_cycles': Config.MAX_STARVATION_CYCLES,
            'vehicle_model': 'yolov8n.pt',
            'emergency_model': 'ambulance_best.pt',
            'confidence_threshold': 0.25,
            'road_areas': {
                'road1': Config.ROAD_AREAS.get('road1', 350.0),
                'road2': Config.ROAD_AREAS.get('road2', 320.0),
                'road3': Config.ROAD_AREAS.get('road3', 350.0),
                'road4': Config.ROAD_AREAS.get('road4', 300.0)
            },
            'database': {
                'host': Config.DB_HOST,
                'user': Config.DB_USER,
                'name': Config.DB_NAME,
                'port': Config.DB_PORT,
                'status': db_status
            }
        }
    })


@settings_api_bp.route('/update', methods=['POST'])
def update_settings():
    """
    Updates system parameters and dynamically injects them into the running
    IntersectionSignalManager and Config in memory.
    """
    data = request.get_json(silent=True) or {}

    try:
        manager = get_signal_manager()

        if 'min_green' in data and data['min_green'] is not None:
            val = int(data['min_green'])
            if 5 <= val <= 45:
                Config.MIN_GREEN_TIME = val
                manager.min_green = val
                manager.timing_calculator.min_green = val

        if 'max_green' in data and data['max_green'] is not None:
            val = int(data['max_green'])
            if val >= Config.MIN_GREEN_TIME and val <= 180:
                Config.MAX_GREEN_TIME = val
                manager.max_green = val
                manager.timing_calculator.max_green = val

        if 'yellow_time' in data and data['yellow_time'] is not None:
            val = int(data['yellow_time'])
            if 2 <= val <= 10:
                Config.YELLOW_TIME = val
                manager.yellow_time = val

        if 'starvation_cycles' in data and data['starvation_cycles'] is not None:
            val = int(data['starvation_cycles'])
            if 1 <= val <= 10:
                Config.MAX_STARVATION_CYCLES = val

        if 'road_areas' in data and isinstance(data['road_areas'], dict):
            for rid, area in data['road_areas'].items():
                if rid in Config.ROAD_AREAS:
                    try:
                        Config.ROAD_AREAS[rid] = float(area)
                    except (ValueError, TypeError):
                        pass

        if 'db_host' in data:
            Config.DB_HOST = str(data['db_host']).strip()
        if 'db_user' in data:
            Config.DB_USER = str(data['db_user']).strip()
        if 'db_password' in data and data['db_password']:
            Config.DB_PASSWORD = str(data['db_password']).strip()
        if 'db_name' in data:
            Config.DB_NAME = str(data['db_name']).strip()
        if 'db_port' in data:
            try:
                Config.DB_PORT = int(data['db_port'])
            except ValueError:
                pass

        logger.info(
            f"[Settings] Updated active system config: MinGreen={Config.MIN_GREEN_TIME}s, "
            f"MaxGreen={Config.MAX_GREEN_TIME}s, Yellow={Config.YELLOW_TIME}s, Starvation={Config.MAX_STARVATION_CYCLES}"
        )

        return jsonify({
            'success': True,
            'message': 'System settings updated and applied to live signal controller successfully.',
            'settings': {
                'min_green': Config.MIN_GREEN_TIME,
                'max_green': Config.MAX_GREEN_TIME,
                'yellow_time': Config.YELLOW_TIME,
                'starvation_cycles': Config.MAX_STARVATION_CYCLES,
                'road_areas': Config.ROAD_AREAS
            }
        })
    except Exception as e:
        logger.exception(f"Error updating settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@settings_api_bp.route('/test_db', methods=['POST'])
def test_db_connection():
    """
    Tests connectivity to the configured MySQL database.
    """
    try:
        conn = get_db_connection()
        if conn and conn.is_connected():
            conn.close()
            return jsonify({
                'success': True,
                'status': 'ONLINE',
                'message': f"Successfully connected to MySQL database '{Config.DB_NAME}' at {Config.DB_HOST}:{Config.DB_PORT}."
            })
        else:
            return jsonify({
                'success': False,
                'status': 'STANDALONE_SQLITE',
                'message': f"MySQL database at {Config.DB_HOST}:{Config.DB_PORT} is offline. High-performance built-in SQLite engine is active."
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'OFFLINE',
            'message': f"Connection failed: {e}. Fallback SQLite engine is operational."
        })


@settings_api_bp.route('/reset', methods=['POST'])
def reset_settings():
    """Resets all settings back to default engineering values."""
    Config.MIN_GREEN_TIME = 15
    Config.MAX_GREEN_TIME = 60
    Config.YELLOW_TIME = 4
    Config.MAX_STARVATION_CYCLES = 3
    Config.ROAD_AREAS = {
        'road1': 350.0,
        'road2': 320.0,
        'road3': 350.0,
        'road4': 300.0
    }

    manager = get_signal_manager()
    manager.min_green = 15
    manager.max_green = 60
    manager.yellow_time = 4
    manager.timing_calculator.min_green = 15
    manager.timing_calculator.max_green = 60

    return jsonify({
        'success': True,
        'message': 'Settings restored to default standard specifications.',
        'settings': {
            'min_green': 15,
            'max_green': 60,
            'yellow_time': 4,
            'starvation_cycles': 3,
            'road_areas': Config.ROAD_AREAS
        }
    })

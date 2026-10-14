from flask import Blueprint, jsonify, request
from optimization.optimizer import get_signal_manager
from routes.traffic_api import traffic_state

signal_api_bp = Blueprint('signal_api', __name__, url_prefix='/api/signal')


@signal_api_bp.route('/status', methods=['GET'])
def get_signal_status():
    """
    Returns live dynamic traffic signal states, countdown timers,
    active phase, and decision reasons computed by the adaptive signal optimizer.
    """
    manager = get_signal_manager()
    status = manager.get_status()
    return jsonify(status)


@signal_api_bp.route('/optimize', methods=['POST'])
def trigger_optimization():
    """
    Triggers an immediate cycle recalculation using current road metrics
    and returns the decision without waiting for the current green phase to expire.
    """
    manager = get_signal_manager()
    payload = request.get_json(silent=True) or {}
    metrics = payload.get('metrics') or traffic_state
    decision = manager.optimize_cycle(metrics)
    return jsonify({
        "success": True,
        "decision": decision,
        "current_status": manager.get_status()
    })

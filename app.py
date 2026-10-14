import os
import logging
from flask import Flask
from config import Config
from routes import register_blueprints
from database.db import init_db

# Set up logging format for stdout tracing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """
    Application factory to instantiate, configure, and initialize the Flask server.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Verify and create runtime directories
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'], app.config['MODEL_FOLDER']]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            logger.info(f"Created system directory: {folder}")
            
    # Pre-create folders for road inputs/outputs
    for road_id in ['road1', 'road2', 'road3', 'road4']:
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], road_id), exist_ok=True)
        os.makedirs(os.path.join(app.config['OUTPUT_FOLDER'], road_id), exist_ok=True)

    # Register blueprints (routes)
    register_blueprints(app)
    
    # Run database tables initialization inside application context
    with app.app_context():
        init_db()

    # Pre-warm YOLO model for instant inference
    try:
        from traffic_engine.detector import get_shared_detector
        get_shared_detector()
        logger.info("YOLO vehicle detector pre-warmed and ready.")
    except Exception as e:
        logger.warning(f"YOLO pre-warm skipped: {e}")

    # Initialize and start adaptive traffic signal manager simulation clock
    try:
        from optimization.optimizer import get_signal_manager
        get_signal_manager()
        logger.info("Adaptive Traffic Signal Optimizer simulation engine ready.")
    except Exception as e:
        logger.warning(f"Signal Optimizer initialization skipped: {e}")

    return app

# Instantiate the app
app = create_app()

if __name__ == '__main__':
    logger.info("Initializing Intelligent Traffic Optimization Dev Server...")
    # Bind to localhost port 5000 as requested
    app.run(host='127.0.0.1', port=5000, debug=True)

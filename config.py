import os

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file if it exists (for production/deployment configurations)
    load_dotenv()
except ImportError:
    # Fallback if python-dotenv is not installed in the current environment
    pass

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_traffic_signal_123_abc')
    
    # Base directory of the application
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Folders configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    MODEL_FOLDER = os.path.join(BASE_DIR, 'models')
    
    # Maximum allowed upload file size: 100MB (Windows/Flask friendly)
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 100 * 1024 * 1024))
    
    # Allowed video extensions for traffic stream inputs
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
    
    # Database Configuration (MySQL Connection settings)
    # We load from environment variables so credentials are never hard-coded in the source repository.
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')  # Set empty by default for local student setups
    DB_NAME = os.environ.get('DB_NAME', 'traffic_signal_db')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    
    # System settings for optimization heuristics
    MIN_GREEN_TIME = int(os.environ.get('MIN_GREEN_TIME', 15))  # Minimum green duration in seconds
    MAX_GREEN_TIME = int(os.environ.get('MAX_GREEN_TIME', 60))  # Maximum green duration in seconds
    YELLOW_TIME = int(os.environ.get('YELLOW_TIME', 4))        # Yellow duration in seconds
    MAX_STARVATION_CYCLES = int(os.environ.get('MAX_STARVATION_CYCLES', 3)) # Max cycles a road waits before priority boost

    # Estimated physical vehicle surface areas in m² (Standard Urban Traffic Engineering Specifications)
    VEHICLE_AREAS = {
        'motorcycle': 1.33,
        'car': 5.74,
        'bus': 14.41,
        'truck': 10.76,
        'bicycle': 1.10
    }

    # Total defined physical road area (m²) separately configured for each of the four roads
    ROAD_AREAS = {
        'road1': float(os.environ.get('ROAD1_AREA', 350.0)),  # Road 1 (North Branch)
        'road2': float(os.environ.get('ROAD2_AREA', 320.0)),  # Road 2 (East Branch)
        'road3': float(os.environ.get('ROAD3_AREA', 350.0)),  # Road 3 (South Branch)
        'road4': float(os.environ.get('ROAD4_AREA', 300.0)),  # Road 4 (West Branch)
    }

    # Area-based density percentage classification thresholds
    DENSITY_THRESHOLDS = {
        'LOW': 25.0,        # < 25.0%
        'MEDIUM': 50.0,     # 25.0% to 50.0%
        'HIGH': 75.0,       # 50.0% to 75.0%
        'VERY_HIGH': 100.0  # >= 75.0%
    }

    # Congestion classification parameters based on vehicle movement and queue characteristics
    CONGESTION_SETTINGS = {
        'STOPPED_SPEED_THRESHOLD_PX': 2.0,  # Vehicles moving less than 2px/frame considered stopped/crawling
        'HIGH_STOPPED_RATIO': 0.50,         # >= 50% vehicles stopped -> HIGH congestion
        'MODERATE_STOPPED_RATIO': 0.25,     # 25% - 50% stopped -> MODERATE congestion
        'SMOOTHING_WINDOW': 5               # Rolling window of frames for temporal smoothing
    }

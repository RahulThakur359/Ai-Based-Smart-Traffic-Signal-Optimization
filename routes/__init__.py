from .dashboard import dashboard_bp
from .upload import upload_bp
from .traffic_api import traffic_api_bp
from .signal_api import signal_api_bp
from .report_api import report_api_bp
from .settings_api import settings_api_bp
from .auth import auth_bp

def register_blueprints(app):
    """
    Dynamically registers all application blueprints on the Flask instance.
    """
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(traffic_api_bp)
    app.register_blueprint(signal_api_bp)
    app.register_blueprint(report_api_bp)
    app.register_blueprint(settings_api_bp)



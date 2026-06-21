from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from loguru import logger
import sys
from app.config import Config

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    CORS(app)
    db.init_app(app)
    socketio.init_app(app)
    
    from app.routes import files, audio, tasks, config as config_routes, image, birefnet
    app.register_blueprint(files.bp)
    app.register_blueprint(audio.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(config_routes.bp)
    app.register_blueprint(image.bp)
    app.register_blueprint(birefnet.birefnet_bp)
    
    config_class.init_app()
    
    logger.remove()
    logger.add(
        sys.stderr,
        format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
        level=config_class.LOG_LEVEL
    )
    logger.add(
        f"{config_class.LOG_DIR}/app.log",
        rotation=config_class.LOG_MAX_SIZE,
        retention=f"{config_class.LOG_RETENTION_DAYS} days",
        level=config_class.LOG_LEVEL
    )
    
    with app.app_context():
        db.create_all()
    
    logger.info("VATools application initialized")
    
    return app

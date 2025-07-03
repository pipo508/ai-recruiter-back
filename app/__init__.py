import os
import sys
import logging
import traceback
from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from dotenv import load_dotenv

from app.extensions import db, migrate, init_faiss
from app.config.default import config

def setup_logging():
    """Configura el logging para que sea visible en la consola"""
    # Configurar el logger raíz
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Asegura que vaya a stdout
            logging.FileHandler('app.log')  # Opcional: también a archivo
        ]
    )
    
    # Configurar loggers específicos
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Forzar que todos los logs se muestren
    logging.getLogger().setLevel(logging.DEBUG)

def create_app(config_name: str | None = None):
    print("--- INICIANDO CREATE_APP ---", flush=True)
    
    # IMPORTANTE: Configurar logging ANTES de crear la app
    setup_logging()

    app = Flask(__name__)
    load_dotenv()

    if not config_name:
        config_name = os.getenv("FLASK_ENV", "development")

    app.config.from_object(config[config_name])

    # Configurar el logger de la app de manera más agresiva
    app.logger.setLevel(logging.DEBUG)
    
    # Crear un handler personalizado para la consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Limpiar handlers existentes y agregar el nuestro
    app.logger.handlers.clear()
    app.logger.addHandler(console_handler)
    app.logger.propagate = True  # Asegurar que se propague

    app.logger.info(f"[INFO] Aplicación inicializada. Configuración activa: '{config_name}'.")

    # SQLAlchemy: solo warnings
    app.config['SQLALCHEMY_ECHO'] = False
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 🔧 Asegurar DEBUG
    app.config["DEBUG"] = True
    app.debug = True
    
    # ─────── CORS ───────
    allowed_origins = [
        "http://127.0.0.1:5500", "http://localhost:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8080", "http://3.138.181.127:5000",
        "http://ai-recruiter",

    ]
    CORS(app, resources={r"/*": {
        "origins": allowed_origins,
        "allow_headers": ["Authorization", "Content-Type"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    }})
    app.logger.info(f"CORS configurado para: {allowed_origins}")

    # ─────── Hooks de log de respuestas y errores ───────
    @app.after_request
    def log_response(resp):
        if resp.status_code >= 400:
            app.logger.warning(f"{resp.status_code} → {request.method} {request.url}")
        else:
            # También logear requests exitosos para debugging
            app.logger.info(f"✅ {resp.status_code} → {request.method} {request.url}")
        return resp

    @app.errorhandler(Exception)
    def handle_error(err):
        app.logger.error(
            "Excepción no controlada en %s\n%s: %s\n%s",
            request.url if request else "ruta desconocida",
            type(err).__name__, err,
            traceback.format_exc(),
        )
        return jsonify(error="Error interno del servidor"), 500

    # ─────── Extensiones y blueprints ───────
    with app.app_context():
        init_extensions(app)
        register_blueprints(app)
        register_shell_context(app)
        db.create_all()
        from flask_migrate import stamp
        stamp()

    return app


# ────────────────────── Helpers ──────────────────────
def init_extensions(app):
    app.logger.info("Inicializando extensiones…")
    db.init_app(app)
    migrate.init_app(app, db)
    init_faiss(app)
    app.logger.info("Extensiones inicializadas.")


def register_blueprints(app):
    from app.controllers.ControllersHome import bp as home_bp
    from app.controllers.ControllersUser import bp as user_bp
    from app.controllers.ControllersDocument import bp as document_bp
    from app.controllers.ControllersSearch import bp as search_bp

    app.register_blueprint(home_bp, url_prefix="/api/home")
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(document_bp, url_prefix="/api/document")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.logger.info("Blueprints registrados.")


def register_shell_context(app):
    @app.shell_context_processor
    def ctx():
        from app.models.User import User
        from app.models.Document import Document
        from app.models.VectorEmbedding import VectorEmbedding
        return dict(app=app, db=db, User=User, Document=Document, VectorEmbedding=VectorEmbedding)
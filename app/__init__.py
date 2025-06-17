import os
import logging
from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from dotenv import load_dotenv
import traceback

from app.Extensions import db, migrate, init_faiss
from app.config.default import config

def create_app(config_name=None):
    app = Flask(__name__)
    load_dotenv()

    if not config_name:
        config_name = os.getenv("FLASK_ENV", "development")

    app.config.from_object(config[config_name])
    
    # 🔧 Asegurar DEBUG
    app.config["DEBUG"] = True
    app.debug = True

    # 💡 Configurar logging para consola
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)

    app.logger.info(f"[INFO] Aplicación inicializada. Configuración activa: '{config_name}'.")

    # SQLAlchemy: solo warnings
    app.config['SQLALCHEMY_ECHO'] = False
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    allowed_origins = [
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
    ]
    CORS(app, resources={r"/*": {
        "origins": allowed_origins,
        "allow_headers": ["Authorization", "Content-Type"]
    }})
    app.logger.info(f"[INFO] CORS configurado. Orígenes permitidos: {allowed_origins}.")

    # 🔍 Logging antes de cada request
    @app.before_request
    def log_request():
        if request.path != '/favicon.ico':
            headers = dict(request.headers)
            auth_header = headers.get("Authorization", "No Authorization header")
            app.logger.debug(f"[DEBUG] Request → {request.method} {request.url}")
            app.logger.debug(f"[DEBUG] Headers: {headers}")
            app.logger.debug(f"[DEBUG] Authorization: {auth_header}")
            if request.method in ['POST', 'PUT', 'PATCH']:
                app.logger.debug(f"[DEBUG] Body: {request.get_data(as_text=True)}")

    # 🧩 Logging después de cada response con errores
    @app.after_request
    def log_response(response):
        if response.status_code >= 400:
            app.logger.warning(f"[WARN] Respuesta {response.status_code} para {request.method} {request.url}")
            app.logger.debug(f"[DEBUG] Response body: {response.get_data(as_text=True)}")
        return response

    # 🛑 Error Handler
    @app.errorhandler(Exception)
    def handle_error(error):
        error_route = request.url if request else "ruta desconocida"
        current_app.logger.error(
            f"[ERROR] Error inesperado en {error_route}\n"
            f"  [Tipo de Error] {type(error).__name__}: {str(error)}\n"
            f"  [TRACEBACK]\n{traceback.format_exc()}"
        )
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(error)
        }), 500

    # Modelos
    from app.models.User import User
    from app.models.Document import Document
    from app.models.VectorEmbedding import VectorEmbedding

    init_extensions(app)
    register_blueprints(app)
    register_shell_context(app)

    return app

def init_extensions(app):
    app.logger.info("[INFO] Inicializando extensiones...")
    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        init_faiss(app)
    app.logger.info("[INFO] Extensiones inicializadas correctamente.")

def register_blueprints(app):
    from app.controllers.ControllersHome import bp as home_bp
    from app.controllers.ControllersUser import bp as user_bp
    from app.controllers.ControllersDocument import bp as document_bp
    from app.controllers.ControllersSearch import bp as search_bp

    app.register_blueprint(home_bp, url_prefix="/home")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(document_bp, url_prefix="/document")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.logger.info("[INFO] Blueprints registrados.")

def register_shell_context(app):
    @app.shell_context_processor
    def ctx():
        from app.models.User import User
        from app.models.Document import Document
        from app.models.VectorEmbedding import VectorEmbedding
        return {
            "app": app,
            "db": db,
            "User": User,
            "Document": Document,
            "VectorEmbedding": VectorEmbedding
        }

"""
Módulo principal de la aplicación Flask que inicializa la app,
configura las extensiones y registra los blueprints.
"""

import os
import logging
from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from dotenv import load_dotenv
import traceback

from app.Extensions import db, migrate, init_faiss
from app.config.default import config

def create_app(config_name=None):
    """
    Crea y configura una instancia de la aplicación Flask.

    Args:
        config_name: Nombre de la configuración a cargar (development, testing, production).

    Returns:
        Instancia configurada de Flask.
    """
    app = Flask(__name__)

    # Cargar variables de entorno desde .env
    load_dotenv()

    # Determinar qué configuración usar
    if not config_name:
        config_name = os.getenv("FLASK_ENV", "development")

    # Cargar configuración
    app.config.from_object(config[config_name])
    app.logger.info(f"[INFO] Aplicación inicializada. Configuración activa: '{config_name}'.")

    # --- Limpieza de Logs ---
    # MODIFICACIÓN: Asegurar que SQLAlchemy no muestre logs de consultas
    app.config['SQLALCHEMY_ECHO'] = False
    
    # Desactiva los logs detallados de SQLAlchemy para mantener la consola limpia.
    # Solo mostrará mensajes de ADVERTENCIA (WARNING) o superiores.
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # Asegurar que exista el directorio de uploads
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Configurar CORS para permitir múltiples orígenes y cabeceras de autorización
    allowed_origins = [
        "http://127.0.0.1:5500",    # Live Server
        "http://localhost:3000",    # Create React App
        "http://localhost:5173",    # Vite (puerto por defecto)
        "http://127.0.0.1:5173",    # Vite con IP
    ]
    CORS(app, resources={r"/*": {
        "origins": allowed_origins,
        "allow_headers": ["Authorization", "Content-Type"]
    }})
    app.logger.info(f"[INFO] CORS configurado. Orígenes permitidos: {allowed_origins}.")

    # Registrar manejador para solicitudes
    @app.before_request
    def log_request():
        if request.path != '/favicon.ico': # Evita logs innecesarios
            # MODIFICACIÓN: Cambiado de .info a .debug para reducir la verbosidad
            current_app.logger.debug(f"[DEBUG] Solicitud entrante: {request.method} {request.url}")

    # Manejador de errores global
    @app.errorhandler(Exception)
    def handle_error(error):
        error_route = request.url if request else "ruta desconocida"
        error_message = f"Se ha producido un error no controlado en la ruta '{error_route}'."
        suggestion = "Revisar el traceback para identificar la causa del fallo en el código."
        
        current_app.logger.error(
            f"[ERROR] {error_message}\n"
            f"  [Tipo de Error] {type(error).__name__}: {str(error)}\n"
            f"  [Sugerencia] {suggestion}\n"
            f"  [TRACEBACK]\n{traceback.format_exc()}"
        )
        
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(error)
        }), 500

    # Importar modelos para asegurar que estén registrados
    from app.models.User import User
    from app.models.Document import Document
    from app.models.VectorEmbedding import VectorEmbedding

    # Inicializar extensiones
    init_extensions(app)

    # Registrar blueprints
    register_blueprints(app)

    # Configurar el shell context
    register_shell_context(app)

    return app

def init_extensions(app):
    """
    Inicializa todas las extensiones de Flask con la aplicación.

    Args:
        app: Instancia de Flask app.
    """
    app.logger.info("[INFO] Inicializando extensiones de Flask...")
    db.init_app(app)
    app.logger.info("[INFO] Extensión SQLAlchemy inicializada.")
    migrate.init_app(app, db)
    app.logger.info("[INFO] Extensión Flask-Migrate inicializada.")
    with app.app_context():
        init_faiss(app)
    app.logger.info("[INFO] Índice FAISS inicializado.")


def register_blueprints(app):
    """Registra todos los blueprints en la aplicación."""
    from app.controllers.ControllersHome import bp as home_bp
    from app.controllers.ControllersUser import bp as user_bp
    from app.controllers.ControllersDocument import bp as document_bp
    from app.controllers.ControllersSearch import bp as search_bp
    
    app.logger.info("[INFO] Registrando blueprints...")
    app.register_blueprint(home_bp, url_prefix="/home")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(document_bp, url_prefix="/document")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.logger.info("[INFO] Blueprints registrados correctamente.")

def register_shell_context(app):
    """
    Configura el contexto para el shell de Flask.

    Args:
        app: Instancia de Flask app.
    """
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
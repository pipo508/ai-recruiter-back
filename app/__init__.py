
"""
Módulo principal de la aplicación Flask que inicializa la app,
configura las extensiones y registra los blueprints.
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import traceback

from app.extensions import db, migrate, init_faiss
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
    app.logger.info(f"Aplicación inicializada con configuración: {config_name}")

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
    app.logger.info(f"CORS configurado para orígenes: {allowed_origins}")

    # Registrar manejador para solicitudes
    @app.before_request
    def log_request():
        app.logger.info(f"Solicitud recibida: {request.method} {request.url}")

    # Manejador de errores global
    @app.errorhandler(Exception)
    def handle_error(error):
        app.logger.error(f"Error no manejado: {str(error)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(error),
            'traceback': traceback.format_exc()
        }), 500

    # Importar modelos para asegurar que estén registrados
    from app.models.models_user import User
    from app.models.models_document import Document
    from app.models.models_vector_embedding import VectorEmbedding

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
    app.logger.info("Inicializando extensiones...")
    db.init_app(app)
    app.logger.info("SQLAlchemy inicializado")
    migrate.init_app(app, db)
    app.logger.info("Flask-Migrate inicializado")
    with app.app_context():
        init_faiss()

def register_blueprints(app):
    from app.controllers.controllers_home import bp as home_bp
    from app.controllers.controllers_user import bp as user_bp
    from app.controllers.controllers_document import bp as document_bp
    from app.controllers.controllers_search import bp as search_bp
    # from app.controllers.controllers_query import bp as query_bp

    app.register_blueprint(home_bp, url_prefix="/home")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(document_bp, url_prefix="/document")
    app.register_blueprint(search_bp, url_prefix="/search")
    # app.register_blueprint(query_bp, url_prefix="/query")

def register_shell_context(app):
    """
    Configura el contexto para el shell de Flask.

    Args:
        app: Instancia de Flask app.
    """
    @app.shell_context_processor
    def ctx():
        from app.models.models_user import User
        from app.models.models_document import Document
        from app.models.models_vector_embedding import VectorEmbedding
        return {
            "app": app,
            "db": db,
            "User": User,
            "Document": Document,
            "VectorEmbedding": VectorEmbedding
        }

def init_extensions(app):
    # ...
    db.init_app(app)
    # ...
    migrate.init_app(app, db)
    # ...
    with app.app_context():
        init_faiss(app) # Pasar la instancia de la app

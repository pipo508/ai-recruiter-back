"""
Módulo de configuración que define diferentes clases para los entornos
de desarrollo, pruebas y producción.
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class Config:
    """
    Clase base de configuración con configuraciones comunes para todos los entornos.
    """
    # --- Configuración de Seguridad y Autenticación ---
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-default')
    # LÍNEA AÑADIDA: Algoritmo para firmar los tokens JWT
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    
    # --- Configuración General de Flask ---
    DEBUG = True
    TESTING = False
    
    # --- Configuración de la base de datos ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Primero, intenta obtener la URL de conexión completa de Render.
    database_uri = os.getenv('DATABASE_URL')

    # Si la URL de Render existe y empieza con "postgres://", la adaptamos para SQLAlchemy.
    if database_uri and database_uri.startswith("postgres://"):
        database_uri = database_uri.replace("postgres://", "postgresql://", 1)

    # Si NO estamos en Render (es decir, no se encontró DATABASE_URL), 
    # entonces construimos la URI con las variables locales de tu archivo .env.
    if not database_uri:
        DB_USER = os.getenv('DB_USER')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME')
        database_uri = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Finalmente, asignamos la URI correcta (sea de Render o local) a la configuración.
    SQLALCHEMY_DATABASE_URI = database_uri
    
    # --- Configuración de FAISS ---
    FAISS_INDEX_PATH = os.path.join(os.getcwd(), 'instance', 'main_faiss.index')
    FAISS_EMBEDDING_DIMENSION = 3072 # ¡Verifica que coincida con tu modelo de embedding!

    # --- Configuración de OpenAI ---
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
    OPENAI_COMPLETION_MODEL = os.getenv('OPENAI_COMPLETION_MODEL', 'gpt-4o')
    
    # --- Configuración de la Aplicación ---
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Limita el tamaño de subida a 50MB
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf'}
    MIN_TEXT_LENGTH = 100  # Mínimo número de caracteres para considerar válido un texto


class DevelopmentConfig(Config):
    """Configuración para el entorno de desarrollo."""
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Muestra queries SQL en la consola


class TestingConfig(Config):
    """Configuración para el entorno de pruebas."""
    TESTING = True
    DEBUG = True
    DB_NAME = os.getenv('TEST_DB_NAME', 'test_db')
    
    # Esta URI también debería usar la lógica flexible, pero para simplificar,
    # la dejamos apuntando a una DB de prueba local.
    SQLALCHEMY_DATABASE_URI = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{DB_NAME}"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Configuración para el entorno de producción."""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("La variable de entorno SECRET_KEY no está definida para producción.")
    LOG_LEVEL = 'INFO'


# Diccionario para seleccionar la configuración según el entorno
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
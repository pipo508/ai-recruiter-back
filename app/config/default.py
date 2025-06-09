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
    # Configuración de Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = False
    TESTING = False
    
    # Configuración de FAISS
    FAISS_INDEX_PATH = os.path.join(os.getcwd(), 'instance', 'main_faiss.index')
    FAISS_EMBEDDING_DIMENSION = 3072 #si usas text-embedding-3-large con esa dimensión. ¡Verifica esto!


    # Configuración de la base de datos
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME')
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Configuración de OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
    OPENAI_COMPLETION_MODEL = os.getenv('OPENAI_COMPLETION_MODEL', 'gpt-4o')
    
    # Configuración de la aplicación
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Limita el tamaño de subida a 16MB
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf'}
    MIN_TEXT_LENGTH = 100  # Mínimo número de caracteres para considerar válido un texto


class DevelopmentConfig(Config):
    """
    Configuración para el entorno de desarrollo.
    """
    DEBUG = True
    SQLALCHEMY_ECHO = True  # Muestra queries SQL en la consola


class TestingConfig(Config):
    """
    Configuración para el entorno de pruebas.
    """
    TESTING = True
    DEBUG = True
    
    # Usar base de datos de prueba
    DB_NAME = os.getenv('TEST_DB_NAME', 'test_db')
    SQLALCHEMY_DATABASE_URI = f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}"
    
    # Desactivar CSRF para facilitar pruebas
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """
    Configuración para el entorno de producción.
    """
    # Sobrescribir SECRET_KEY con valor más fuerte para producción
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # Más configuraciones específicas de producción
    LOG_LEVEL = 'INFO'


# Diccionario para seleccionar la configuración según el entorno
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
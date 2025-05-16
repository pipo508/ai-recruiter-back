"""
Módulo para configurar y mantener instancias de las extensiones y servicios
utilizados en toda la aplicación.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import faiss
import firebase_admin
from firebase_admin import credentials, storage

# Instancia de SQLAlchemy para gestión de la base de datos
db = SQLAlchemy()

# Instancia de Migrate para gestionar migraciones de base de datos
migrate = Migrate()

# Variable para almacenar la instancia inicializada de Firebase
firebase_app = None

# Variable para almacenar el bucket de Firebase Storage
firebase_bucket = None

# Variable para almacenar el índice FAISS
faiss_index = None

def init_firebase(app):
    """
    Inicializa la conexión con Firebase usando las credenciales configuradas
    
    Args:
        app: Instancia de Flask app con la configuración cargada
    
    Returns:
        Instancia inicializada de la app de Firebase
    """
    global firebase_app, firebase_bucket
    
    # Verifica si ya está inicializado
    if firebase_app is not None:
        return firebase_app
    
    # Obtiene la ruta al archivo de credenciales de Firebase desde la configuración
    cred_path = app.config.get('FIREBASE_CREDENTIALS_PATH')
    
    if not cred_path:
        app.logger.warning("No se ha configurado la ruta de credenciales para Firebase")
        return None
    
    try:
        # Inicializa la app de Firebase con las credenciales
        cred = credentials.Certificate(cred_path)
        firebase_app = firebase_admin.initialize_app(cred, {
            'storageBucket': app.config.get('FIREBASE_STORAGE_BUCKET')
        })
        
        # Obtiene referencia al bucket de storage
        firebase_bucket = storage.bucket()
        
        app.logger.info("Firebase inicializado correctamente")
        return firebase_app
    
    except Exception as e:
        app.logger.error(f"Error al inicializar Firebase: {str(e)}")
        return None

def init_faiss():
    """
    Inicializa o carga un índice FAISS para búsqueda vectorial
    
    Returns:
        Índice FAISS inicializado
    """
    global faiss_index
    
    # Si el índice ya existe, lo devuelve
    if faiss_index is not None:
        return faiss_index
    
    # Crea un nuevo índice para vectores de OpenAI (1536 dimensiones)
    embedding_size = 1536  # Tamaño de los embeddings de text-embedding-ada-002
    faiss_index = faiss.IndexFlatL2(embedding_size)
    
    return faiss_index

def get_firebase_bucket():
    """
    Obtiene el bucket de Firebase Storage
    
    Returns:
        Bucket de Firebase o None si no está inicializado
    """
    return firebase_bucket

def get_faiss_index():
    """
    Obtiene el índice FAISS
    
    Returns:
        Índice FAISS o None si no está inicializado
    """
    return faiss_index
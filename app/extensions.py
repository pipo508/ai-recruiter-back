"""
Módulo para configurar y mantener instancias de las extensiones y servicios
utilizados en toda la aplicación.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import faiss
import os
from flask import current_app


# Instancia de SQLAlchemy para gestión de la base de datos
db = SQLAlchemy()

# Instancia de Migrate para gestionar migraciones de base de datos
migrate = Migrate()


faiss_index = None
_faiss_index_path = None # Para guardar la ruta

def init_faiss(app):
    """
    Inicializa o carga un índice FAISS.
    Usa IndexIDMap para asociar IDs de documentos directamente.
    """
    global faiss_index, _faiss_index_path

    if faiss_index is not None:
        return faiss_index

    _faiss_index_path = app.config['FAISS_INDEX_PATH']
    embedding_dimension = app.config['FAISS_EMBEDDING_DIMENSION']

    # Crear directorio para el índice si no existe
    os.makedirs(os.path.dirname(_faiss_index_path), exist_ok=True)

    if os.path.exists(_faiss_index_path):
        try:
            current_app.logger.info(f"Cargando índice FAISS desde {_faiss_index_path}")
            faiss_index = faiss.read_index(_faiss_index_path)
            current_app.logger.info(f"Índice FAISS cargado. Número actual de vectores: {faiss_index.ntotal}")
        except Exception as e:
            current_app.logger.error(f"Error al cargar el índice FAISS desde {_faiss_index_path}: {e}. Se creará uno nuevo.")
            faiss_index = None # Asegurar que se cree uno nuevo

    if faiss_index is None: # Si no existía o falló la carga
        current_app.logger.info(f"Creando nuevo índice FAISS en {_faiss_index_path} con dimensión {embedding_dimension}")
        # Usamos IndexFlatL2 como el índice base
        index_flat = faiss.IndexFlatL2(embedding_dimension)
        # Envolvemos con IndexIDMap para usar nuestros propios IDs (Document.id)
        faiss_index = faiss.IndexIDMap(index_flat)
        current_app.logger.info("Nuevo índice FAISS creado.")
        # Guardar el índice vacío inmediatamente
        save_faiss_index()

    return faiss_index

def get_faiss_index():
    """Obtiene el índice FAISS inicializado."""
    global faiss_index
    if faiss_index is None:
        current_app.logger.warning("Se intentó obtener el índice FAISS antes de inicializarlo o la inicialización falló.")
        # Podrías intentar inicializarlo aquí como fallback si es apropiado para tu flujo
        # init_faiss(current_app._get_current_object())
    return faiss_index

def save_faiss_index():
    """Guarda el índice FAISS actual en el disco."""
    global faiss_index, _faiss_index_path
    if faiss_index is not None and _faiss_index_path is not None:
        try:
            current_app.logger.info(f"Guardando índice FAISS en {_faiss_index_path} con {faiss_index.ntotal} vectores.")
            faiss.write_index(faiss_index, _faiss_index_path)
            current_app.logger.info("Índice FAISS guardado correctamente.")
        except Exception as e:
            current_app.logger.error(f"Error al guardar el índice FAISS en {_faiss_index_path}: {e}")
    else:
        current_app.logger.warning("Intento de guardar índice FAISS, pero no está inicializado o la ruta no está configurada.")

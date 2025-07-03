from flask import Blueprint, jsonify, current_app
from app.extensions import db  # Corregido
from sqlalchemy import text # <-- AÑADIR ESTA IMPORTACIÓN

# Crear blueprint para las rutas de home
bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    """
    Ruta de inicio de la aplicación.
    
    Returns:
        JSON con información básica de la API
    """
    return jsonify({
        'status': 'online',
        'name': 'Document Processing API',
        'version': '1.0.0',
        'description': 'API para procesamiento de documentos con OCR y búsqueda vectorial'
    })

@bp.route('/health')
def health():
    """
    Endpoint para verificar la salud de la aplicación.
    Útil para monitoreo y comprobaciones de estado.
    
    Returns:
        JSON con estado de salud de la API y sus componentes
    """
    # Comprobar conexión a base de datos
    db_status = "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Comprobar conexión a Firebase si está configurado
    firebase_status = "not configured"
    if current_app.config.get('FIREBASE_CREDENTIALS_PATH'):
        try:
            from app.extensions import get_firebase_bucket  # Corregido
            bucket = get_firebase_bucket()
            if bucket:
                firebase_status = "ok"
            else:
                firebase_status = "not initialized"
        except Exception as e:
            firebase_status = f"error: {str(e)}"
    
    # Comprobar configuración de OpenAI
    openai_status = "not configured"
    if current_app.config.get('OPENAI_API_KEY'):
        openai_status = "configured"
    
    return jsonify({
        'status': 'healthy',
        'version': 'logs-1-julio', # <-- ¡Nuestra marca inconfundible!
        'services': {
            'database': db_status,
            'firebase': firebase_status,
            'openai': openai_status
        }
    })

@bp.route('/status')
def status():
    """
    Endpoint para obtener información detallada del estado de la aplicación.
    
    Returns:
        JSON con información detallada del estado de la API
    """
    # Obtener algunas estadísticas básicas
    try:
        from app.models import User, Document, Query  # Corregido
        user_count = db.session.query(User).count()
        document_count = db.session.query(Document).count()
        query_count = db.session.query(Query).count()
        
        stats = {
            'users': user_count,
            'documents': document_count,
            'queries': query_count
        }
    except Exception as e:
        stats = {
            'error': f"No se pueden obtener estadísticas: {str(e)}"
        }
    
    return jsonify({
        'status': 'online',
        'environment': current_app.config.get('ENV', 'production'),
        'debug_mode': current_app.debug,
        'statistics': stats
    })

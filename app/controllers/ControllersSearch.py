from app.services.SearchService import SearchService
from app.services.HybridSearchService import HybridSearchService  # NUEVA IMPORTACIÓN
from app.services.SearchHistoryService import SearchHistoryService
import json
from flask import Blueprint, request, jsonify, current_app
bp = Blueprint('search', __name__)

# Modificar el endpoint de búsqueda
@bp.route('/', methods=['POST'], strict_slashes=False)
def search():
    """
    Endpoint de búsqueda híbrida
    """
    try:
        data = request.get_json() or {}
        query = data.get('query')
        use_hybrid = data.get('hybrid', True)  # Por defecto usar híbrido
        
        if not query:
            return jsonify({'error': 'Se requiere un texto de consulta en el campo "query"'}), 400

        if use_hybrid:
            # Usar búsqueda híbrida
            search_service = HybridSearchService()
            result_data = search_service.perform_hybrid_search(query)
        else:
            # Usar búsqueda semántica tradicional
            search_service = SearchService()
            result_data = search_service.perform_search(query)
            
        return jsonify(result_data), 200

    except Exception as e:
        current_app.logger.error(f"Error en la ruta de búsqueda: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@bp.route('/history', methods=['GET'], strict_slashes=False)
def get_search_history():
    """
    Obtiene el historial completo de búsquedas.
    """
    try:
        history_service = SearchHistoryService()
        history = history_service.get_all_search_results()
        history_data = [res.to_dict() for res in history]
        return jsonify(history_data), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener historial: {e}")
        return jsonify({'error': 'Error al obtener el historial'}), 500

@bp.route('/history/<int:search_id>', methods=['GET'], strict_slashes=False)
def get_search_result_by_id(search_id):
    """
    Obtiene un resultado de búsqueda específico por su ID.
    """
    try:
        history_service = SearchHistoryService()
        result = history_service.get_search_result_by_id(search_id)
        return jsonify(result.to_dict()), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'Error interno al obtener resultado'}), 500

@bp.route('/history/<int:search_id>', methods=['DELETE'], strict_slashes=False)
def delete_search_result(search_id):
    """
    Elimina un resultado de búsqueda. Delega toda la lógica al SearchHistoryService.
    """
    try:
        history_service = SearchHistoryService()
        history_service.delete_search_result_and_file(search_id)
        return jsonify({'message': 'Resultado de búsqueda eliminado correctamente'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        # --- CAMBIO CLAVE PARA DEPURACIÓN ---
        # Registra el error completo para que puedas verlo en la consola del servidor.
        current_app.logger.error(f"Excepción no controlada al eliminar {search_id}: {e}", exc_info=True)
        
        # Devuelve el mensaje de error real en la respuesta JSON para verlo en el navegador.
        # ¡IMPORTANTE! Haz esto solo en un entorno de desarrollo, nunca en producción.
        return jsonify({
            'error': 'Error interno del servidor. Ver la consola del backend para detalles.',
            'exception_type': type(e).__name__,
            'exception_details': str(e)
        }), 500
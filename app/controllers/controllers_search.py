import os
import json
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.services.OpenAIService import OpenAIRewriteService
from app.services.search_result_service import SearchResultService
from app.extensions import get_faiss_index, db
from app.models.models_document import Document

# Crear el blueprint
bp = Blueprint('search', __name__)

@bp.route('/', methods=['POST'], strict_slashes=False)
def search():
    """
    Realiza una búsqueda de similitudes en FAISS basada en un texto de consulta.
    Convierte el texto a embedding, busca documentos similares, calcula porcentajes
    de similitud, guarda los resultados en la carpeta 'resultados' y en la base de datos,
    y devuelve los resultados con el perfil estructurado en JSON.
    """
    try:
        data = request.get_json() or {}
        query = data.get('query')
        if not query:
            current_app.logger.error("Falta el campo 'query' en la solicitud")
            return jsonify({'error': 'Se requiere un texto de consulta en el campo "query"'}), 400

        openai_service = OpenAIRewriteService()
        try:
            embedding = openai_service.generate_embedding(query)
        except Exception as e:
            current_app.logger.error(f"Error al generar embedding: {str(e)}")
            return jsonify({'error': 'Error al generar embedding', 'details': str(e)}), 500

        faiss_idx = get_faiss_index()
        if faiss_idx is None:
            current_app.logger.error("Índice FAISS no disponible")
            return jsonify({'error': 'Índice FAISS no disponible'}), 500

        k = 5
        query_vector = np.array([embedding], dtype=np.float32)
        distances, indices = faiss_idx.search(query_vector, k)

        results = []
        for i in range(len(indices[0])):
            if indices[0][i] == -1:
                break
            document_id = int(indices[0][i])
            distance = distances[0][i].item()
            similitud = 1 / (1 + distance)
            porcentaje = similitud * 100

            document = Document.query.get(document_id)
            if document:
                profile = document.text_json if document.text_json else {}
                if not profile:
                    current_app.logger.warning(f"Documento {document_id} no tiene JSON estructurado guardado")
                else:
                    current_app.logger.info(f"Usando JSON estructurado existente para documento {document_id}")

                results.append({
                    'document_id': document.id,
                    'filename': document.filename,
                    'similarity_percentage': float(round(porcentaje, 2)),
                    'profile': profile
                })
            else:
                current_app.logger.warning(f"Documento con ID {document_id} no encontrado en la base de datos")

        # Guardar los resultados en archivo JSON
        resultados_folder = 'resultados'
        os.makedirs(resultados_folder, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'resultados_{timestamp}.json'
        filepath = os.path.join(resultados_folder, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'query': query,
                    'results': results
                }, f, indent=4, ensure_ascii=False)
            current_app.logger.info(f"Resultados guardados en {filepath}")
        except Exception as e:
            current_app.logger.error(f"Error al guardar resultados en {filepath}: {str(e)}")
            # Continuar para guardar en la base de datos aunque falle el guardado en archivo

        # Guardar en la base de datos usando el servicio
        search_result_service = SearchResultService()
        try:
            search_result = search_result_service.save_search_result(query, results, filename)
            current_app.logger.info(f"Resultado de búsqueda guardado en la base de datos con ID {search_result.id}")
        except Exception as e:
            current_app.logger.error(f"Error al guardar en la base de datos: {str(e)}")
            # No fallar la solicitud si falla el guardado en la base de datos
            # Puedes decidir si quieres devolver un error aquí

        return jsonify({
            'results': results,
            'search_result_id': search_result.id if 'search_result' in locals() else None
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error en búsqueda: {str(e)}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/history', methods=['GET'], strict_slashes=False)
def get_search_history():
    """
    Obtiene el historial completo de búsquedas ordenado por fecha (más reciente primero).
    """
    try:
        search_result_service = SearchResultService()
        history = search_result_service.get_all_search_results()
        
        # Convertir a diccionario para la respuesta JSON
        history_data = []
        for result in history:
            history_data.append({
                'id': result.id,
                'query': result.query,
                'result_json': result.result_json,
                'saved_file': result.saved_file,
                'created_at': result.created_at.isoformat() if result.created_at else None
            })
        
        current_app.logger.info(f"Historial obtenido: {len(history_data)} resultados")
        return jsonify(history_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener historial: {str(e)}")
        return jsonify({'error': 'Error al obtener el historial de búsquedas', 'details': str(e)}), 500


@bp.route('/history/<int:search_id>', methods=['GET'], strict_slashes=False)
def get_search_result_by_id(search_id):
    """
    Obtiene un resultado de búsqueda específico por su ID.
    """
    try:
        search_result_service = SearchResultService()
        result = search_result_service.get_search_result_by_id(search_id)
        
        if not result:
            current_app.logger.warning(f"Resultado de búsqueda con ID {search_id} no encontrado")
            return jsonify({'error': 'Resultado de búsqueda no encontrado'}), 404
        
        result_data = {
            'id': result.id,
            'query': result.query,
            'result_json': result.result_json,
            'saved_file': result.saved_file,
            'created_at': result.created_at.isoformat() if result.created_at else None
        }
        
        current_app.logger.info(f"Resultado de búsqueda {search_id} obtenido correctamente")
        return jsonify(result_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener resultado de búsqueda {search_id}: {str(e)}")
        return jsonify({'error': 'Error al obtener el resultado de búsqueda', 'details': str(e)}), 500


@bp.route('/history/<int:search_id>', methods=['DELETE'], strict_slashes=False)
def delete_search_result(search_id):
    """
    Elimina un resultado de búsqueda específico por su ID.
    """
    try:
        search_result_service = SearchResultService()
        result = search_result_service.get_search_result_by_id(search_id)
        
        if not result:
            current_app.logger.warning(f"Resultado de búsqueda con ID {search_id} no encontrado para eliminar")
            return jsonify({'error': 'Resultado de búsqueda no encontrado'}), 404
        
        # Eliminar archivo guardado si existe
        if result.saved_file:
            try:
                filepath = os.path.join('resultados', result.saved_file)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    current_app.logger.info(f"Archivo {filepath} eliminado correctamente")
            except Exception as e:
                current_app.logger.warning(f"No se pudo eliminar el archivo {result.saved_file}: {str(e)}")
        
        # Eliminar de la base de datos
        success = search_result_service.delete_search_result(search_id)
        
        if success:
            current_app.logger.info(f"Resultado de búsqueda {search_id} eliminado correctamente")
            return jsonify({'message': 'Resultado de búsqueda eliminado correctamente'}), 200
        else:
            return jsonify({'error': 'Error al eliminar el resultado de búsqueda'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar resultado de búsqueda {search_id}: {str(e)}")
        return jsonify({'error': 'Error al eliminar el resultado de búsqueda', 'details': str(e)}), 500
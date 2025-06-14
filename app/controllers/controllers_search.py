import os
import json
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.services.OpenAIService import OpenAIRewriteService
from app.services.search_result_service import SearchResultService
from app.extensions import get_faiss_index, db
from app.models.models_document import Document
from app.models.models_candidate import Candidate

# Crear el blueprint para las rutas de búsqueda
bp = Blueprint('search', __name__)


@bp.route('/', methods=['POST'], strict_slashes=False)
def search():
    """
    Realiza una búsqueda de similitudes en FAISS. Obtiene los datos del perfil
    exclusivamente desde el modelo 'Candidate'. Si un documento no tiene un
    candidato asociado, se omite de los resultados.
    """
    try:
        data = request.get_json() or {}
        query = data.get('query')
        if not query:
            current_app.logger.error("Falta el campo 'query' en la solicitud")
            return jsonify({'error': 'Se requiere un texto de consulta en el campo "query"'}), 400

        # Generar el embedding para el texto de la consulta
        openai_service = OpenAIRewriteService()
        try:
            embedding = openai_service.generate_embedding(query)
        except Exception as e:
            current_app.logger.error(f"Error al generar embedding: {str(e)}")
            return jsonify({'error': 'Error al generar embedding', 'details': str(e)}), 500

        # Obtener el índice FAISS
        faiss_idx = get_faiss_index()
        if faiss_idx is None:
            current_app.logger.error("Índice FAISS no disponible")
            return jsonify({'error': 'Índice FAISS no disponible'}), 500

        # Realizar la búsqueda en FAISS
        k = 10  # Número de resultados a obtener
        query_vector = np.array([embedding], dtype=np.float32)
        distances, indices = faiss_idx.search(query_vector, k)

        results = []
        for i in range(len(indices[0])):
            if indices[0][i] == -1:
                break
            document_id = int(indices[0][i])

            # Lógica principal: obtener datos solo del modelo Candidate
            # Se busca el candidato por el ID del documento encontrado en FAISS.
            candidate = Candidate.query.filter_by(document_id=document_id).first()

            # Si el candidato NO existe en la base de datos, se omite este resultado.
            if not candidate:
                current_app.logger.warning(f"Documento {document_id} encontrado en FAISS, pero no tiene perfil en 'candidates'. Se omite.")
                continue

            # Si el candidato existe, se procesa y se añade a los resultados.
            distance = distances[0][i].item()
            similitud = 1 / (1 + distance)
            porcentaje = similitud * 100
            
            # Se convierte el objeto Candidate a un diccionario para la respuesta JSON.
            profile = candidate.to_dict()

            results.append({
                'document_id': candidate.document_id,
                'filename': candidate.document.filename,  # Se accede al nombre del archivo a través de la relación
                'similarity_percentage': float(round(porcentaje, 2)),
                'profile': profile
            })

        # --- Guardado de Resultados ---

        # Guardar en archivo JSON
        resultados_folder = 'resultados'
        os.makedirs(resultados_folder, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'resultados_{timestamp}.json'
        filepath = os.path.join(resultados_folder, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({'query': query, 'results': results}, f, indent=4, ensure_ascii=False)
            current_app.logger.info(f"Resultados guardados en {filepath}")
        except Exception as e:
            current_app.logger.error(f"Error al guardar resultados en archivo {filepath}: {str(e)}")

        # Guardar en la base de datos a través del servicio
        search_result_service = SearchResultService()
        search_result = None
        try:
            search_result = search_result_service.save_search_result(query, results, filename)
            current_app.logger.info(f"Resultado de búsqueda guardado en BD con ID {search_result.id}")
        except Exception as e:
            current_app.logger.error(f"Error al guardar en la base de datos: {str(e)}")

        return jsonify({
            'results': results,
            'search_result_id': search_result.id if search_result else None
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fatal en la ruta de búsqueda: {str(e)}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/history', methods=['GET'], strict_slashes=False)
def get_search_history():
    """
    Obtiene el historial completo de búsquedas ordenado por fecha (más reciente primero).
    """
    try:
        search_result_service = SearchResultService()
        history = search_result_service.get_all_search_results()
        
        history_data = [res.to_dict() for res in history]
        
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
        
        current_app.logger.info(f"Resultado de búsqueda {search_id} obtenido correctamente")
        return jsonify(result.to_dict()), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener resultado de búsqueda {search_id}: {str(e)}")
        return jsonify({'error': 'Error al obtener el resultado de búsqueda', 'details': str(e)}), 500


@bp.route('/history/<int:search_id>', methods=['DELETE'], strict_slashes=False)
def delete_search_result(search_id):
    """
    Elimina un resultado de búsqueda específico por su ID, incluyendo el archivo asociado.
    """
    try:
        search_result_service = SearchResultService()
        result_to_delete = search_result_service.get_search_result_by_id(search_id)
        
        if not result_to_delete:
            current_app.logger.warning(f"Intento de eliminar resultado de búsqueda con ID {search_id} no encontrado")
            return jsonify({'error': 'Resultado de búsqueda no encontrado'}), 404
        
        # Eliminar archivo guardado si existe
        if result_to_delete.saved_file:
            try:
                filepath = os.path.join('resultados', result_to_delete.saved_file)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    current_app.logger.info(f"Archivo {filepath} eliminado correctamente")
            except Exception as e:
                current_app.logger.warning(f"No se pudo eliminar el archivo {result_to_delete.saved_file}: {str(e)}")
        
        # Eliminar de la base de datos
        success = search_result_service.delete_search_result(search_id)
        
        if success:
            current_app.logger.info(f"Resultado de búsqueda {search_id} eliminado correctamente de la BD")
            return jsonify({'message': 'Resultado de búsqueda eliminado correctamente'}), 200
        else:
            # Este caso es poco probable si la búsqueda inicial tuvo éxito, pero se maneja por seguridad.
            return jsonify({'error': 'Error al eliminar el resultado de búsqueda de la BD'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error al eliminar resultado de búsqueda {search_id}: {str(e)}")
        return jsonify({'error': 'Error al eliminar el resultado de búsqueda', 'details': str(e)}), 500
import os
import json
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.services.OpenAIService import OpenAIRewriteService
from app.extensions import get_faiss_index, db
from app.models.models_document import Document

bp = Blueprint('search', __name__)

@bp.route('/', methods=['POST'], strict_slashes=False)
def search():
    """
    Realiza una búsqueda de similitudes en FAISS basada en un texto de consulta.
    Convierte el texto a embedding, busca documentos similares, calcula porcentajes
    de similitud, guarda los resultados en la carpeta 'resultados' y devuelve los
    resultados con el perfil estructurado en JSON que ya existe en la base de datos.
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
            distance = distances[0][i].item()  # Convertir a float de Python
            similitud = 1 / (1 + distance)
            porcentaje = similitud * 100

            document = Document.query.get(document_id)
            if document:
                # Usar el JSON estructurado que ya existe en la base de datos
                profile = document.text_json if document.text_json else {}
                
                if not profile:
                    current_app.logger.warning(f"Documento {document_id} no tiene JSON estructurado guardado")
                else:
                    current_app.logger.info(f"Usando JSON estructurado existente para documento {document_id}")

                results.append({
                    'document_id': document.id,
                    'filename': document.filename,
                    'similarity_percentage': float(round(porcentaje, 2)),  # Asegurar float de Python
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

        return jsonify(results), 200

    except Exception as e:
        current_app.logger.error(f"Error en búsqueda: {str(e)}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500
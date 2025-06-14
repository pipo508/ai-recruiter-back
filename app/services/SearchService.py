# app/services/search_service.py

import os
import json
import numpy as np
from flask import current_app
from datetime import datetime

from app.services.OpenAIService import OpenAIRewriteService
from app.services.SearchHistoryService import SearchHistoryService # Importa el servicio renombrado
from app.Extensions import get_faiss_index
from app.models.Candidate import Candidate 

class SearchService:
    def __init__(self):
        self.openai_service = OpenAIRewriteService()
        self.history_service = SearchHistoryService()

    def perform_search(self, query: str, k: int = 10) -> dict:
        """
        Orquesta todo el proceso de búsqueda: embedding, FAISS, consulta a BD y guardado.
        """
        embedding = self.openai_service.generate_embedding(query)
        faiss_idx = get_faiss_index()
        if faiss_idx is None:
            raise Exception("Índice FAISS no disponible")

        query_vector = np.array([embedding], dtype=np.float32)
        distances, indices = faiss_idx.search(query_vector, k)

        results = self._process_faiss_results(distances, indices)
        filename = self._save_results_to_file(query, results)
        search_result_db = self.history_service.save_search_result(query, results, filename)

        return {
            'results': results,
            'search_result_id': search_result_db.id if search_result_db else None
        }

    def _process_faiss_results(self, distances, indices) -> list:
        """
        Procesa los resultados de FAISS y obtiene los perfiles de la base de datos.
        """
        processed_results = []
        for i in range(len(indices[0])):
            if indices[0][i] == -1: break
            
            document_id = int(indices[0][i])
            candidate = Candidate.query.filter_by(document_id=document_id).first()

            if not candidate:
                current_app.logger.warning(f"Doc {document_id} en FAISS sin perfil de candidato. Se omite.")
                continue

            distance = distances[0][i].item()
            similarity_percentage = round((1 / (1 + distance)) * 100, 2)
            
            processed_results.append({
                'document_id': candidate.document_id,
                'filename': candidate.document.filename,
                'similarity_percentage': similarity_percentage,
                'profile': candidate.to_dict()
            })
        return processed_results

    def _save_results_to_file(self, query: str, results: list) -> str:
        """
        Guarda los resultados de la búsqueda en un archivo JSON.
        """
        try:
            resultados_folder = 'resultados'
            os.makedirs(resultados_folder, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f'resultados_{timestamp}.json'
            filepath = os.path.join(resultados_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({'query': query, 'results': results}, f, indent=4, ensure_ascii=False)
            
            current_app.logger.info(f"Resultados guardados en {filepath}")
            return filename
        except Exception as e:
            current_app.logger.error(f"Error al guardar resultados en archivo: {e}")
            return None
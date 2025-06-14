# app/services/search_history_service.py

import os
from app.repositories.SearchResultRepository import SearchResultRepository
from app.models.Result import SearchResult
from flask import current_app

class SearchHistoryService:
    def __init__(self):
        self.repository = SearchResultRepository()

    def save_search_result(self, query: str, results: dict, filename: str = None) -> SearchResult:
        if not query: raise ValueError("El texto de búsqueda no puede estar vacío")
        
        search_result = SearchResult(query=query, result_json=results, saved_file=filename)
        return self.repository.create(search_result)

    def get_all_search_results(self):
        """
        Obtiene el historial de búsquedas usando el método correcto del repositorio.
        """
        return self.repository.find_all_ordered_by_date()

    def get_search_result_by_id(self, search_id: int):
        """
        Obtiene un resultado de búsqueda por su ID.
        """
        result = self.repository.find_by_id(search_id)
        if not result:
            raise ValueError("Resultado de búsqueda no encontrado")
        return result

    def delete_search_result_and_file(self, search_id: int) -> bool:
        """
        Orquesta la eliminación del registro en la BD y del archivo asociado.
        """
        # 1. Obtener el registro para saber qué archivo borrar
        result_to_delete = self.repository.find_by_id(search_id)
        if not result_to_delete:
            raise ValueError("Resultado de búsqueda no encontrado para eliminar")

        # 2. Eliminar el archivo del sistema de archivos
        if result_to_delete.saved_file:
            try:
                filepath = os.path.join('resultados', result_to_delete.saved_file)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    current_app.logger.info(f"Archivo {filepath} eliminado")
            except Exception as e:
                # Se registra el error pero se continúa para borrar el registro de BD
                current_app.logger.warning(f"No se pudo eliminar el archivo {result_to_delete.saved_file}: {e}")
        
        # 3. Eliminar el registro de la base de datos
        return self.repository.delete_by_id(search_id)

    def search_in_history(self, query: str):
        """
        Busca en el historial de búsquedas.
        """
        return self.repository.find_by_query_like(query)
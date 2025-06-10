"""
Servicio para la gestión de lógica de negocio relacionada con resultados de búsqueda.
Coordina operaciones entre el controlador y el repositorio de resultados de búsqueda.
"""

# 1. Se añaden las importaciones necesarias
from app.extensions import db
from app.models.models_result import SearchResult
from app.repositories.search_result_repository import SearchResultRepository
from flask import current_app

class SearchResultService:
    def __init__(self):
        self.repository = SearchResultRepository()

    def save_search_result(self, query: str, results: dict, filename: str = None) -> SearchResult:
        if not query:
            raise ValueError("El texto de búsqueda no puede estar vacío")
        if not results:
            raise ValueError("Los resultados no pueden estar vacíos")

        try:
            search_result = SearchResult(
                query=query,
                result_json=results,
                saved_file=filename
            )
            return self.repository.create(search_result)
        except Exception as e:
            current_app.logger.error(f"Error al guardar resultado de búsqueda: {str(e)}")
            raise Exception(f"Error al guardar el resultado de búsqueda: {str(e)}")

    # 2. Se CORRIGE este método para usar la consulta de ordenamiento correcta y se elimina el duplicado.
    def get_all_search_results(self):
        """
        Obtiene todos los resultados de búsqueda ordenados por fecha de creación (más reciente primero).
        """
        try:
            # Esta es la forma correcta y moderna de hacer la consulta ordenada
            query = db.select(SearchResult).order_by(SearchResult.created_at.desc())
            results = db.session.execute(query).scalars().all()
            return results
        except Exception as e:
            current_app.logger.error(f"Error al obtener resultados ordenados por fecha: {str(e)}")
            raise Exception(f"Error al obtener todos los resultados de búsqueda: {str(e)}")

    # 3. Se CONSOLIDA el método para buscar por ID y se elimina el duplicado.
    def get_search_result_by_id(self, search_id: int):
        """
        Obtiene un resultado de búsqueda específico por su ID.
        """
        try:
            # Reutilizamos el método get_search_result que ya tenías definido,
            # ya que hace lo mismo que el duplicado.
            return self.get_search_result(search_id)
        except Exception as e:
            raise Exception(f"Error al obtener el resultado de búsqueda {search_id}: {str(e)}")

    def delete_search_result(self, search_id: int):
        """
        Elimina un resultado de búsqueda específico por su ID.
        """
        try:
            return self.repository.delete_by_id(search_id)
        except Exception as e:
            raise Exception(f"Error al eliminar el resultado de búsqueda {search_id}: {str(e)}")

    def search_in_history(self, query: str):
        """
        Busca en el historial de búsquedas por términos en la consulta.
        """
        try:
            return self.repository.find_by_query_like(query)
        except Exception as e:
            raise Exception(f"Error al buscar en el historial: {str(e)}")

    # NOTA: El método original get_search_result(self, result_id) se ha mantenido
    # y es utilizado por get_search_result_by_id.
    def get_search_result(self, result_id: int) -> SearchResult:
        result = self.repository.find_by_id(result_id)
        if not result:
            raise ValueError("Resultado de búsqueda no encontrado")
        return result
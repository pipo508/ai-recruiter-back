# app/services/SearchHistoryService.py

import os
import logging
from app.repositories.SearchResultRepository import SearchResultRepository
from app.models.Result import SearchResult
from flask import current_app

# Es una buena práctica obtener un logger específico para el módulo
logger = logging.getLogger(__name__)

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
        Esta versión incluye un manejo de rutas más robusto y un registro de errores mejorado.
        """
        # 1. Obtener el registro para saber qué archivo borrar
        result_to_delete = self.repository.find_by_id(search_id)
        if not result_to_delete:
            raise ValueError("Resultado de búsqueda no encontrado para eliminar")

        # 2. Eliminar el archivo del sistema de archivos, si existe
        if result_to_delete.saved_file:
            # Construcción de la ruta de forma robusta usando la configuración de la app.
            # Debes asegurarte de definir 'RESULTADOS_FOLDER' en tu configuración de Flask.
            # Por ejemplo: app.config['RESULTADOS_FOLDER'] = os.path.join(app.instance_path, 'resultados')
            results_folder = current_app.config.get('RESULTADOS_FOLDER', 'resultados')
            filepath = os.path.join(results_folder, result_to_delete.saved_file)
            
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Archivo {filepath} eliminado correctamente.")
                else:
                    logger.warning(f"El archivo asociado '{result_to_delete.saved_file}' no fue encontrado en '{filepath}' y no se eliminó.")
            except (IOError, OSError) as e:
                # Es mejor práctica capturar excepciones específicas del sistema de archivos
                # en lugar de una 'Exception' genérica.
                # Se registra el error pero se continúa para borrar el registro de BD.
                logger.error(f"Error al intentar eliminar el archivo {filepath}: {e}", exc_info=True)
        
        # 3. Eliminar el registro de la base de datos
        # SI ESTA LÍNEA FALLA, es muy probable que se deba a una restricción
        # de clave foránea (foreign key) en la base de datos.
        # La excepción resultante será capturada por el controlador, que devolverá el error 500.
        return self.repository.delete_by_id(search_id)

    def search_in_history(self, query: str):
        """
        Busca en el historial de búsquedas.
        """
        return self.repository.find_by_query_like(query)
"""
Repositorio para la gestión de datos de resultados de búsqueda.
Encapsula las operaciones de base de datos relacionadas con el modelo SearchResult.
"""

from app.Extensions import db
from app.models.Result import SearchResult
from app.repositories.RepositoryBase import Create, Read
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc
import traceback

class SearchResultRepository(Create, Read):
    def create(self, entity: SearchResult):
        try:
            db.session.add(entity)
            db.session.commit()
            return entity
        except IntegrityError as e:
            db.session.rollback()
            raise Exception("Error de integridad al crear el resultado de búsqueda")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al crear el resultado de búsqueda: {str(e)}")

    def find_by_id(self, id: int):
        return SearchResult.query.get(id)

    def find_all(self):
        return SearchResult.query.all()
    
    def find_all_ordered_by_date(self):
        """
        Obtiene todos los resultados de búsqueda ordenados por fecha de creación (más reciente primero).
        """
        try:
            # Método alternativo usando db.session.query() para evitar conflictos
            return db.session.query(SearchResult).order_by(desc(SearchResult.created_at)).all()
        except Exception as e:
            # Agregamos información más detallada del error
            error_details = f"Error al obtener resultados ordenados por fecha: {str(e)}"
            print(f"[DEBUG] {error_details}")
            print(f"[DEBUG] Traceback completo:")
            traceback.print_exc()
            
            # Intentemos obtener información sobre los campos del modelo
            try:
                print(f"[DEBUG] Campos disponibles en SearchResult:")
                for attr in dir(SearchResult):
                    if not attr.startswith('_'):
                        print(f"[DEBUG]   - {attr}")
            except Exception as debug_e:
                print(f"[DEBUG] Error al inspeccionar modelo: {debug_e}")
            
            raise Exception(error_details)

    def delete_by_id(self, search_id: int):
        """
        Elimina un resultado de búsqueda por su ID.
        """
        try:
            result = SearchResult.query.get(search_id)
            if result:
                db.session.delete(result)
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al eliminar resultado de búsqueda {search_id}: {str(e)}")

    def find_by_query_like(self, query_text: str):
        """
        Busca resultados de búsqueda que contengan el término especificado en la consulta.
        """
        try:
            # Usamos db.session.query() para evitar conflictos con el campo 'query'
            return db.session.query(SearchResult).filter(
                SearchResult.query.ilike(f'%{query_text}%')
            ).order_by(desc(SearchResult.created_at)).all()
        except Exception as e:
            print(f"[DEBUG] Error en find_by_query_like: {str(e)}")
            traceback.print_exc()
            raise Exception(f"Error al buscar por consulta similar: {str(e)}")

    def find_recent(self, limit: int = 10):
        """
        Obtiene los resultados de búsqueda más recientes limitados por el número especificado.
        """
        try:
            return db.session.query(SearchResult).order_by(
                desc(SearchResult.created_at)
            ).limit(limit).all()
        except Exception as e:
            print(f"[DEBUG] Error en find_recent: {str(e)}")
            traceback.print_exc()
            raise Exception(f"Error al obtener resultados recientes: {str(e)}")

    def count_all(self):
        """
        Cuenta el total de resultados de búsqueda.
        """
        try:
            return db.session.query(SearchResult).count()
        except Exception as e:
            print(f"[DEBUG] Error en count_all: {str(e)}")
            traceback.print_exc()
            raise Exception(f"Error al contar resultados: {str(e)}")
"""
Repositorio para la gestión de datos de resultados de búsqueda.
Encapsula las operaciones de base de datos relacionadas con el modelo SearchResult.
"""

from app.Extensions import db
from app.models.Result import SearchResult
from app.repositories.RepositoryBase import Create, Read
from sqlalchemy.exc import IntegrityError

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
    
    # Agregar estos métodos a tu clase SearchResultRepository existente

    def find_all_ordered_by_date(self):
        """
        Obtiene todos los resultados de búsqueda ordenados por fecha de creación (más reciente primero).
        """
        try:
            return SearchResult.query.order_by(SearchResult.created_at.desc()).all()
        except Exception as e:
            raise Exception(f"Error al obtener resultados ordenados por fecha: {str(e)}")

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

    def find_by_query_like(self, query: str):
        """
        Busca resultados de búsqueda que contengan el término especificado en la consulta.
        """
        try:
            return SearchResult.query.filter(
                SearchResult.query.ilike(f'%{query}%')
            ).order_by(SearchResult.created_at.desc()).all()
        except Exception as e:
            raise Exception(f"Error al buscar por consulta similar: {str(e)}")

    def find_recent(self, limit: int = 10):
        """
        Obtiene los resultados de búsqueda más recientes limitados por el número especificado.
        """
        try:
            return SearchResult.query.order_by(
                SearchResult.created_at.desc()
            ).limit(limit).all()
        except Exception as e:
            raise Exception(f"Error al obtener resultados recientes: {str(e)}")

    def count_all(self):
        """
        Cuenta el total de resultados de búsqueda.
        """
        try:
            return SearchResult.query.count()
        except Exception as e:
            raise Exception(f"Error al contar resultados: {str(e)}")
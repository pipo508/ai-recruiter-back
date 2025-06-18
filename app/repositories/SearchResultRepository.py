"""
Repositorio para la gestión de datos de resultados de búsqueda.
Encapsula las operaciones de base de datos relacionadas con el modelo SearchResult.
Versión actualizada a la sintaxis moderna de SQLAlchemy 2.0.
"""

from app.Extensions import db
from app.models.Result import SearchResult
from app.repositories.RepositoryBase import Create, Read
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
import traceback

class SearchResultRepository(Create, Read):
    def create(self, entity: SearchResult):
        """
        Crea un nuevo registro de resultado de búsqueda en la base de datos.
        """
        try:
            db.session.add(entity)
            db.session.commit()
            return entity
        except IntegrityError:
            db.session.rollback()
            # Es mejor no exponer detalles internos, se puede loggear el error si es necesario.
            raise Exception("Error de integridad al crear el resultado de búsqueda")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al crear el resultado de búsqueda: {str(e)}")

    def find_by_id(self, id: int):
        """
        Busca un resultado por su ID usando el método moderno y optimizado.
        """
        # Sintaxis moderna para buscar por clave primaria. Es el reemplazo directo de .query.get().
        return db.session.get(SearchResult, id)

    def find_all(self):
        """
        Obtiene todos los resultados de búsqueda.
        """
        # Sintaxis moderna para un SELECT * FROM ...
        statement = db.select(SearchResult)
        return db.session.execute(statement).scalars().all()
    
    def find_all_ordered_by_date(self):
        """
        Obtiene todos los resultados ordenados por fecha (más reciente primero).
        """
        statement = db.select(SearchResult).order_by(desc(SearchResult.created_at))
        return db.session.execute(statement).scalars().all()

    def delete_by_id(self, search_id: int):
        """
        Elimina un resultado de búsqueda por su ID.
        """
        try:
            # Primero, encontramos el objeto usando el método ya corregido.
            result_to_delete = self.find_by_id(search_id)
            if result_to_delete:
                db.session.delete(result_to_delete)
                db.session.commit()
                return True
            # Si no se encuentra, no es un error, simplemente no se borró nada.
            return False
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al eliminar resultado de búsqueda {search_id}: {str(e)}")

    def find_by_query_like(self, query_text: str):
        """
        Busca resultados que contengan el término especificado en la consulta.
        """
        # La ambigüedad con el campo 'query' se resuelve usando el objeto del modelo.
        search_pattern = f'%{query_text}%'
        statement = db.select(SearchResult).where(
            SearchResult.query.ilike(search_pattern)
        ).order_by(desc(SearchResult.created_at))
        return db.session.execute(statement).scalars().all()

    def find_recent(self, limit: int = 10):
        """
        Obtiene los resultados de búsqueda más recientes.
        """
        statement = db.select(SearchResult).order_by(
            desc(SearchResult.created_at)
        ).limit(limit)
        return db.session.execute(statement).scalars().all()

    def count_all(self):
        """
        Cuenta el total de resultados de búsqueda.
        """
        # La forma moderna de contar es usando la función func.count() de SQLAlchemy.
        statement = db.select(func.count()).select_from(SearchResult)
        return db.session.execute(statement).scalar_one()
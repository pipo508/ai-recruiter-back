from datetime import datetime
from app.extensions import db

class SearchResult(db.Model):
    """
    Modelo que representa un resultado de búsqueda realizado por un usuario.

    Atributos:
        id: ID único del resultado
        query: Texto de búsqueda utilizado
        result_json: Lista de resultados en formato JSON (document_id, filename, similarity_percentage, profile)
        saved_file: Nombre del archivo JSON donde se guardaron los resultados
        created_at: Fecha y hora de creación
    """
    __tablename__ = 'search_results'

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.Text, nullable=False)
    result_json = db.Column(db.JSON, nullable=False)
    saved_file = db.Column(db.String(255), nullable=True)  # ejemplo: resultados_2025-06-09_12-30-00.json
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SearchResult id={self.id} query="{self.query[:30]}...">'

    def to_dict(self):
        return {
            'id': self.id,
            'query': self.query,
            'result_json': self.result_json,
            'saved_file': self.saved_file,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

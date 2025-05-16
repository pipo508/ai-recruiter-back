"""
Módulo que define los modelos Query y Candidate para gestionar consultas
de usuarios y los resultados de búsqueda vectorial.
"""

from main import db
from datetime import datetime

class Query(db.Model):
    """
    Modelo que representa una consulta realizada por un usuario.
    
    Atributos:
        id: Identificador único de la consulta
        user_id: ID del usuario que realizó la consulta
        original_query: Texto original de la consulta ingresada por el usuario
        rewritten_query: Consulta reescrita/optimizada por OpenAI
        created_at: Fecha y hora de la consulta
    """
    __tablename__ = 'queries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_query = db.Column(db.Text, nullable=False)
    rewritten_query = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', back_populates='queries')
    candidates = db.relationship('Candidate', back_populates='query', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        """Representación en string del objeto Query"""
        return f'<Query {self.id}: {self.original_query[:30]}...>'


class Candidate(db.Model):
    """
    Modelo que representa un documento candidato encontrado como resultado de una consulta.
    
    Atributos:
        id: Identificador único del candidato
        query_id: ID de la consulta que generó este candidato
        text_block_id: ID del bloque de texto encontrado
        document_id: ID del documento al que pertenece el bloque de texto
        similarity_score: Puntuación de similitud vectorial
        rank: Posición en el ranking de resultados
        created_at: Fecha y hora de creación del candidato
    """
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(db.Integer, db.ForeignKey('queries.id'), nullable=False)
    text_block_id = db.Column(db.Integer, db.ForeignKey('text_blocks.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    query = db.relationship('Query', back_populates='candidates')
    text_block = db.relationship('TextBlock')
    document = db.relationship('Document')
    
    def __repr__(self):
        """Representación en string del objeto Candidate"""
        return f'<Candidate {self.id} for Query {self.query_id}, Rank: {self.rank}>'

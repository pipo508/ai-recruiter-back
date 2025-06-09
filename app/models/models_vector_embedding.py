"""
Módulo que define el modelo VectorEmbedding para vincular embeddings en FAISS
con documentos en la base de datos.
"""

from datetime import datetime
from app.extensions import db

class VectorEmbedding(db.Model):
    """
    Modelo que representa un embedding vectorial generado para un documento.
    
    Atributos:
        id: Identificador único del embedding
        document_id: ID del documento asociado
        faiss_index_id: ID del vector en el índice FAISS
        embedding_model: Modelo usado para generar el embedding
        created_at: Fecha y hora de creación
        updated_at: Fecha y hora de última actualización
    """
    __tablename__ = 'vector_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    faiss_index_id = db.Column(db.BigInteger, nullable=False)  # ID del vector en FAISS
    embedding_model = db.Column(db.String(100), default='text-embedding-3-small')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    document = db.relationship('Document', back_populates='vector_embeddings')

    def __repr__(self):
        return f'<VectorEmbedding document_id={self.document_id} faiss_index_id={self.faiss_index_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'faiss_index_id': self.faiss_index_id,
            'embedding_model': self.embedding_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
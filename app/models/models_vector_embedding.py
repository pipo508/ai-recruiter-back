"""
Módulo que define el modelo VectorEmbedding para almacenar vectores de embeddings
generados a partir de bloques de texto.
"""

from main import db
from datetime import datetime
import numpy as np
import pickle

class VectorEmbedding(db.Model):
    """
    Modelo que representa un vector de embedding generado para un bloque de texto.
    
    Atributos:
        id: Identificador único del vector
        document_id: ID del documento asociado
        text_block_id: ID del bloque de texto del que se generó este vector
        embedding_model: Nombre del modelo de OpenAI usado para generar el embedding
        embedding_binary: Vector de embedding serializado
        embedding_size: Tamaño del vector de embedding
        faiss_index_id: Identificador en el índice FAISS
        created_at: Fecha y hora de creación del vector
    """
    __tablename__ = 'vector_embeddings'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    text_block_id = db.Column(db.Integer, db.ForeignKey('text_blocks.id'), nullable=False, unique=True)
    embedding_model = db.Column(db.String(100), nullable=False)  # e.g., 'text-embedding-ada-002'
    embedding_binary = db.Column(db.LargeBinary, nullable=False)  # Serialized numpy array
    embedding_size = db.Column(db.Integer, nullable=False)
    faiss_index_id = db.Column(db.Integer, nullable=True)  # ID dentro del índice FAISS
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    document = db.relationship('Document', back_populates='vector_embeddings')
    text_block = db.relationship('TextBlock', back_populates='vector_embedding')
    
    def __repr__(self):
        """Representación en string del objeto VectorEmbedding"""
        return f'<VectorEmbedding {self.id} for TextBlock {self.text_block_id}>'
    
    @property
    def embedding(self):
        """
        Deserializa y devuelve el vector de embedding como array de numpy.
        
        Returns:
            numpy.ndarray: Vector de embedding deserializado
        """
        return pickle.loads(self.embedding_binary)
    
    @embedding.setter
    def embedding(self, vector):
        """
        Serializa y guarda un vector de embedding.
        
        Args:
            vector (numpy.ndarray): Vector de embedding a serializar y guardar
        """
        self.embedding_binary = pickle.dumps(vector)
        self.embedding_size = len(vector)

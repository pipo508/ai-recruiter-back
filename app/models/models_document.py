"""
Módulo que define el modelo Document para representar documentos PDF subidos 
y procesados en el sistema.
"""

from datetime import datetime
from app.extensions import db

class Document(db.Model):
    """
    Modelo que representa un documento PDF subido por un usuario.
    
    Atributos:
        id: Identificador único del documento
        user_id: ID del usuario que subió el documento
        filename: Nombre original del archivo
        firebase_path: Ruta de almacenamiento en Firebase
        status: Estado del procesamiento del documento
        char_count: Número de caracteres extraídos del texto
        needs_ocr: Indicador de si el documento necesita OCR
        ocr_processed: Indicador de si el OCR ya fue realizado
        created_at: Fecha y hora de subida del documento
        updated_at: Fecha y hora de última actualización
    """
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    firebase_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, processed, error
    char_count = db.Column(db.Integer, default=0)
    needs_ocr = db.Column(db.Boolean, default=False)
    ocr_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', back_populates='documents')
    # Comentadas hasta que los modelos TextBlock y VectorEmbedding estén implementados
    # text_blocks = db.relationship('TextBlock', back_populates='document', lazy='dynamic', cascade='all, delete-orphan')
    # vector_embeddings = db.relationship('VectorEmbedding', back_populates='document', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        """Representación en string del objeto Document"""
        return f'<Document {self.filename}>'
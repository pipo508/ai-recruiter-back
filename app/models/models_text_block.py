"""
Módulo que define el modelo TextBlock para almacenar bloques de texto extraídos
de documentos, ya sea por extracción directa o después del procesamiento OCR.
"""

from main import db
from datetime import datetime

class TextBlock(db.Model):
    """
    Modelo que representa un bloque de texto extraído de un documento.
    
    Atributos:
        id: Identificador único del bloque de texto
        document_id: ID del documento al que pertenece este bloque
        content: Contenido textual del bloque
        page_number: Número de página del documento original
        section_title: Título de la sección a la que pertenece (opcional)
        sequence_number: Número de secuencia dentro del documento
        source_type: Origen del texto (extracción directa u OCR)
        created_at: Fecha y hora de creación del bloque
    """
    __tablename__ = 'text_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    section_title = db.Column(db.String(255), nullable=True)
    sequence_number = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(50), default='extraction')  # extraction, ocr
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    document = db.relationship('Document', back_populates='text_blocks')
    vector_embedding = db.relationship('VectorEmbedding', uselist=False, back_populates='text_block', cascade='all, delete-orphan')
    
    def __repr__(self):
        """Representación en string del objeto TextBlock"""
        return f'<TextBlock {self.id} from Document {self.document_id}>'

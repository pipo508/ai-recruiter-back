"""
Módulo que define el modelo Document para representar documentos PDF subidos 
y procesados en el sistema.
"""

from datetime import datetime
from app.Extensions import db

class Document(db.Model):
    """
    Modelo que representa un documento PDF subido por un usuario.
    
    Atributos:
        id: Identificador único del documento.
        user_id: ID del usuario que subió el documento.
        filename: Nombre original del archivo.
        storage_path: Ruta o identificador del archivo en el servicio de almacenamiento.
        file_url: URL de acceso al documento almacenado.
        rewritten_text: Texto extraído y potencialmente reescrito del documento.
        status: Estado del procesamiento del documento (e.g., uploaded, processing, processed, error).
        char_count: Número de caracteres extraídos del texto.
        needs_ocr: Indicador de si el documento necesita OCR.
        ocr_processed: Indicador de si el OCR ya fue realizado.
        created_at: Fecha y hora de subida del documento.
        updated_at: Fecha y hora de última actualización.
    """
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=True)
    rewritten_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='uploaded')
    char_count = db.Column(db.Integer, default=0)
    needs_ocr = db.Column(db.Boolean, default=False)
    ocr_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # --- Relaciones ---

    # Relación uno a uno con el modelo Candidate.
    # Si se elimina un Documento, el Candidato asociado también se eliminará en cascada.
    candidate = db.relationship('Candidate', back_populates='document', uselist=False, cascade='all, delete-orphan')

    # Relación con el usuario que subió el documento.
    user = db.relationship('User', back_populates='documents')
    
    # Relación con los embeddings vectoriales asociados.
    vector_embeddings = db.relationship('VectorEmbedding', back_populates='document', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        """Representación en string del objeto Document."""
        return f'<Document {self.filename}>'
    
    def to_dict(self):
        """
        Convierte el documento y su perfil de candidato asociado (si existe) 
        a un diccionario para respuestas JSON.
        """
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'storage_path': self.storage_path,
            'file_url': self.file_url,
            'rewritten_text': self.rewritten_text,
            'status': self.status,
            'char_count': self.char_count,
            'needs_ocr': self.needs_ocr,
            'ocr_processed': self.ocr_processed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        # Incluir el perfil del candidato si la relación existe.
        if self.candidate:
            data['profile'] = self.candidate.to_dict()
        else:
            data['profile'] = None
        
        return data
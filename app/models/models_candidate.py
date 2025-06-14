# app/models/models_candidate.py

from app.extensions import db
from datetime import datetime

class Candidate(db.Model):
    __tablename__ = 'candidates'

    id = db.Column(db.Integer, primary_key=True)
    # Relación uno a uno con el documento original
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), unique=True, nullable=False)

    # --- CAMPOS PRINCIPALES (Columnas estándar) ---
    nombre_completo = db.Column(db.String(255), nullable=False, index=True)
    puesto_actual = db.Column(db.String(255), index=True)
    habilidad_principal = db.Column(db.String(255), index=True)
    anios_experiencia = db.Column(db.Integer, default=0)
    cantidad_proyectos = db.Column(db.Integer, default=0)
    descripcion_profesional = db.Column(db.Text)
    github = db.Column(db.String(512))
    email = db.Column(db.String(120), index=True)
    telefono = db.Column(db.String(50))
    ubicacion = db.Column(db.String(255), index=True)
    candidato_ideal = db.Column(db.Text)

    # --- CAMPOS DE LISTA (Columnas de tipo JSON) ---
    # Almacenamos la lista de strings directamente como un JSON array
    habilidades_clave = db.Column(db.JSON)  # Ejemplo: ["Python", "Flask", "Docker"]

    # Almacenamos la lista de diccionarios de experiencia como un JSON array
    experiencia_profesional = db.Column(db.JSON)

    # Almacenamos la lista de diccionarios de educación como un JSON array
    educacion = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Relación Inversa ---
    document = db.relationship('Document', back_populates='candidate')

    def to_dict(self):
        """Convierte el objeto Candidate en un diccionario JSON completo."""
        return {
            "Nombre completo": self.nombre_completo,
            "Puesto actual": self.puesto_actual,
            "Habilidad principal": self.habilidad_principal,
            "Años de experiencia total": self.anios_experiencia,
            "Cantidad de proyectos/trabajos": self.cantidad_proyectos,
            "Descripción profesional": self.descripcion_profesional,
            "GitHub": self.github,
            "Email": self.email,
            "Número de teléfono": self.telefono,
            "Ubicación": self.ubicacion,
            "Habilidades clave": self.habilidades_clave or [],
            "Candidato ideal": self.candidato_ideal,
            "Experiencia Profesional": self.experiencia_profesional or [],
            "Educación": self.educacion or []
        }
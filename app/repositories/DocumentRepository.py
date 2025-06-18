# app/repositories/document_repository.py

from app.Extensions import db
from app.models.Candidate import Candidate
from app.models.VectorEmbedding import VectorEmbedding
from app.models.Document import Document
from app.repositories.RepositoryBase import Create, Read, Update, Delete
from sqlalchemy.exc import IntegrityError
from flask import current_app
import traceback
import datetime
from sqlalchemy.orm import joinedload

class DocumentRepository(Create, Read, Update, Delete):

    def create(self, entity: Document) -> Document:
        """
        Añade una nueva entidad Document a la base de datos.
        """
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando INSERT para nuevo documento. Archivo: '{entity.filename}'.")
        try:
            db.session.add(entity)
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Documento '{entity.filename}' insertado con ID: {entity.id}.")
            return entity
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la operación INSERT para el documento '{entity.filename}'. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            raise

    def update(self, entity: Document, id: int, data: dict) -> Document:
        """
        Actualiza un documento existente con los datos proporcionados.
        """
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando UPDATE para el documento ID {id}. Campos a actualizar: {list(data.keys())}.")
        try:
            for key, value in data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            entity.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Documento ID {id} actualizado correctamente.")
            return entity
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la operación UPDATE para el documento ID {id}. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            raise

    def delete(self, entity: Document):
        """
        Elimina un documento de la base de datos.
        """
        doc_id = entity.id
        doc_filename = entity.filename
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando DELETE para el documento ID {doc_id} (Archivo: '{doc_filename}').")
        try:
            db.session.delete(entity)
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Documento ID {doc_id} ('{doc_filename}') eliminado de la base de datos.")
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la operación DELETE para el documento ID {doc_id}. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            raise

    def find_by_id(self, id: int) -> Document | None:
        """Busca un documento por su ID."""
        return Document.query.get(id)

    def find_by_id_with_candidate(self, document_id: int) -> Document | None:
        """
        Busca un documento por su ID, cargando la relación con el candidato.
        """
        return Document.query.options(joinedload(Document.candidate)).get(document_id)

    def find_all(self) -> list[Document]:
        """Retorna todos los documentos."""
        return Document.query.all()

    def find_by_filename_and_user(self, filename: str, user_id: int) -> Document | None:
        """
        Busca un documento por nombre de archivo y usuario, aplicando normalización.
        """
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        normalized_base = base_name.replace('_', '').replace(' ', '').lower()

        documents = Document.query.filter_by(user_id=user_id).all()
        for doc in documents:
            doc_base = doc.filename.rsplit('.', 1)[0] if '.' in doc.filename else doc.filename
            if doc_base.replace('_', '').replace(' ', '').lower() == normalized_base:
                return doc
        return None

    def find_by_storage_path(self, path: str) -> Document | None:
        """Busca un documento por su ruta de almacenamiento."""
        return Document.query.filter_by(storage_path=path).first()

    def create_candidate(self, profile_data: dict, document_id: int) -> Candidate | None:
        """
        Crea y guarda una nueva entidad Candidate asociada a un Document.
        """
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando INSERT para nuevo candidato. Asociado al Documento ID: {document_id}.")
        try:
            new_candidate = Candidate(
                document_id=document_id,
                nombre_completo=profile_data.get("Nombre completo"),
                puesto_actual=profile_data.get("Puesto actual"),
                habilidad_principal=profile_data.get("Habilidad principal"),
                anios_experiencia=profile_data.get("Años de experiencia total"),
                cantidad_proyectos=profile_data.get("Cantidad de proyectos/trabajos"),
                descripcion_profesional=profile_data.get("Descripción profesional"),
                github=profile_data.get("GitHub"),
                email=profile_data.get("Email"),
                telefono=profile_data.get("Número de teléfono"),
                ubicacion=profile_data.get("Ubicación"),
                candidato_ideal=profile_data.get("Candidato ideal"),
                habilidades_clave=profile_data.get("Habilidades clave", []),
                experiencia_profesional=profile_data.get("Experiencia Profesional", []),
                educacion=profile_data.get("Educación", [])
            )
            db.session.add(new_candidate)
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Candidato '{new_candidate.nombre_completo}' insertado con ID: {new_candidate.id}.")
            return new_candidate
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la operación INSERT para el candidato del documento ID {document_id}. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            return None

    def save_candidate_and_document_update(self, candidate: Candidate, document: Document) -> Candidate:
        """
        Guarda los cambios en un candidato y actualiza el documento en una transacción.
        """
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando UPDATE para el candidato ID {candidate.id} y el documento ID {document.id} en una transacción.")
        try:
            candidate.updated_at = datetime.datetime.utcnow()
            document.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Candidato ID {candidate.id} y Documento ID {document.id} actualizados atómicamente.")
            return candidate
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la transacción de actualización para el candidato ID {candidate.id} y el documento ID {document.id}. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            raise

    def save_vector_embedding(self, vector_embedding: VectorEmbedding):
        """
        Guarda un registro de VectorEmbedding en la base de datos.
        """
        doc_id = vector_embedding.document_id
        current_app.logger.debug(f"[DEBUG] DB: Ejecutando INSERT para el registro de VectorEmbedding. Documento ID: {doc_id}.")
        try:
            db.session.add(vector_embedding)
            db.session.commit()
            current_app.logger.debug(f"[DEBUG] DB: Registro de VectorEmbedding para el documento ID {doc_id} guardado.")
        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] DB: Falló la operación INSERT para el registro de VectorEmbedding del documento ID {doc_id}. Se ejecutó un rollback.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
    

    def find_all_by_user_id(self, user_id: int):
        """Encuentra todos los documentos de un usuario específico."""
        return Document.query.filter_by(user_id=user_id).all()

    def delete_all_by_user_id(self, user_id: int):
        """Elimina todos los documentos de un usuario específico."""
        try:
            documents = Document.query.filter_by(user_id=user_id).all()
            deleted_count = len(documents)
            
            for doc in documents:
                db.session.delete(doc)
            
            db.session.commit()
            return deleted_count
        except Exception as e:
            db.session.rollback()
            raise e
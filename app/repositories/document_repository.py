from app.extensions import db
from app.models import Document
from app.repositories.repository_base import Create, Read, Update, Delete
from sqlalchemy.exc import IntegrityError
from flask import current_app
import traceback
from sqlalchemy.sql import func
import datetime

class DocumentRepository(Create, Read, Update, Delete):
    def create(self, entity: Document):
        current_app.logger.info(f"Creando documento: {entity.filename} para user_id: {entity.user_id}")
        try:
            db.session.add(entity)
            db.session.commit()
            current_app.logger.info(f"Documento creado con ID: {entity.id}")
            return entity
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception("Error al crear el documento: posible violación de restricciones")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception(f"Error al crear el documento: {str(e)}")

    def update(self, entity: Document, id: int):
        current_app.logger.info(f"Actualizando documento con ID: {id}")
        existing_document = Document.query.get(id)
        if not existing_document:
            current_app.logger.error(f"Documento no encontrado: {id}")
            raise ValueError("Documento no encontrado")
        try:
            if entity.status is not None:
                existing_document.status = entity.status
            if entity.char_count is not None:
                existing_document.char_count = entity.char_count
            if entity.needs_ocr is not None:
                existing_document.needs_ocr = entity.needs_ocr
            if entity.ocr_processed is not None:
                existing_document.ocr_processed = entity.ocr_processed
            existing_document.updated_at = datetime.utcnow()

            db.session.commit()
            current_app.logger.info(f"Documento actualizado: {id}")
            return existing_document
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Error al actualizar documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception("Error al actualizar el documento: posible violación de restricciones")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al actualizar documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception(f"Error al actualizar el documento: {str(e)}")

    def find_by_id(self, id: int):
        current_app.logger.info(f"Buscando documento por ID: {id}")
        return Document.query.get(id)

    def find_all(self):
        """Retorna todos los documentos"""
        current_app.logger.info("Obteniendo todos los documentos")
        return Document.query.all()

    def find_by_filename_and_user(self, filename: str, user_id: int):
        current_app.logger.info(f"Buscando documento con nombre: {filename} en toda la base de datos")
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        normalized_base = base_name.replace('_', '').replace(' ', '').lower()

        documents = Document.query.all()

        for doc in documents:
            doc_base = doc.filename.rsplit('.', 1)[0] if '.' in doc.filename else doc.filename
            doc_normalized = doc_base.replace('_', '').replace(' ', '').lower()

            if doc_normalized == normalized_base:
                current_app.logger.info(f"Documento encontrado (normalizado): {doc.id}, {doc.filename}")
                return doc

        result = Document.query.filter(
            Document.filename.ilike(f"%{base_name}%")
        ).first()

        if result:
            current_app.logger.info(f"Documento encontrado: {result.id}, {result.filename}")
        else:
            current_app.logger.info(f"No se encontró documento con nombre similar a: {filename}")

        return result

    def find_by_storage_path_and_user(self, storage_path: str, user_id: int):
        """
        Busca un documento por su storage_path y user_id.
        
        Args:
            storage_path (str): Ruta del archivo en S3
            user_id (int): ID del usuario
            
        Returns:
            Document: El documento encontrado o None si no existe
        """
        current_app.logger.info(f"Buscando documento con storage_path: {storage_path} para user_id: {user_id}")
        document = Document.query.filter_by(storage_path=storage_path, user_id=user_id).first()
        if document:
            current_app.logger.info(f"Documento encontrado: {document.id}, {document.filename}")
        else:
            current_app.logger.info(f"No se encontró documento con storage_path: {storage_path}")
        return document

    def delete(self, entity: Document):
        """
        Elimina un documento de la base de datos.
        
        Args:
            entity (Document): Objeto Document a eliminar
        """
        current_app.logger.info(f"Eliminando documento con ID: {entity.id}")
        try:
            db.session.delete(entity)
            db.session.commit()
            current_app.logger.info(f"Documento eliminado: {entity.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al eliminar documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception(f"Error al eliminar el documento: {str(e)}")
        
    def find_by_storage_path(self, path):
        return Document.query.filter_by(storage_path=path).first()
    
    def find_by_user_id_without_json(self, user_id: int):
        """
        Encuentra todos los documentos de un usuario que no tienen JSON válido
        (text_json es NULL o es un diccionario vacío)
        """
        from sqlalchemy import or_, and_
        
        return Document.query.filter(
            and_(
                Document.user_id == user_id,
                or_(
                    Document.text_json.is_(None),  # NULL
                    Document.text_json == {},       # Diccionario vacío
                    Document.text_json == []        # Array vacío (por si acaso)
                )
            )
        ).all()

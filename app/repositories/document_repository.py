from app.extensions import db
from app.models import Document
from app.repositories.repository_base import Create, Read, Update, Delete
from sqlalchemy.exc import IntegrityError
from flask import current_app
import traceback
from sqlalchemy.sql import func

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
        current_app.logger.info("Obteniendo todos los documentos")
        return Document.query.all()
    
    def find_by_filename_and_user(self, filename: str, user_id: int):
        """
        Busca un documento por nombre de archivo y ID de usuario.
        Utiliza una búsqueda no sensible a casos (case-insensitive).
        
        Args:
            filename: Nombre del archivo a buscar
            user_id: ID del usuario propietario
            
        Returns:
            Document o None si no se encuentra
        """
        current_app.logger.info(f"Buscando documento con nombre: {filename} para user_id: {user_id}")
        # Eliminar la extensión para una coincidencia más flexible
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Normalizar el nombre base quitando guiones bajos y espacios
        normalized_base = base_name.replace('_', '').replace(' ', '').lower()
        
        # Buscar documentos del usuario
        documents = Document.query.filter(Document.user_id == user_id).all()
        
        # Comparar normalizando cada nombre de archivo
        for doc in documents:
            doc_base = doc.filename.rsplit('.', 1)[0] if '.' in doc.filename else doc.filename
            doc_normalized = doc_base.replace('_', '').replace(' ', '').lower()
            
            if doc_normalized == normalized_base:
                current_app.logger.info(f"Documento encontrado (normalizado): {doc.id}, {doc.filename}")
                return doc
                
        # Caída al método anterior si no se encuentra por normalización
        result = Document.query.filter(
            Document.user_id == user_id,
            Document.filename.ilike(f"%{base_name}%")
        ).first()
        
        if result:
            current_app.logger.info(f"Documento encontrado: {result.id}, {result.filename}")
        else:
            current_app.logger.info(f"No se encontró documento con nombre similar a: {filename} para user_id: {user_id}")
        
        return result

    def delete(self, entity: Document, id: int):
        current_app.logger.info(f"Eliminando documento con ID: {id}")
        try:
            document = Document.query.get(id)
            if not document:
                raise ValueError("Documento no encontrado")
            db.session.delete(document)
            db.session.commit()
            current_app.logger.info(f"Documento eliminado: {id}")
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al eliminar documento: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise Exception(f"Error al eliminar el documento: {str(e)}")
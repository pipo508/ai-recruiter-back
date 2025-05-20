import os
import traceback
from datetime import datetime
from flask import current_app
import PyPDF2

from app.models import Document
from app.repositories.document_repository import DocumentRepository
from app.services.OpenAIRewriteService import OpenAIRewriteService
from app.services.OpenAIVisionService import OpenAIVisionService
from app.services.aws_service import AWSService

class DocumentService:
    def __init__(self, aws_bucket: str):
        self.repo = DocumentRepository()
        self.rewrite_service = OpenAIRewriteService()
        self.vision_service = OpenAIVisionService()
        self.aws_service = AWSService()
        self.aws_bucket = aws_bucket

        # Carpetas locales en caso de fallback o debugging
        os.makedirs('Uploads', exist_ok=True)
        os.makedirs('textos_extraidos', exist_ok=True)
        os.makedirs('pdf_reescritos', exist_ok=True)
        os.makedirs('textos_no_extraidos', exist_ok=True)

    def process_pdf(self, file_path: str, user_id: int, filename: str, use_vision: bool = False) -> dict:
        try:
            current_app.logger.info(f"Procesando archivo: {filename} para user_id: {user_id}")

            if self.repo.find_by_filename_and_user(filename, user_id):
                return {
                    'success': False,
                    'filename': filename,
                    'reason': 'El documento ya existe en la base de datos',
                    'needs_vision': False
                }

            extracted_text = self.extract_text(file_path, use_vision)
            if not extracted_text or len(extracted_text.strip()) < 50:
                if use_vision:
                    os.rename(file_path, os.path.join('textos_no_extraidos', filename))
                    return {
                        'success': False,
                        'filename': filename,
                        'reason': 'No se pudo extraer texto suficiente con Vision',
                        'needs_vision': False
                    }
                return {
                    'success': False,
                    'filename': filename,
                    'reason': 'No se pudo extraer texto del PDF',
                    'needs_vision': True,
                    'temp_path_id': filename  # Incluir temp_path_id para el frontend
                }

            # Reescribir texto
            rewritten_text = self.rewrite_service.rewrite_text(extracted_text)
            base_filename = os.path.splitext(filename)[0]
            rewritten_filename = f"{base_filename}_reescrito.txt"
            local_rewritten_path = os.path.join('pdf_reescritos', rewritten_filename)

            try:
                with open(local_rewritten_path, 'w', encoding='utf-8') as f:
                    f.write(rewritten_text)

                # Subir el archivo original a la carpeta curriculums/
                s3_path = f"curriculums/{filename}"
                file_url, final_filename = self.aws_service.subir_pdf(file_path, filename)
                if file_url is None:
                    raise Exception("Fallo al subir el archivo a S3")

                # Actualizar s3_path si el nombre cambió debido a un conflicto
                s3_path = f"curriculums/{final_filename}"
            except Exception as e:
                current_app.logger.error(f"Error al guardar o subir el archivo reescrito: {str(e)}")
                return {
                    'success': False,
                    'filename': filename,
                    'reason': 'Error al crear o subir el archivo reescrito',
                    'needs_vision': False
                }

            # Guardar en DB
            document = Document(
                user_id=user_id,
                filename=final_filename,  # Usar el nombre final (en caso de que se haya modificado)
                storage_path=s3_path,
                file_url=file_url,
                status='processed',
                char_count=len(rewritten_text),
                needs_ocr=use_vision,
                ocr_processed=use_vision,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            saved_document = self.repo.create(document)

            # Limpiar original
            try:
                os.remove(file_path)
            except Exception as e:
                current_app.logger.warning(f"No se pudo eliminar archivo original: {file_path}. Error: {e}")

            return {
                'success': True,
                'status': 200,  # Añadir status para el frontend
                'document': {
                    'id': saved_document.id,
                    'filename': saved_document.filename,
                    'char_count': saved_document.char_count,
                    'file_url': saved_document.file_url
                },
                'rewritten_file': {
                    'filename': rewritten_filename,
                    's3_path': s3_path
                }
            }

        except Exception as e:
            current_app.logger.error(f"Error procesando archivo {filename}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return {
                'success': False,
                'filename': filename,
                'reason': str(e),
                'needs_vision': not use_vision,
                'status': 500  # Añadir status para el frontend
            }

    def extract_text(self, file_path: str, use_vision: bool) -> str:
        try:
            if use_vision:
                return self.vision_service.extract_text_from_pdf_with_vision(file_path)

            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ''.join([page.extract_text() or '' for page in reader.pages])
                return text.strip()

        except Exception as e:
            current_app.logger.error(f"Error extrayendo texto de {file_path}: {str(e)}")
            return ""

    def get_pdf(self, user_id: int, filename: str) -> dict:
        try:
            document = self.repo.find_by_filename_and_user(filename, user_id)
            if not document:
                return {
                    'success': False,
                    'reason': 'Documento no encontrado'
                }

            # Obtener URL para el archivo en S3
            file_url = self.aws_service.get_file_url(document.storage_path)

            return {
                'success': True,
                'file_url': file_url,
                'filename': document.filename
            }

        except Exception as e:
            current_app.logger.error(f"Error obteniendo PDF para user {user_id} y archivo {filename}: {str(e)}")
            return {
                'success': False,
                'reason': str(e)
            }

    def get_all_documents(self):  # ✅ ya no acepta user_id
        return self.repo.find_all()

    def delete_file(self, s3_path: str, user_id: int) -> dict:
        """
        Elimina un archivo de S3 y su registro correspondiente en la base de datos.
        
        Args:
            s3_path (str): Ruta del archivo en el bucket (e.g., 'curriculums/nombre_archivo.pdf')
            user_id (int): ID del usuario para verificar autorización
        
        Returns:
            dict: Resultado con 'success' (True/False), 'message' y 'status' para el frontend
        """
        try:
            # Validar que s3_path esté en la carpeta permitida
            if not s3_path.startswith('curriculums/'):
                current_app.logger.warning(f"Ruta no permitida: {s3_path}")
                return {
                    'success': False,
                    'message': 'Ruta no permitida. El archivo debe estar en la carpeta curriculums/',
                    'status': 403
                }

            # Buscar el documento en la base de datos por s3_path y user_id
            document = self.repo.find_by_storage_path_and_user(s3_path, user_id)
            if not document:
                current_app.logger.warning(f"No se encontró documento con s3_path: {s3_path} para user_id: {user_id}")
                return {
                    'success': False,
                    'message': f'No se encontró el archivo {s3_path} en la base de datos',
                    'status': 404
                }

            # Eliminar el archivo de S3
            if not self.aws_service.borrar_archivo(s3_path):
                current_app.logger.warning(f"No se pudo eliminar el archivo de S3: {s3_path}")
                return {
                    'success': False,
                    'message': f'No se pudo eliminar el archivo {s3_path} de S3',
                    'status': 404
                }

            # Eliminar el registro de la base de datos
            self.repo.delete(document)
            current_app.logger.info(f"Documento eliminado de la base de datos: {document.id}, s3_path: {s3_path}")

            return {
                'success': True,
                'message': f'Archivo {s3_path} eliminado exitosamente',
                'status': 200
            }

        except Exception as e:
            current_app.logger.error(f"Error al eliminar archivo {s3_path}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Error al eliminar el archivo: {str(e)}',
                'status': 500
            }
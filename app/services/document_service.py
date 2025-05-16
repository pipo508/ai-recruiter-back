import os
import shutil
import traceback
import PyPDF2
from flask import current_app
from app.models import Document
from app.repositories.document_repository import DocumentRepository
from app.services.OpenAIVisionService import OpenAIVisionService


class DocumentService:
    def __init__(self):
        self.repository = DocumentRepository()
        self.EXTRACTED_TEXTS_FOLDER = 'textos_extraidos'
        self.NON_EXTRACTED_TEXTS_FOLDER = 'textos_no_extraidos'
        os.makedirs(self.EXTRACTED_TEXTS_FOLDER, exist_ok=True)
        os.makedirs(self.NON_EXTRACTED_TEXTS_FOLDER, exist_ok=True)

    def extract_text_from_pdf(self, file_path: str) -> str:
        try:
            current_app.logger.info(f"Extrayendo texto de: {file_path}")
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
        except Exception as e:
            current_app.logger.error(f"Error al extraer texto de {file_path}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return ""
    
    def extract_text_with_vision(self, file_path: str) -> str:
        """
        Extrae texto de un PDF usando OpenAI Vision cuando la extracción normal falló.
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Texto extraído mediante Vision API o cadena vacía si falla
        """
        try:
            current_app.logger.info(f"Iniciando extracción de texto con Vision para: {file_path}")
            vision_service = OpenAIVisionService()
            
            # Limitar a un número razonable de páginas para controlar costos de API
            max_pages = int(os.getenv('VISION_MAX_PAGES', '20'))
            text = vision_service.extract_text_from_pdf_with_vision(file_path, max_pages)
            
            current_app.logger.info(f"Texto extraído con Vision: {len(text)} caracteres")
            return text
        except Exception as e:
            current_app.logger.error(f"Error al extraer texto con Vision de {file_path}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return ""

    def create(self, user_id: int, filename: str, firebase_path: str) -> Document:
        document = Document(
            user_id=user_id,
            filename=filename,
            firebase_path=firebase_path
        )
        return self.repository.create(document)

    def update(self, document_id: int, status: str, char_count: int, needs_ocr: bool, ocr_processed: bool):
        dummy_doc = Document(
            status=status,
            char_count=char_count,
            needs_ocr=needs_ocr,
            ocr_processed=ocr_processed
        )
        return self.repository.update(dummy_doc, document_id)

    def check_duplicate(self, filename: str, user_id: int) -> Document:
        """
        Verifica si ya existe un documento con el mismo nombre para el usuario.
        Utiliza un método mejorado de comparación que normaliza nombres de archivos.
        
        Args:
            filename: Nombre del archivo a verificar
            user_id: ID del usuario propietario
            
        Returns:
            Document existente o None si no hay duplicado
        """
        current_app.logger.info(f"Verificando si existe duplicado: {filename} para user_id: {user_id}")
        existing_doc = self.repository.find_by_filename_and_user(filename, user_id)
        if existing_doc:
            current_app.logger.info(f"Documento duplicado encontrado: {existing_doc.id}, {existing_doc.filename}")
        return existing_doc

    def _get_unique_filepath(self, folder: str, filename: str) -> str:
        """
        Devuelve un path único en folder para filename,
        agregando sufijo incremental si existe el archivo.
        """
        base, ext = os.path.splitext(filename)
        candidate = filename
        i = 1
        while os.path.exists(os.path.join(folder, candidate)):
            candidate = f"{base}_{i}{ext}"
            i += 1
        return os.path.join(folder, candidate)

    def process_pdf(self, file_path: str, user_id: int, filename: str, use_vision: bool = False):
        """
        Procesa un archivo PDF: extrae texto y guarda en el sistema.
        Ahora incluye un parámetro para indicar si debe usar Vision en caso de falla.
        
        Args:
            file_path: Ruta al archivo PDF
            user_id: ID del usuario
            filename: Nombre original del archivo
            use_vision: Si se debe intentar con Vision cuando la extracción normal falla
            
        Returns:
            Dict con el resultado del procesamiento
        """
        try:
            current_app.logger.info(f"Procesando archivo: {filename} para user_id: {user_id}")
            
            # Verificar si el documento ya existe para este usuario
            existing_document = self.check_duplicate(filename, user_id)
            if existing_document:
                current_app.logger.info(f"Documento duplicado encontrado: {existing_document.id}, {existing_document.filename}")
                # Crear respuesta segura para serialización JSON
                return {
                    'success': False,
                    'duplicate': True,
                    'document': {
                        'id': existing_document.id,
                        'filename': existing_document.filename,
                        'char_count': existing_document.char_count or 0
                    },
                    'reason': 'El documento ya ha sido cargado anteriormente',
                    'filename': filename
                }
            
            # Intentar extracción normal primero
            text = self.extract_text_from_pdf(file_path)
            current_app.logger.info(f"Texto extraído: {len(text)} caracteres")

            # Verificar si se extrajo suficiente texto
            text_sufficient = text and len(text) > 100
            
            # Si no hay suficiente texto y no se ha solicitado usar Vision todavía
            if not text_sufficient and not use_vision:
                return {
                    'success': False,
                    'needs_vision': True,
                    'reason': 'Texto insuficiente o no extraíble. Se requiere procesamiento con Vision.',
                    'filename': filename
                }
            
            # Si no hay texto y se nos pide usar Vision
            if not text_sufficient and use_vision:
                current_app.logger.info(f"Intentando extracción con Vision para: {filename}")
                text = self.extract_text_with_vision(file_path)
                text_sufficient = text and len(text) > 100
                
                # Si Vision tampoco pudo extraer texto suficiente
                if not text_sufficient:
                    failed_path = os.path.join(self.NON_EXTRACTED_TEXTS_FOLDER, filename)
                    current_app.logger.info(f"Vision falló. Moviendo archivo a textos no extraídos: {failed_path}")
                    os.makedirs(os.path.dirname(failed_path), exist_ok=True)
                    shutil.move(file_path, failed_path)
                    return {
                        'success': False,
                        'vision_failed': True,
                        'reason': 'No se pudo extraer texto incluso usando Vision',
                        'filename': filename
                    }

            # Si tenemos suficiente texto (sea por extracción normal o Vision)
            if text_sufficient:
                uploads_folder = "Uploads"
                os.makedirs(uploads_folder, exist_ok=True)
                unique_upload_path = self._get_unique_filepath(uploads_folder, filename)
                current_app.logger.info(f"Guardando copia persistente del PDF en: {unique_upload_path}")
                shutil.copy(file_path, unique_upload_path)

                # Guardar texto extraído
                text_path = os.path.join(self.EXTRACTED_TEXTS_FOLDER, f"{os.path.splitext(filename)[0]}.txt")
                current_app.logger.info(f"Guardando texto en: {text_path}")
                os.makedirs(os.path.dirname(text_path), exist_ok=True)
                with open(text_path, 'w', encoding='utf-8') as text_file:
                    text_file.write(text)

                # Crear y actualizar documento
                document = self.create(
                    user_id=int(user_id),
                    filename=os.path.basename(unique_upload_path),
                    firebase_path=unique_upload_path
                )
                current_app.logger.info(f"Documento creado con ID: {document.id}")

                # Actualizar con detalles específicos según el método de extracción
                self.update(
                    document_id=document.id,
                    status='processed',
                    char_count=len(text),
                    needs_ocr=not bool(self.extract_text_from_pdf(file_path)),  # Marcar si se necesitó OCR
                    ocr_processed=use_vision  # Indica si se usó Vision para la extracción
                )
                current_app.logger.info(f"Documento actualizado: {document.id}")

                return {
                    'success': True,
                    'vision_used': use_vision,
                    'document': {
                        'id': document.id,
                        'filename': os.path.basename(unique_upload_path),
                        'char_count': len(text)
                    }
                }
            else:
                failed_path = os.path.join(self.NON_EXTRACTED_TEXTS_FOLDER, filename)
                current_app.logger.info(f"Moviendo archivo a textos no extraídos: {failed_path}")
                os.makedirs(os.path.dirname(failed_path), exist_ok=True)
                shutil.move(file_path, failed_path)
                return {
                    'success': False,
                    'reason': 'Texto insuficiente o no extraíble',
                    'filename': filename
                }
        except Exception as e:
            current_app.logger.error(f"Error procesando archivo {filename}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return {
                'success': False,
                'reason': str(e),
                'filename': filename
            }
        

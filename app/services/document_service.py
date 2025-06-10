import os
import traceback
from datetime import datetime
from flask import current_app
import PyPDF2
import numpy as np
from app.extensions import db

from app.models.models_document import Document # Importar Document desde su archivo
from app.models.models_vector_embedding import VectorEmbedding # Importar VectorEmbedding desde su archivo
from app.repositories.document_repository import DocumentRepository
from app.services.OpenAIService import OpenAIRewriteService
from app.services.OpenAIVisionService import OpenAIVisionService # Asumo que existe
from app.services.aws_service import AWSService # Asumo que existe
from app.extensions import get_faiss_index, save_faiss_index # Importar funciones de FAISS

class DocumentService:
    def __init__(self, aws_bucket: str):
        self.repo = DocumentRepository()
        self.rewrite_service = OpenAIRewriteService()
        self.vision_service = OpenAIVisionService()
        self.aws_service = AWSService()
        self.aws_bucket = aws_bucket
        self.MIN_TEXT_LENGTH = 500  # Mínimo de caracteres para considerar que tiene texto válido
        # ... (creación de carpetas) ...

    def process_pdf(self, file_path: str, user_id: int, filename: str, use_vision: bool = False) -> dict:
        try:
            current_app.logger.info(f"Procesando archivo: {filename} para user_id: {user_id}")

            # Verificar si es un PDF válido
            if not self._is_valid_pdf(file_path):
                return {
                    'success': False,
                    'filename': filename,
                    'reason': 'El archivo no es un PDF válido',
                    'needs_vision': False,
                    'status': 400
                }

            # ... (Lógica para verificar si el documento ya existe) ...

            # Extraer texto y determinar si necesita OCR
            extracted_text, needs_ocr = self._extract_and_validate_text(file_path, use_vision)
            
            # Si no se pudo extraer texto suficiente y no estamos usando OCR, marcamos que necesita OCR
            if not extracted_text or len(extracted_text.strip()) < self.MIN_TEXT_LENGTH:
                if not use_vision:
                    current_app.logger.info(f"Archivo {filename} tiene menos de {self.MIN_TEXT_LENGTH} caracteres ({len(extracted_text.strip()) if extracted_text else 0}). Necesita OCR.")
                    return {
                        'success': False,
                        'filename': filename,
                        'reason': f'El documento tiene muy poco texto ({len(extracted_text.strip()) if extracted_text else 0} caracteres). Requiere procesamiento con OCR.',
                        'needs_vision': True,
                        'status': 200
                    }
                else:
                    # Si ya usamos OCR y aún no hay texto suficiente, es un error
                    return {
                        'success': False,
                        'filename': filename,
                        'reason': 'No se pudo extraer texto suficiente ni con OCR',
                        'needs_vision': False,
                        'status': 400
                    }

            # Procesar texto: reescribir solo si NO se usó OCR
            if use_vision:
                # Con OCR no reescribimos, el texto ya viene estructurado
                final_text = extracted_text
                current_app.logger.info(f"Texto extraído con OCR para {filename}, no se reescribe")
            else:
                # Sin OCR, reescribimos el texto
                final_text = self.rewrite_service.rewrite_text(extracted_text)
                current_app.logger.info(f"Texto reescrito para {filename}")

            # GENERAR JSON ESTRUCTURADO AQUÍ
            try:
                current_app.logger.info(f"Generando JSON estructurado para {filename}")
                structured_json = self.rewrite_service.structure_profile(final_text)
                current_app.logger.info(f"JSON estructurado generado exitosamente para {filename}")
            except Exception as e:
                current_app.logger.warning(f"Error al estructurar el perfil para {filename}: {str(e)}")
                structured_json = {}

            base_filename = os.path.splitext(filename)[0]
            
            # Guardar documento en DB PRIMERO para obtener su ID
            document = Document(
                user_id=user_id,
                filename=filename, # Se actualizará si S3 cambia el nombre
                storage_path="pending", # Se actualizará después de subir a S3
                file_url=None,
                rewritten_text=final_text,
                text_json=structured_json,  # AGREGAR EL JSON ESTRUCTURADO AQUÍ
                status='processing', # Cambia a 'processed' más adelante
                char_count=len(final_text),
                needs_ocr=needs_ocr,
                ocr_processed=use_vision,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            saved_document = self.repo.create(document) # Documento guardado con ID asignado
            current_app.logger.info(f"Documento '{saved_document.filename}' creado con ID: {saved_document.id} y JSON estructurado guardado")

            # Generar embedding
            embedding_list = self.rewrite_service.generate_embedding(final_text)
            embedding_vector_np = np.array(embedding_list).astype('float32').reshape(1, -1) # FAISS espera (n_vectors, dimension)

            # Añadir embedding a FAISS usando el ID del documento
            faiss_idx = get_faiss_index()
            if faiss_idx:
                document_id_np = np.array([saved_document.id], dtype=np.int64)
                faiss_idx.add_with_ids(embedding_vector_np, document_id_np)
                current_app.logger.info(f"Embedding para Document ID {saved_document.id} añadido a FAISS. Total vectores: {faiss_idx.ntotal}")
                save_faiss_index() # Guardar el índice actualizado

                # Crear y guardar el registro VectorEmbedding
                vector_embedding_record = VectorEmbedding(
                    document_id=saved_document.id,
                    faiss_index_id=saved_document.id, # Usamos el mismo Document.id como ID en FAISS
                    embedding_model=current_app.config['OPENAI_EMBEDDING_MODEL']
                )
                # Necesitarás un método en tu repositorio de VectorEmbedding o añadirlo aquí
                from app.extensions import db # Acceso directo a db.session para simplificar
                db.session.add(vector_embedding_record)
                # El commit se hará junto con la actualización del documento más adelante
                current_app.logger.info(f"Registro VectorEmbedding creado para Document ID {saved_document.id}")

            else:
                current_app.logger.error("Índice FAISS no disponible. El embedding no se pudo añadir.")
                # Aquí podrías manejar el error, quizás marcando el documento para re-indexación

            # Subir el archivo original a S3 y actualizar documento
            s3_path_original = f"curriculums/{filename}" # Nombre base
            file_url, final_s3_filename = self.aws_service.subir_pdf(file_path, filename) # Asumo que subir_pdf devuelve URL y nombre final
            if file_url is None:
                raise Exception("Fallo al subir el archivo original a S3")
            
            saved_document.storage_path = f"curriculums/{final_s3_filename}" # Actualizar con el nombre real en S3
            saved_document.file_url = file_url
            saved_document.filename = final_s3_filename # Actualizar nombre si cambió en S3
            saved_document.status = 'processed'
            saved_document.updated_at = datetime.utcnow()
            
            # Guardar cambios en el documento y el nuevo VectorEmbedding
            db.session.commit() # Commit aquí para todas las operaciones de esta sesión
            current_app.logger.info(f"Documento ID {saved_document.id} actualizado y procesado con JSON estructurado.")
            
            # Limpieza de archivos temporales
            try:
                os.remove(file_path) # Eliminar PDF original subido
            except Exception as e:
                current_app.logger.warning(f"No se pudo eliminar archivo original temporal: {file_path}. Error: {e}")

            return {
                'success': True,
                'status': 200,
                'document': saved_document.to_dict(), # Usar el método to_dict()
                'message': f"Documento '{saved_document.filename}' procesado {'con OCR' if use_vision else 'y reescrito'} con JSON estructurado."
            }

        except Exception as e:
            db.session.rollback() # Revertir en caso de error
            current_app.logger.error(f"Error procesando archivo {filename}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return {
                'success': False,
                'filename': filename,
                'reason': str(e),
                'needs_vision': False,
                'status': 500
            }

    def _is_valid_pdf(self, file_path: str) -> bool:
        """
        Verifica si el archivo es un PDF válido.
        """
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                # Intentar acceder al número de páginas para validar el PDF
                num_pages = len(reader.pages)
                current_app.logger.info(f"PDF válido con {num_pages} páginas")
                return num_pages > 0
        except Exception as e:
            current_app.logger.error(f"Archivo no es un PDF válido: {str(e)}")
            return False

    def _extract_and_validate_text(self, file_path: str, use_vision: bool) -> tuple:
        """
        Extrae texto del PDF y determina si necesita OCR.
        
        Returns:
            tuple: (extracted_text, needs_ocr)
        """
        try:
            if use_vision:
                # Si ya decidimos usar OCR, extraer con Vision
                text = self.vision_service.extract_text_from_pdf_with_vision(file_path)
                current_app.logger.info(f"Texto extraído con OCR: {len(text) if text else 0} caracteres")
                return text or "", True
            else:
                # Intentar extracción normal primero
                text = self._extract_text_pypdf2(file_path)
                text_length = len(text.strip()) if text else 0
                
                current_app.logger.info(f"Texto extraído con PyPDF2: {text_length} caracteres")
                
                # Determinar si necesita OCR basado en la cantidad de texto
                needs_ocr = text_length < self.MIN_TEXT_LENGTH
                
                return text, needs_ocr

        except Exception as e:
            current_app.logger.error(f"Error extrayendo texto de {file_path}: {str(e)}")
            return "", True  # Si hay error, asumir que necesita OCR

    def _extract_text_pypdf2(self, file_path: str) -> str:
        """
        Extrae texto usando PyPDF2.
        """
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = []
                
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text() or ''
                        text_parts.append(page_text)
                        current_app.logger.debug(f"Página {page_num + 1}: {len(page_text)} caracteres")
                    except Exception as e:
                        current_app.logger.warning(f"Error en página {page_num + 1}: {str(e)}")
                        continue
                
                full_text = ''.join(text_parts).strip()
                current_app.logger.info(f"Total de texto extraído: {len(full_text)} caracteres")
                
                return full_text

        except Exception as e:
            current_app.logger.error(f"Error con PyPDF2 en {file_path}: {str(e)}")
            return ""

    # Método legacy mantenido para compatibilidad
    def extract_text(self, file_path: str, use_vision: bool) -> str:
        """
        Método legacy - usar _extract_and_validate_text en su lugar.
        """
        text, _ = self._extract_and_validate_text(file_path, use_vision)
        return text

    def get_pdf(self, user_id: int, filename: str) -> dict:
        try:
            document = self.repo.find_by_filename_and_user(filename, user_id)
            if not document:
                return {
                    'success': False,
                    'reason': 'Documento no encontrado'
                }

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

    def get_all_documents(self):
        return self.repo.find_all()

    def delete_file(self, s3_path: str, user_id: int) -> dict:
        try:
            if not s3_path.startswith('curriculums/'):
                current_app.logger.warning(f"Ruta no permitida: {s3_path}")
                return {
                    'success': False,
                    'message': 'Ruta no permitida. El archivo debe estar en la carpeta curriculums/',
                    'status': 403
                }

            document = self.repo.find_by_storage_path(s3_path)
            if not document:
                current_app.logger.warning(f"No se encontró documento con s3_path: {s3_path} para user_id: {user_id}")
                return {
                    'success': False,
                    'message': f'No se encontró el archivo {s3_path} en la base de datos',
                    'status': 404
                }

            if not self.aws_service.borrar_archivo(s3_path):
                current_app.logger.warning(f"No se pudo eliminar el archivo de S3: {s3_path}")
                return {
                    'success': False,
                    'message': f'No se pudo eliminar el archivo {s3_path} de S3',
                    'status': 404
                }

            # Eliminar el documento de la base de datos (esto también elimina VectorEmbedding por cascada)
            self.repo.delete(document)
            current_app.logger.info(f"Documento eliminado de la base de datos: {document.id}, s3_path: {s3_path}")

            # Eliminar el vector de FAISS
            faiss_idx = get_faiss_index()
            if faiss_idx:
                try:
                    document_id_np = np.array([document.id], dtype=np.int64)
                    faiss_idx.remove_ids(document_id_np)
                    current_app.logger.info(f"Vector para Document ID {document.id} eliminado de FAISS. Total vectores restantes: {faiss_idx.ntotal}")
                    save_faiss_index()  # Guardar el índice actualizado
                except Exception as e:
                    current_app.logger.error(f"Error al eliminar vector de FAISS para Document ID {document.id}: {str(e)}")
                    # Continuamos porque el documento ya fue eliminado de S3 y la base de datos
            else:
                current_app.logger.warning("Índice FAISS no disponible. No se pudo eliminar el vector.")

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
            
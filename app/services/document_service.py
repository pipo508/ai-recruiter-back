# app/services/document_service.py

import os
import traceback
from datetime import datetime
from flask import current_app
import PyPDF2
import numpy as np
from app.extensions import db, get_faiss_index, save_faiss_index
from app.models.models_document import Document
from app.models.models_vector_embedding import VectorEmbedding
from app.repositories.document_repository import DocumentRepository
from app.services.OpenAIService import OpenAIRewriteService
from app.services.OpenAIVisionService import OpenAIVisionService
from app.services.aws_service import AWSService
from app.models.models_candidate import Candidate

class DocumentService:
    def __init__(self, aws_bucket: str):
        self.repo = DocumentRepository()
        self.rewrite_service = OpenAIRewriteService()
        self.vision_service = OpenAIVisionService()
        self.aws_service = AWSService()
        self.aws_bucket = aws_bucket
        self.MIN_TEXT_LENGTH = 500  # Mínimo para extracción estándar
        # --- INICIO DE LA MODIFICACIÓN 1 ---
        self.MIN_VISION_TEXT_LENGTH = 400  # Mínimo para extracción con Vision/OCR
        # --- FIN DE LA MODIFICACIÓN 1 ---

    # app/services/document_service.py - Reemplazar el método process_pdf con este:

    def process_pdf(self, file_path: str, user_id: int, filename: str, use_vision: bool = False) -> dict:
        """
        Procesa un archivo PDF, lo guarda y crea un perfil de candidato asociado.
        """
        try:
            # --- 1. Lógica de verificación, extracción y reescritura de texto ---
            # (Esta parte de tu código está bien y no la modificamos)
            if not use_vision:
                existing_document = self.repo.find_by_filename_and_user(filename, user_id)
                if existing_document:
                    return {'success': False, 'filename': filename, 'reason': 'El documento ya existe.', 'status': 409}

            if not self._is_valid_pdf(file_path):
                return {'success': False, 'filename': filename, 'reason': 'No es un PDF válido.', 'status': 400}

            extraction_method = "Vision/OCR" if use_vision else "PyPDF2"
            extracted_text = self.vision_service.extract_text_from_pdf_with_vision(file_path) if use_vision else self._extract_text_pypdf2(file_path)
            
            if not extracted_text or len(extracted_text.strip()) < self.MIN_TEXT_LENGTH:
                # (Lógica de texto insuficiente, etc.)
                if not use_vision:
                    return {'success': False, 'filename': filename, 'reason': 'Texto insuficiente, ¿intentar con OCR?', 'needs_vision': True, 'status': 200}
                else:
                    return {'success': False, 'filename': filename, 'reason': f'Texto extraído con OCR insuficiente.', 'status': 400}
            
            final_text = self.rewrite_service.rewrite_text(extracted_text) if not use_vision else extracted_text

            
            # --- 2. GUARDAR EL DOCUMENTO (SIN text_json) ---
            # <<< CORRECCIÓN PRINCIPAL: Se elimina 'text_json' de aquí >>>
            try:
                document = Document(
                    user_id=user_id,
                    filename=filename,
                    storage_path="pending",
                    file_url=None,
                    rewritten_text=final_text,
                    status='processing',
                    char_count=len(final_text),
                    ocr_processed=use_vision
                )
                saved_document = self.repo.create(document)
                current_app.logger.info(f"Documento guardado en BD con ID: {saved_document.id}")
            except Exception as db_error:
                current_app.logger.error(f"Error guardando en BD para '{filename}': {db_error}")
                raise

            # --- 3. CREAR EL CANDIDATO ASOCIADO ---
            # Se llama a esta función que contiene la lógica para crear el perfil
            try:
                self.create_candidate_from_text(final_text, saved_document.id)
                current_app.logger.info(f"Perfil de candidato creado para documento ID: {saved_document.id}")
            except Exception as candidate_error:
                current_app.logger.warning(f"No se pudo crear el perfil del candidato para '{filename}': {candidate_error}")


            # --- 4. GENERAR Y GUARDAR EMBEDDING ---
            try:
                embedding_list = self.rewrite_service.generate_embedding(final_text)
                self._save_embedding_to_faiss(saved_document.id, embedding_list)
            except Exception as embedding_error:
                current_app.logger.warning(f"Error generando embedding para '{filename}': {embedding_error}")

            # --- 5. SUBIR A S3 Y FINALIZAR ---
            try:
                file_url, final_s3_filename = self.aws_service.subir_pdf(file_path, filename)
                
                if file_url is None:
                    raise Exception("Error al subir archivo a S3")
                
                saved_document.storage_path = f"curriculums/{final_s3_filename}"
                saved_document.file_url = file_url
                saved_document.filename = final_s3_filename
                saved_document.status = 'processed'
                saved_document.updated_at = db.func.now()
                db.session.commit()
            except Exception as s3_error:
                saved_document.status = 'error'
                db.session.commit()
                raise Exception(f"Error subiendo archivo a S3: {s3_error}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

            # --- 6. RETORNO EXITOSO ---
            return {
                'success': True,
                'status': 200,
                'document': saved_document.to_dict(),
                'message': f"Documento '{saved_document.filename}' procesado exitosamente."
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error crítico procesando '{filename}': {e}", exc_info=True)
            if os.path.exists(locals().get('file_path', '')):
                os.remove(locals().get('file_path'))
            return {
                'success': False,
                'filename': filename,
                'reason': f'Error interno del servidor: {e}',
                'status': 500
            }
        
    # El resto de los métodos (_is_valid_pdf, _extract_text_pypdf2, etc.) permanecen sin cambios.
    def _is_valid_pdf(self, file_path: str) -> bool:
        """Verifica si el archivo es un PDF válido usando PyPDF2."""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                return len(reader.pages) > 0
        except Exception as e:
            current_app.logger.error(f"Archivo no es un PDF válido: {str(e)}")
            return False

    def _extract_text_pypdf2(self, file_path: str) -> str:
        """Extrae texto usando PyPDF2."""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = [page.extract_text() or '' for page in reader.pages]
                return ''.join(text_parts).strip()
        except Exception as e:
            current_app.logger.error(f"Error con PyPDF2 en {file_path}: {str(e)}")
            return ""

    def _save_embedding_to_faiss(self, document_id, embedding_list):
        """Genera y guarda el embedding de un texto en el índice FAISS."""
        try:
            faiss_idx = get_faiss_index()
            if not faiss_idx:
                current_app.logger.error("Índice FAISS no disponible.")
                return

            embedding_vector_np = np.array(embedding_list).astype('float32').reshape(1, -1)
            document_id_np = np.array([document_id], dtype=np.int64)

            faiss_idx.add_with_ids(embedding_vector_np, document_id_np)
            save_faiss_index()
            current_app.logger.info(f"Embedding para Document ID {document_id} añadido a FAISS.")

            vector_embedding_record = VectorEmbedding(
                document_id=document_id,
                faiss_index_id=document_id,
                embedding_model=current_app.config['OPENAI_EMBEDDING_MODEL']
            )
            db.session.add(vector_embedding_record)

        except Exception as e:
            current_app.logger.error(f"Error al guardar embedding para doc {document_id}: {e}")

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

            self.repo.delete(document)
            current_app.logger.info(f"Documento eliminado de la base de datos: {document.id}, s3_path: {s3_path}")

            faiss_idx = get_faiss_index()
            if faiss_idx:
                try:
                    document_id_np = np.array([document.id], dtype=np.int64)
                    faiss_idx.remove_ids(document_id_np)
                    current_app.logger.info(f"Vector para Document ID {document.id} eliminado de FAISS. Total vectores restantes: {faiss_idx.ntotal}")
                    save_faiss_index()
                except Exception as e:
                    current_app.logger.error(f"Error al eliminar vector de FAISS para Document ID {document.id}: {str(e)}")
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
    def create_candidate_from_text(self, text: str, document_id: int) -> Candidate | None:
        """
        Orquesta la creación de un candidato:
        1. Convierte texto a JSON.
        2. Valida que el JSON contiene datos esenciales.
        3. Mapea el JSON a un objeto del modelo 'Candidate'.
        4. Guarda el nuevo candidato en la base de datos.
        """
        current_app.logger.info(f"Iniciando estructuración de perfil para document_id: {document_id}")
        
        # 1. Llama a la función para obtener el JSON estructurado.
        profile_data = self.rewrite_service.structure_profile(text) # Se usa self.rewrite_service en lugar de self.structure_profile

        # --- INICIO DE LA CORRECCIÓN ---

        # 2. Validación robusta de los datos recibidos.
        # Se verifica que profile_data no sea None, no sea un diccionario vacío
        # y que contenga las claves obligatorias.
        if not profile_data or not isinstance(profile_data, dict) or "Nombre completo" not in profile_data or "Email" not in profile_data:
            current_app.logger.error(
                f"No se pudieron obtener datos estructurados o faltan campos esenciales para el document_id: {document_id}. "
                f"Datos recibidos de OpenAI: {profile_data}"
            )
            return None

        try:
            # 3. Mapea los datos del JSON al modelo Candidate.
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

            # 4. Agrega y guarda en la base de datos.
            db.session.add(new_candidate)
            db.session.commit()
            
            current_app.logger.info(f"Candidato '{new_candidate.nombre_completo}' (ID: {new_candidate.id}) creado exitosamente.")
            
            return new_candidate

        except Exception as e:
            db.session.rollback()
            # Se mejora el log para registrar el error específico (ej. IntegrityError por email duplicado).
            current_app.logger.error(f"Error al guardar el candidato para document_id {document_id} en la base de datos: {str(e)}")
            current_app.logger.error(traceback.format_exc()) # Añadido para un debug más completo
            return None
        
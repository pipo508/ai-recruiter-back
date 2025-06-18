# app/services/document_service.py

import os
import traceback
from datetime import datetime
from flask import current_app
import PyPDF2
import numpy as np
from app.Extensions import db, get_faiss_index, save_faiss_index
from app.models.Document import Document
from app.models.VectorEmbedding import VectorEmbedding
from app.repositories.DocumentRepository import DocumentRepository
from app.services.OpenAIService import OpenAIRewriteService
from app.services.OpenAIVisionService import OpenAIVisionService
from app.services.AwsService import AWSService
from app.models.Candidate import Candidate

UPLOAD_FOLDER = 'Uploads'

class DocumentService:
    def __init__(self, aws_bucket: str):
        self.repo = DocumentRepository()
        self.rewrite_service = OpenAIRewriteService()
        self.vision_service = OpenAIVisionService()
        self.aws_service = AWSService()
        self.aws_bucket = aws_bucket
        self.MIN_TEXT_LENGTH = 500
        self.MIN_VISION_TEXT_LENGTH = 400

    def process_pdf(self, file_path: str, user_id: int, filename: str, use_vision: bool = False) -> dict:
        """
        Orquesta el proceso completo de un PDF: validación, extracción, guardado,
        generación de perfil, embedding enfocado y subida a S3.
        """
        try:
            current_app.logger.debug(f"[DEBUG] [Paso 1/7] Iniciando validación para el archivo '{filename}'.")
            if not use_vision:
                existing_document = self.repo.find_by_filename_and_user(filename, user_id)
                if existing_document:
                    current_app.logger.warning(f"[ADVERTENCIA] Proceso cancelado para '{filename}'. Razón: El documento ya existe para este usuario (user_id: {user_id}).")
                    return {'success': False, 'filename': filename, 'reason': 'El documento ya existe.', 'status': 409}

            if not self._is_valid_pdf(file_path):
                current_app.logger.error(f"[ERROR] Proceso cancelado para '{filename}'. Razón: El archivo no es un PDF válido o está corrupto.")
                return {'success': False, 'filename': filename, 'reason': 'No es un PDF válido o está dañado.', 'status': 400}

            extraction_method = "Vision/OCR" if use_vision else "PyPDF2"
            current_app.logger.debug(f"[DEBUG] [Paso 2/7] Extrayendo texto usando el método: {extraction_method}.")
            extracted_text = self.vision_service.extract_text_from_pdf_with_vision(file_path) if use_vision else self._extract_text_pypdf2(file_path)
            
            min_length = self.MIN_VISION_TEXT_LENGTH if use_vision else self.MIN_TEXT_LENGTH
            if not extracted_text or len(extracted_text.strip()) < min_length:
                reason = f'Texto extraído con {extraction_method} es insuficiente (largo: {len(extracted_text.strip())}, mínimo: {min_length}).'
                current_app.logger.warning(f"[ADVERTENCIA] Proceso cancelado para '{filename}'. Razón: {reason}")
                if not use_vision:
                    return {'success': False, 'filename': filename, 'reason': 'Texto insuficiente, se recomienda usar OCR/Vision.', 'needs_vision': True, 'status': 200}
                else:
                    return {'success': False, 'filename': filename, 'reason': reason, 'status': 400}
            
            final_text = self.rewrite_service.rewrite_text(extracted_text)

            current_app.logger.debug(f"[DEBUG] [Paso 3/7] Creando registro del documento en la base de datos.")
            document = Document(
                user_id=user_id, filename=filename, storage_path="pending",
                rewritten_text=final_text, status='processing', char_count=len(final_text),
                ocr_processed=use_vision
            )
            saved_document = self.repo.create(document)
            current_app.logger.info(f"[INFO] Registro de documento creado con éxito. ID asignado: {saved_document.id}.")

            current_app.logger.debug(f"[DEBUG] [Paso 4/7] Generando perfil estructurado del candidato desde el texto.")
            # MODIFICACIÓN: Capturamos el objeto 'candidate' que se crea.
            candidate_profile = self.create_candidate_from_text(final_text, saved_document.id)
            
            # Si no se pudo crear un perfil, no podemos continuar con el embedding.
            if not candidate_profile:
                # Marcamos el documento como procesado pero con un error en el perfilado para revisión manual.
                self.repo.update(saved_document, saved_document.id, {'status': 'processed_with_profile_error'})
                raise Exception(f"No se pudo generar un perfil de candidato para el documento {saved_document.id}. No se puede crear el embedding.")

            current_app.logger.debug(f"[DEBUG] [Paso 5/7] Generando y almacenando el embedding vectorial.")

            # --- INICIO DE LA MODIFICACIÓN CLAVE ---
            # 1. Creamos el texto optimizado para la búsqueda a partir del perfil.
            search_document_text = self._create_search_document_for_candidate(candidate_profile)
            
            # 2. Generamos el embedding a partir de este nuevo texto enfocado.
            embedding_list = self.rewrite_service.generate_embedding(search_document_text)
            # --- FIN DE LA MODIFICACIÓN CLAVE ---

            self._save_embedding_to_faiss(saved_document.id, embedding_list)

            current_app.logger.debug(f"[DEBUG] [Paso 6/7] Subiendo archivo a S3 y actualizando el estado del documento.")
            file_url, final_s3_filename = self.aws_service.subir_pdf(file_path, filename)
            if file_url is None:
                raise Exception("Fallo en la subida del archivo a S3. El servicio AWS no retornó una URL.")
            
            update_data = {
                'storage_path': f"curriculums/{final_s3_filename}",
                'file_url': file_url,
                'filename': final_s3_filename,
                'status': 'processed'
            }
            updated_document = self.repo.update(saved_document, saved_document.id, update_data)

            current_app.logger.debug(f"[DEBUG] [Paso 7/7] Realizando limpieza de archivos temporales.")
            self._clean_intermediate_files(os.path.basename(file_path))
            
            current_app.logger.info(f"[ÉXITO] Proceso completado satisfactoriamente para el archivo '{filename}'. Documento ID: {updated_document.id}.")
            return {'success': True, 'status': 200, 'document': updated_document.to_dict()}

        except Exception as e:
            db.session.rollback()
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] Error crítico durante el procesamiento del archivo '{filename}'. La operación ha sido revertida.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            # Si ya se había creado el documento en la DB, lo marcamos como 'error'.
            if 'saved_document' in locals() and saved_document.id:
                self.repo.update(saved_document, saved_document.id, {'status': 'error'})

            self._clean_intermediate_files(os.path.basename(file_path))
            return {'success': False, 'filename': filename, 'reason': f'Error interno del servidor: {e}', 'status': 500}    

    def get_document_details(self, document_id: int, requesting_user_id: int) -> dict:
        document = self.repo.find_by_id_with_candidate(document_id)
        if not document:
            return {'success': False, 'message': 'Documento no encontrado', 'status': 404}

        profile_data = {}
        if document.candidate:
            profile_data = document.candidate.to_dict()
        elif document.rewritten_text:
            try:
                candidate = self.create_candidate_from_text(document.rewritten_text, document.id)
                if candidate:
                    profile_data = candidate.to_dict()
            except Exception as e:
                current_app.logger.warning(f"[ADVERTENCIA] No se pudo auto-generar el perfil para el documento {document_id} al solicitar sus detalles. Causa: {e}")

        response_data = {
            'document_id': document.id, 'user_id': document.user_id,
            'filename': document.filename, 'profile': profile_data
        }
        return {'success': True, 'data': response_data, 'status': 200}

    def update_candidate_profile(self, document_id: int, new_data: dict, requesting_user_id: int) -> dict:
        document = self.repo.find_by_id_with_candidate(document_id)
        if not document:
            return {'success': False, 'message': 'Documento no encontrado', 'status': 404}

        if not document.candidate:
            return {'success': False, 'message': 'No existe un perfil de candidato para este documento', 'status': 404}

        key_to_attribute_map = {
            "Nombre completo": "nombre_completo", "Puesto actual": "puesto_actual",
            "Habilidad principal": "habilidad_principal", "Años de experiencia total": "anios_experiencia",
            "Cantidad de proyectos/trabajos": "cantidad_proyectos", "Descripción profesional": "descripcion_profesional",
            "GitHub": "github", "Email": "email", "Número de teléfono": "telefono", "Ubicación": "ubicacion",
            "Candidato ideal": "candidato_ideal", "Habilidades clave": "habilidades_clave",
            "Experiencia Profesional": "experiencia_profesional", "Educación": "educacion"
        }

        try:
            for key, value in new_data.items():
                attribute_name = key_to_attribute_map.get(key)
                if attribute_name and hasattr(document.candidate, attribute_name):
                    setattr(document.candidate, attribute_name, value)
            
            updated_candidate = self.repo.save_candidate_and_document_update(document.candidate, document)
            return {'success': True, 'data': updated_candidate.to_dict(), 'status': 200}
        except Exception as e:
            current_app.logger.error(f"[ERROR] Falla en la capa de servicio al actualizar el perfil del candidato para el documento {document_id}. Causa: {e}")
            return {'success': False, 'message': f'Error interno del servidor: {e}', 'status': 500}

    def delete_file(self, s3_path: str, user_id: int) -> dict:
        try:
            document = self.repo.find_by_storage_path(s3_path)
            if not document:
                return {'success': False, 'message': 'Archivo no encontrado en la base de datos', 'status': 404}

            if not self.aws_service.borrar_archivo(s3_path):
                current_app.logger.warning(f"[ADVERTENCIA] No se pudo eliminar el archivo de S3 en la ruta '{s3_path}'. Se procederá a eliminar los registros de la base de datos de todos modos.")
            
            faiss_idx = get_faiss_index()
            if faiss_idx:
                faiss_idx.remove_ids(np.array([document.id], dtype=np.int64))
                save_faiss_index()
                current_app.logger.debug(f"[DEBUG] Embedding vectorial para el documento {document.id} ha sido eliminado del índice FAISS.")

            self.repo.delete(document)
            return {'success': True, 'message': 'Archivo y todos sus datos asociados han sido eliminados', 'status': 200}
        except Exception as e:
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] Error al intentar eliminar el archivo '{s3_path}'.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            return {'success': False, 'message': f'Error interno del servidor: {e}', 'status': 500}
    
    def delete_all_user_documents(self, user_id: int) -> dict:
        """
        Elimina todos los documentos de un usuario específico incluyendo:
        - Archivos en S3
        - Registros en base de datos
        - Índices vectoriales en FAISS
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            dict: Resultado de la operación con estadísticas
        """
        try:
            # Obtener todos los documentos del usuario
            user_documents = self.repo.find_all_by_user_id(user_id)
            
            if not user_documents:
                current_app.logger.info(f"[INFO] No se encontraron documentos para el usuario {user_id}")
                return {
                    'success': True, 
                    'message': 'No hay documentos para eliminar', 
                    'status': 200,
                    'deleted_count': 0
                }

            total_documents = len(user_documents)
            document_ids = [doc.id for doc in user_documents]
            s3_paths = [doc.storage_path for doc in user_documents if doc.storage_path]
            
            current_app.logger.info(
                f"[INFO] Iniciando eliminación completa para usuario {user_id}. "
                f"Documentos a eliminar: {total_documents}"
            )

            # Estadísticas para el resultado
            failed_s3_deletions = 0
            
            # 1. Eliminar archivos de S3
            if s3_paths:
                current_app.logger.debug(f"[DEBUG] Eliminando {len(s3_paths)} archivos de S3")
                failed_s3_deletions = self._delete_s3_files_batch(s3_paths, user_id)
            
            # 2. Eliminar índices FAISS
            if document_ids:
                self._remove_faiss_indices_batch(document_ids)
            
            # 3. Eliminar registros de base de datos (en transacción)
            try:
                self.repo.delete_all_by_user_id(user_id)
                current_app.logger.info(
                    f"[INFO] Eliminados {total_documents} registros de base de datos para usuario {user_id}"
                )
            except Exception as db_error:
                current_app.logger.error(
                    f"[ERROR] Error al eliminar registros de base de datos para usuario {user_id}: {str(db_error)}"
                )
                # Si falla la BD, es un error crítico
                raise db_error

            # Preparar mensaje de resultado
            if failed_s3_deletions == 0:
                message = f'Eliminación completa exitosa: {total_documents} documentos y todos sus datos asociados han sido eliminados'
            else:
                message = f'Eliminación mayormente exitosa: {total_documents} documentos eliminados de BD y FAISS, pero {failed_s3_deletions} archivos no pudieron eliminarse de S3'

            current_app.logger.info(
                f"[ÉXITO] Eliminación completa finalizada para usuario {user_id}. "
                f"Documentos: {total_documents}, Fallos S3: {failed_s3_deletions}"
            )

            return {
                'success': True,
                'message': message,
                'status': 200,
                'deleted_count': total_documents,
                'failed_s3_deletions': failed_s3_deletions
            }

        except Exception as e:
            error_details = traceback.format_exc()
            current_app.logger.error(
                f"[ERROR] Error crítico en eliminación completa para usuario {user_id}.\n"
                f"  [Causa] {str(e)}\n"
                f"  [TRACEBACK]\n{error_details}"
            )
            return {
                'success': False, 
                'message': f'Error interno del servidor durante eliminación completa: {str(e)}', 
                'status': 500
            }

    def _delete_s3_files_batch(self, s3_paths: list, user_id: int) -> int:
        """
        Elimina múltiples archivos de S3 en lote.
        
        Args:
            s3_paths (list): Lista de rutas S3 a eliminar
            user_id (int): ID del usuario (para logging)
            
        Returns:
            int: Número de eliminaciones fallidas
        """
        failed_count = 0
        
        try:
            # Si el servicio AWS soporta eliminación en lote, úsalo
            if hasattr(self.aws_service, 'borrar_archivos_lote'):
                failed_paths = self.aws_service.borrar_archivos_lote(s3_paths)
                failed_count = len(failed_paths)
                
                if failed_count > 0:
                    current_app.logger.warning(
                        f"[ADVERTENCIA] {failed_count} archivos no pudieron eliminarse de S3 "
                        f"para usuario {user_id}: {failed_paths[:5]}{'...' if len(failed_paths) > 5 else ''}"
                    )
            else:
                # Eliminación individual como fallback
                for s3_path in s3_paths:
                    try:
                        if not self.aws_service.borrar_archivo(s3_path):
                            failed_count += 1
                            current_app.logger.warning(
                                f"[ADVERTENCIA] No se pudo eliminar archivo S3: {s3_path}"
                            )
                    except Exception as e:
                        failed_count += 1
                        current_app.logger.warning(
                            f"[ADVERTENCIA] Error eliminando archivo S3 {s3_path}: {str(e)}"
                        )
                        
        except Exception as e:
            current_app.logger.error(
                f"[ERROR] Error crítico eliminando archivos S3 para usuario {user_id}: {str(e)}"
            )
            failed_count = len(s3_paths)  # Asumimos que todos fallaron
        
        return failed_count

    def _remove_faiss_indices_batch(self, document_ids: list):
        """
        Elimina múltiples índices FAISS en lote.
        
        Args:
            document_ids (list): Lista de IDs de documentos
        """
        try:
            faiss_idx = get_faiss_index()
            if faiss_idx and document_ids:
                # Convertir a numpy array como requiere FAISS
                ids_array = np.array(document_ids, dtype=np.int64)
                faiss_idx.remove_ids(ids_array)
                save_faiss_index()
                
                current_app.logger.debug(
                    f"[DEBUG] Eliminados {len(document_ids)} embeddings vectoriales del índice FAISS"
                )
            else:
                current_app.logger.warning(
                    "[ADVERTENCIA] Índice FAISS no disponible para eliminación de embeddings"
                )
                
        except Exception as e:
            current_app.logger.error(
                f"[ERROR] Error eliminando índices FAISS: {str(e)}. "
                f"IDs afectados: {document_ids[:10]}{'...' if len(document_ids) > 10 else ''}"
            )
            # No re-lanzamos la excepción porque FAISS no es crítico para la operación
            
    def get_pdf_url(self, user_id: int, filename: str) -> dict:
        document = self.repo.find_by_filename_and_user(filename, user_id)
        if not document:
            return {'success': False}
        file_url = self.aws_service.get_file_url(document.storage_path)
        return {'success': True, 'file_url': file_url}

    def get_all_documents(self):
        return self.repo.find_all()

    def create_candidate_from_text(self, text: str, document_id: int) -> Candidate | None:
        profile_data = self.rewrite_service.structure_profile(text)
        if not profile_data or "Nombre completo" not in profile_data:
            current_app.logger.error(f"[ERROR] No se pudo crear el candidato para el documento {document_id}. Razón: Los datos estructurados por la IA fueron insuficientes o no contenían un 'Nombre completo'.")
            return None
        
        return self.repo.create_candidate(profile_data, document_id)

    def cleanup_temp_file(self, filename: str):
        try:
            temp_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(temp_path):
                os.remove(temp_path)
                current_app.logger.debug(f"[DEBUG] Archivo temporal eliminado: '{temp_path}'.")
        except Exception as e:
            current_app.logger.error(f"[ERROR] No se pudo eliminar el archivo temporal '{filename}'. Causa: {e}.")

    def _clean_intermediate_files(self, original_filename):
        self.cleanup_temp_file(original_filename)

    def _is_valid_pdf(self, file_path: str) -> bool:
        try:
            with open(file_path, 'rb') as file:
                PyPDF2.PdfReader(file)
            return True
        except Exception:
            return False

    def _extract_text_pypdf2(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                return ''.join(page.extract_text() or '' for page in reader.pages).strip()
        except Exception as e:
            current_app.logger.error(f"[ERROR] Fallo en la extracción de texto con PyPDF2 para el archivo '{os.path.basename(file_path)}'. Causa: {e}.")
            return ""

    def _save_embedding_to_faiss(self, document_id, embedding_list):
        try:
            faiss_idx = get_faiss_index()
            if not faiss_idx: 
                current_app.logger.warning(f"[ADVERTENCIA] No se encontró un índice FAISS activo. El embedding vectorial para el documento {document_id} no será guardado.")
                return

            embedding_vector_np = np.array(embedding_list).astype('float32').reshape(1, -1)
            faiss_idx.add_with_ids(embedding_vector_np, np.array([document_id], dtype=np.int64))
            save_faiss_index()

            vector_embedding_record = VectorEmbedding(
                document_id=document_id, faiss_index_id=document_id,
                embedding_model=current_app.config['OPENAI_EMBEDDING_MODEL']
            )
            self.repo.save_vector_embedding(vector_embedding_record)
            current_app.logger.debug(f"[DEBUG] Embedding vectorial para el documento {document_id} guardado en FAISS y su registro en la DB.")
        except Exception as e:
            current_app.logger.error(f"[ERROR] Fallo al guardar el embedding para el documento {document_id}. Causa: {e}.")

    def _create_search_document_for_candidate(self, candidate: Candidate) -> str:
        """
        Crea una cadena de texto optimizada para la búsqueda semántica a partir de un perfil de candidato.
        """
        if not candidate:
            return ""

        # Concatenamos solo los campos más relevantes para una búsqueda de RRHH.
        puesto = candidate.puesto_actual or "No especificado"
        habilidad_principal = candidate.habilidad_principal or "No especificada"
        
        # Unimos las habilidades clave en una cadena legible.
        habilidades_clave = ", ".join(candidate.habilidades_clave) if candidate.habilidades_clave else "No especificadas"
        
        # Usamos la descripción profesional que es rica en contexto.
        descripcion = candidate.descripcion_profesional or ""

        # Construimos el documento final para el embedding.
        search_document = (
            f"Puesto: {puesto}. "
            f"Habilidad principal: {habilidad_principal}. "
            f"Habilidades clave: {habilidades_clave}. "
            f"Resumen profesional: {descripcion}"
        )
        
        current_app.logger.debug(f"Documento de búsqueda creado para embedding (Doc ID: {candidate.document_id}): {search_document[:200]}...")
        return search_document
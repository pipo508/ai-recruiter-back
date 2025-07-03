from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.services.DocumentService import DocumentService
from app.middleware import require_auth
import os
import traceback


bp = Blueprint('document', __name__, static_folder='static')
UPLOAD_FOLDER = 'Uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@bp.route('/process-pdfs', methods=['POST'])
@require_auth
def process_pdfs():
    """Procesa PDFs y emite logs claros sin ruido externo."""
    
    # LOGS INMEDIATOS PARA DEBUGGING
    print("🔥 INICIO DEL ENDPOINT process_pdfs", flush=True)
    current_app.logger.critical("🔥 INICIO DEL ENDPOINT process_pdfs")
    
    user_id_form = request.form.get("user_id")
    ai_plus_enabled = request.form.get("ai_enabled", "false").lower() == "true"
    
    # Logs con print Y logger para asegurar visibilidad
    print(f"📋 DATOS RECIBIDOS - user_id: {user_id_form}, ai_plus: {ai_plus_enabled}", flush=True)
    current_app.logger.critical(f"📋 DATOS RECIBIDOS - user_id: {user_id_form}, ai_plus: {ai_plus_enabled}")
    
    current_app.logger.info(f"[INFO] Inicio de procesamiento de archivos. Endpoint: POST /process-pdfs. User ID: {user_id_form}.")
    current_app.logger.info(f"[INFO] Inicio. user_id={user_id_form}, ai_plus={ai_plus_enabled}")

    try:
        # Validación de archivos
        if "files[]" not in request.files or not request.files.getlist("files[]"):
            print("❌ ERROR: No se encontraron archivos en la request", flush=True)
            current_app.logger.warning("[WARN] La solicitud no contenía archivos.")
            return jsonify(error="No se encontraron archivos"), 400

        if not user_id_form:
            print("❌ ERROR: Falta user_id", flush=True)
            current_app.logger.warning("[WARN] Falta user_id.")
            return jsonify(error="user_id requerido"), 400

        user_id = int(user_id_form)
        if user_id != request.user["user_id"]:
            print(f"❌ ERROR: user_id no coincide. Token: {request.user['user_id']}, Form: {user_id}", flush=True)
            current_app.logger.error("[ERROR] user_id del token ≠ formulario")
            return jsonify(error="No autorizado"), 403

        files = request.files.getlist("files[]")
        print(f"📁 ARCHIVOS DETECTADOS: {len(files)}", flush=True)
        current_app.logger.critical(f"📁 ARCHIVOS DETECTADOS: {len(files)}")
        
        # Mostrar nombres de archivos
        for i, f in enumerate(files):
            print(f"  📄 Archivo {i+1}: {f.filename}", flush=True)
            current_app.logger.critical(f"  📄 Archivo {i+1}: {f.filename}")

        doc_service = DocumentService(os.getenv("AWS_BUCKET"))
        processed, failed, needs_vision = [], [], []

        current_app.logger.info(f"[INFO] Procesando {len(files)} archivo(s)…")

        for i, f in enumerate(files):
            if f.filename == "":
                print(f"⚠️  Archivo {i+1}: filename vacío, saltando", flush=True)
                continue
                
            filename = secure_filename(f.filename)
            print(f"🔄 PROCESANDO Archivo {i+1}/{len(files)}: '{filename}'", flush=True)
            current_app.logger.critical(f"🔄 PROCESANDO Archivo {i+1}/{len(files)}: '{filename}'")

            try:
                path = os.path.join(UPLOAD_FOLDER, filename)
                print(f"💾 Guardando archivo en: {path}", flush=True)
                
                f.save(path)
                current_app.logger.critical(f"[P2] Llamando a DocumentService para '{filename}'")
                
                print(f"🤖 Llamando a DocumentService.process_pdf()", flush=True)
                res = doc_service.process_pdf(
                    path, user_id, filename,
                    use_vision=False, ai_plus_enabled=ai_plus_enabled
                )

                if res.get("success"):
                    print(f"✅ ÉXITO: {filename} procesado correctamente", flush=True)
                    processed.append(res["document"])
                elif res.get("needs_vision"):
                    print(f"👁️  VISION REQUERIDA: {filename}", flush=True)
                    needs_vision.append({
                        "filename": filename,
                        "reason": res["reason"],
                        "temp_path_id": os.path.basename(path),
                    })
                else:
                    print(f"❌ FALLÓ: {filename} - {res.get('reason', 'Error desconocido')}", flush=True)
                    failed.append({
                        "filename": res.get("filename", filename),
                        "reason": res.get("reason", "Error desconocido"),
                    })

            except Exception as e:
                tb = traceback.format_exc()
                print(f"💥 EXCEPCIÓN en '{filename}': {e}", flush=True)
                current_app.logger.error(f"[ERROR] Falla '{filename}': {e}\n{tb}")
                failed.append({"filename": filename, "reason": str(e)})

        summary = f"OK: {len(processed)}, Visión: {len(needs_vision)}, Fallidos: {len(failed)}"
        print(f"📊 RESUMEN FINAL: {summary}", flush=True)
        current_app.logger.info(f"[FIN] {summary}")

        resp = {
            "message": summary,
            "processed": processed,
            "needs_vision": needs_vision,
            "failed": failed,
        }

        if not processed and not failed and needs_vision:
            print("🔄 Devolviendo 202 - Requiere Vision", flush=True)
            return jsonify(resp), 202  # requiere acción Vision

        print("✅ Devolviendo 200 - Proceso completado", flush=True)
        return jsonify(resp), 200

    except Exception as e:
        tb = traceback.format_exc()
        print(f"💥 ERROR FATAL en /process-pdfs: {e}", flush=True)
        current_app.logger.error(f"[FATAL] /process-pdfs: {e}\n{tb}")
        return jsonify(error="Error interno", details=str(e)), 500
    

    
@bp.route('/process-with-vision', methods=['POST'])
@require_auth
def process_with_vision():
    data = request.get_json() or {}
    user_id_json = data.get('user_id')
    temp_path_id = data.get('temp_path_id')
    current_app.logger.info(f"[INFO] Inicio de procesamiento con Vision. Endpoint: POST /process-with-vision. User ID: {user_id_json}, Archivo: {temp_path_id}.")
    
    try:
        if not temp_path_id or not user_id_json:
            current_app.logger.warning("[ADVERTENCIA] Solicitud a /process-with-vision con datos faltantes.")
            return jsonify({'error': 'Se requiere temp_path_id y user_id'}), 400
        
        user_id = int(user_id_json)
        if user_id != request.user['user_id']:
            current_app.logger.error(f"[ERROR] Conflicto de autorización en POST /process-with-vision. ID de token: {request.user['user_id']}, ID de JSON: {user_id}.")
            return jsonify({'error': 'No autorizado: el user_id no coincide con el del token'}), 403

        temp_path = os.path.join(UPLOAD_FOLDER, temp_path_id)
        if not os.path.exists(temp_path):
            current_app.logger.warning(f"[ADVERTENCIA] Archivo no encontrado para procesamiento con Vision. ID de ruta temporal: '{temp_path_id}'. Posible causa: el archivo expiró o nunca existió.")
            return jsonify({'error': 'El archivo temporal no existe o ha expirado'}), 404

        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.process_pdf(temp_path, user_id, temp_path_id, use_vision=True)
        
        if result['success']:
            current_app.logger.info(f"[ÉXITO] Documento procesado correctamente con Vision. Archivo: '{temp_path_id}'.")
            return jsonify({'success': True, 'message': 'Documento procesado correctamente con Vision', 'document': result['document']}), 200
        else:
            current_app.logger.error(f"[ERROR] Falló el procesamiento con Vision para el archivo '{temp_path_id}'. Causa: {result.get('reason')}.")
            return jsonify({'success': False, 'message': 'No se pudo procesar el documento con Vision', 'reason': result.get('reason')}), 400
            
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint POST /process-with-vision.\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/skip-vision-processing', methods=['POST'])
@require_auth
def skip_vision_processing():
    temp_path_id = (request.get_json() or {}).get('temp_path_id')
    current_app.logger.info(f"[INFO] Solicitud para omitir Vision y limpiar archivo. Endpoint: POST /skip-vision-processing. Archivo: {temp_path_id}.")
    
    try:
        if not temp_path_id:
            return jsonify({'error': 'Se requiere temp_path_id'}), 400
        
        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        doc_service.cleanup_temp_file(temp_path_id)
        
        current_app.logger.info(f"[INFO] Procesamiento con Vision omitido. Archivo temporal '{temp_path_id}' ha sido eliminado.")
        return jsonify({'success': True, 'message': 'Procesamiento con Vision cancelado y archivo temporal eliminado'}), 200
    
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint POST /skip-vision-processing.\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/<int:document_id>', methods=['GET'])
@require_auth
def get_document(document_id):
    current_app.logger.info(f"[INFO] Solicitud de obtención de documento. Endpoint: GET /document/{document_id}. User ID: {request.user['user_id']}.")
    
    try:
        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.get_document_details(document_id, request.user['user_id'])

        if not result['success']:
            # El servicio ya debería haber logueado la razón específica (403, 404).
            return jsonify({'error': result['message']}), result['status']
            
        return jsonify(result['data']), 200
    
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint GET /document/{document_id}.\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/<int:document_id>', methods=['PUT'])
@require_auth
def update_document(document_id):
    current_app.logger.info(f"[INFO] Solicitud de actualización de documento. Endpoint: PUT /document/{document_id}. User ID: {request.user['user_id']}.")
    
    try:
        new_data = request.get_json()
        if not new_data:
            current_app.logger.warning(f"[ADVERTENCIA] Solicitud PUT a /document/{document_id} sin datos en el cuerpo.")
            return jsonify({'error': 'No se proporcionaron datos para actualizar'}), 400
            
        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.update_candidate_profile(document_id, new_data, request.user['user_id'])

        if not result['success']:
            return jsonify({'error': result['message']}), result['status']

        current_app.logger.info(f"[ÉXITO] Documento ID {document_id} actualizado correctamente.")
        return jsonify(result['data']), 200
    
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint PUT /document/{document_id}.\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/delete-file', methods=['DELETE'])
@require_auth
def delete_file():
    s3_path = (request.get_json() or {}).get('s3_path')
    current_app.logger.info(f"[INFO] Solicitud de eliminación de archivo. Endpoint: DELETE /delete-file. User ID: {request.user['user_id']}. Ruta S3: '{s3_path}'.")
    
    try:
        if not s3_path:
            return jsonify({'error': 'El campo s3_path es requerido'}), 400

        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.delete_file(s3_path, request.user['user_id'])
        
        if result['success']:
            current_app.logger.info(f"[ÉXITO] Finaliza la operación de borrado para la ruta '{s3_path}'. Mensaje: {result['message']}")
        else:
            # El servicio ya logueó el error específico.
            current_app.logger.warning(f"[ADVERTENCIA] Finaliza la operación de borrado para '{s3_path}' sin éxito. Mensaje: {result['message']}")

        return jsonify({'success': result['success'], 'message': result['message']}), result['status']
    
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint DELETE /delete-file.\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


@bp.route('/delete-all', methods=['DELETE'])
@require_auth
def delete_all():
    """
    Elimina todos los documentos del usuario, sus archivos en S3 e índices FAISS.
    Requiere confirmación explícita del usuario.
    """
    request_data = request.get_json() or {}
    confirmation = request_data.get('confirmation')
    user_id = request.user['user_id']
    
    current_app.logger.info(
        f"[INFO] Solicitud de eliminación completa. Endpoint: DELETE /delete-all. "
        f"User ID: {user_id}. Confirmación: {confirmation is not None}"
    )
    
    try:
        # Validar confirmación explícita
        if not confirmation or confirmation != "DELETE_ALL_DOCUMENTS":
            return jsonify({
                'error': 'Confirmación requerida',
                'message': 'Para eliminar todos los documentos, debe incluir "confirmation": "DELETE_ALL_DOCUMENTS" en el cuerpo de la solicitud'
            }), 400

        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.delete_all_user_documents(user_id)
        
        if result['success']:
            current_app.logger.info(
                f"[ÉXITO] Eliminación completa exitosa para el usuario {user_id}. "
                f"Documentos eliminados: {result.get('deleted_count', 0)}. "
                f"Mensaje: {result['message']}"
            )
        else:
            current_app.logger.warning(
                f"[ADVERTENCIA] Eliminación completa falló para el usuario {user_id}. "
                f"Mensaje: {result['message']}"
            )

        return jsonify({
            'success': result['success'], 
            'message': result['message'],
            'deleted_count': result.get('deleted_count', 0),
            'failed_s3_deletions': result.get('failed_s3_deletions', 0)
        }), result['status']
    
    except Exception as e:
        error_details = traceback.format_exc()
        current_app.logger.error(
            f"[ERROR] Error fatal en el endpoint DELETE /delete-all.\n"
            f"  [Usuario] {user_id}\n"
            f"  [Causa] {str(e)}\n"
            f"  [TRACEBACK]\n{error_details}"
        )
        return jsonify({
            'error': 'Error interno del servidor', 
            'details': str(e)
        }), 500

@bp.route('/list', methods=['GET'])
@require_auth
def list_documents():
    current_app.logger.info("[INFO] Solicitud para listar todos los documentos. Endpoint: GET /list.")
    try:
        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        docs = doc_service.get_all_documents()
        return jsonify([doc.to_dict() for doc in docs]), 200
    except Exception as e:
        current_app.logger.error(f"[ERROR] No se pudieron listar los documentos. Endpoint: GET /list. Causa: {str(e)}")
        return jsonify({'error': 'No se pudieron obtener los documentos'}), 500


@bp.route('/get-pdf', methods=['GET'])
@require_auth
def get_pdf():
    user_id = request.args.get('user_id', type=int)
    filename = request.args.get('filename', type=str)
    current_app.logger.info(f"[INFO] Solicitud de URL de PDF. Endpoint: GET /get-pdf. User ID: {user_id}, Archivo: {filename}.")
    
    try:
        if not user_id or not filename:
            return jsonify({'error': 'Faltan parámetros user_id o filename'}), 400
        doc_service = DocumentService(os.getenv('AWS_BUCKET'))
        result = doc_service.get_pdf_url(user_id, filename)

        if not result['success']:
            return jsonify({'error': 'Documento no encontrado'}), 404

        return jsonify({'success': True, 'file_url': result['file_url']})
    
    except Exception as e:
        current_app.logger.error(f"[ERROR] No se pudo obtener la URL del PDF. Endpoint: GET /get-pdf. Causa: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@bp.route('/upload-form', methods=['GET'])
def upload_form():
    """Sirve un formulario HTML simple para pruebas de carga de archivos."""
    return send_from_directory('static', 'upload_pdf.html')


@bp.route('/prueba', methods=['GET'])
def prueba():
    """Endpoint de prueba para verificar que el controlador está activo."""
    current_app.logger.info("[INFO] Endpoint de prueba invocado: GET /prueba.")
    return jsonify({'message': 'Endpoint de prueba del controlador de documentos funcionando correctamente'})
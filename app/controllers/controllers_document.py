from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.services.document_service import DocumentService
from app.middleware import require_auth
import os
import traceback

bp = Blueprint('document', __name__, static_folder='static')
UPLOAD_FOLDER = 'Uploads'
TEXTOS_EXTRAIDOS = 'textos_extraidos'
PDF_REESCRITOS = 'pdf_reescritos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEXTOS_EXTRAIDOS, exist_ok=True)
os.makedirs(PDF_REESCRITOS, exist_ok=True)

def clean_intermediate_files(original_filename, extracted_filename=None):
    """
    Elimina los archivos intermedios una vez que se ha completado el proceso
    y el archivo está en la carpeta final pdf_reescritos.
    """
    try:
        upload_path = os.path.join(UPLOAD_FOLDER, original_filename)
        if os.path.exists(upload_path):
            os.remove(upload_path)
            current_app.logger.info(f"Archivo original eliminado: {upload_path}")
        if extracted_filename:
            extracted_path = os.path.join(TEXTOS_EXTRAIDOS, extracted_filename)
            if os.path.exists(extracted_path):
                os.remove(extracted_path)
                current_app.logger.info(f"Archivo de texto extraído eliminado: {extracted_path}")
    except Exception as e:
        current_app.logger.error(f"Error al eliminar archivos intermedios: {str(e)}")

@bp.route('/process-pdfs', methods=['POST'])
@require_auth
def process_pdfs():
    try:
        current_app.logger.info(f"Recibida solicitud POST a /document/process-pdfs con user_id: {request.form.get('user_id')}")
        current_app.logger.info(f"Archivos recibidos: {[file.filename for file in request.files.getlist('files[]')]}")

        if 'files[]' not in request.files:
            return jsonify({'error': 'No se encontraron archivos'}), 400
        user_id = request.form.get('user_id')
        if not user_id:
            return jsonify({'error': 'Se requiere user_id'}), 400
        user_id = int(user_id)
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado: user_id no coincide'}), 403

        files = request.files.getlist('files[]')
        aws_bucket = os.getenv('AWS_BUCKET')
        doc_service = DocumentService(aws_bucket)

        processed_documents = []
        failed_documents = []
        needs_vision_documents = []
        rewritten_files = []

        for file in files:
            if file.filename == '':
                continue
            try:
                filename = secure_filename(file.filename)
                temp_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(temp_path)

                result = doc_service.process_pdf(temp_path, user_id, filename, use_vision=False)

                if result['success']:
                    doc_info = result['document']
                    processed_documents.append(doc_info)
                    rewritten_files.append(result['rewritten_file'])
                    extracted_filename = None
                    if 'extracted_filename' in result:
                        extracted_filename = result['extracted_filename']
                    elif 'extracted_text_path' in result:
                        extracted_filename = os.path.basename(result['extracted_text_path'])
                    clean_intermediate_files(filename, extracted_filename)
                elif result.get('needs_vision', False):
                    needs_vision_documents.append({
                        'filename': filename,
                        'temp_path': temp_path,
                        'reason': result['reason']
                    })
                else:
                    failed_documents.append({
                        'filename': result['filename'],
                        'reason': result['reason']
                    })
                    if os.path.exists(temp_path): os.remove(temp_path)
            except Exception as e:
                current_app.logger.error(f"Error procesando archivo {file.filename}: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                failed_documents.append({'filename': file.filename, 'reason': str(e)})
                temp_path = locals().get('temp_path')
                if temp_path and os.path.exists(temp_path): os.remove(temp_path)

        if not needs_vision_documents:
            try:
                for f in os.listdir(UPLOAD_FOLDER):
                    if f.endswith('.pdf'):
                        os.remove(os.path.join(UPLOAD_FOLDER, f))
            except Exception as e:
                current_app.logger.warning(f"Error al limpiar carpetas: {str(e)}")

        def safe_dict(d):
            return {k: (v if isinstance(v, (str, int, float, bool)) else str(v) if v is not None else "") for k, v in d.items()}

        response = {
            'message': f"Procesados {len(processed_documents)} documentos, requieren Vision {len(needs_vision_documents)}, fallidos {len(failed_documents)}, reescritos {len(rewritten_files)}",
            'processed': [safe_dict(doc) for doc in processed_documents],
            'needs_vision': [{'filename': d['filename'], 'reason': d['reason'], 'temp_path_id': os.path.basename(d['temp_path'])} for d in needs_vision_documents],
            'failed': [safe_dict(doc) for doc in failed_documents],
            'rewritten': [safe_dict(file) for file in rewritten_files]
        }
        return jsonify(response), 200
    except Exception as e:
        current_app.logger.error(f"Error general en process_pdfs: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@bp.route('/process-with-vision', methods=['POST'])
@require_auth
def process_with_vision():
    try:
        current_app.logger.info("Recibida solicitud para procesar con Vision")
        data = request.get_json() or {}
        temp_path_id = data.get('temp_path_id')
        user_id = data.get('user_id')
        if not temp_path_id or not user_id:
            return jsonify({'error': 'Se requiere temp_path_id y user_id'}), 400
        user_id = int(user_id)
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado: user_id no coincide'}), 403

        aws_bucket = os.getenv('AWS_BUCKET')
        doc_service = DocumentService(aws_bucket)
        temp_path = os.path.join(UPLOAD_FOLDER, temp_path_id)
        if not os.path.exists(temp_path):
            return jsonify({'error': 'El archivo temporal no existe o expiró'}), 404

        result = doc_service.process_pdf(temp_path, user_id, temp_path_id, use_vision=True)
        if result['success']:
            clean_intermediate_files(temp_path_id)
            doc_info = result['document']
            return jsonify({'success': True, 'message': 'Documento procesado correctamente con Vision', 'document': {k: v for k, v in doc_info.items()}, 'vision_used': True, 'rewritten': [result.get('rewritten_file', {})]}), 200
        else:
            if os.path.exists(temp_path): os.remove(temp_path)
            return jsonify({'success': False, 'message': 'No se pudo procesar el documento con Vision', 'reason': result.get('reason', 'Error desconocido')}), 200
    except Exception as e:
        current_app.logger.error(f"Error en process_with_vision: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@bp.route('/skip-vision-processing', methods=['POST'])
@require_auth
def skip_vision_processing():
    try:
        data = request.get_json() or {}
        temp_path_id = data.get('temp_path_id')
        if not temp_path_id:
            return jsonify({'error': 'Se requiere temp_path_id'}), 400
        temp_path = os.path.join(UPLOAD_FOLDER, temp_path_id)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            current_app.logger.info(f"Archivo temporal eliminado: {temp_path}")
        return jsonify({'success': True, 'message': 'Procesamiento con Vision cancelado y archivo temporal eliminado'}), 200
    except Exception as e:
        current_app.logger.error(f"Error en skip_vision_processing: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@bp.route('/download-rewritten/<filename>', methods=['GET'])
@require_auth
def download_rewritten(filename):
    try:
        safe_filename = secure_filename(filename)
        file_path = os.path.join(PDF_REESCRITOS, safe_filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Archivo no encontrado'}), 404
        return send_from_directory(directory=PDF_REESCRITOS, path=safe_filename, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error al descargar archivo: {str(e)}")
        return jsonify({'error': 'Error al descargar archivo'}), 500

@bp.route('/upload-form', methods=['GET'])
def upload_form():
    return send_from_directory('static', 'upload_pdf.html')

@bp.route('/prueba', methods=['GET'])
def prueba():
    return jsonify({'message': 'Endpoint de prueba funcionando correctamente'})

@bp.route('/get-pdf', methods=['GET'])
@require_auth
def get_pdf():
    try:
        user_id = request.args.get('user_id', type=int)
        filename = request.args.get('filename', type=str)

        if not user_id or not filename:
            return jsonify({'error': 'Faltan parámetros user_id o filename'}), 400

        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado: user_id no coincide'}), 403

        aws_bucket = os.getenv('AWS_BUCKET')
        doc_service = DocumentService(aws_bucket)
        result = doc_service.get_pdf(user_id, filename)

        if not result['success']:
            return jsonify({'error': 'Documento no encontrado'}), 404

        return jsonify({
            'success': True,
            'file_url': result['file_url'],
            'filename': filename
        })
    except Exception as e:
        current_app.logger.error(f"Error en get_pdf: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@bp.route('/list', methods=['GET'])
@require_auth
def list_documents():
    try:
        aws_bucket = os.getenv('AWS_BUCKET')
        doc_service = DocumentService(aws_bucket)

        docs = doc_service.get_all_documents()  # ✅ sin user_id
        return jsonify([doc.to_dict() for doc in docs]), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error en list_documents: {str(e)}")
        return jsonify({'error': 'No se pudieron obtener los documentos'}), 500

@bp.route('/delete-file', methods=['DELETE'])
@require_auth
def delete_file():
    try:
        current_app.logger.info("Recibida solicitud para eliminar archivo de S3 y base de datos")
        data = request.get_json() or {}
        s3_path = data.get('s3_path')

        current_app.logger.info(f"Delete file received s3_path: {s3_path}")  # <---- Aquí

        if not s3_path:
            return jsonify({'error': 'Se requiere s3_path', 'status': 400}), 400

        user_id = request.user['user_id']

        aws_bucket = os.getenv('AWS_BUCKET')
        doc_service = DocumentService(aws_bucket)
        
        result = doc_service.delete_file(s3_path, user_id)

        return jsonify({
            'success': result['success'],
            'message': result['message']
        }), result['status']

    except Exception as e:
        current_app.logger.error(f"Error en delete_file: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e), 'status': 500}), 500

from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.services.document_service import DocumentService
import os
import traceback

bp = Blueprint('document', __name__, static_folder='static')
UPLOAD_FOLDER = 'Uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@bp.route('/process-pdfs', methods=['POST'])
def process_pdfs():
    try:
        current_app.logger.info(f"Recibida solicitud POST a /document/process-pdfs con user_id: {request.form.get('user_id')}")
        current_app.logger.info(f"Archivos recibidos: {[file.filename for file in request.files.getlist('files[]')]}")

        if 'files[]' not in request.files:
            return jsonify({'error': 'No se encontraron archivos'}), 400

        if not request.form.get('user_id'):
            return jsonify({'error': 'Se requiere user_id'}), 400

        user_id = request.form.get('user_id')
        files = request.files.getlist('files[]')

        processed_documents = []
        duplicate_documents = []
        failed_documents = []
        needs_vision_documents = []  # Nuevo: documentos que necesitan procesamiento con Vision

        doc_service = DocumentService()

        for file in files:
            if file.filename == '':
                continue

            try:
                filename = secure_filename(file.filename)
                temp_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(temp_path)

                # Parámetro use_vision inicialmente en False
                result = doc_service.process_pdf(temp_path, int(user_id), filename)

                if result['success']:
                    processed_documents.append(result['document'])
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                elif result.get('duplicate', False):
                    duplicate_documents.append({
                        'filename': filename,
                        'existing_document': result.get('document', {}),
                        'reason': result['reason']
                    })
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                
                # Nuevo: detectar documentos que necesitan Vision
                elif result.get('needs_vision', False):
                    needs_vision_documents.append({
                        'filename': filename,
                        'temp_path': temp_path,  # Guardar la ruta temporal para procesamiento posterior
                        'reason': result['reason']
                    })

                else:
                    failed_documents.append({
                        'filename': result['filename'],
                        'reason': result['reason']
                    })
                    # Limpiar archivo temporal si existe
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

            except Exception as e:
                current_app.logger.error(f"Error procesando archivo {file.filename}: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                failed_documents.append({
                    'filename': file.filename,
                    'reason': str(e)
                })
                # Asegurar limpieza del archivo temporal en caso de error
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)

        # Preparar respuestas seguras para serialización
        def safe_dict(d):
            return {k: (v if isinstance(v, (str, int, float, bool)) else str(v) if v is not None else "") for k, v in d.items()}

        serializable_processed = [safe_dict(doc) for doc in processed_documents]
        serializable_duplicates = [
            {
                'filename': doc['filename'],
                'reason': doc['reason'],
                'existing_document': safe_dict(doc['existing_document'])
            } for doc in duplicate_documents
        ]
        serializable_failed = [safe_dict(doc) for doc in failed_documents]
        
        # Preparar lista de documentos que necesitan Vision, excluyendo la ruta temporal del JSON
        serializable_needs_vision = []
        for doc in needs_vision_documents:
            temp_path = doc.pop('temp_path', None)  # Quitar de la respuesta JSON pero conservar el valor
            serializable_needs_vision.append({
                'filename': doc['filename'],
                'reason': doc['reason'],
                'temp_path_id': os.path.basename(temp_path) if temp_path else None  # Usar solo el nombre del archivo como ID
            })

        response = {
            'message': f'Procesados {len(serializable_processed)} documentos, duplicados {len(serializable_duplicates)}, ' +
                      f'requieren Vision {len(serializable_needs_vision)}, fallidos {len(serializable_failed)}',
            'processed': serializable_processed,
            'duplicates': serializable_duplicates,
            'needs_vision': serializable_needs_vision,
            'failed': serializable_failed
        }

        return jsonify(response)

    except Exception as e:
        current_app.logger.error(f"Error general en process_pdfs: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(e)
        }), 500


@bp.route('/process-with-vision', methods=['POST'])
def process_with_vision():
    """
    Endpoint para procesar un PDF con OpenAI Vision que previamente falló con extracción normal.
    Espera un ID de archivo temporal y el ID de usuario.
    """
    try:
        current_app.logger.info(f"Recibida solicitud para procesar con Vision")
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Se requieren datos en formato JSON'}), 400
            
        temp_path_id = data.get('temp_path_id')
        user_id = data.get('user_id')
        
        if not temp_path_id or not user_id:
            return jsonify({'error': 'Se requiere temp_path_id y user_id'}), 400
            
        # Reconstruir la ruta completa al archivo temporal
        temp_path = os.path.join(UPLOAD_FOLDER, temp_path_id)
        
        # Verificar si el archivo existe
        if not os.path.exists(temp_path):
            return jsonify({'error': 'El archivo temporal no existe o expiró'}), 404
            
        # Procesar con Vision
        doc_service = DocumentService()
        result = doc_service.process_pdf(temp_path, int(user_id), temp_path_id, use_vision=True)
        
        # Devolver resultados según el procesamiento
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Documento procesado correctamente con Vision',
                'document': result['document'],
                'vision_used': True
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No se pudo procesar el documento con Vision',
                'reason': result.get('reason', 'Error desconocido')
            })
            
    except Exception as e:
        current_app.logger.error(f"Error en process_with_vision: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(e)
        }), 500


@bp.route('/skip-vision-processing', methods=['POST'])
def skip_vision_processing():
    """
    Endpoint para descartar un PDF que requiere Vision cuando el usuario decide no procesarlo.
    """
    try:
        data = request.get_json()
        if not data or 'temp_path_id' not in data:
            return jsonify({'error': 'Se requiere temp_path_id'}), 400
            
        temp_path_id = data.get('temp_path_id')
        temp_path = os.path.join(UPLOAD_FOLDER, temp_path_id)
        
        # Verificar si el archivo existe y eliminarlo
        if os.path.exists(temp_path):
            os.remove(temp_path)
            current_app.logger.info(f"Archivo temporal eliminado: {temp_path}")
            
        return jsonify({
            'success': True,
            'message': 'Procesamiento con Vision cancelado y archivo temporal eliminado'
        })
            
    except Exception as e:
        current_app.logger.error(f"Error en skip_vision_processing: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Error interno del servidor',
            'details': str(e)
        }), 500


@bp.route('/upload-form', methods=['GET'])
def upload_form():
    return send_from_directory('static', 'upload_pdf.html')

@bp.route('/prueba', methods=['GET'])
def prueba():
    return jsonify({'message': 'Endpoint de prueba funcionando correctamente'})
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.services.document_service import DocumentService
from app.middleware import require_auth
import os
import json
from sqlalchemy.orm.attributes import flag_modified
import collections.abc
from app.extensions import db
from app.services.OpenAIService import OpenAIRewriteService
from app.models.models_document import Document
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
        embedding_files = []

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
                    embedding_files.append({
                        'document_id': doc_info['id'],
                        'embedding_model': current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
                    })
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
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except Exception as e:
                current_app.logger.error(f"Error procesando archivo {file.filename}: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                failed_documents.append({'filename': file.filename, 'reason': str(e)})
                temp_path = locals().get('temp_path')
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

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
            'message': f"Procesados {len(processed_documents)} documentos, requieren Vision {len(needs_vision_documents)}, fallidos {len(failed_documents)}, embeddings {len(embedding_files)}",
            'processed': [safe_dict(doc) for doc in processed_documents],
            'needs_vision': [{'filename': d['filename'], 'reason': d['reason'], 'temp_path_id': os.path.basename(d['temp_path'])} for d in needs_vision_documents],
            'failed': [safe_dict(doc) for doc in failed_documents],
            'embeddings': [safe_dict(file) for file in embedding_files]
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
            return jsonify({
                'success': True,
                'message': 'Documento procesado correctamente con Vision',
                'document': {k: v for k, v in doc_info.items()},
                'vision_used': True,
                'rewritten': [result.get('rewritten_file', {})],
                'embeddings': [result.get('embedding_file', {})]
            }), 200
        else:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({
                'success': False,
                'message': 'No se pudo procesar el documento con Vision',
                'reason': result.get('reason', 'Error desconocido')
            }), 200
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

        docs = doc_service.get_all_documents()
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

        current_app.logger.info(f"Delete file received s3_path: {s3_path}")

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

# controllers_document.py

@bp.route('/<int:document_id>', methods=['GET'])
@require_auth
def get_document(document_id):
    """
    Obtiene un documento por su ID y devuelve la información estructurada del perfil
    desde el modelo Candidate asociado.
    """
    try:
        current_app.logger.info(f"Solicitando documento con ID: {document_id}")
        
        document = Document.query.get(document_id)
        if not document:
            current_app.logger.warning(f"Documento con ID {document_id} no encontrado")
            return jsonify({'error': 'Documento no encontrado'}), 404

        profile_data = None
        # Verificar si ya existe un candidato asociado a este documento
        if document.candidate:
            current_app.logger.info(f"Usando perfil de candidato existente para documento {document_id}")
            profile_data = document.candidate.to_dict()
        else:
            # Si no hay candidato, se puede crear uno a partir del texto reescrito
            try:
                current_app.logger.info(f"No se encontró candidato, generando nuevo perfil para documento {document_id}")
                doc_service = DocumentService(aws_bucket=os.getenv('AWS_BUCKET')) # o inyectar de otra forma
                
                # Se asume que el texto reescrito está disponible
                if document.rewritten_text:
                    # Usar el servicio para crear el candidato y guardarlo en la BD
                    candidate = doc_service.create_candidate_from_text(document.rewritten_text, document.id)
                    if candidate:
                        profile_data = candidate.to_dict()
                        current_app.logger.info(f"Candidato creado y guardado para documento {document_id}")
                    else:
                        profile_data = {} # Falló la creación
                else:
                    profile_data = {} # No hay texto para procesar

            except Exception as e:
                current_app.logger.warning(f"Error al crear el perfil del candidato para documento {document_id}: {str(e)}")
                profile_data = {}

        response_data = {
            'document_id': document.id,
            'user_id': document.user_id,
            'filename': document.filename,
            'profile': profile_data
        }

        current_app.logger.info(f"Devolviendo datos del documento {document_id}")
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener documento {document_id}: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500


# (Añade este código al final de controllers_document.py)

def deep_update(d, u):
    """
    Realiza una actualización profunda (recursiva) de un diccionario.
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


@bp.route('/<int:document_id>', methods=['PUT'])
@require_auth
def update_document(document_id):
    """
    Actualiza el perfil de un candidato existente asociado a un documento.
    Este endpoint recibe un JSON con los campos a actualizar.
    """
    try:
        # --- 1. Buscar el documento y el candidato asociado ---
        document = Document.query.get(document_id)
        if not document:
            return jsonify({'error': 'Documento no encontrado'}), 404

        # --- 2. Verificar Permisos ---
        # Comprueba si el usuario que hace la solicitud es el dueño del documento.
        if document.user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado para modificar este documento'}), 403

        # Accede al perfil del candidato a través de la relación definida en los modelos.
        candidate = document.candidate
        if not candidate:
            return jsonify({'error': 'No existe un perfil de candidato para este documento'}), 404

        # --- 3. Obtener y validar los datos de entrada ---
        new_data = request.get_json()
        if not new_data:
            return jsonify({'error': 'No se proporcionaron datos para actualizar'}), 400

        # --- 4. Mapear claves del JSON a atributos del Modelo ---
        # Este diccionario es clave para traducir las claves del frontend
        # a los nombres de las columnas en la tabla 'candidates'.
        key_to_attribute_map = {
            "Nombre completo": "nombre_completo",
            "Puesto actual": "puesto_actual",
            "Habilidad principal": "habilidad_principal",
            "Años de experiencia total": "anios_experiencia",
            "Cantidad de proyectos/trabajos": "cantidad_proyectos",
            "Descripción profesional": "descripcion_profesional",
            "GitHub": "github",
            "Email": "email",
            "Número de teléfono": "telefono",
            "Ubicación": "ubicacion",
            "Candidato ideal": "candidato_ideal",
            "Habilidades clave": "habilidades_clave", # Campo JSON (lista de strings)
            "Experiencia Profesional": "experiencia_profesional", # Campo JSON (lista de objetos)
            "Educación": "educacion" # Campo JSON (lista de objetos)
        }

        # --- 5. Actualizar el objeto 'candidate' dinámicamente ---
        # Itera sobre los datos recibidos en el JSON de la solicitud.
        for key, value in new_data.items():
            attribute_name = key_to_attribute_map.get(key)
            # Si la clave existe en el mapa y el candidato tiene ese atributo...
            if attribute_name and hasattr(candidate, attribute_name):
                # ...actualiza el atributo con el nuevo valor.
                # setattr() es como hacer 'candidate.nombre_completo = "nuevo valor"'.
                # Funciona perfectamente para campos JSON también.
                setattr(candidate, attribute_name, value)
        
        # Actualiza las fechas de modificación.
        candidate.updated_at = db.func.now()
        document.updated_at = db.func.now()

        # --- 6. Guardar los cambios en la Base de Datos ---
        db.session.commit()

        current_app.logger.info(f"Perfil del candidato para el documento ID {document_id} actualizado exitosamente.")
        
        # Devuelve el perfil completo y actualizado como confirmación.
        return jsonify(candidate.to_dict()), 200

    except Exception as e:
        # Si algo falla, revierte la transacción para no dejar datos corruptos.
        db.session.rollback()
        current_app.logger.error(f"Error al actualizar el candidato para el documento {document_id}: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500
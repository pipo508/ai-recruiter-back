# app/controllers/controllers_user.py

from flask import Blueprint, jsonify, request, current_app
from app.services.UserService import UserService
import jwt
import os
from datetime import datetime, timedelta
from app.Middleware import require_auth
import traceback

bp = Blueprint('user', __name__)

# Configuración usando variables de entorno
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key-for-development')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')

# Validar que la SECRET_KEY esté configurada en producción
if not os.getenv('SECRET_KEY') and os.getenv('FLASK_ENV') == 'production':
    raise ValueError("SECRET_KEY debe estar configurada en producción")

# Los endpoints de register y login ya estaban bien estructurados y se mantienen igual.
@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'email', 'password')):
        return jsonify({'error': 'Datos incompletos'}), 400
    try:
        user_service = UserService()
        user = user_service.register(
            username=data['username'], email=data['email'], password=data['password']
        )
        return jsonify({'message': 'Usuario registrado', 'user': {'id': user.id, 'username': user.username}}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        current_app.logger.error(f"Error en register: {str(e)}")
        return jsonify({'error': 'Error interno al registrar'}), 500

@bp.route('/login', methods=['POST'])
def login():
    current_app.logger.info("=== INICIO LOGIN ===")
    data = request.get_json()
    current_app.logger.info(f"Datos recibidos: {data}")
    
    if not data or not all(k in data for k in ('username', 'password')):
        return jsonify({'error': 'Datos incompletos'}), 400
    
    try:
        current_app.logger.info("Creando UserService...")
        user_service = UserService()
        
        current_app.logger.info(f"Intentando login para usuario: {data['username']}")
        user = user_service.login(username=data['username'], password=data['password'])
        current_app.logger.info(f"Usuario autenticado: {user.id}")
        
        current_app.logger.info("Creando payload JWT...")
        payload = {
            'user_id': user.id, 
            'username': user.username, 
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=10),  # Expira en 10 horas
        }
        current_app.logger.info(f"Payload creado: {payload}")
        
        current_app.logger.info("Generando token JWT...")
        current_app.logger.info(f"SECRET_KEY configurada: {'Sí' if SECRET_KEY else 'No'}")
        current_app.logger.info(f"JWT_ALGORITHM: {JWT_ALGORITHM}")
        
        token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
        current_app.logger.info(f"Token generado exitosamente: {type(token)}")
        
        return jsonify({
            'message': 'Login exitoso', 
            'user': {'id': user.id, 'username': user.username}, 
            'token': token
        })
    except ValueError as e:
        current_app.logger.error(f"Error de validación en login: {str(e)}")
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        current_app.logger.error(f"Error completo en login: {str(e)}")
        current_app.logger.error(f"Tipo de error: {type(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Error interno al autenticar'}), 500

@bp.route('/profile/<int:user_id>', methods=['GET'])
@require_auth
def get_profile(user_id):
    """
    Obtiene el perfil de un usuario. Ahora es más limpio.
    """
    try:
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        # El controlador llama al servicio y recibe un diccionario listo para la respuesta.
        user_profile = UserService().get_profile_with_stats(user_id)
        return jsonify({'user': user_profile})

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error al obtener perfil: {str(e)}")
        return jsonify({'error': 'Error al obtener perfil'}), 500

@bp.route('/profile', methods=['GET'])
@require_auth
def get_all_profiles():
    """
    Devuelve todos los perfiles. Ahora no realiza lógica de BD.
    """
    try:
        # El servicio devuelve una lista de diccionarios lista para ser convertida a JSON.
        all_profiles = UserService().get_all_users_with_stats()
        return jsonify({'users': all_profiles})
    except Exception as e:
        current_app.logger.error(f"Error al obtener todos los perfiles: {str(e)}")
        return jsonify({'error': 'Error al obtener todos los perfiles'}), 500

@bp.route('/profile/<int:user_id>', methods=['PUT'])
@require_auth
def update_profile(user_id):
    """
    Actualiza el perfil de un usuario.
    """
    try:
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        user_service = UserService()
        user = user_service.update_profile(
            user_id=user_id, email=data.get('email'), password=data.get('password')
        )
        # La respuesta se construye con los datos del usuario actualizado.
        return jsonify({
            'message': 'Perfil actualizado correctamente',
            'user': {'id': user.id, 'username': user.username, 'email': user.email}
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400 # 400 para errores de validación
    except Exception as e:
        current_app.logger.error(f"Error al actualizar perfil: {str(e)}")
        return jsonify({'error': 'Error al actualizar el perfil'}), 500
"""
Controlador para la gestión de usuarios.
Maneja registro, autenticación y perfil de usuarios.
"""

from flask import Blueprint, jsonify, request, current_app
from app.services.user_service import UserService
import jwt
from datetime import datetime, timedelta
from app.middleware import require_auth  # Importamos el decorador

bp = Blueprint('user', __name__)

# Configuración de la clave secreta (en producción, usa variables de entorno)
SECRET_KEY = "your-secret-key-12345"  # ¡Cambia esto en producción!
JWT_ALGORITHM = "HS256"

@bp.route('/prueba', methods=['GET'])
def prueba():
    """
    Endpoint de prueba para verificar el funcionamiento del controlador.
    """
    return jsonify({'message': 'Endpoint de prueba funcionando correctamente'})

@bp.route('/register', methods=['POST'])
def register():
    """
    Registra un nuevo usuario en el sistema.
    """
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Datos incompletos. Se requiere username, email y password'}), 400
    
    try:
        user = UserService().register(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )
        return jsonify({
            'message': 'Usuario registrado correctamente',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        current_app.logger.error(f"Error al registrar usuario: {str(e)}")
        return jsonify({'error': 'Error al registrar usuario'}), 500

@bp.route('/login', methods=['POST'])
def login():
    """
    Autentica a un usuario y genera un token JWT.
    """
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Datos incompletos. Se requiere username y password'}), 400
    
    try:
        user = UserService().login(
            username=data['username'],
            password=data['password']
        )
        # Generar el token JWT
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=1)  # Expira en 1 hora
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        return jsonify({
            'message': 'Login exitoso',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            },
            'token': token
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        current_app.logger.error(f"Error al autenticar usuario: {str(e)}")
        return jsonify({'error': 'Error al autenticar usuario'}), 500

@bp.route('/profile/<int:user_id>', methods=['GET'])
@require_auth
def get_profile(user_id):
    """
    Obtiene el perfil de un usuario por su ID.
    """
    try:
        # Verificar que el user_id coincide con el del token
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado: user_id no coincide'}), 403

        user = UserService().get_profile(user_id)
        doc_count = user.documents.count() if hasattr(user, 'documents') else 0
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'stats': {
                    'documents': doc_count
                }
            }
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error al obtener perfil: {str(e)}")
        return jsonify({'error': 'Error al obtener perfil'}), 500

@bp.route('/profile', methods=['GET'])
@require_auth
def get_all_profiles():
    """
    Devuelve todos los perfiles de usuario con estadísticas básicas.
    """
    try:
        users = UserService().get_all_users()
        all_profiles = []

        for user in users:
            doc_count = user.documents.count() if hasattr(user, 'documents') else 0

            profile = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'stats': {
                    'documents': doc_count
                }
            }
            all_profiles.append(profile)

        return jsonify({'users': all_profiles})

    except Exception as e:
        current_app.logger.error(f"Error al obtener todos los perfiles: {str(e)}")
        return jsonify({'error': 'Error al obtener todos los perfiles'}), 500

@bp.route('/profile/<int:user_id>', methods=['PUT'])
@require_auth
def update_profile(user_id):
    """
    Actualiza el perfil de un usuario por su ID.
    """
    try:
        # Verificar que el user_id coincide con el del token
        if user_id != request.user['user_id']:
            return jsonify({'error': 'No autorizado: user_id no coincide'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos para actualizar'}), 400
        
        user = UserService().update_profile(
            user_id=user_id,
            email=data.get('email'),
            password=data.get('password')
        )
        return jsonify({
            'message': 'Perfil actualizado correctamente',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        current_app.logger.error(f"Error al actualizar perfil: {str(e)}")
        return jsonify({'error': 'Error al actualizar el perfil'}), 500
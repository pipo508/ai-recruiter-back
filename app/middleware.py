from functools import wraps
import jwt
from flask import request, jsonify, current_app

# Debe coincidir con la clave en controllers_user.py
SECRET_KEY = "your-secret-key-12345"  # En producción, usa variables de entorno
JWT_ALGORITHM = "HS256"

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token requerido'}), 401
        
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            request.user = payload  # Pasamos el payload (user_id, username, email) al endpoint
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido'}), 401
        except Exception as e:
            current_app.logger.error(f"Error al validar token: {str(e)}")
            return jsonify({'error': 'Error al procesar el token'}), 500
            
        return f(*args, **kwargs)
    return decorated
from functools import wraps
import jwt
from flask import request, jsonify, current_app


def require_auth(f):
    """
    Decorador que protege un endpoint, requiriendo un token JWT válido
    en la cabecera 'Authorization'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autorización requerido'}), 401
        
        try:
            # --- CAMBIO CLAVE: Obtener la configuración desde la app ---
            secret_key = current_app.config['SECRET_KEY']
            jwt_algorithm = current_app.config['JWT_ALGORITHM']
            
            token = auth_header.split(' ')[1]
            
            # Usar las variables leídas desde la configuración
            payload = jwt.decode(token, secret_key, algorithms=[jwt_algorithm])
            
            request.user = payload  # Pasamos el payload al endpoint

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'El token ha expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido'}), 401
        except KeyError as e:
            # Captura el error si 'SECRET_KEY' o 'JWT_ALGORITHM' no están en la config
            current_app.logger.error(f"Error crítico de configuración: Falta la clave {str(e)}")
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        except Exception as e:
            current_app.logger.error(f"Error al validar token: {str(e)}")
            return jsonify({'error': 'Error al procesar el token'}), 500
            
        return f(*args, **kwargs)
        
    return decorated
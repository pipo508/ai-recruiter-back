# app/middleware.py
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
        # --- LOG DE DIAGNÓSTICO ---
        current_app.logger.critical("[AUTH_DEBUG] Entrando en el decorador require_auth.")
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            # --- LOG DE DIAGNÓSTICO ---
            current_app.logger.warning("[AUTH_DEBUG] ERROR: No se encontró 'Authorization: Bearer ...' en la cabecera.")
            return jsonify({'error': 'Token de autorización requerido'}), 401
        
        try:
            secret_key = current_app.config['SECRET_KEY']
            jwt_algorithm = current_app.config['JWT_ALGORITHM']
            
            token = auth_header.split(' ')[1]
            # --- LOG DE DIAGNÓSTICO ---
            current_app.logger.info(f"[AUTH_DEBUG] Token encontrado. Intentando decodificar...")

            payload = jwt.decode(token, secret_key, algorithms=[jwt_algorithm])
            
            # --- LOG DE DIAGNÓSTICO ---
            current_app.logger.info(f"[AUTH_DEBUG] Token decodificado con éxito. Payload: {payload}")
            
            request.user = payload

        except jwt.ExpiredSignatureError:
            current_app.logger.error("[AUTH_DEBUG] ERROR: El token ha expirado.")
            return jsonify({'error': 'El token ha expirado'}), 401
        except jwt.InvalidTokenError:
            current_app.logger.error("[AUTH_DEBUG] ERROR: El token es inválido.")
            return jsonify({'error': 'Token inválido'}), 401
        except Exception as e:
            current_app.logger.error(f"[AUTH_DEBUG] ERROR INESPERADO al validar token: {str(e)}")
            return jsonify({'error': 'Error al procesar el token'}), 500
        
        # --- LOG DE DIAGNÓSTICO ---
        current_app.logger.critical("[AUTH_DEBUG] Autenticación exitosa. Pasando a la función del controlador.")
        return f(*args, **kwargs)
        
    return decorated
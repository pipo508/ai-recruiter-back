"""
Servicio para la gestión de lógica de negocio relacionada con usuarios.
Coordina operaciones entre el controlador y el repositorio de usuarios.
"""

from app.models import User
from app.repositories import UserRepository
from werkzeug.security import check_password_hash
from flask import current_app

class UserService:
    def __init__(self):
        self.repository = UserRepository()

    def register(self, username: str, email: str, password: str) -> User:
        if not username or len(username) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres")
        if not email or "@" not in email:
            raise ValueError("El correo electrónico no es válido")
        if not password or len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")

        if self.repository.get_by_username(username):
            raise ValueError("El nombre de usuario ya está en uso")
        if self.repository.get_by_email(email):
            raise ValueError("El correo electrónico ya está registrado")

        try:
            user = User(username=username, email=email)
            user.set_password(password)
            return self.repository.create(user)
        except Exception as e:
            current_app.logger.error(f"Error al registrar usuario: {str(e)}")
            raise Exception(f"Error al registrar el usuario: {str(e)}")

    def login(self, username: str, password: str) -> User:
        if not username or not password:
            raise ValueError("Se requiere nombre de usuario y contraseña")

        user = self.repository.get_by_username(username)
        if not user or not user.check_password(password):
            raise ValueError("Credenciales incorrectas")

        return user

    def get_profile(self, user_id: int) -> User:
        user = self.repository.find_by_id(user_id)
        if not user:
            raise ValueError("Usuario no encontrado")
        return user

    def update_profile(self, user_id: int, email: str = None, password: str = None) -> User:
        user = self.repository.find_by_id(user_id)
        if not user:
            raise ValueError("Usuario no encontrado")

        # Crear un objeto User con los datos actualizados
        updated_user = User(username=user.username, email=email or user.email)
        if password:
            updated_user.set_password(password)
        else:
            updated_user.password_hash = user.password_hash

        return self.repository.update(updated_user, user_id)

    def get_all_users(self):
        return self.repository.get_all_users()

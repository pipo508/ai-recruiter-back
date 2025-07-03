# app/services/user_service.py

from app.models import User
from app.repositories import UserRepository
from werkzeug.security import check_password_hash
from flask import current_app

class UserService:
    def __init__(self):
        self.repository = UserRepository()

    def register(self, username: str, email: str, password: str) -> User:
        # La lógica de registro ya estaba bien aquí.
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

        user = User(username=username, email=email)
        user.set_password(password)
        return self.repository.create(user)

    def login(self, username: str, password: str) -> User:
        current_app.logger.debug(f"Intentando login para usuario: {username}  123")
        # La lógica de login también es correcta.
        if not username or not password:
            raise ValueError("Se requiere nombre de usuario y contraseña")

        user = self.repository.get_by_username(username)
        if not user or not user.check_password(password):
            raise ValueError("Credenciales incorrectas")
        return user

    def get_profile_with_stats(self, user_id: int) -> dict:
        """
        Obtiene el perfil del usuario y lo enriquece con estadísticas.
        """
        user = self.repository.find_by_id(user_id)
        if not user:
            raise ValueError("Usuario no encontrado")
        
        # El servicio orquesta la obtención de datos y estadísticas
        stats = self.repository.get_user_stats(user_id)

        # Devuelve un diccionario listo para ser usado por el controlador
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'created_at': user.created_at.isoformat(),
            'stats': stats
        }

    def get_all_users_with_stats(self) -> list[dict]:
        """
        Obtiene todos los usuarios y enriquece cada uno con sus estadísticas.
        """
        users = self.repository.get_all_users()
        profiles_with_stats = []
        for user in users:
            # Reutiliza la lógica para obtener el perfil individual
            profile_data = self.get_profile_with_stats(user.id)
            profiles_with_stats.append(profile_data)
        return profiles_with_stats

    def update_profile(self, user_id: int, email: str = None, password: str = None) -> User:
        """
        Actualiza el perfil de un usuario. Lógica simplificada.
        """
        # Prepara un diccionario con los datos a actualizar
        update_data = {}
        if email:
            if "@" not in email:
                raise ValueError("El correo electrónico no es válido")
            update_data['email'] = email
        
        # Si se provee una nueva contraseña, la hashea y la añade a los datos
        if password:
            if len(password) < 6:
                raise ValueError("La contraseña debe tener al menos 6 caracteres")
            temp_user = User()
            temp_user.set_password(password)
            update_data['password_hash'] = temp_user.password_hash
        
        if not update_data:
            raise ValueError("No se proporcionaron datos para actualizar")

        return self.repository.update(user_id, update_data)
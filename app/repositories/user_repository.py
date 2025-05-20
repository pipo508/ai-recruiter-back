"""
Repositorio para la gestión de datos de usuarios.
Encapsula las operaciones de base de datos relacionadas con el modelo User.
"""

from app.extensions import db
from app.models import User
from app.repositories.repository_base import Create, Read, Update, Delete
from sqlalchemy.exc import IntegrityError

class UserRepository(Create, Read, Update, Delete):
    def create(self, entity: User):
        try:
            db.session.add(entity)
            db.session.commit()
            return entity
        except IntegrityError as e:
            db.session.rollback()
            if "users_username_key" in str(e):
                raise ValueError("El nombre de usuario ya está en uso")
            if "users_email_key" in str(e):
                raise ValueError("El correo electrónico ya está registrado")
            raise Exception("Error al crear el usuario")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al crear el usuario: {str(e)}")

    def find_by_id(self, id: int):
        return User.query.get(id)

    def find_all(self):
        return User.query.all()

    def update(self, entity: User, id: int):
        existing_user = User.query.get(id)
        if not existing_user:
            raise ValueError("Usuario no encontrado")

        try:
            existing_user.username = entity.username
            existing_user.email = entity.email
            if entity.password_hash:
                existing_user.password_hash = entity.password_hash
            db.session.commit()
            return existing_user
        except IntegrityError as e:
            db.session.rollback()
            if "users_username_key" in str(e):
                raise ValueError("El nombre de usuario ya está en uso")
            if "users_email_key" in str(e):
                raise ValueError("El correo electrónico ya está registrado")
            raise Exception("Error al actualizar el usuario")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al actualizar el usuario: {str(e)}")

    def delete(self, entity: User, id: int):
        user = User.query.get(id)
        if not user:
            raise ValueError("Usuario no encontrado")

        try:
            db.session.delete(user)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error al eliminar el usuario: {str(e)}")

    def get_by_username(self, username: str):
        return User.query.filter_by(username=username).first()

    def get_by_email(self, email: str):
        return User.query.filter_by(email=email).first()
    
    def get_all_users(self):
        return User.query.all()

    
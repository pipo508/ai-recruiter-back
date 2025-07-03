# app/repositories/user_repository.py

from app.extensions import db
from app.models import User
from app.repositories.RepositoryBase import Create, Read, Update, Delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

class UserRepository(Create, Read, Update, Delete):
    def create(self, entity: User):
        try:
            db.session.add(entity)
            db.session.commit()
            return entity
        except IntegrityError as e:
            db.session.rollback()
            # La lógica para interpretar el error de integridad es correcta aquí.
            if "users_username_key" in str(e).lower():
                raise ValueError("El nombre de usuario ya está en uso")
            if "users_email_key" in str(e).lower():
                raise ValueError("El correo electrónico ya está registrado")
            raise Exception("Error al crear el usuario: Conflicto de datos")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error desconocido al crear el usuario: {str(e)}")

    def find_by_id(self, id: int):
        return User.query.get(id)

    def find_all(self):
        """
        Retorna todos los usuarios, cumpliendo con el contrato de la clase base Read.
        """
        return User.query.order_by(User.username).all()

    def update(self, user_id: int, data: dict):
        """
        Método de actualización más flexible. Acepta un diccionario con los nuevos datos.
        """
        existing_user = self.find_by_id(user_id)
        if not existing_user:
            raise ValueError("Usuario no encontrado")

        try:
            # Actualiza solo los campos proporcionados en el diccionario
            for key, value in data.items():
                if value is not None and hasattr(existing_user, key):
                    setattr(existing_user, key, value)
            
            db.session.commit()
            return existing_user
        except IntegrityError as e:
            db.session.rollback()
            if "users_email_key" in str(e).lower():
                raise ValueError("El correo electrónico ya está en uso")
            raise Exception("Error al actualizar el usuario: Conflicto de datos")
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error desconocido al actualizar el usuario: {str(e)}")

    def delete(self, user_id: int):
        """
        Elimina un usuario por su ID. Se corrigió la firma del método.
        """
        user = self.find_by_id(user_id)
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

    def get_user_stats(self, user_id: int) -> dict:
        """
        Obtiene estadísticas de un usuario, como el conteo de documentos.
        """
        # Esta es una forma eficiente de contar registros relacionados.
        doc_count = db.session.query(func.count(User.documents)).filter(User.id == user_id).scalar()
        return {
            'documents': doc_count or 0
        }
"""
Esquema Marshmallow para el modelo User.
Define reglas de validación y serialización para usuarios.
"""

from marshmallow import Schema, fields, validates, ValidationError, validates_schema
from email_validator import validate_email, EmailNotValidError

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True, validate=lambda x: 3 <= len(x) <= 80)
    email = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True, validate=lambda x: len(x) >= 6)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    documents = fields.Nested('DocumentSchema', many=True, dump_only=True, exclude=('user',))

    @validates('username')
    def validate_username(self, value):
        if not value.strip():
            raise ValidationError('El nombre de usuario no puede estar vacío')

    @validates('email')
    def validate_email_field(self, value):
        try:
            validate_email(value)
        except EmailNotValidError:
            raise ValidationError('El correo electrónico no es válido')

    @validates_schema
    def validate_unique_fields(self, data, **kwargs):
        from app.models import User
        if 'username' in data:
            if User.query.filter_by(username=data['username']).first():
                raise ValidationError('El nombre de usuario ya está en uso', field_name='username')
        if 'email' in data:
            if User.query.filter_by(email=data['email']).first():
                raise ValidationError('El correo electrónico ya está registrado', field_name='email')

class UserUpdateSchema(Schema):
    email = fields.Str()
    password = fields.Str(load_only=True, validate=lambda x: len(x) >= 6 if x else True)

    @validates('email')
    def validate_email_field(self, value):
        if value:
            try:
                validate_email(value)
            except EmailNotValidError:
                raise ValidationError('El correo electrónico no es válido')
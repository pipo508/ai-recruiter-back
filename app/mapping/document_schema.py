"""
Esquema Marshmallow para el modelo Document.
Define reglas de validación y serialización para documentos.
"""

from marshmallow import Schema, fields, validates, ValidationError

class DocumentSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(required=True)
    filename = fields.Str(required=True, validate=lambda x: len(x) > 0)
    firebase_path = fields.Str(required=True, validate=lambda x: len(x) > 0)
    status = fields.Str(validate=lambda x: x in ['uploaded', 'processing', 'processed', 'error'])
    char_count = fields.Int(dump_only=True)
    needs_ocr = fields.Bool(dump_only=True)
    ocr_processed = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    user = fields.Nested('UserSchema', dump_only=True, exclude=('documents',))

    @validates('user_id')
    def validate_user_id(self, value):
        from app.models import User
        if not User.query.get(value):
            raise ValidationError('El usuario especificado no existe')

class DocumentUpdateSchema(Schema):
    filename = fields.Str(validate=lambda x: len(x) > 0 if x else True)
    status = fields.Str(validate=lambda x: x in ['uploaded', 'processing', 'processed', 'error'] if x else True)
    char_count = fields.Int()
    needs_ocr = fields.Bool()
    ocr_processed = fields.Bool()
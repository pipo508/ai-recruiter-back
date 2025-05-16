"""
Inicialización del módulo de modelos.
Importa todos los modelos de la aplicación para facilitar su acceso
y asegurar que las relaciones de SQLAlchemy se configuren correctamente.
"""

from .models_user import User
from .models_document import Document
# Otros modelos comentados hasta que se implementen
# from .text_block import TextBlock
# from .vector import VectorEmbedding
# from .query import Query
# from .candidate import Candidate
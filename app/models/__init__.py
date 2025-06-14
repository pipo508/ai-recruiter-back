"""
Inicialización del módulo de modelos.
Importa todos los modelos de la aplicación para facilitar su acceso
y asegurar que las relaciones de SQLAlchemy se configuren correctamente.
"""

from .User import User
from .Document import Document
from .VectorEmbedding import VectorEmbedding


# Otros modelos comentados hasta que se implementen
# from .text_block import TextBlock
# from .vector import VectorEmbedding
# from .query import Query
# from .candidate import Candidate
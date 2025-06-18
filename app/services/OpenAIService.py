import os
import json
import numpy as np
from openai import OpenAI
from flask import current_app
from app.Promts  import REWRITE_PROMPT, STRUCTURE_PROMPT , QUERY_EXPANSION_PROMPT  # <-- importación nueva

class OpenAIRewriteService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
        self.client = OpenAI(api_key=self.api_key)

    def rewrite_text(self, text: str) -> str:
        """Reescribe el texto proporcionado utilizando OpenAI con el prompt especificado."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un asistente que reescribe textos en un formato estructurado de CV. Sigue estrictamente el formato proporcionado."
                    },
                    {
                        "role": "user",
                        "content": REWRITE_PROMPT + text
                    }
                ],
                max_tokens=1024,
                temperature=0.7
            )
            rewritten_text = response.choices[0].message.content.strip()
            return rewritten_text
        except Exception as e:
            current_app.logger.error(f"Error al reescribir texto con OpenAI: {str(e)}")
            raise

    def generate_embedding(self, text: str) -> list:
        """Genera un embedding para el texto."""
        try:
            embedding_model_to_use = current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
            response = self.client.embeddings.create(
                model=embedding_model_to_use,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            current_app.logger.error(f"Error al generar embedding: {str(e)}")
            raise

    def structure_profile(self, text: str) -> dict:
        """Convierte un texto reescrito en un JSON estructurado con la información del perfil."""
        try:
            prompt = STRUCTURE_PROMPT + text + "\n\nDevuelve solo el JSON, sin texto adicional."
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente que convierte texto en JSON estructurado."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            json_text = response.choices[0].message.content
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                current_app.logger.error(f"Error al parsear JSON de OpenAI: {str(e)}")
                return {}
        except Exception as e:
            current_app.logger.error(f"Error al estructurar el perfil: {str(e)}")
            return {}


    # Pega esta función dentro de la clase OpenAIRewriteService en tu archivo

    def expandir_consulta_con_llm(self, query: str) -> str:
        """
        Expande una consulta de búsqueda utilizando un LLM para mejorar la búsqueda semántica.

        Args:
            query: La consulta original del usuario (ej: "dev python senior").

        Returns:
            La consulta expandida con sinónimos y términos relacionados, lista para generar un embedding.
            En caso de error, devuelve la consulta original para no interrumpir el flujo.
        """
        try:
            # Asegúrate de importar QUERY_EXPANSION_PROMPT junto a los otros prompts
            # from app.Promts import REWRITE_PROMPT, STRUCTURE_PROMPT, QUERY_EXPANSION_PROMPT
            prompt_completo = QUERY_EXPANSION_PROMPT + query

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en optimización de búsquedas para reclutamiento TI."},
                    {"role": "user", "content": prompt_completo}
                ],
                max_tokens=150,  # Suficiente para una consulta expandida
                temperature=0.4  # Un poco de creatividad pero manteniendo el foco
            )
            expanded_query = response.choices[0].message.content.strip()
            # Fallback por si el modelo responde con texto extra (aunque el prompt lo evita)
            if not expanded_query:
                return query
            return expanded_query

        except Exception as e:
            current_app.logger.error(f"Error al expandir la consulta con OpenAI: {str(e)}. Devolviendo la consulta original.")
            # Devolvemos la consulta original como fallback para que la búsqueda pueda continuar
            return query
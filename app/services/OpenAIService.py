import os
import json
import numpy as np
from openai import OpenAI
from flask import current_app
from app.Promts  import REWRITE_PROMPT, STRUCTURE_PROMPT  # <-- importación nueva

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

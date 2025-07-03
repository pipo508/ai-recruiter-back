import os
import json
import numpy as np
from openai import OpenAI
from flask import current_app
from app.promts  import REWRITE_PROMPT, STRUCTURE_PROMPT , QUERY_EXPANSION_PROMPT , CRITICAL_KEYWORDS_PROMPT

class OpenAIRewriteService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
        self.client = OpenAI(api_key=self.api_key)

    def rewrite_text(self, text: str, ai_plus_enabled: bool = False) -> str:
        """Reescribe el texto proporcionado utilizando OpenAI con el prompt especificado."""
        try:
            # --- MODIFICACIÓN INICIO ---
            # Selecciona el modelo basado en el flag. gpt-3.5-turbo es el default.
            model_to_use = "gpt-4o-mini" if ai_plus_enabled else "gpt-3.5-turbo"
            current_app.logger.info(f"Usando el modelo '{model_to_use}' para reescritura de texto.")
            # --- MODIFICACIÓN FIN ---

            response = self.client.chat.completions.create(
                model=model_to_use, # <-- Variable para el modelo
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
                max_tokens=3000,
                temperature=0.7
            )
            rewritten_text = response.choices[0].message.content.strip()
            return rewritten_text
        except Exception as e:
            current_app.logger.error(f"Error al reescribir texto con OpenAI: {str(e)}")
            raise

    def generate_embedding(self, text: str) -> list:
        """Genera un embedding para el texto. Este modelo no cambia."""
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

    def structure_profile(self, text: str, ai_plus_enabled: bool = False) -> dict:
        """Convierte un texto reescrito en un JSON estructurado con la información del perfil."""
        try:
            # --- MODIFICACIÓN INICIO ---
            # Selecciona el modelo basado en el flag. gpt-3.5-turbo es el default.
            model_to_use = "gpt-4o-mini" if ai_plus_enabled else "gpt-3.5-turbo"
            current_app.logger.info(f"Usando el modelo '{model_to_use}' para estructuración de perfil.")
            # --- MODIFICACIÓN FIN ---
            
            prompt = STRUCTURE_PROMPT + text + "\n\nDevuelve solo el JSON, sin texto adicional."
            response = self.client.chat.completions.create(
                model=model_to_use, # <-- Variable para el modelo
                messages=[
                    {"role": "system", "content": "Eres un asistente que convierte texto en JSON estructurado."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,
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

    def expandir_consulta_con_llm(self, query: str) -> str:
        """Expande una consulta de búsqueda utilizando un LLM para mejorar la búsqueda semántica."""
        try:
            prompt_completo = QUERY_EXPANSION_PROMPT + query
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en optimización de búsquedas para reclutamiento TI."},
                    {"role": "user", "content": prompt_completo}
                ],
                max_tokens=150,
                temperature=0.4
            )
            expanded_query = response.choices[0].message.content.strip()
            if not expanded_query:
                return query
            return expanded_query
        except Exception as e:
            current_app.logger.error(f"Error al expandir la consulta con OpenAI: {str(e)}. Devolviendo la consulta original.")
            return query

    def extraer_keywords_criticas(self, query: str) -> list:
        """Extrae keywords críticas de una consulta usando LLM."""
        try:
            prompt = CRITICAL_KEYWORDS_PROMPT + query
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis de consultas de búsqueda de candidatos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            result_text = response.choices[0].message.content.strip()
            import json
            result_json = json.loads(result_text)
            keywords = result_json.get("critical_keywords", [])
            normalized_keywords = [kw.lower().strip() for kw in keywords if kw.strip()]
            return normalized_keywords
        except Exception as e:
            current_app.logger.error(f"Error extrayendo keywords críticas: {e}")
            return []
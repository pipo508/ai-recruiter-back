import os
import json
import numpy as np
from openai import OpenAI
from flask import current_app

class OpenAIRewriteService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
        self.client = OpenAI(api_key=self.api_key)

    def rewrite_text(self, text: str) -> str:
        """Reescribe el texto proporcionado utilizando OpenAI con el prompt especificado."""
        PROMPT_BASE = """
Reescribe el siguiente texto en el formato especificado, extrayendo la información relevante. El texto puede contener las siguientes secciones, aunque no estén en orden. Si alguna sección no está presente, dejala vacia. Mantené la estructura exacta, sin modificar los nombres de las secciones.
se preciso en datos sensibles como nombres, apellidos, emails, etc. no los modifiques.
Formato de salida (respetar títulos y forma):

Nombre completo:
Puesto actual:
Habilidad principal:
Años de experiencia total:
Cantidad de proyectos/trabajos:
Descripción profesional:
GitHub:
Email:
Habilidades clave:

Candidato ideal:
[Texto con máximo 30 palabras, basado en el perfil]

Experiencia Profesional:
[Puesto]  
[Empresa]  
[Año inicio] - [Año fin]  
[Descripción breve del rol]

(repetir bloque si hay más experiencias)

Educación:
[Título o carrera]  
[Institución]  
[Año inicio] - [Año fin]  
[Descripción breve]

(repetir bloque si hay más formaciones)

"""
        try:
            response = self.client.chat.completions.create(
                #model="gpt-4o-mini",
                model= "gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un asistente que reescribe textos en un formato estructurado de CV. Sigue estrictamente el formato proporcionado."
                    },
                    {
                        "role": "user",
                        "content": PROMPT_BASE + text
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
        """
        Genera un embedding para el texto.
        """
        try:
            # Usar el modelo de la configuración de la app
            embedding_model_to_use = current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
            
            response = self.client.embeddings.create(
                model=embedding_model_to_use,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            current_app.logger.error(f"Error al generar embedding: {str(e)}")
            raise

    def structure_profile(self, text):
        """
        Convierte un texto reescrito en un JSON estructurado con la información del perfil.
        
        Args:
            text (str): Texto reescrito del perfil del candidato.
        
        Returns:
            dict: JSON con la estructura solicitada.
        """
        try:
            prompt = """
    Convierte el siguiente texto reescrito del perfil de un candidato en un JSON con la siguiente estructura:
    {
    "Nombre completo": "Nombre Apellido",
    "Puesto actual": "Desarrollador",
    "Habilidad principal": "Python",
    "Años de experiencia total": 5,
    "Cantidad de proyectos/trabajos": 10,
    "Descripción profesional": "Descripción breve",
    "GitHub": "https://github.com/usuario",
    "Email": "email@dominio.com",
    "Habilidades clave": ["Python", "Flask"],
    "Candidato ideal": "Descripción breve del candidato ideal (máx. 30 palabras)",
    "Experiencia Profesional": [
        {
        "Puesto": "Desarrollador",
        "Empresa": "Empresa X",
        "Año inicio": 2018,
        "Año fin": "Presente",
        "Descripción breve del rol": "Descripción del rol"
        }
    ],
    "Educación": [
        {
        "Título o carrera": "Ingeniería en Sistemas",
        "Institución": "Universidad Y",
        "Año inicio": 2014,
        "Año fin": 2018,
        "Descripción breve": "Descripción de la educación"
        }
    ]
    }

    Si falta información, usa valores predeterminados como "" para strings, 0 para números, [] para listas, o "Presente" para Año fin si está en curso. Asegúrate de que "Candidato ideal" no exceda 30 palabras.

    Texto reescrito:
    """

            prompt += text
            prompt += "\n\nDevuelve solo el JSON, sin texto adicional."

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
import os
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
                model="gpt-4o-mini",
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
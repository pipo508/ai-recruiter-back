import os
from openai import OpenAI
from flask import current_app

class OpenAIVisionService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
        
        self.client = OpenAI(api_key=self.api_key)
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"
        self.max_tokens = 4096

    def extract_text_from_pdf_with_vision(self, pdf_path, max_pages=20):
        """
        Extrae texto de un PDF utilizando GPT-4o Vision.
        """
        current_app.logger.info(f"Extrayendo texto con Vision de: {pdf_path}")
        try:
            import fitz  # PyMuPDF
            import base64
            import requests
            from io import BytesIO
            from PIL import Image
            
            # Convertir PDF a imágenes
            images = self._convert_pdf_to_images(pdf_path, max_pages)
            current_app.logger.info(f"PDF convertido a {len(images)} imágenes")

            # Validación: descartar si hay más de 2 imágenes
            if len(images) > 2:
                current_app.logger.warning("El PDF tiene más de 2 páginas. Se descarta la extracción.")
                return None

            all_text = []

            for i, img_bytes in enumerate(images):
                current_app.logger.info(f"Procesando imagen {i+1}/{len(images)} con Vision API")
                base64_image = self._encode_image(img_bytes)

                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Eres un asistente de extracción de texto de documentos PDF. "
                            "Extraé del siguiente texto las siguientes secciones, aunque no estén en orden. "
                            "Si alguna sección no está presente, dejala vacia. Mantené la estructura exacta, sin modificar los nombres de las secciones.\n\n"
                            "Formato de salida (respetar títulos y forma):\n\n"
                            "Nombre completo:\n"
                            "Puesto actual:\n"
                            "Habilidad principal:\n"
                            "Años de experiencia total:\n"
                            "Cantidad de proyectos/trabajos:\n"
                            "Descripción profesional:\n"
                            "GitHub:\n"
                            "Email:\n"
                            "Habilidades clave:\n\n"
                            "Candidato ideal:\n"
                            "[Texto con máximo 30 palabras, basado en el perfil]\n\n"
                            "Experiencia Profesional:\n"
                            "[Puesto]  \n"
                            "[Empresa]  \n"
                            "[Año inicio] - [Año fin]  \n"
                            "[Descripción breve del rol]\n\n"
                            "(repetir bloque si hay más experiencias)\n\n"
                            "Educación:\n"
                            "[Título o carrera]  \n"
                            "[Institución]  \n"
                            "[Año inicio] - [Año fin]  \n"
                            "[Descripción breve]\n\n"
                            "(repetir bloque si hay más formaciones)"
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Esta es la página {i+1} de un documento PDF."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ]

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens
                )

                extracted_text = response.choices[0].message.content
                all_text.append(extracted_text)

            combined_text = "\n\n".join(all_text)
            structured_text = self._post_process_text(combined_text)

            return structured_text

        except Exception as e:
            current_app.logger.error(f"Error al extraer texto con Vision: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            raise

    def _convert_pdf_to_images(self, pdf_path, max_pages=None):
        """
        Convierte un PDF a una lista de imágenes PNG (BytesIO) usando PyMuPDF.
        """
        current_app.logger.info(f"Convirtiendo PDF a imágenes: {pdf_path}")
        try:
            import fitz  # PyMuPDF
            from io import BytesIO
            from PIL import Image
            
            doc = fitz.open(pdf_path)
            num_pages = doc.page_count
            pages_to_process = min(num_pages, max_pages) if max_pages else num_pages

            current_app.logger.info(f"Procesando {pages_to_process} de {num_pages} páginas")

            images = []

            for page_num in range(pages_to_process):
                page = doc.load_page(page_num)
                matrix = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=matrix)

                img_data = pix.tobytes("png")
                img_bytes = BytesIO(img_data)
                img_bytes.seek(0)

                img = Image.open(img_bytes)
                max_size = 2000
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)

                    img_bytes = BytesIO()
                    img.save(img_bytes, format="PNG")
                    img_bytes.seek(0)

                images.append(img_bytes)

            return images

        except Exception as e:
            current_app.logger.error(f"Error al convertir PDF a imágenes: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            raise

    def _encode_image(self, image_bytes):
        """Codifica una imagen en base64 para enviar a la API de OpenAI."""
        import base64
        return base64.b64encode(image_bytes.getvalue()).decode('utf-8')

    def _post_process_text(self, text):
        """
        Limpia el texto extraído (elimina duplicados, líneas vacías múltiples).
        """
        lines = text.split('\n')
        processed_lines = []

        for i, line in enumerate(lines):
            if line.strip() == "" and (i > 0 and lines[i-1].strip() == ""):
                continue
            if i > 0 and line.strip() == lines[i-1].strip():
                continue
            processed_lines.append(line)

        return '\n'.join(processed_lines)

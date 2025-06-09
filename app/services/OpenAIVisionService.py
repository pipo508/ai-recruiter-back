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

    def extract_text_from_pdf_with_vision(self, pdf_path, max_pages=2):
        """
        Extrae texto de un PDF utilizando GPT-4o Vision.
        Limita a máximo 2 páginas y retorna texto ya estructurado.
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
            if len(images) > max_pages:
                current_app.logger.warning(f"El PDF tiene más de {max_pages} páginas. Se descarta la extracción.")
                return None

            if len(images) == 0:
                current_app.logger.warning("No se pudieron convertir páginas del PDF.")
                return None

            all_text = []

            for i, img_bytes in enumerate(images):
                current_app.logger.info(f"Procesando imagen {i+1}/{len(images)} con Vision API")
                base64_image = self._encode_image(img_bytes)

                # Prompt para extraer Y estructurar directamente
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Eres un asistente especializado en extraer y estructurar información de CVs/currículums desde imágenes. "
                            "Debes extraer toda la información visible y organizarla en el formato estructurado especificado. "
                            "Si alguna sección no está presente en la imagen, déjala vacía pero mantén la estructura. "
                            "Sé preciso con datos sensibles como nombres, apellidos, emails, etc. No los modifiques.\n\n"
                            "Formato de salida obligatorio:\n\n"
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
                            {
                                "type": "text", 
                                "text": f"Extrae y estructura toda la información de este CV (página {i+1}). Mantén el formato exacto especificado:"
                            },
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
                    max_tokens=self.max_tokens,
                    temperature=0.3  # Menor temperatura para mayor consistencia
                )

                extracted_text = response.choices[0].message.content
                all_text.append(extracted_text)
                current_app.logger.info(f"Texto extraído de página {i+1}: {len(extracted_text)} caracteres")

            # Combinar texto de todas las páginas
            if len(all_text) == 1:
                combined_text = all_text[0]
            else:
                # Si hay múltiples páginas, combinar inteligentemente
                combined_text = self._merge_multiple_pages(all_text)

            # Post-procesar para limpiar el texto
            structured_text = self._post_process_text(combined_text)
            
            current_app.logger.info(f"Texto final estructurado: {len(structured_text)} caracteres")
            return structured_text

        except Exception as e:
            current_app.logger.error(f"Error al extraer texto con Vision: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            raise

    def _merge_multiple_pages(self, text_pages):
        """
        Combina texto de múltiples páginas de manera inteligente.
        Evita duplicar secciones y combina información complementaria.
        """
        current_app.logger.info("Combinando texto de múltiples páginas")
        
        # Estrategia simple: usar la primera página como base y añadir información adicional de las siguientes
        base_text = text_pages[0]
        
        # Para páginas adicionales, extraer solo secciones que puedan estar incompletas en la primera página
        additional_info = []
        
        for i, page_text in enumerate(text_pages[1:], 2):
            # Buscar secciones que puedan tener información adicional
            if "Experiencia Profesional:" in page_text:
                exp_section = self._extract_section(page_text, "Experiencia Profesional:", "Educación:")
                if exp_section and len(exp_section.strip()) > 50:  # Solo si tiene contenido significativo
                    additional_info.append(f"\n--- Información adicional de página {i} ---\n{exp_section}")
            
            if "Educación:" in page_text:
                edu_section = self._extract_section(page_text, "Educación:", None)
                if edu_section and len(edu_section.strip()) > 50:
                    additional_info.append(f"\n--- Educación adicional de página {i} ---\n{edu_section}")
        
        # Combinar todo
        if additional_info:
            combined = base_text + "\n" + "\n".join(additional_info)
        else:
            combined = base_text
            
        return combined

    def _extract_section(self, text, start_marker, end_marker):
        """
        Extrae una sección específica del texto entre dos marcadores.
        """
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""
            
            start_idx += len(start_marker)
            
            if end_marker:
                end_idx = text.find(end_marker, start_idx)
                if end_idx != -1:
                    return text[start_idx:end_idx].strip()
            
            return text[start_idx:].strip()
        except:
            return ""

    def _convert_pdf_to_images(self, pdf_path, max_pages=2):
        """
        Convierte un PDF a una lista de imágenes PNG (BytesIO) usando PyMuPDF.
        Limitado a max_pages páginas.
        """
        current_app.logger.info(f"Convirtiendo PDF a imágenes: {pdf_path} (máximo {max_pages} páginas)")
        try:
            import fitz  # PyMuPDF
            from io import BytesIO
            from PIL import Image
            
            doc = fitz.open(pdf_path)
            num_pages = doc.page_count
            pages_to_process = min(num_pages, max_pages)

            current_app.logger.info(f"Procesando {pages_to_process} de {num_pages} páginas")

            images = []

            for page_num in range(pages_to_process):
                page = doc.load_page(page_num)
                # Usar mayor resolución para mejor OCR
                matrix = fitz.Matrix(2.5, 2.5)  # Aumentado de 2 a 2.5
                pix = page.get_pixmap(matrix=matrix, alpha=False)  # Sin canal alpha para reducir tamaño

                img_data = pix.tobytes("png")
                img_bytes = BytesIO(img_data)
                img_bytes.seek(0)

                # Redimensionar si es necesario para no sobrepasar límites de API
                img = Image.open(img_bytes)
                max_size = 2048  # Límite conservativo para API de OpenAI
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)

                    img_bytes = BytesIO()
                    img.save(img_bytes, format="PNG", optimize=True)
                    img_bytes.seek(0)

                images.append(img_bytes)
                current_app.logger.info(f"Página {page_num + 1} convertida: {img.width}x{img.height}")

            doc.close()
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
        Limpia el texto extraído (elimina duplicados, líneas vacías múltiples, etc.).
        """
        if not text:
            return ""
            
        lines = text.split('\n')
        processed_lines = []
        prev_line = ""

        for line in lines:
            line_clean = line.strip()
            
            # Saltar líneas completamente vacías consecutivas
            if line_clean == "" and prev_line == "":
                continue
                
            # Saltar líneas duplicadas consecutivas
            if line_clean == prev_line and line_clean != "":
                continue
                
            # Saltar líneas que parecen ser artefactos del OCR
            if len(line_clean) == 1 and line_clean.isalpha():
                continue
                
            processed_lines.append(line)
            prev_line = line_clean

        # Unir líneas y limpiar espacios múltiples
        final_text = '\n'.join(processed_lines)
        final_text = '\n'.join([line.rstrip() for line in final_text.split('\n')])
        
        return final_text.strip()
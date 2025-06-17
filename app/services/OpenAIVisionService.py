# app/services/OpenAIVisionService.py

import os
import base64
import fitz # PyMuPDF
from PIL import Image, ImageEnhance
import io
import re
from openai import OpenAI
from flask import current_app
import traceback

class OpenAIVisionService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"
        self.max_tokens = 4096
        
        self.MAX_PAGES = 3
        self.DPI_SCALE = 2.0
        self.MAX_IMAGE_SIZE = 2048
        self.QUALITY_THRESHOLD = 100

    def extract_text_from_pdf_with_vision(self, pdf_path, max_pages=None):
        max_pages = max_pages or self.MAX_PAGES
        current_app.logger.info(f"Iniciando extracción con Vision de: {pdf_path}")
        
        try:
            images = self._convert_pdf_to_images_robust(pdf_path, max_pages)
            if not images:
                raise ValueError("No se pudieron generar imágenes del PDF")

            current_app.logger.debug(f"PDF convertido a {len(images)} imágenes exitosamente")

            extracted_pages = []
            for i, img_data in enumerate(images):
                try:
                    page_text = self._process_image_with_vision(img_data, i + 1)
                    if page_text and len(page_text.strip()) > self.QUALITY_THRESHOLD:
                        extracted_pages.append(page_text)
                        current_app.logger.debug(f"Página {i+1} procesada: {len(page_text)} caracteres")
                    else:
                        current_app.logger.warning(f"Página {i+1} produjo texto insuficiente o nulo")
                except Exception as e:
                    current_app.logger.error(f"Error procesando página {i+1}: {str(e)}")
                    continue

            if not extracted_pages:
                raise ValueError("No se pudo extraer texto de ninguna página")

            final_text = self._combine_and_structure_pages(extracted_pages)
            
            current_app.logger.info(f"Extracción completada: {len(final_text)} caracteres totales")
            return final_text

        except Exception as e:
            current_app.logger.error(f"Error crítico en extracción con Vision: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise

    def _convert_pdf_to_images_robust(self, pdf_path, max_pages):
        current_app.logger.debug(f"Convirtiendo PDF a imágenes: {pdf_path}")
        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            pages_to_process = min(total_pages, max_pages)
            current_app.logger.debug(f"Documento tiene {total_pages} páginas, procesando {pages_to_process}")
            if total_pages == 0: raise ValueError("El PDF no tiene páginas válidas")
            images = []
            successful_pages = 0
            for page_num in range(pages_to_process):
                try:
                    page = doc.load_page(page_num)
                    if page.rect.is_empty: continue
                    matrix = fitz.Matrix(self.DPI_SCALE, self.DPI_SCALE)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    img_data = pix.tobytes("png")
                    pil_image = Image.open(io.BytesIO(img_data))
                    optimized_image = self._optimize_image_for_ocr(pil_image)
                    img_buffer = io.BytesIO()
                    optimized_image.save(img_buffer, format='PNG', optimize=True)
                    img_buffer.seek(0)
                    images.append(img_buffer)
                    successful_pages += 1
                    current_app.logger.debug(f"Página {page_num + 1} convertida exitosamente: {optimized_image.size}")
                except Exception as e:
                    current_app.logger.error(f"Error convirtiendo página {page_num + 1}: {str(e)}")
                    continue
            doc.close()
            if successful_pages == 0: raise ValueError("No se pudo convertir ninguna página del PDF")
            current_app.logger.debug(f"Conversión completada: {successful_pages} páginas exitosas")
            return images
        except Exception as e:
            current_app.logger.error(f"Error en conversión de PDF: {str(e)}")
            raise

    def _optimize_image_for_ocr(self, pil_image):
        try:
            if pil_image.mode != 'RGB': pil_image = pil_image.convert('RGB')
            width, height = pil_image.size
            if width > self.MAX_IMAGE_SIZE or height > self.MAX_IMAGE_SIZE:
                ratio = min(self.MAX_IMAGE_SIZE / width, self.MAX_IMAGE_SIZE / height)
                new_size = (int(width * ratio), int(height * ratio))
                pil_image = pil_image.resize(new_size, Image.LANCZOS)
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.2)
            return pil_image
        except Exception as e:
            current_app.logger.warning(f"Error optimizando imagen: {str(e)}")
            return pil_image

    def _process_image_with_vision(self, img_buffer, page_number):
        # ... este método ya estaba bien, no se necesita cambiar ...
        try:
            img_buffer.seek(0)
            base64_image = base64.b64encode(img_buffer.read()).decode('utf-8')
            messages = [
                {"role": "system", "content": self._get_vision_system_prompt()},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Extrae y estructura toda la información de esta página de CV (página {page_number}). Usa el formato exacto especificado. Si no hay información para alguna sección, déjala vacía pero mantén la estructura."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}", "detail": "high"}}
                ]}
            ]
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=self.max_tokens, temperature=0.1, top_p=0.9
            )
            extracted_text = response.choices[0].message.content
            if not extracted_text:
                current_app.logger.warning(f"API retornó respuesta vacía para página {page_number}")
                return None
            return extracted_text.strip()
        except Exception as e:
            current_app.logger.error(f"Error en API Vision para página {page_number}: {str(e)}")
            raise

    def _get_vision_system_prompt(self):
        return """Eres un asistente experto en extraer información de CVs/currículums desde imágenes.
INSTRUCCIONES CRÍTICAS:
- Extrae TODA la información visible con máxima precisión, incluyendo nombres, fechas, descripciones de puestos, tecnologías, etc.
- Devuelve la información ÚNICAMENTE en el formato especificado, sin explicaciones, introducciones ni texto adicional.
- Si una sección no está presente en el CV, mantenla en la estructura con un valor vacío (string vacío, lista vacía o nulo donde corresponda).
- Estructura la salida de la siguiente manera:
... (el resto del prompt) ...
"""

    def _combine_and_structure_pages(self, extracted_pages):
        if len(extracted_pages) == 1:
            return self._clean_final_text(extracted_pages[0])
        
        current_app.logger.debug(f"Combinando texto de {len(extracted_pages)} páginas")
        base_text = extracted_pages[0]
        
        for i, page_text in enumerate(extracted_pages[1:], 2):
            additional_experience = self._extract_additional_section(page_text, "Experiencia Profesional:", ["Educación:", "Habilidades"])
            additional_education = self._extract_additional_section(page_text, "Educación:", ["Certificaciones:", "Proyectos:", "Referencias:"])
            
            if additional_experience:
                base_text += f"\n\n--- Experiencia adicional (página {i}) ---\n{additional_experience}"
            if additional_education:
                base_text += f"\n\n--- Educación adicional (página {i}) ---\n{additional_education}"
        
        return self._clean_final_text(base_text)

    # --- INICIO DE LA CORRECCIÓN ---

    def _extract_additional_section(self, text, section_start, section_ends):
        """
        CORREGIDO: Extrae el contenido de una sección específica de una página adicional.
        """
        try:
            start_index = text.lower().find(section_start.lower())
            if start_index == -1:
                return ""

            start_index += len(section_start)
            end_index = len(text)

            for end_marker in section_ends:
                marker_index = text.lower().find(end_marker.lower(), start_index)
                if marker_index != -1:
                    end_index = min(end_index, marker_index)
            
            return text[start_index:end_index].strip()
        except Exception:
            return ""

    def _clean_final_text(self, text):
        """
        CORREGIDO: Realiza una limpieza básica del texto final.
        """
        if not text:
            return ""
        return text.strip()


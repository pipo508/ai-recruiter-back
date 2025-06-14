# app/services/OpenAIVisionService.py

import os
import base64
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance
import io
from openai import OpenAI
from flask import current_app
import traceback

class OpenAIVisionService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            current_app.logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"  # Mejor modelo para Vision
        self.max_tokens = 4096
        
        # Configuraciones optimizadas para OCR
        self.MAX_PAGES = 3  # Aumentado de 2 a 3
        self.DPI_SCALE = 2.0  # Resolución para conversión
        self.MAX_IMAGE_SIZE = 2048  # Tamaño máximo de imagen
        self.QUALITY_THRESHOLD = 100  # Mínimo de caracteres esperados por página

    def extract_text_from_pdf_with_vision(self, pdf_path, max_pages=None):
        """
        Extrae texto de un PDF utilizando GPT-4o Vision con mejor manejo de errores
        y optimizaciones para diferentes tipos de documentos.
        """
        max_pages = max_pages or self.MAX_PAGES
        current_app.logger.info(f"Iniciando extracción con Vision de: {pdf_path}")
        
        try:
            # Validar que el archivo existe
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"El archivo PDF no existe: {pdf_path}")

            # Convertir PDF a imágenes con manejo de errores mejorado
            images = self._convert_pdf_to_images_robust(pdf_path, max_pages)
            
            if not images:
                current_app.logger.error("No se pudieron generar imágenes del PDF")
                return None

            current_app.logger.info(f"PDF convertido a {len(images)} imágenes exitosamente")

            # Procesar cada imagen con la API de Vision
            extracted_pages = []
            for i, img_data in enumerate(images):
                try:
                    page_text = self._process_image_with_vision(img_data, i + 1)
                    if page_text and len(page_text.strip()) > self.QUALITY_THRESHOLD:
                        extracted_pages.append(page_text)
                        current_app.logger.info(f"Página {i+1} procesada: {len(page_text)} caracteres")
                    else:
                        current_app.logger.warning(f"Página {i+1} produjo texto insuficiente")
                        
                except Exception as e:
                    current_app.logger.error(f"Error procesando página {i+1}: {str(e)}")
                    continue

            if not extracted_pages:
                current_app.logger.error("No se pudo extraer texto de ninguna página")
                return None

            # Combinar y estructurar el texto final
            final_text = self._combine_and_structure_pages(extracted_pages)
            
            current_app.logger.info(f"Extracción completada: {len(final_text)} caracteres totales")
            return final_text

        except Exception as e:
            current_app.logger.error(f"Error crítico en extracción con Vision: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            raise

    def _convert_pdf_to_images_robust(self, pdf_path, max_pages):
        """
        Conversión robusta de PDF a imágenes con múltiples intentos y validaciones.
        """
        current_app.logger.info(f"Convirtiendo PDF a imágenes: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            pages_to_process = min(total_pages, max_pages)
            
            current_app.logger.info(f"Documento tiene {total_pages} páginas, procesando {pages_to_process}")
            
            if total_pages == 0:
                raise ValueError("El PDF no tiene páginas válidas")

            images = []
            successful_pages = 0

            for page_num in range(pages_to_process):
                try:
                    page = doc.load_page(page_num)
                    
                    # Verificar que la página tiene contenido
                    if page.rect.is_empty: # Usamos page.rect.is_empty que es más antiguo y robusto
                        current_app.logger.warning(f"Página {page_num + 1} está vacía o no tiene dimensiones")
                        continue
                    
                    # Usar matriz de transformación optimizada
                    matrix = fitz.Matrix(self.DPI_SCALE, self.DPI_SCALE)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    
                    # Convertir a PIL Image para mejor manejo
                    img_data = pix.tobytes("png")
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    # Optimizar imagen
                    optimized_image = self._optimize_image_for_ocr(pil_image)
                    
                    # Convertir a bytes
                    img_buffer = io.BytesIO()
                    optimized_image.save(img_buffer, format='PNG', optimize=True)
                    img_buffer.seek(0)
                    
                    images.append(img_buffer)
                    successful_pages += 1
                    
                    current_app.logger.info(f"Página {page_num + 1} convertida exitosamente: {optimized_image.size}")
                    
                except Exception as e:
                    current_app.logger.error(f"Error convirtiendo página {page_num + 1}: {str(e)}")
                    continue

            doc.close()
            
            if successful_pages == 0:
                raise ValueError("No se pudo convertir ninguna página del PDF")
                
            current_app.logger.info(f"Conversión completada: {successful_pages} páginas exitosas")
            return images

        except Exception as e:
            current_app.logger.error(f"Error en conversión de PDF: {str(e)}")
            raise

    def _optimize_image_for_ocr(self, pil_image):
        """
        Optimiza la imagen para mejor reconocimiento OCR.
        """
        try:
            # Convertir a RGB si es necesario
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Redimensionar si es muy grande
            width, height = pil_image.size
            if width > self.MAX_IMAGE_SIZE or height > self.MAX_IMAGE_SIZE:
                ratio = min(self.MAX_IMAGE_SIZE / width, self.MAX_IMAGE_SIZE / height)
                new_size = (int(width * ratio), int(height * ratio))
                pil_image = pil_image.resize(new_size, Image.LANCZOS)
                current_app.logger.info(f"Imagen redimensionada a: {new_size}")
            
            # Mejorar contraste para OCR
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.2)  # Aumentar contraste ligeramente
            
            return pil_image
            
        except Exception as e:
            current_app.logger.warning(f"Error optimizando imagen: {str(e)}")
            return pil_image  # Retornar imagen original si falla la optimización

    def _process_image_with_vision(self, img_buffer, page_number):
        """
        Procesa una imagen individual con la API de Vision de OpenAI.
        """
        try:
            # Codificar imagen en base64
            img_buffer.seek(0)
            base64_image = base64.b64encode(img_buffer.read()).decode('utf-8')
            
            # Prompt optimizado para extracción de CVs
            messages = [
                {
                    "role": "system",
                    "content": self._get_vision_system_prompt()
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Extrae y estructura toda la información de esta página de CV (página {page_number}). "
                                   "Usa el formato exacto especificado. Si no hay información para alguna sección, "
                                   "déjala vacía pero mantén la estructura."
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

            # Llamada a la API con configuración optimizada
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.1,  # Muy baja para consistencia
                top_p=0.9
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
        """
        Retorna el prompt del sistema optimizado para extracción de CVs.
        """
        return """Eres un asistente experto en extraer información de CVs/currículums desde imágenes.

INSTRUCCIONES CRÍTICAS:
- Extrae TODA la información visible con máxima precisión
- Mantén nombres, emails, enlaces y datos exactos tal como aparecen
- Si no puedes leer algo claramente, indica [ILEGIBLE] en esa posición
- No inventes ni asumas información que no esté claramente visible
- Mantén el formato estructurado exacto que se especifica

FORMATO DE SALIDA OBLIGATORIO:

Nombre completo:
Puesto actual:
Numero de teléfono:
Ubicación:"Ciudad, País"
Habilidad principal:
Años de experiencia total:
Cantidad de proyectos/trabajos:
Descripción profesional:
GitHub:
Email:
Habilidades clave:

Candidato ideal:
[Máximo 30 palabras basadas en el perfil visible]

Experiencia Profesional:
[Puesto]
[Empresa]
[Año inicio] - [Año fin]
[Descripción breve del rol]

(repetir para cada experiencia)

Educación:
[Título o carrera]
[Institución]
[Año inicio] - [Año fin]
[Descripción breve]

(repetir para cada formación)

REGLAS ADICIONALES:
- Si una sección no tiene información, déjala vacía pero incluye el título
- Para fechas, usa formato "YYYY" o "YYYY-YYYY"
- Si algo sigue vigente, usa "Presente" como año fin
- Extrae números de teléfono, LinkedIn, portfolio si están visibles"""

    def _combine_and_structure_pages(self, extracted_pages):
        """
        Combina el texto de múltiples páginas de manera inteligente.
        """
        if len(extracted_pages) == 1:
            return self._clean_final_text(extracted_pages[0])
        
        current_app.logger.info("Combinando múltiples páginas")
        
        # Usar la primera página como base
        base_text = extracted_pages[0]
        
        # Extraer información adicional de páginas siguientes
        for i, page_text in enumerate(extracted_pages[1:], 2):
            # Buscar información adicional en experiencia y educación
            additional_experience = self._extract_additional_section(
                page_text, "Experiencia Profesional:", ["Educación:", "Habilidades"]
            )
            additional_education = self._extract_additional_section(
                page_text, "Educación:", ["Certificaciones:", "Proyectos:", "Referencias:"]
            )
            
            if additional_experience:
                base_text += f"\n\n--- Experiencia adicional (página {i}) ---\n{additional_experience}"
            
            if additional_education:
                base_text += f"\n\n--- Educación adicional (página {i}) ---\n{additional_education}"
        
        return self._clean_final_text(base_text)

    def _extract_additional_section(self, text, section_start, section_ends):
        """
        Extrae una sección específica del texto.
        """
        try:
            start_idx = text.find(section_start)
            if start_idx == -1:
                return ""
            
            start_idx += len(section_start)
            
            # Buscar el final de la sección
            end_idx = len(text)
            for end_marker in section_ends:
                marker_idx = text.find(end_marker, start_idx)
                if marker_idx != -1 and marker_idx < end_idx:
                    end_idx = marker_idx
            
            section_text = text[start_idx:end_idx].strip()
            
            # Solo retornar si tiene contenido significativo
            if len(section_text) > 20:
                return section_text
            
            return ""
            
        except Exception as e:
            current_app.logger.warning(f"Error extrayendo sección: {str(e)}")
            return ""

    def _clean_final_text(self, text):
        """
        Limpia el texto final eliminando duplicados y mejorando formato.
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = []
        prev_line = ""
        
        for line in lines:
            line_clean = line.strip()
            
            # Saltar líneas vacías consecutivas
            if line_clean == "" and prev_line == "":
                continue
            
            # Saltar líneas duplicadas exactas consecutivas
            if line_clean == prev_line and line_clean != "":
                continue
            
            # Limpiar artefactos comunes del OCR
            if len(line_clean) == 1 and line_clean.isalpha():
                continue
            
            if line_clean in ["---", "___", "..."]:
                continue
            
            cleaned_lines.append(line)
            prev_line = line_clean
        
        # Unir y limpiar espacios finales
        final_text = '\n'.join(cleaned_lines)
        final_text = '\n'.join([line.rstrip() for line in final_text.split('\n')])
        
        return final_text.strip()
import os
import cv2
import pytesseract
import re
from dotenv import load_dotenv

load_dotenv()
# Si usas Windows, asegurate de ajustar la ruta a Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def upscale_image(image, scale=2.0):
    """
    Aumenta la resolución de la imagen para mejorar la detección de pequeños detalles.
    """
    height, width = image.shape[:2]
    return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_CUBIC)

def preprocess_for_ocr(image):
    """
    Convierte la imagen a escala de grises, mejora el contraste, y aplica un filtrado
    y operaciones morfológicas para resaltar pequeños detalles (como puntos).
    """
    # Convertir a escala de grises y mejorar contraste
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # Aplicar un filtro mediana para suavizar el ruido
    filtered = cv2.medianBlur(gray, 3)

    # Umbral adaptativo para binarizar la imagen
    thresh = cv2.adaptiveThreshold(
        filtered,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        2
    )

    # Operaciones morfológicas leves para resaltar detalles pequeños
    # Un kernel pequeño para evitar eliminar puntos
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    thresh = cv2.erode(thresh, kernel, iterations=1)
    
    return thresh

def extract_sections(image_path, min_area=500):
    """
    Procesa la imagen, realiza preprocesamiento, detecta bloques de texto (secciones)
    y aplica OCR sobre cada uno de ellos.
    """
    # Leer la imagen
    image = cv2.imread(image_path)
    if image is None:
        print(f"No se pudo leer la imagen: {image_path}")
        return None

    # Aumentar resolución para pequeños textos
    image_upscaled = upscale_image(image, scale=2.0)
    
    # Aplicar preprocesamiento: mejora de contraste, umbral y operaciones morfológicas
    processed = preprocess_for_ocr(image_upscaled)
    
    # Encontrar contornos externos que delimiten áreas de texto
    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    sections = []
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue  # Ignorar zonas demasiado pequeñas
        
        # Obtener el rectángulo delimitador
        x, y, w, h = cv2.boundingRect(contour)
        roi = image_upscaled[y:y+h, x:x+w]
        
        # Configuración: LSTM y psm 6 (bloque uniforme de texto)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(roi, lang='spa+eng', config=custom_config)
        text = text.strip()
        
        if text:
            sections.append({"bbox": (x, y, w, h), "text": text})
    
    # Ordenar las secciones de arriba hacia abajo usando la coordenada 'y'
    sections = sorted(sections, key=lambda s: s['bbox'][1])
    return sections

def extract_information(full_text):
    """
    Extrae información relevante utilizando expresiones regulares:
      - Emails
      - URLs
      - Números de teléfono
    """
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_text)
    urls = re.findall(r'https?://[^\s]+', full_text)
    phone_numbers = re.findall(r'\+?\d[\d\s\-]{8,}\d', full_text)
    return emails, urls, phone_numbers

def classify_sections(sections):
    """
    Clasifica cada bloque de texto usando palabras clave típicas en un currículum.
    """
    classified_sections = {
        "Experiencia": [],
        "Educación": [],
        "Habilidades": [],
        "Contacto": [],
        "Otros": []
    }
    
    keywords = {
        "Experiencia": ["experiencia", "trabajo", "empleo", "cargo", "laboral"],
        "Educación": ["educación", "formación", "universidad", "instituto", "título"],
        "Habilidades": ["habilidades", "skills", "competencias", "conocimientos"],
        "Contacto": ["contacto", "email", "e-mail", "teléfono", "celular", "dirección", "linkedin", "facebook", "instagram", "twitter"]
    }
    
    for sec in sections:
        text_lower = sec["text"].lower()
        matched = False
        for section, keys in keywords.items():
            if any(keyword in text_lower for keyword in keys):
                classified_sections[section].append(sec["text"])
                matched = True
                break
        if not matched:
            classified_sections["Otros"].append(sec["text"])
    
    return classified_sections

def process_resume(image_path):
    """
    Procesa un currículum en formato imagen:
      - Extrae las secciones de texto mediante OCR.
      - Une el texto extraído para buscar emails, URLs y teléfonos.
      - Clasifica las secciones usando palabras clave.
    """
    sections = extract_sections(image_path)
    if sections is None:
        return None
    
    full_text = "\n".join([sec["text"] for sec in sections])
    emails, urls, phone_numbers = extract_information(full_text)
    classified_sections = classify_sections(sections)
    
    return {
        "file": image_path,
        "sections": sections,
        "full_text": full_text,
        "emails": emails,
        "urls": urls,
        "phone_numbers": phone_numbers,
        "classified_sections": classified_sections
    }

def main():
    folder_path = os.getenv("CANDIDATES_DIR")  # Asegurate de que la carpeta exista y contenga imágenes
    results = []
    
    if not os.path.exists(folder_path):
        print(f"La carpeta '{folder_path}' no existe. Verifica la ruta.")
        return
    
    # Procesar cada imagen en la carpeta
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
            image_path = os.path.join(folder_path, file_name)
            print(f"\nProcesando: {image_path}")
            result = process_resume(image_path)
            if result:
                results.append(result)
                
    
    # Opcional: guardar resultados en un archivo JSON
    # import json
    # with open('resumes_processed.json', 'w', encoding='utf-8') as f:
    #     json.dump(results, f, ensure_ascii=False, indent=4)
    
if __name__ == "__main__":
    main()

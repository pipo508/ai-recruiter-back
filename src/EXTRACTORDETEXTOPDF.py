import json
import re
import glob
import os
import atexit
import shutil
import tempfile
import traceback  # Añadido para mostrar errores detallados
from collections import defaultdict

import logging
from pathlib import Path
import fitz        # PyMuPDF
import camelot     # pip install camelot-py[cv]
import spacy       # pip install spacy ; python -m spacy download en_core_web_sm

# Silenciar advertencias de camelot y fitz
import warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
import os

load_dotenv()  # Carga las variables de entorno desde .env
# Redefinimos la función rmtree para evitar el error de permisos al final
orig_rmtree = shutil.rmtree
def silent_rmtree(*args, **kwargs):
    try:
        orig_rmtree(*args, **kwargs)
    except:
        pass
shutil.rmtree = silent_rmtree

# Configuración de logging personalizado para depuración
class CustomFormatter(logging.Formatter):
    def format(self, record):
        return super().format(record)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter("%(message)s"))
logger.addHandler(handler)

# Desactivar otros loggers
logging.getLogger("camelot").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("PIL").setLevel(logging.ERROR)
logging.getLogger("fitz").setLevel(logging.ERROR)

# Carga de NER de spaCy
nlp = spacy.load("en_core_web_sm")
EMAIL_RE = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s\-\.\(\)]{7,}\d")

# Redirigir stderr temporalmente para mensajes de PyMuPDF
import sys
from io import StringIO

class SuppressOutput:
    def __enter__(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        return self
    
    def __exit__(self, *args):
        sys.stdout = self.stdout
        sys.stderr = self.stderr

# Funciones de extracción
def extract_text(page):
    """Extrae bloques ordenados; OCR solo si faltan caracteres."""
    with SuppressOutput():
        blocks = page.get_text("blocks", sort=True)
        text = "\n".join(b[4] for b in blocks)
        if "\uFFFD" in text:
            tp_ocr = page.get_textpage_ocr(language="spa", dpi=300)
            text = page.get_text("blocks", sort=True, textpage=tp_ocr)
    return text

def extract_tables(pdf_path):
    """Extrae tablas con Camelot en modos 'stream' y 'lattice'."""
    tables = []
    for flavor in ("stream", "lattice"):
        try:
            with SuppressOutput():
                tbls = camelot.read_pdf(
                    pdf_path, 
                    flavor=flavor, 
                    pages="1-end",
                    suppress_stdout=True
                )
                for table in tbls:
                    tables.append(table.df.to_dict(orient="records"))
        except Exception as e:
            logger.error(f"Error al extraer tablas ({flavor}): {str(e)}")
    return tables

def extract_entities(text):
    """Extrae entidades spaCy y contactos vía regex."""
    doc = nlp(text)
    ents = defaultdict(list)
    for ent in doc.ents:
        ents[ent.label_].append(ent.text)
    ents["EMAILS"] = EMAIL_RE.findall(text)
    ents["PHONES"] = PHONE_RE.findall(text)
    return ents

def clean_text(text):
    """Limpia el texto eliminando caracteres no deseados y espacios múltiples."""
    if not text:
        return ""
    # Eliminar caracteres no deseados y normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('•', '').strip()
    return text

def extract_section_content(text, section_markers):
    """Extrae contenido entre marcadores de sección."""
    for marker in section_markers:
        pattern = f"{marker}(.*?)(?:{'|'.join(section_markers)}|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""

def find_value_in_tables(tables, key_words, default=""):
    """Busca valores en tablas basado en palabras clave."""
    for table in tables:
        for row in table:
            for k, v in row.items():
                if any(kw.lower() in str(v).lower() for kw in key_words):
                    # Verifica si k es string o int antes de usar isdigit()
                    if isinstance(k, str) and k.isdigit():
                        next_col = str(int(k) + 1)
                    elif isinstance(k, int):
                        next_col = str(k + 1)
                    else:
                        next_col = '1'
                    
                    if next_col in row:
                        return clean_text(row[next_col])
    return default

def extract_structured_data_for_embedding(full_text, tables, entities):
    """Extrae datos estructurados para embeddings."""
    
    # Dividir el texto en secciones
    lines = full_text.split('\n')
    text_without_linebreaks = ' '.join(lines)
    
    # Extraer nombre del CV
    name = ""
    name_candidates = entities.get("PERSON", [])
    if name_candidates:
        # Filtrar candidatos de nombre que parezcan más un nombre real
        for candidate in name_candidates:
            if len(candidate.split()) >= 2 and not any(word.lower() in ["ingeniería", "universidad", "escuela"] for word in candidate.split()):
                name = candidate
                break
    
    # Si no encontramos un nombre adecuado, usar la primera línea del texto que podría ser el nombre
    if not name and lines:
        first_line = lines[0].strip()
        if first_line and len(first_line) < 50:  # Nombres típicamente no son muy largos
            name = first_line
    
    # Extraer email
    email = entities.get("EMAILS", [""])[0] if entities.get("EMAILS") else ""

    
    # Extraer teléfono - limpiar el número
    phone = entities.get("PHONES", [""])[0]
    phone = re.sub(r'[^0-9+]', '', phone) if phone else ""
    
    # Extraer ubicación
    location = find_value_in_tables(tables, ["mendoza", "argentina"])
    if not location:
        location = next((loc for loc in entities.get("GPE", []) if "mendoza" in loc.lower() or "argentina" in loc.lower()), "")
    
    # Extraer resumen profesional
    professional_summary = find_value_in_tables(tables, ["perfil profesional", "resumen", "objetivo"])
    
    # Extraer sección "sobre mí"
    about_me = find_value_in_tables(tables, ["sobre mí", "acerca de", "perfil personal"])
    
    # Experiencia: Buscar secciones de experiencia laboral
    experience_section = find_value_in_tables(tables, ["experiencia profesional", "experiencia laboral"])
    
    # Extraer experiencias individuales
    experiences = []
    exp_pattern = r"(.*?)\s*(\d{4}.*?Presente|\d{4}.*?\d{4}|[0-9]+\s*(?:año|años).*?experiencia)\s*(.*?)(?=\n\n|\Z)"
    
    for table in tables:
        for row in table:
            # Buscar títulos de trabajo
            title_keywords = ["administrador", "ayudante", "asistente", "desarrollador"]
            title = ""
            for k, v in row.items():
                if isinstance(v, str) and any(kw.lower() in v.lower() for kw in title_keywords):
                    title = v
                    
                    # Buscar fechas o períodos asociados
                    period = ""
                    for period_keywords in ["presente", "actual", "año", "años", "201", "202"]:
                        if period_keywords in str(row.get(k, "")) or (int(k)+1 < len(row) and period_keywords in str(row.get(str(int(k)+1), ""))):
                            period = row.get(str(int(k)+1), "")
                            break
                    
                    # Buscar descripciones
                    desc_lines = []
                    for i in range(1, 5):  # Buscar en las siguientes filas
                        row_index = table.index(row) + i
                        if row_index < len(table):
                            next_row = table[row_index]
                            for _, cell_value in next_row.items():
                                if isinstance(cell_value, str) and "•" in cell_value:
                                    desc_lines.append(clean_text(cell_value))
                    
                    description = ". ".join(desc_lines)
                    
                    if title:
                        experiences.append({
                            "title": clean_text(title),
                            "period": clean_text(period),
                            "description": description
                        })
    
    # Si no encontramos experiencias estructuradas, intentar extraerlas del texto
    if not experiences:
        exp_matches = re.finditer(exp_pattern, experience_section, re.DOTALL)
        for match in exp_matches:
            title = match.group(1).strip()
            period = match.group(2).strip()
            description = match.group(3).strip()
            experiences.append({
                "title": clean_text(title),
                "period": clean_text(period),
                "description": clean_text(description)
            })
    
    # Extraer educación
    education = []
    edu_institutions = ["universidad de mendoza", "escuela manuel ignacio molina", "escuela ejercito"]
    
    for table in tables:
        for row in table:
            for k, v in row.items():
                if isinstance(v, str) and any(edu.lower() in v.lower() for edu in edu_institutions):
                    institution = v
                    
                    # Buscar grado/título
                    degree = ""
                    next_row_index = table.index(row) + 1
                    if next_row_index < len(table):
                        next_row = table[next_row_index]
                        for _, cell_value in next_row.items():
                            if isinstance(cell_value, str) and ("ingeniería" in cell_value.lower() or "bachiller" in cell_value.lower()):
                                degree = cell_value
                                break
                    
                    # Buscar período
                    period = ""
                    for row_i in table:
                        for _, cell_value in row_i.items():
                            if isinstance(cell_value, str) and re.search(r'\d{4}-\d{4}|\d{4}\s*-\s*presente|actual', cell_value.lower()):
                                if clean_text(institution).lower() in text_without_linebreaks.lower()[text_without_linebreaks.lower().find(cell_value.lower())-100:text_without_linebreaks.lower().find(cell_value.lower())+100]:
                                    period = cell_value
                                    break
                    
                    education.append({
                        "institution": clean_text(institution),
                        "degree": clean_text(degree),
                        "period": clean_text(period)
                    })
    
    # Extraer habilidades técnicas
    technical_skills = []
    skill_sections = ["stack tecnológico", "tecnologías", "habilidades", "skills"]
    
    # Buscar en tablas
    for table in tables:
        for row in table:
            for k, v in row.items():
                if isinstance(v, str):
                    if "▹" in v or any(section.lower() in v.lower() for section in skill_sections):
                        skill_line = clean_text(v.replace("▹", ""))
                        if "/" in skill_line:
                            skills = [s.strip() for s in skill_line.split("/")]
                            technical_skills.extend(skills)
                        else:
                            technical_skills.append(skill_line)
    
    # Si no encontramos suficientes habilidades, buscar tecnologías comunes en el texto
    common_techs = ["python", "django", "flask", "java", "spring", "mysql", "postgresql", 
                     "git", "github", "linux", "maven", "api", "rest", "angular", "react"]
    
    if len(technical_skills) < 3:
        for tech in common_techs:
            if tech.lower() in text_without_linebreaks.lower() and tech not in technical_skills:
                technical_skills.append(tech.capitalize())
    
    # Eliminar duplicados y palabras vacías
    technical_skills = [skill for skill in technical_skills if len(skill) > 2 and skill.lower() not in ["las", "los", "con", "para"]]
    technical_skills = list(set(technical_skills))
    
    # Extraer idiomas
    languages = []
    lang_pattern = r"(?:▹|•)?\s*(\w+)\s*[-:]\s*(\w+)"
    
    for table in tables:
        for row in table:
            for k, v in row.items():
                if isinstance(v, str) and "idiomas" in v.lower():
                    # Buscar en filas cercanas
                    for i in range(1, 5):
                        row_index = table.index(row) + i
                        if row_index < len(table):
                            next_row = table[row_index]
                            for _, cell_value in next_row.items():
                                if isinstance(cell_value, str):
                                    lang_matches = re.findall(lang_pattern, cell_value)
                                    for lang_match in lang_matches:
                                        languages.append({
                                            "language": lang_match[0],
                                            "level": lang_match[1]
                                        })
    
    # Si no encontramos idiomas estructurados, al menos incluir español
    if not languages:
        languages.append({"language": "Español", "level": "Nativo"})
    
    # Extraer proyectos
    projects = []
    project_titles = ["Sistema de Gestión", "Plataforma", "Aplicación", "Desarrollo"]
    
    for table in tables:
        proj_info = {"name": "", "description": "", "technologies": []}
        
        for row in table:
            for k, v in row.items():
                if isinstance(v, str) and any(title.lower() in v.lower() for title in project_titles):
                    if not proj_info["name"]:  # Si no tenemos nombre, este es el primer encuentro del proyecto
                        proj_info["name"] = clean_text(v)
                    else:  # Si ya tenemos nombre, este podría ser un nuevo proyecto
                        if proj_info["description"]:  # Si ya tenemos descripción para el proyecto anterior
                            projects.append(proj_info.copy())
                            proj_info = {"name": clean_text(v), "description": "", "technologies": []}
                        else:
                            proj_info["name"] = clean_text(v)
                
                # Buscar descripciones de proyecto (generalmente con viñetas)
                elif isinstance(v, str) and "•" in v and proj_info["name"]:
                    if proj_info["description"]:
                        proj_info["description"] += ". " + clean_text(v)
                    else:
                        proj_info["description"] = clean_text(v)
                
                # Buscar tecnologías 
                elif isinstance(v, str) and any(tech.lower() in v.lower() for tech in common_techs) and proj_info["name"]:
                    techs = re.split(r'[\s,]+', v)
                    for tech in techs:
                        if tech.lower() in [t.lower() for t in common_techs]:
                            if tech not in proj_info["technologies"]:
                                proj_info["technologies"].append(tech)
        
        # Agregar el último proyecto si tiene información
        if proj_info["name"] and proj_info["description"]:
            projects.append(proj_info)
    
    # Extraer actividades
    activities = []
    activity_sections = ["actividades", "hobbies", "intereses"]
    
    for table in tables:
        for row in table:
            for k, v in row.items():
                if isinstance(v, str) and any(section.lower() in v.lower() for section in activity_sections):
                    # Buscar en filas cercanas
                    for i in range(1, 5):
                        row_index = table.index(row) + i
                        if row_index < len(table):
                            next_row = table[row_index]
                            for _, cell_value in next_row.items():
                                if isinstance(cell_value, str) and "▹" in cell_value:
                                    activity = clean_text(cell_value.replace("▹", ""))
                                    activities.append(activity)
    
    # Estructura final para embeddings
    structured_result = {
        "personal_info": {
            "full_name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "about": about_me
        },
        "professional_summary": professional_summary,
        "experience": experiences,
        "education": education,
        "skills": {
            "technical": technical_skills,
            "languages": languages
        },
        "projects": projects,
        "activities": activities
    }
    
    return structured_result

def process_cv(pdf_path, txt_dir="resultados_txt", json_dir="resultados_json"):
    try:
        logger.info(f"Procesando: {pdf_path}")
        with SuppressOutput():
            doc = fitz.open(pdf_path)
            full_text = "\n\n".join(extract_text(p) for p in doc)
            doc.close()

        # 🚨 Validación de contenido mínimo
        if not full_text.strip() or len(full_text.strip()) < 300:
            logger.warning(f"⚠️ El archivo {pdf_path} tiene poco texto ({len(full_text.strip())} caracteres). No se guarda ni procesa.")
            return None

        # Guardar texto
        Path(txt_dir).mkdir(parents=True, exist_ok=True)
        txt_path = Path(txt_dir) / (Path(pdf_path).stem + ".txt")
        txt_path.write_text(full_text, encoding="utf-8")
        logger.info(f"Texto guardado en: {txt_path}")

        # Tablas y entidades
        logger.info("Extrayendo tablas y entidades...")
        tables = extract_tables(pdf_path)
        entities = extract_entities(full_text)

        # Estructura optimizada para embeddings
        logger.info("Estructurando datos...")
        structured_result = extract_structured_data_for_embedding(full_text, tables, entities)

        # Guardar JSON estructurado
        Path(json_dir).mkdir(parents=True, exist_ok=True)
        result_path = Path(json_dir) / (Path(pdf_path).stem + "_structured.json")
        
        if structured_result is None:
            logger.error("No se pudo generar datos estructurados")
            return None

        try:
            json_content = json.dumps(structured_result, ensure_ascii=False, indent=2)
            result_path.write_text(json_content, encoding="utf-8")
            logger.info(f"JSON guardado en: {result_path}")
        except Exception as e:
            logger.error(f"Error al guardar JSON: {e}")
            logger.error(traceback.format_exc())
            return None

        logger.info(f"CV cargado correctamente: {Path(pdf_path).name}")
        return str(result_path)

    except Exception as e:
        logger.error(f"Error procesando {pdf_path}: {e}")
        logger.error(traceback.format_exc())
        return None


def main(input_dir=os.getenv("CANDIDATES_DIR"), workers=4):
    pdfs = glob.glob(os.path.join(input_dir, "*.pdf"))
    
    if not pdfs:
        logger.info("No se encontraron archivos PDF en la carpeta 'candidatos'")
        return
    
    logger.info(f"Encontrados {len(pdfs)} archivos PDF para procesar")
    
    # Verificar que las carpetas de destino existan o crearlas
    Path(os.getenv("TXT_DIR")).mkdir(parents=True, exist_ok=True)
    Path(os.getenv("JSON_DIR")).mkdir(parents=True, exist_ok=True)
    
    # Usar un solo proceso para evitar problemas de permisos en Windows
    results = []
    for pdf in pdfs:
        result = process_cv(pdf, txt_dir="resultados_txt", json_dir="resultados_json")
        if result:
            results.append(result)
    
    logger.info(f"Procesamiento completado: {len(results)} de {len(pdfs)} archivos procesados correctamente")
    
    # Verificar la existencia de los archivos JSON generados
    json_files = glob.glob(os.path.join("resultados_json", "*_structured.json"))
    logger.info(f"Archivos JSON generados: {len(json_files)}")
    for json_file in json_files:
        logger.info(f"  - {json_file}")

# Limpiar archivos temporales al salir
def cleanup_temp():
    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith('tmp'):
            try:
                path = os.path.join(temp_dir, item)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except:
                pass

atexit.register(cleanup_temp)

if __name__ == "__main__":
    main()
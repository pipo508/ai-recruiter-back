import os
import re
import json
import google.generativeai as genai
from google.generativeai import GenerationConfig
from dotenv import load_dotenv

load_dotenv()

# ─── Configuración de la API Key ─────────────────────────────────────────────
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Define la variable de entorno GOOGLE_API_KEY antes de ejecutar.")
genai.configure(api_key=api_key)

# ─── Parámetros del modelo ───────────────────────────────────────────────────
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=GenerationConfig(
        temperature=0.0,
        top_p=0.7
    )
)

# ─── Directorios y manifiesto ────────────────────────────────────────────────
INPUT_DIR     = os.getenv("TXT_DIR")
OUTPUT_DIR    = os.getenv("REWRITTEN_DIR")

if not os.path.exists(INPUT_DIR):
    raise RuntimeError(f"Directorio de entrada '{INPUT_DIR}' no encontrado.")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)  

MANIFEST_PATH = os.path.join(OUTPUT_DIR, "manifest.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cargamos o inicializamos el manifiesto
if os.path.exists(MANIFEST_PATH):
    with open(MANIFEST_PATH, "r", encoding="utf-8") as mf:
        manifest = json.load(mf)   # { "original.txt": "Salida_Nombre_Apellido.txt", ... }
else:
    manifest = {}

# ─── Plantilla de prompt ────────────────────────────────────────────────────
PROMPT_TEMPLATE = """
Antes de comenzar, detecta el nombre completo de la persona (nombre y apellido/s) en el texto. Escríbelo en la primera línea así:
Nombre detectado: NOMBRE COMPLETO

Luego, reescribe el siguiente texto con un lenguaje claro, preciso y profesional.

Organiza la información extraída en secciones coherentes y bien tituladas, corrigiendo cualquier error de formato, ortografía o estructura causado por el OCR.

🔍 Asegúrate de:
- Extraer y ordenar correctamente la información relevante, incluso si el texto original está desordenado.
- Corregir nombres propios, títulos, instituciones, fechas, correos electrónicos, direcciones y teléfonos.
- Mantener un estilo formal, directo y sin adornos innecesarios.
- Elimina cualquier rastro de formato original, como saltos de línea extra, guiones, o marcas de OCR.
- Si hay listas en el texto original, manténlas como listas en el texto reescrito, usando viñetas o números según sea apropiado.
- Asegúrate de que no haya espacios extra ni caracteres especiales que no sean necesarios.

🗂 Estructura sugerida (sigue este orden):
1. Información personal (incluye el nombre completo)
2. Perfil profesional (si aplica)
3. Experiencia laboral
4. Formación académica
5. Certificaciones
6. Idiomas
7. Habilidades técnicas
8. Referencias (si las hay)
9. Información de contacto

📌 Formato:
- Usa títulos claros para cada sección.
- Nombres de empresas, instituciones y cargos en mayúscula inicial.
- Fechas en formato MM/AAAA o solo AAAA si no hay más detalle.
- Correos electrónicos y teléfonos con formato estandarizado.

⚠️ Si el nombre del archivo "{file_base}" aparece dentro del texto, ignóralo.

Texto original:
\"\"\"{content}\"\"\"
"""

# ─── Función auxiliar para limpiar nombre detectado ───────────────────────────
def limpiar_nombre_detectado(linea):
    # Línea: "Nombre detectado: Juan Pérez"
    nombre = linea.split(":", 1)[1].strip().lower()
    nombre = re.sub(r'\s+', ' ', nombre)
    # Convertir a formato Archivo: "Juan_Perez.txt"
    return nombre.title().replace(" ", "_") + ".txt"

# ─── Procesamiento de archivos ───────────────────────────────────────────────
for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".txt"):
        continue

    # Si ya fue procesado, lo saltamos
    if fname in manifest:
        print(f"⚠️ {fname} ya procesado como {manifest[fname]}. Saltado.")
        continue

    in_path   = os.path.join(INPUT_DIR, fname)
    file_base = os.path.splitext(fname)[0]

    with open(in_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Creamos el prompt
    prompt = PROMPT_TEMPLATE.format(content=content, file_base=file_base)

    try:
        # Llamada a Gemini
        response  = model.generate_content(prompt)
        rewritten = response.text.strip()

        # Extraemos el nombre detectado y el contenido reescrito
        lines = rewritten.splitlines()
        if len(lines) > 0 and lines[0].lower().startswith("nombre detectado:"):
            primera_linea = lines[0]
            nuevo_nombre = limpiar_nombre_detectado(primera_linea)
            content = "\n".join(lines[1:]).strip()  # Tomamos solo el contenido a partir de la segunda línea
        else:
            # Fallback en caso de que Gemini no cumpla el formato
            nuevo_nombre = fname
            content = rewritten.strip()

        # Guardamos el archivo reescrito
        out_path = os.path.join(OUTPUT_DIR, nuevo_nombre)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Actualizamos el manifiesto y lo persistimos
        manifest[fname] = nuevo_nombre
        with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, ensure_ascii=False, indent=2)

        print(f"✅ {fname} reescrito y guardado como {nuevo_nombre}")

    except Exception as e:
        print(f"❌ Error con {fname}: {e}")
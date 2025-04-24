#!/usr/bin/env python3
import os
import subprocess
import sys
import json
from pathlib import Path
from OCR_IMAGES import process_resume
from EXTRACTORDETEXTOPDF import process_cv
from dotenv import load_dotenv

load_dotenv()
# Directorios
CANDIDATES_DIR = Path(os.getenv("CANDIDATES_DIR"))
TXT_DIR = Path(os.getenv("TXT_DIR"))
JSON_DIR = Path(os.getenv("JSON_DIR"))
REWRITTEN_DIR = Path(os.getenv("REWRITTEN_DIR"))
EMBEDDINGS_FILE = Path(os.getenv("EMBEDDINGS_FILE"))
PROMPT_FILE = Path(os.getenv("PROMPT_FILE"))

# Reportes
processed, skipped, missing_name = [], [], []

def print_header(title):
    print("\n" + "="*len(title))
    print(title)
    print("="*len(title) + "\n")

def cargar_embeddings_existentes():
    if not EMBEDDINGS_FILE.exists():
        return []
    with EMBEDDINGS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def guardar_embeddings(embeddings):
    with EMBEDDINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(embeddings, f, ensure_ascii=False, indent=2)

def generar_embeddings_incremental():
    print_header("Embeddings incrementales")
    existentes = cargar_embeddings_existentes()
    ya_subidos = {e['filename'] for e in existentes}

    nuevos_archivos = [f for f in REWRITTEN_DIR.glob("*.txt") if f.name not in ya_subidos]
    if not nuevos_archivos:
        print("🟢 Todos los archivos ya tienen embeddings.")
        return

    print(f"📄 Archivos nuevos: {len(nuevos_archivos)}")
    for f in nuevos_archivos:
        print(f" - {f.name}")

    temp_path = Path("temp_files.txt")
    with temp_path.open("w", encoding="utf-8") as f:
        for archivo in nuevos_archivos:
            f.write(f"{archivo.name}\n")

    try:
        subprocess.run([sys.executable, "EMBEDING.py", "--input-list", "temp_files.txt", "-o", "temp_embeddings.json"], check=True)
        nuevos = json.load(open("temp_embeddings.json", encoding="utf-8"))
        existentes.extend(nuevos)
        guardar_embeddings(existentes)
        os.remove("temp_embeddings.json")
        os.remove("temp_files.txt")
        print("✅ Embeddings actualizados.")
    except Exception as e:
        print(f"❌ Error en embeddings: {e}")

def eliminar_embedding():
    if not EMBEDDINGS_FILE.exists():
        print("⚠️ No hay embeddings.")
        return

    embeddings = cargar_embeddings_existentes()
    print_header("Eliminar embedding")
    for idx, e in enumerate(embeddings, 1):
        print(f" {idx}. {e['filename']}")
    sel = input("Número a eliminar (Enter para cancelar): ").strip()
    if not sel.isdigit():
        print("❌ Cancelado.")
        return

    idx = int(sel) - 1
    if 0 <= idx < len(embeddings):
        eliminado = embeddings.pop(idx)
        guardar_embeddings(embeddings)
        print(f"🗑️ Eliminado: {eliminado['filename']}")
    else:
        print("❌ Fuera de rango.")

def process_pdf(path):
    try:
        result = process_cv(str(path), txt_dir=str(TXT_DIR), json_dir=str(JSON_DIR))
        return bool(result)
    except Exception as e:
        print(f"❌ Error en PDF {path.name}: {e}")
        return False

def process_image(path):
    try:
        result = process_resume(str(path))
        return bool(result and result.get("full_text"))
    except Exception as e:
        print(f"❌ Error en imagen {path.name}: {e}")
        return False

def main():
    print_header("Paso 1: Extracción de CVs")
    if not CANDIDATES_DIR.exists():
        print("❌ Carpeta 'candidatos' no existe.")
        return

    for file in sorted(CANDIDATES_DIR.iterdir()):
        name = file.name
        txt_file = TXT_DIR / f"{file.stem}.txt"
        json_file = JSON_DIR / f"{file.stem}_structured.json"

        if txt_file.exists() and json_file.exists():
            print(f"⏩ {name} ya procesado.")
            skipped.append(name)
            continue

        if file.suffix.lower() == ".pdf":
            print(f"📄 Procesando PDF: {name}")
            success = process_pdf(file)
        elif file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}:
            print(f"📷 Procesando imagen: {name}")
            success = process_image(file)
        else:
            print(f"⛔ No soportado: {name}")
            success = False

        if success:
            processed.append(name)
        else:
            skipped.append(name)

    print_header("Resumen del Paso 1: Extracción completada")
    print(f"Total procesados : {len(processed)}")
    print(f"Total omitidos   : {len(skipped)}")
    if skipped:
        print("Archivos omitidos:")
        for i, file_name in enumerate(skipped, 1):
            print(f" {i}. {file_name}")

    if TXT_DIR.exists() and any(TXT_DIR.iterdir()):
        print_header("Paso 2: Reescritura con Gemini")
        if input("¿Reescribir con Gemini? (s/n): ").strip().lower().startswith("s"):
            try:
                subprocess.run([sys.executable, "GEMINI_REESCRIBIR.py"], check=True)
                print("✅ Reescritura lista.")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("ℹ️ Saltando reescritura.")

    if input("¿Eliminar embedding manualmente? (s/n): ").strip().lower().startswith("s"):
        eliminar_embedding()
        print("ℹ️ Puedes volver a cargar ese archivo ahora.")
        if input("¿Cargar nuevamente el archivo eliminado? (s/n): ").strip().lower().startswith("s"):
            generar_embeddings_incremental()

    if REWRITTEN_DIR.exists() and any(REWRITTEN_DIR.glob("*.txt")):
        print_header("Paso 3: Embeddings")
        if input("¿Generar embeddings? (s/n): ").strip().lower().startswith("s"):
            generar_embeddings_incremental()
        else:
            print("ℹ️ Embeddings omitidos.")

    print_header("Paso 4: Prompt para calificación")
    if input("¿Ingresar prompt manual? (s/n): ").strip().lower().startswith("s"):
        prompt = input("Escribe tu prompt: ").strip()
        if prompt:
            PROMPT_FILE.write_text(prompt, encoding="utf-8")
            print("✅ Prompt guardado.")
        else:
            print("⚠️ Prompt vacío, usando el existente.")
    else:
        print(f"✅ Usando {PROMPT_FILE}")

    print_header("Paso 5: Calificación de candidatos")
    try:
        subprocess.run([sys.executable, "CALIFICACION.py"], check=True)
    except Exception as e:
        print(f"❌ Error en calificación: {e}")

    print_header("Paso 6: Candidatos sin nombre")
    for json_path in sorted(JSON_DIR.glob("*_structured.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        full_name = data.get("personal_info", {}).get("full_name", "").strip()
        if not full_name:
            missing_name.append(json_path.stem.replace("_structured", ""))

    if missing_name:
        print("Candidatos sin nombre:")
        for i, name in enumerate(missing_name, 1):
            print(f" {i}. {name}")
    else:
        print("✅ Todos tienen nombre.")

    print_header("Resumen final")
    print(f"Procesados: {len(processed)}")
    print(f"Omitidos  : {len(skipped)}")
    

if __name__ == "__main__":
    main()

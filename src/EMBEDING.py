import os
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional
import google.generativeai as genai
from tqdm import tqdm
from typing import List, Tuple
import re
from dotenv import load_dotenv
import os

load_dotenv()  # Carga las variables de entorno desde .env




def configure_api(key_env_var: str = "GOOGLE_API_KEY") -> None:
    api_key = os.getenv(key_env_var)
    if not api_key:
        logging.error("No se encontró la clave API en la variable %s", key_env_var)
        raise EnvironmentError(f"Debes configurar la variable de entorno {key_env_var} con tu API Key.")
    genai.configure(api_key=api_key)
    logging.debug("API Key de Google Gemini configurada correctamente.")


def load_texts_from_file(file_path: Path) -> List[Tuple[str, str]]:
    """
    Carga los archivos listados en temp_files.txt y devuelve una lista de tuplas (filename, content).
    """
    if not file_path.exists():
        logging.error("El archivo %s no existe.", file_path)
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    docs: List[Tuple[str, str]] = []
    with file_path.open("r", encoding="utf-8") as f:
        filenames = [line.strip() for line in f.readlines()]
        for filename in filenames:
            file_path = Path(os.getenv("REWRITTEN_DIR")) / filename
            if file_path.exists():
                try:
                    text = file_path.read_text(encoding="utf-8").strip()
                    if text:
                        docs.append((filename, text))
                except Exception as e:
                    logging.warning("No se pudo leer %s: %s", filename, e)
    return docs


def preprocess_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'^\s*[\•\-\*]\s+', '- ', text, flags=re.MULTILINE)
    return text


def embed_documents(docs: List[Tuple[str, str]], model_name: str = "models/embedding-001", batch_size: Optional[int] = None) -> List[Dict]:
    results: List[Dict] = []
    total = len(docs)

    def extract_title(filename: str, text: str) -> str:
        for line in text.split("\n"):
            if line.lower().startswith("información personal"):
                lines = text.split("\n")
                idx = lines.index(line)
                for next_line in lines[idx + 1:]:
                    if "Nombre:" in next_line:
                        return next_line.replace("Nombre:", "").strip()
        return filename.replace(".txt", "").replace("_", " ")

    if batch_size and batch_size > 1:
        for i in tqdm(range(0, total, batch_size), desc="Lotes de embeddings"):
            batch = docs[i : i + batch_size]
            contents = [preprocess_text(text) for _, text in batch]
            titles = [extract_title(filename, text) for filename, text in batch]
            try:
                response = genai.embed_content(
                    model=model_name,
                    content=contents,
                    task_type="retrieval_document",
                    title=titles
                )
                for (filename, _), emb in zip(batch, response["embedding"]):
                    results.append({"filename": filename, "embedding": emb})
                    logging.debug("Embedding para %s: dimensión %d", filename, len(emb))
            except Exception as e:
                logging.error("Error en batch %d-%d: %s", i, i + batch_size, e)
    else:
        for filename, text in tqdm(docs, desc="Generando embeddings"):
            try:
                resp = genai.embed_content(
                    model=model_name,
                    content=preprocess_text(text),
                    task_type="retrieval_document",
                    title=extract_title(filename, text)
                )
                emb = resp["embedding"]
                results.append({"filename": filename, "embedding": emb})
                logging.debug("Embedding para %s: dimensión %d", filename, len(emb))
            except Exception as e:
                logging.warning("Error al generar embedding para %s: %s", filename, e)
    return results


def save_embeddings(embeddings: List[Dict], output_path: Path) -> None:
    try:
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(embeddings, f, ensure_ascii=False, indent=2)
        logging.info("Embeddings guardados en %s", output_path)
    except Exception as e:
        logging.error("No se pudo guardar embeddings: %s", e)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera embeddings de documentos .txt usando Google Gemini.")
    parser.add_argument("-o", "--output", type=Path, default=Path("embeddings.json"), help="Archivo JSON de salida")
    parser.add_argument("--input-list", type=Path, required=True, help="Archivo con la lista de archivos para procesar")
    parser.add_argument("-b", "--batch-size", type=int, default=None, help="Tamaño de lote para peticiones de batch embeddings")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Nivel de logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s [%(levelname)s] %(message)s")

    configure_api()

    docs = load_texts_from_file(args.input_list)
    if not docs:
        logging.warning("No se encontraron documentos para procesar en %s", args.input_list)
        return
    logging.info("Cargados %d documentos para embedding.", len(docs))

    embeddings = embed_documents(docs, model_name="models/embedding-001", batch_size=args.batch_size)

    save_embeddings(embeddings, args.output)


if __name__ == '__main__':
    main()

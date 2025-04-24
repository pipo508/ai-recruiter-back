#!/usr/bin/env python3
"""
Script para buscar documentos similares a un prompt usando embeddings de Google Gemini.
"""
import os
import json
import numpy as np
import google.generativeai as genai
from pathlib import Path
import logging
import re
from typing import List, Tuple
from dotenv import load_dotenv
import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables de entorno desde .env


def configure_api(key_env_var: str = "GOOGLE_API_KEY") -> None:
    """
    Configura la API Key de Google Generative AI / Gemini.
    """
    api_key = os.getenv(key_env_var)
    if not api_key:
        logging.error("No se encontró la clave API en la variable %s", key_env_var)
        raise EnvironmentError(
            f"Debes configurar la variable de entorno {key_env_var} con tu API Key."
        )
    genai.configure(api_key=api_key)
    logging.debug("API Key de Google Gemini configurada correctamente.")

def preprocess_text(text: str) -> str:
    """
    Preprocesa el texto para embeddings: normaliza espacios y elimina caracteres no deseados.
    """
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'^\s*[\•\-\*]\s+', '- ', text, flags=re.MULTILINE)
    return text

def load_embeddings(embeddings_path: str) -> Tuple[List[str], np.ndarray]:
    """
    Carga embeddings desde un archivo JSON que contenga una lista de dicts
    con {'filename', 'embedding': [float,...]}.
    """
    try:
        with open(embeddings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        filenames = [item['filename'] for item in data]
        vectors = np.array([item['embedding'] for item in data])
        logging.info("Cargados %d embeddings desde %s", len(filenames), embeddings_path)
        return filenames, vectors
    except Exception as e:
        logging.error("Error al cargar embeddings desde %s: %s", embeddings_path, e)
        raise

def embed_query(text: str, model_name: str = "models/embedding-001") -> np.ndarray:
    """
    Genera el embedding del texto de consulta.
    """
    try:
        response = genai.embed_content(
            model=model_name,
            content=preprocess_text(text),
            task_type="retrieval_query"
        )
        embedding = np.array(response["embedding"])
        logging.debug("Embedding generado para consulta de longitud %d", len(embedding))
        return embedding
    except Exception as e:
        logging.error("Error al generar embedding para consulta: %s", e)
        raise

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Calcula la similitud coseno entre dos vectores.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        logging.warning("Norma de vector es cero, retornando similitud 0")
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)

def find_top_k(query_vec: np.ndarray, doc_vecs: np.ndarray, filenames: List[str], k: int = 10) -> List[Tuple[str, float]]:
    """
    Devuelve los k documentos más cercanos según similitud coseno.
    """
    try:
        sims = np.array([cosine_similarity(query_vec, doc_vec) for doc_vec in doc_vecs])
        idx_sorted = np.argsort(-sims)
        top_idxs = idx_sorted[:k]
        results = [(filenames[i], float(sims[i])) for i in top_idxs]
        logging.info("Encontrados %d documentos similares", len(results))
        return results
    except Exception as e:
        logging.error("Error al buscar documentos similares: %s", e)
        raise

def save_top_results(
    results: List[Tuple[str, float]],
    output_file: str = "resultados_similares.txt",
    folder_path: str = "resultados_reescritos",
    max_lines_per_doc: int = 50
) -> None:
    """
    Guarda los resultados en un archivo de texto, incluyendo el contenido de los documentos.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Top {len(results)} documentos más similares al prompt:\n\n")
            
            for i, (fname, score) in enumerate(results, 1):
                f.write(f"{i}. {fname}: similitud={score:.4f}\n")
                
                doc_path = Path(folder_path) / fname
                try:
                    content = doc_path.read_text(encoding='utf-8')
                    lines = content.split('\n')[:max_lines_per_doc]
                    content = '\n'.join(lines)
                    if len(lines) == max_lines_per_doc:
                        content += '\n[... Contenido truncado]'
                    f.write("Contenido:\n")
                    f.write(f"{content}\n")
                except Exception as e:
                    f.write(f"No se pudo leer el contenido del archivo: {e}\n")
                
                f.write("-" * 80 + "\n\n")
        
        logging.info("Resultados guardados en %s", output_file)
    except Exception as e:
        logging.error("Error al guardar resultados: %s", e)
        raise

def main(
    embeddings_file: str = os.getenv("EMBEDDINGS_FILE"),
    prompt_file: str = os.getenv("PROMPT_FILE"),
    folder_path: str = os.getenv("REWRITTEN_DIR"),
    output_file: str = "resultados_similares.txt",
    top_k: int = 10
) -> None:

    """
    Busca los documentos más similares al prompt usando embeddings.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    configure_api()
    
    filenames, doc_vectors = load_embeddings(embeddings_file)
    
    if not Path(prompt_file).exists():
        logging.error("No existe el archivo de prompt: %s", prompt_file)
        raise FileNotFoundError(f"No existe el archivo de prompt: {prompt_file}")
    
    query_text = Path(prompt_file).read_text(encoding='utf-8').strip()
    logging.info("Prompt cargado desde %s", prompt_file)
    
    query_vec = embed_query(query_text)
    
    results = find_top_k(query_vec, doc_vectors, filenames, k=top_k)
    
    print(f"Top {top_k} documentos más similares a tu prompt:\n")
    for fname, score in results:
        print(f"- {fname}: similitud={score:.4f}")
    
    save_top_results(results, output_file, folder_path)

if __name__ == '__main__':
    main()
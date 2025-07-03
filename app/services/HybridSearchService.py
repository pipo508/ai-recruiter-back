
import os
import json
import numpy as np
from flask import current_app
from datetime import datetime
from typing import List, Dict, Tuple
import re

from app.services.OpenAIService import OpenAIRewriteService
from app.services.SearchHistoryService import SearchHistoryService
from app.extensions import get_faiss_index
from app.models.Candidate import Candidate

class HybridSearchService:
    def __init__(self):
        self.openai_service = OpenAIRewriteService()
        self.history_service = SearchHistoryService()
        
        # Configuración de pesos para el scoring híbrido
        self.semantic_weight = 0.7  # 70% peso semántico
        self.exact_weight = 0.3     # 30% peso exacto
        self.keyword_boost = 15     # Puntos extra por keyword encontrada
        
    def perform_hybrid_search(self, query: str, k: int = 10) -> dict:
        """
        Búsqueda híbrida: combina semántica + exacta
        """
        # Paso 1: Extraer keywords críticas
        critical_keywords = self.openai_service.extraer_keywords_criticas(query)
        current_app.logger.info(f"Keywords críticas extraídas: {critical_keywords}")
        
        # Paso 2: Búsqueda semántica (tu lógica actual)
        semantic_results = self._perform_semantic_search(query, k * 2)  # Buscar más candidatos
        
        # Paso 3: Si no hay keywords críticas, devolver solo semántica
        if not critical_keywords:
            current_app.logger.info("No hay keywords críticas, usando solo búsqueda semántica")
            final_results = semantic_results[:k]  # Tomar solo los k mejores
        else:
            # Paso 4: Aplicar filtro exacto y re-rankear
            final_results = self._apply_exact_matching(semantic_results, critical_keywords, k)
        
        # Paso 5: Guardar resultados
        filename = self._save_results_to_file(query, final_results, critical_keywords)
        search_result_db = self.history_service.save_search_result(query, final_results, filename)
        
        return {
            'results': final_results,
            'critical_keywords': critical_keywords,
            'search_result_id': search_result_db.id if search_result_db else None
        }
    
    def _perform_semantic_search(self, query: str, k: int) -> list:
        """
        Búsqueda semántica (tu lógica actual)
        """
        query_processed = self.openai_service.expandir_consulta_con_llm(query)
        current_app.logger.info(f"Consulta procesada: {query_processed}")
        
        embedding = self.openai_service.generate_embedding(query_processed)
        faiss_idx = get_faiss_index()
        
        if faiss_idx is None:
            raise Exception("Índice FAISS no disponible")
        
        query_vector = np.array([embedding], dtype=np.float32)
        distances, indices = faiss_idx.search(query_vector, k)
        
        return self._process_faiss_results(distances, indices)
    
    def _apply_exact_matching(self, semantic_results: list, critical_keywords: List[str], k: int) -> list:
        """
        Aplica matching exacto y re-rankea los resultados
        """
        enhanced_results = []
        
        for result in semantic_results:
            # Obtener texto completo del candidato para búsqueda exacta
            candidate_text = self._get_candidate_full_text(result)
            
            # Contar keywords encontradas
            found_keywords = self._count_exact_matches(candidate_text, critical_keywords)
            
            # Calcular nuevo score
            semantic_score = result['similarity_percentage']
            exact_matches = len(found_keywords)
            total_keywords = len(critical_keywords)
            
            # Score exacto: porcentaje de keywords encontradas
            exact_score = (exact_matches / total_keywords * 100) if total_keywords > 0 else 0
            
            # Score final híbrido
            final_score = (
                semantic_score * self.semantic_weight + 
                exact_score * self.exact_weight + 
                exact_matches * self.keyword_boost
            )
            
            # Asegurar que no exceda 100%
            final_score = min(final_score, 100)
            
            # Agregar información extra al resultado
            enhanced_result = result.copy()
            enhanced_result.update({
                'semantic_score': semantic_score,
                'exact_score': exact_score,
                'similarity_percentage': final_score,  # Reemplazar score original
                'found_keywords': found_keywords,
                'missing_keywords': [kw for kw in critical_keywords if kw not in found_keywords]
            })
            
            enhanced_results.append(enhanced_result)
        
        # Re-ordenar por score final y tomar los k mejores
        enhanced_results.sort(key=lambda x: x['similarity_percentage'], reverse=True)
        return enhanced_results[:k]
    
    def _get_candidate_full_text(self, result: dict) -> str:
        """
        Extrae todo el texto del candidato para búsqueda exacta
        """
        profile = result.get('profile', {})
        
        # Combinar todos los campos de texto del perfil
        text_parts = []
        
        # Campos principales
        for field in ['Nombre completo', 'Puesto actual', 'Habilidad principal', 
                     'Descripción profesional', 'Candidato ideal']:
            value = profile.get(field, '')
            if value:
                text_parts.append(str(value))
        
        # Habilidades clave
        habilidades = profile.get('Habilidades clave', [])
        if habilidades:
            text_parts.extend([str(h) for h in habilidades])
        
        # Experiencia profesional
        experiencias = profile.get('Experiencia Profesional', [])
        for exp in experiencias:
            for field in ['Puesto', 'Empresa', 'Descripción breve del rol']:
                value = exp.get(field, '')
                if value:
                    text_parts.append(str(value))
        
        # Educación
        educaciones = profile.get('Educación', [])
        for edu in educaciones:
            for field in ['Título o carrera', 'Institución', 'Descripción breve']:
                value = edu.get(field, '')
                if value:
                    text_parts.append(str(value))
        
        return ' '.join(text_parts).lower()
    
    def _count_exact_matches(self, candidate_text: str, keywords: List[str]) -> List[str]:
        """
        Cuenta las keywords que aparecen literalmente en el texto
        """
        found_keywords = []
        candidate_text_lower = candidate_text.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Buscar la keyword como palabra completa (no como substring)
            if re.search(r'\b' + re.escape(keyword_lower) + r'\b', candidate_text_lower):
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _process_faiss_results(self, distances, indices) -> list:
        """
        Procesa los resultados de FAISS (tu lógica actual)
        """
        processed_results = []
        for i in range(len(indices[0])):
            if indices[0][i] == -1: 
                break
            
            document_id = int(indices[0][i])
            candidate = Candidate.query.filter_by(document_id=document_id).first()

            if not candidate:
                current_app.logger.warning(f"Doc {document_id} en FAISS sin perfil de candidato. Se omite.")
                continue

            distance = distances[0][i].item()
            similarity_percentage = round((1 / (1 + distance)) * 100, 2)
            
            processed_results.append({
                'document_id': candidate.document_id,
                'filename': candidate.document.filename,
                'similarity_percentage': similarity_percentage,
                'profile': candidate.to_dict()
            })
        return processed_results
    
    def _save_results_to_file(self, query: str, results: list, critical_keywords: list) -> str:
        """
        Guarda los resultados con información adicional del híbrido
        """
        try:
            resultados_folder = 'resultados'
            os.makedirs(resultados_folder, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f'resultados_hybrid_{timestamp}.json'
            filepath = os.path.join(resultados_folder, filename)
            
            data = {
                'query': query,
                'critical_keywords': critical_keywords,
                'search_type': 'hybrid',
                'results': results
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            current_app.logger.info(f"Resultados híbridos guardados en {filepath}")
            return filename
        except Exception as e:
            current_app.logger.error(f"Error al guardar resultados híbridos: {e}")
            return None
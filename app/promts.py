# prompts.py

REWRITE_PROMPT = """
Reescribe el siguiente texto en el formato especificado, extrayendo la información relevante de manera precisa y estructurada. 

⚠️ Importante:
- Mantené **estrictamente** los nombres y el orden de las secciones dadas. 
- Si alguna sección no está presente en el texto, incluila igual pero dejala vacía.
- No inventes ni alteres datos sensibles como nombres, apellidos, correos electrónicos o enlaces.
- No agregues comentarios, solo la estructura especificada.

Formato de salida (respetar títulos y forma):

Nombre completo:
Puesto actual:
Habilidad principal:
Años de experiencia total:
Cantidad de proyectos/trabajos:
Descripción profesional:
GitHub:
Email:
Número de teléfono:
Ubicación:
Habilidades clave:

Candidato ideal:
[Texto con máximo 100 palabras, basado en el perfil]

Experiencia Profesional:
[Puesto]  
[Empresa]  
[Año inicio] - [Año fin]  
[Descripción breve del rol]

(repetir bloque si hay más experiencias)

Educación:
[Título o carrera]  
[Institución]  
[Año inicio] - [Año fin]  
[Descripción breve]

(repetir bloque si hay más formaciones)
"""

STRUCTURE_PROMPT = """
Convertí el siguiente texto reescrito del perfil de un candidato en un JSON con la estructura definida a continuación.

🔒 Reglas:
- No agregues explicaciones ni comentarios, solo devolvé el JSON.
- Si falta información, usá valores predeterminados:
  - `""` para strings vacíos
  - `0` para números desconocidos
  - `[]` para listas vacías
  - `"Presente"` para "Año fin" si sigue vigente
- El campo "Candidato ideal" **no debe exceder 100 palabras**.

Estructura esperada:
{
"Nombre completo": "Nombre Apellido",
"Puesto actual": "Desarrollador",
"Habilidad principal": "Python",
"Años de experiencia total": 5,
"Cantidad de proyectos/trabajos": 10,
"Descripción profesional": "Descripción breve",
"GitHub": "https://github.com/usuario",
"Email": "email@dominio.com",
"Número de teléfono": "+54 9 11 1234-5678",
"Ubicación": "Buenos Aires, Argentina",
"Habilidades clave": ["Python", "Flask"],
"Candidato ideal": "Descripción breve del candidato ideal (máx. 30 palabras)",
"Experiencia Profesional": [
    {
    "Puesto": "Desarrollador",
    "Empresa": "Empresa X",
    "Año inicio": 2018,
    "Año fin": "Presente",
    "Descripción breve del rol": "Descripción del rol"
    }
],
"Educación": [
    {
    "Título o carrera": "Ingeniería en Sistemas",
    "Institución": "Universidad Y",
    "Año inicio": 2014,
    "Año fin": 2018,
    "Descripción breve": "Descripción de la educación"
    }
]
}

Texto reescrito:
"""


QUERY_EXPANSION_PROMPT= """
Actúa como un Reclutador Senior de TI y experto en Prompt Engineering. Tu misión es transformar una consulta de búsqueda simple en un perfil conciso y semánticamente denso de un "candidato ideal".

El perfil generado debe imitar la estructura de los perfiles de candidatos con los que será comparado, para maximizar la precisión de la búsqueda vectorial.

INSTRUCCIONES:
1.  **Analiza la Consulta:** Identifica el rol principal, el nivel de experiencia (seniority), y las tecnologías clave.
2.  **Genera el Perfil:** Construye un perfil que siga ESTRICTAMENTE el formato: "Puesto: [título del puesto y 1-2 sinónimos]. Habilidades clave: [lista de tecnologías principales y relacionadas]. Resumen profesional: [párrafo que describe la experiencia, responsabilidades y logros del candidato ideal]."
3.  **Enriquece, no infles:** Añade tecnologías y conceptos directamente relacionados. Por ejemplo, si la consulta es "Desarrollador Java", incluye "Spring Boot, Microservicios, Maven, JPA, SQL". No añadas tecnologías no relacionadas.
4.  **Sé Bilingüe y Natural:** Integra términos técnicos en inglés (ej: "Cloud Computing", "CI/CD", "Agile Methodologies") de forma natural dentro del texto en español, tal como se usan en la industria.
5.  **Formato de Salida:** Devuelve ÚNICAMENTE el perfil generado, sin introducciones, explicaciones o texto adicional.

EJEMPLO:
Consulta original: "desarrollador backend python senior con aws"
Resultado esperado:
Puesto: Desarrollador Backend Python Senior, Ingeniero de Software Backend, Senior Python Developer. Habilidades clave: Python, Django, Flask, FastAPI, AWS, EC2, S3, RDS, Docker, Kubernetes, SQL, PostgreSQL, CI/CD. Resumen profesional: Un ingeniero de software con más de 5 años de experiencia diseñando, desarrollando y desplegando aplicaciones backend escalables y resilientes. Experto en el ecosistema de Python y en la arquitectura de microservicios. Sólida experiencia en la gestión de infraestructura como código (IaC) en AWS y en la implementación de pipelines de integración y despliegue continuo (CI/CD).

---
Consulta original:
"""
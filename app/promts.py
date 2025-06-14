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
[Texto con máximo 30 palabras, basado en el perfil]

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
- El campo "Candidato ideal" **no debe exceder 30 palabras**.

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
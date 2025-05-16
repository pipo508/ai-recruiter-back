"""
Script para guardar el formulario HTML en la carpeta static de la aplicación.
Ejecutar una vez para configurar el formulario de prueba.
"""

import os

# Crear directorio static si no existe
static_dir = os.path.join('app', 'static')
os.makedirs(static_dir, exist_ok=True)

# Contenido del formulario HTML
html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carga de PDFs</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        form {
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: bold;
        }
        input[type="text"], input[type="file"] {
            margin-bottom: 15px;
            padding: 8px;
            width: 100%;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #45a049;
        }
        #result {
            background-color: #e9f7ef;
            padding: 15px;
            border-radius: 8px;
            display: none;
        }
        .success {
            color: #2ecc71;
        }
        .error {
            color: #e74c3c;
        }
        pre {
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <h1>Procesamiento de Archivos PDF</h1>
    
    <form id="uploadForm">
        <div>
            <label for="userId">ID de Usuario:</label>
            <input type="text" id="userId" name="user_id" required>
        </div>
        
        <div>
            <label for="pdfFiles">Seleccionar PDFs:</label>
            <input type="file" id="pdfFiles" name="files[]" accept=".pdf" multiple required>
        </div>
        
        <button type="submit">Procesar PDFs</button>
    </form>
    
    <div id="result">
        <h2>Resultado:</h2>
        <pre id="resultContent"></pre>
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async function(event) {
            event.preventDefault();
            
            const userId = document.getElementById('userId').value;
            const files = document.getElementById('pdfFiles').files;
            
            if (!userId || files.length === 0) {
                alert('Por favor complete todos los campos requeridos.');
                return;
            }
            
            const formData = new FormData();
            formData.append('user_id', userId);
            
            for (let i = 0; i < files.length; i++) {
                formData.append('files[]', files[i]);
            }
            
            try {
                const response = await fetch('/document/process-pdfs', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                const resultDiv = document.getElementById('result');
                const resultContent = document.getElementById('resultContent');
                
                resultContent.textContent = JSON.stringify(result, null, 2);
                resultDiv.style.display = 'block';
                
                if (!response.ok) {
                    resultDiv.className = 'error';
                } else {
                    resultDiv.className = 'success';
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error al procesar los archivos: ' + error.message);
            }
        });
    </script>
</body>
</html>
"""

# Escribir el contenido al archivo
html_file_path = os.path.join(static_dir, 'upload_pdf.html')
with open(html_file_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Archivo HTML guardado en: {html_file_path}")

# Crear directorios necesarios para la aplicación
os.makedirs('uploads', exist_ok=True)
os.makedirs('textos_extraidos', exist_ok=True)
os.makedirs('textos_no_extraidos', exist_ok=True)

print("Directorios necesarios creados.")
print("Todo listo para probar la carga de PDFs.")
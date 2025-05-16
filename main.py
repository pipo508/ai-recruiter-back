"""
Punto de entrada principal de la aplicación Flask.
Crea y ejecuta la aplicación usando la configuración definida en app/__init__.py.
"""
import os
from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
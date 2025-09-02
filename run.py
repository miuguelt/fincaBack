import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

from app import create_app, db
from flask import jsonify
from flask_jwt_extended.exceptions import JWTExtendedException

app = create_app('development')

@app.errorhandler(JWTExtendedException)
def handle_jwt_errors(e):
    return jsonify({"error": str(e)}), 401

with app.app_context():
    db.create_all()

# -------------------------------------------------------------
# Utilidad: resolver contexto SSL desde variables de entorno
# - Para evitar el error NET::ERR_CERT_AUTHORITY_INVALID en dev,
#   puedes generar un certificado confiable localmente (mkcert)
#   y apuntar las variables SSL_CERT_FILE y SSL_KEY_FILE.
# - Si no existen, se usa 'adhoc' como fallback.
# -------------------------------------------------------------

def _resolve_ssl_context():
    use_https = os.getenv('USE_HTTPS', 'true').lower() == 'true'
    if not use_https:
        print("[RUN] HTTPS desactivado (USE_HTTPS=false)")
        return None

    cert_file = os.getenv('SSL_CERT_FILE')
    key_file = os.getenv('SSL_KEY_FILE')

    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"[RUN] HTTPS con certificado provisto\n  CERT: {cert_file}\n  KEY : {key_file}")
        return (cert_file, key_file)

    print("[RUN] HTTPS con certificado adhoc (autofirmado)")
    return 'adhoc'

if __name__ == "__main__":
    # Lee el puerto desde las variables de entorno o usa 8081 por defecto
    port = int(os.environ.get('PORT', 8081))

    ssl_context = _resolve_ssl_context()

    # Ejecutar la app (HTTPS si ssl_context no es None)
    app.run(host="0.0.0.0", port=port, debug=True, ssl_context=ssl_context)
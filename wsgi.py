
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

from app import create_app, db
app = create_app()

with app.app_context():
    db.create_all()

def _resolve_ssl_context():
    use_https = os.getenv('USE_HTTPS', 'true').lower() == 'true'
    if not use_https:
        return None

    cert_file = os.getenv('SSL_CERT_FILE')
    key_file = os.getenv('SSL_KEY_FILE')

    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        return (cert_file, key_file)

    return 'adhoc'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8081))
    ssl_context = _resolve_ssl_context()
    app.run(host="0.0.0.0", port=port, debug=False, ssl_context=ssl_context)

from flask import jsonify
from flask_jwt_extended.exceptions import JWTExtendedException

@app.errorhandler(JWTExtendedException)
def handle_jwt_errors(e):
    return jsonify({"error": str(e)}), 401
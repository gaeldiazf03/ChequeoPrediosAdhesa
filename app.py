from flask import Flask
import os
from rutas.login import login_bp
from rutas.dashboard import dashboard_bp
from rutas.mapa import mapa_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tu_clave_secreta')

# Registro de Blueprints
app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(mapa_bp)

if __name__ == '__main__':
    app.run(debug=True)
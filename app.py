from flask import Flask, render_template, session, request
import os
from dotenv import load_dotenv
from rutas.login import login_bp
from rutas.dashboard import dashboard_bp
from rutas.mapa import mapa_bp
from rutas.admin import admin_bp
from rutas.actividades import actividades_bp
from services.notificaciones_reintentos import iniciar_scheduler_reintentos
from services.reportes_programados import iniciar_scheduler_reportes_programados


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tu_clave_secreta')

# Cargar variables desde .env cuando se ejecuta directamente con `python app.py`
load_dotenv()

# Registro de Blueprints
app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(mapa_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(actividades_bp)

iniciar_scheduler_reintentos()
iniciar_scheduler_reportes_programados()

# === RUTA DE ACCESO DENEGADO ===
@app.route('/acceso-denegado')
def acceso_denegado():
    """Página que se muestra cuando un usuario intenta acceder sin permisos."""
    usuario = session.get('username', 'Usuario')
    permiso = request.args.get('permiso', 'desconocido')
    return render_template('acceso_denegado.html', usuario=usuario, permiso=permiso), 403

# === RUTA DE ERROR 500 ===
@app.errorhandler(500)
def error_servidor(error):
    """Maneja errores del servidor."""
    return render_template('error_500.html', error=str(error)), 500

# === RUTA DE ERROR 404 ===
@app.errorhandler(404)
def error_no_encontrado(error):
    """Maneja rutas no encontradas."""
    return render_template('error_404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
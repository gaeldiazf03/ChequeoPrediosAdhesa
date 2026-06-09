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


def _debe_iniciar_schedulers():
    """Evita hilos duplicados en debug/reloader y permite apagarlos por entorno."""
    if os.environ.get('RUN_SCHEDULERS', '1') != '1':
        return False

    # En debug con reloader, solo el proceso hijo debe iniciar hilos.
    if os.environ.get('FLASK_DEBUG') == '1' and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return False

    return True


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'tu_clave_secreta')

    # Registro de Blueprints
    app.register_blueprint(login_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(mapa_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(actividades_bp)

    if _debe_iniciar_schedulers():
        iniciar_scheduler_reintentos()
        iniciar_scheduler_reportes_programados()

    # === RUTA DE ACCESO DENEGADO ===
    @app.route('/acceso-denegado')
    def acceso_denegado():
        """Pagina que se muestra cuando un usuario intenta acceder sin permisos."""
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

    return app


app = create_app()

if __name__ == '__main__':
    host = os.environ.get('APP_HOST', '127.0.0.1')
    port = int(os.environ.get('APP_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host=host, port=port, debug=debug)
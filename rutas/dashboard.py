from flask import Blueprint, render_template, request, session, redirect, url_for
from database import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def index():
    if not session.get('logeado'): 
        return redirect(url_for('login.index')) 
    
    slots = db.obtener_todos_los_slots()
    usuarios = db.obtener_todos_los_usuarios() if session.get('rol') == 'admin' else []
    
    return render_template('dashboard.html', slots=slots, usuarios=usuarios, rol_actual=session.get('rol'))

@dashboard_bp.route('/cargar_kml/<int:slot_id>', methods=['POST'])
def cargar(slot_id):
    if not session.get('logeado'): return redirect(url_for('login.index'))
    
    archivo = request.files.get('kml_file')
    if archivo and archivo.filename.endswith('.kml'):
        db.guardar_kml_en_slot(slot_id, archivo.read().decode('utf-8', errors='replace'))
        db.registrar_log(session.get('usuario'), "Carga KML", f"Slot ID: {slot_id}")
    
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/eliminar_kml/<int:slot_id>', methods=['POST'])
def eliminar(slot_id):
    if not session.get('logeado'): return redirect(url_for('login.index'))
    
    password_ingresada = request.form.get('password')
    usuario_actual = session.get('usuario')
    
    if db.verificar_usuario_y_obtener_datos(usuario_actual, password_ingresada)[0]:
        db.vaciar_slot(slot_id)
        db.registrar_log(usuario_actual, "Eliminación KML", f"Slot ID: {slot_id}")
        
    return redirect(url_for('dashboard.index'))

# Envoltorios (Wrappers) para no romper los botones del dashboard.html original
@dashboard_bp.route('/admin/toggle_permiso/<int:user_id>', methods=['POST'])
def admin_toggle_permiso(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_agregar')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_edicion/<int:user_id>', methods=['POST'])
def admin_toggle_edicion(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_editar')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_agregar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_agregar_tareas(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_agregar_tareas')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_marcar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_marcar_tareas(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_marcar_tareas')
    return redirect(url_for('dashboard.index'))

# --- RUTAS DE ADMINISTRADOR RECUPERADAS ---
@dashboard_bp.route('/admin/crear_usuario', methods=['POST'])
def crear_usuario():
    if session.get('rol') == 'admin':
        # Cambiado 'nuevo_username' por 'nuevo_usuario' para coincidir con el HTML
        username = request.form.get('nuevo_usuario') 
        password = request.form.get('nueva_password')
        if username and password:
            db.crear_nuevo_usuario(username, password)
            db.registrar_log(session.get('usuario'), "Crear Usuario", f"Usuario: {username}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/eliminar_usuario/<int:user_id>', methods=['POST'])
def admin_eliminar_usuario(user_id):
    if session.get('rol') == 'admin':
        db.eliminar_usuario(user_id)
        db.registrar_log(session.get('usuario'), "Eliminar Usuario", f"ID: {user_id}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/cambiar_password/<int:user_id>', methods=['POST'])
def admin_cambiar_password(user_id):
    if session.get('rol') == 'admin':
        nueva_pass = request.form.get('nueva_password')
        if nueva_pass:
            db.cambiar_password_usuario(user_id, nueva_pass)
            db.registrar_log(session.get('usuario'), "Cambio Password", f"Usuario ID: {user_id}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_grupo/<grupo>/<int:user_id>', methods=['POST'])
def toggle_grupo(grupo, user_id):
    if session.get('rol') == 'admin':
        if grupo == 'lotes':
            db.alternar_permiso(user_id, 'puede_agregar')
            db.alternar_permiso(user_id, 'puede_editar')
        elif grupo == 'tareas':
            db.alternar_permiso(user_id, 'puede_agregar_tareas')
            db.alternar_permiso(user_id, 'puede_marcar_tareas')
        elif grupo == 'costos':
            db.alternar_permiso(user_id, 'puede_ver_costos')
        elif grupo == 'reportes':
            db.alternar_permiso(user_id, 'puede_descargar_mapa')
            db.alternar_permiso(user_id, 'puede_descargar_logs')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/toggle_descargar_mapa/<int:user_id>', methods=['POST'])
def admin_toggle_descargar_mapa(user_id):
    if session.get('rol') == 'admin':
        db.alternar_permiso(user_id, 'puede_descargar_mapa')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/toggle_descargar_logs/<int:user_id>', methods=['POST'])
def admin_toggle_descargar_logs(user_id):
    if session.get('rol') == 'admin':
        db.alternar_permiso(user_id, 'puede_descargar_logs')
    return redirect(url_for('dashboard.index'))
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from database import db
from services.seguridad import get_permisos_usuario_json

login_bp = Blueprint('login', __name__)

@login_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        valido, rol, add, edit, add_t, check_t, ver_costos, puede_desc_mapa, puede_desc_logs = db.verificar_usuario_y_obtener_datos(username, password)
        
        if valido:
            # Obtener ID del usuario
            with db._get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT id FROM usuarios WHERE username = ?', (username,))
                resultado = c.fetchone()
                user_id = resultado[0] if resultado else None
            
            if not user_id:
                return render_template('login.html', error='Error al procesar usuario')
            
            # Asignar rol predeterminado si no tiene ninguno
            roles_usuario = db.obtener_roles_de_usuario(user_id)
            if not roles_usuario:
                # Buscar rol en tabla roles
                rol_map = {
                    'admin': 'administrador',
                    'supervisor': 'supervisor',
                    'operario': 'operario',
                    'user': 'consultor'
                }
                rol_asignar = rol_map.get(rol, 'consultor')
                
                # Obtener rol_id
                with db._get_connection() as conn:
                    c = conn.cursor()
                    c.execute('SELECT id FROM roles WHERE nombre = ?', (rol_asignar,))
                    rol_result = c.fetchone()
                    if rol_result:
                        db.asignar_rol_a_usuario(user_id, rol_result[0])
            
            # Actualizar conexión y registrar log
            db.actualizar_ultima_conexion(username)
            db.registrar_log(username, "Inicio de Sesión")
            
            # Registrar acceso en auditoría
            from services.seguridad import obtener_ip_cliente
            ip = obtener_ip_cliente(request)
            db.registrar_acceso(
                user_id, username, 'login_exitoso',
                resultado='exitoso',
                ip_address=ip
            )
            
            # Obtener permisos actualizados
            permisos_json = get_permisos_usuario_json(user_id)
            
            # Guardar en sesión (mantener compatibilidad con sistema antiguo)
            session.update({
                'logeado': True, 
                'username': username,
                'user_id': user_id,
                'rol': rol,
                'puede_agregar': add, 
                'puede_editar': edit,
                'puede_agregar_tareas': add_t, 
                'puede_marcar_tareas': check_t,
                'puede_ver_costos': ver_costos,
                'puede_descargar_mapa': bool(puede_desc_mapa),
                'puede_descargar_logs': bool(puede_desc_logs),
                'permisos': permisos_json['permisos'],  # Nuevo sistema
                'es_admin': permisos_json['es_admin']  # Nuevo sistema
            })
            
            return redirect(url_for('dashboard.index'))
        
        return render_template('login.html', error='Credenciales incorrectas')
    
    return render_template('login.html')

@login_bp.route('/logout')
def logout():
    usuario = session.get('username')
    if usuario:
        db.registrar_log(usuario, "Cierre de Sesión")
    session.clear()
    return redirect(url_for('login.index'))

@login_bp.route('/api/permisos', methods=['GET'])
def obtener_permisos_api():
    """API para obtener permisos del usuario autenticado."""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    user_id = session.get('user_id')
    permisos_json = get_permisos_usuario_json(user_id)
    
    return jsonify(permisos_json)
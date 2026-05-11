from flask import Blueprint, render_template, request, session, redirect, url_for
from database import db

login_bp = Blueprint('login', __name__)

@login_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        valido, rol, add, edit, add_t, check_t = db.verificar_usuario_y_obtener_datos(username, password)
        
        if valido:
            db.actualizar_ultima_conexion(username)
            db.registrar_log(username, "Inicio de Sesión")
            session.update({
                'logeado': True, 'usuario': username, 'rol': rol,
                'puede_agregar': add, 'puede_editar': edit,
                'puede_agregar_tareas': add_t, 'puede_marcar_tareas': check_t
            })
            return redirect(url_for('dashboard.index'))
        return render_template('login.html', error='Credenciales incorrectas')
    return render_template('login.html')

@login_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login.index'))
from flask import Flask, render_template, request, redirect, url_for, send_file, session, Response
import simplekml
import io
import os
from datetime import datetime
import database
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_temporal_para_desarrollo')

database.init_db()

# --- FUNCIÓN REUTILIZABLE PARA CONVERTIR MAPAS ---
def convertir_geojson_a_kml(data):
    kml = simplekml.Kml()
    if data and 'features' in data:
        for feature in data['features']:
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coords = feature['geometry']['coordinates']
                geo_type = feature['geometry']['type']

                if geo_type == 'Polygon':
                    kml_coords = [(pt[0], pt[1]) for pt in coords[0]]
                    if len(kml_coords) > 0 and kml_coords[0] != kml_coords[-1]:
                        kml_coords.append(kml_coords[0])

                    props = feature.get('properties', {})
                    
                    # MAGIA AQUÍ: Rescatamos el nombre nativo del KML
                    nombre_lote = props.get('name', 'Nuevo Lote')

                    pol = kml.newpolygon(name=nombre_lote)
                    pol.outerboundaryis = kml_coords
                    pol.style.polystyle.color = simplekml.Color.red
                    
                    # Guardamos el resto (responsable y tareas) oculto en description
                    pol.description = json.dumps(props)
    return kml.kml()

# --- RUTAS PRINCIPALES ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        es_valido, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas = database.verificar_usuario_y_obtener_datos(username, password)
        
        if es_valido:
            database.actualizar_ultima_conexion(username)
            session['logeado'] = True
            session['usuario'] = username
            session['rol'] = rol
            session['puede_agregar'] = puede_agregar
            session['puede_editar'] = puede_editar
            session['puede_agregar_tareas'] = puede_agregar_tareas
            session['puede_marcar_tareas'] = puede_marcar_tareas
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Credenciales incorrectas')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logeado'):
        return redirect(url_for('login'))
        
    slots = database.obtener_todos_los_slots()
    lista_usuarios = []
    
    if session.get('rol') == 'admin':
        lista_usuarios = database.obtener_todos_los_usuarios()
        
    return render_template('dashboard.html', slots=slots, usuarios=lista_usuarios, rol_actual=session.get('rol'))

@app.route('/adhesa/<string:kml_slug>')
def index(kml_slug):
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    slot_info = database.obtener_slot_por_slug(kml_slug)
    if not slot_info:
        return redirect(url_for('dashboard'))
        
    slot_id = slot_info[0]
    nombre_real = slot_info[1]
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    usuario = session.get('usuario', 'Desconocido')
    database.actualizar_metadatos_slot(slot_id, usuario, fecha_actual)
    
    # Reemplaza la extracción de la BD por esto:
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar = database.obtener_permisos_usuario(usuario)

    puede_agregar = (rol == 'admin') or bool(db_agregar)
    puede_editar = (rol == 'admin') or bool(db_editar)
    puede_agregar_tareas = (rol == 'admin') or bool(db_agregar_tar)
    puede_marcar_tareas = (rol == 'admin') or bool(db_marcar_tar)

    usuarios_bd = database.obtener_todos_los_usuarios()
    lista_nombres = [u[1] for u in usuarios_bd]

    # Pasamos las nuevas variables al mapa
    return render_template('mapa.html', slot_id=slot_id, nombre_mapa=nombre_real, 
                           puede_agregar=puede_agregar, puede_editar=puede_editar, 
                           puede_agregar_tareas=puede_agregar_tareas, puede_marcar_tareas=puede_marcar_tareas,
                           usuario_actual=usuario, usuarios_lista=lista_nombres)

# --- RUTAS DE ACCIÓN DE ARCHIVOS ---
@app.route('/cargar_kml/<int:slot_id>', methods=['POST'])
def cargar_kml(slot_id):
    if not session.get('logeado'):
        return redirect(url_for('login'))
        
    archivo = request.files.get('kml_file')
    if archivo and archivo.filename.endswith('.kml'):
        kml_texto = archivo.read().decode('utf-8')
        database.guardar_kml_en_slot(slot_id, kml_texto)
        
    return redirect(url_for('dashboard'))

@app.route('/exportar_kml', methods=['POST'])
def exportar_kml():
    data = request.json
    kml_str = convertir_geojson_a_kml(data)
    mem_file = io.BytesIO()
    mem_file.write(kml_str.encode('utf-8'))
    mem_file.seek(0)
    return send_file(mem_file, mimetype='application/vnd.google-earth.kml+xml', as_attachment=True, download_name='mapa_modificado.kml')

@app.route('/eliminar_kml/<int:slot_id>', methods=['POST'])
def eliminar_kml(slot_id):
    if not session.get('logeado'):
        return redirect(url_for('login'))
    password_ingresada = request.form.get('password')
    usuario_actual = session.get('usuario')
    if database.verificar_usuario(usuario_actual, password_ingresada):
        database.vaciar_slot(slot_id)
    return redirect(url_for('dashboard'))

# --- RUTAS DE AUTOGUARDADO DE LA API ---
@app.route('/api/guardar_kml/<int:slot_id>', methods=['POST'])
def guardar_kml(slot_id):
    if not session.get('logeado'):
        return {"ok": False, "error": "Acceso denegado"}, 401
    
    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar = database.obtener_permisos_usuario(usuario)

    # Validación doble capa: Si no puedes agregar ni editar, no puedes guardar
    puede_guardar = (rol == 'admin') or bool(db_agregar) or bool(db_editar)
    
    if not puede_guardar:
        return {"ok": False, "error": "Sin permisos"}, 403

    data = request.get_json(silent=True)
    if data:
        kml_str = convertir_geojson_a_kml(data)
        database.guardar_kml_en_slot(slot_id, kml_str)

    return {"ok": True}

@app.route('/api/kml/<int:slot_id>')
def api_obtener_kml(slot_id):
    if not session.get('logeado'):
        return "Acceso denegado", 401
    kml_texto = database.obtener_kml_por_id(slot_id)
    if kml_texto:
        return Response(kml_texto, mimetype='application/vnd.google-earth.kml+xml')
    return "KML no encontrado", 404

# --- RUTAS DE ADMINISTRADOR ---
@app.route('/admin/crear_usuario', methods=['POST'])
def admin_crear_usuario():
    if session.get('rol') == 'admin':
        nuevo_user = request.form.get('nuevo_usuario')
        nueva_pass = request.form.get('nueva_password')
        if nuevo_user and nueva_pass:
            database.crear_nuevo_usuario(nuevo_user, nueva_pass)
    return redirect(url_for('dashboard'))

@app.route('/admin/eliminar_usuario/<int:user_id>', methods=['POST'])
def admin_eliminar_usuario(user_id):
    if session.get('rol') == 'admin':
        database.eliminar_usuario(user_id)
    return redirect(url_for('dashboard'))

@app.route('/admin/toggle_permiso/<int:user_id>', methods=['POST'])
def admin_toggle_permiso(user_id):
    if session.get('rol') == 'admin':
        database.alternar_permiso_lotes(user_id)
    return redirect(url_for('dashboard'))

@app.route('/admin/toggle_edicion/<int:user_id>', methods=['POST'])
def admin_toggle_edicion(user_id):
    if session.get('rol') == 'admin':
        database.alternar_permiso_edicion(user_id)
    return redirect(url_for('dashboard'))

@app.route('/admin/toggle_agregar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_agregar_tareas(user_id):
    if session.get('rol') == 'admin':
        database.alternar_permiso_agregar_tareas(user_id)
    return redirect(url_for('dashboard'))

@app.route('/admin/toggle_marcar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_marcar_tareas(user_id):
    if session.get('rol') == 'admin':
        database.alternar_permiso_marcar_tareas(user_id)
    return redirect(url_for('dashboard'))

@app.route('/admin/cambiar_password/<int:user_id>', methods=['POST'])
def admin_cambiar_password(user_id):
    if session.get('rol') == 'admin':
        nueva_pass = request.form.get('nueva_password')
        if nueva_pass:
            database.cambiar_password_usuario(user_id, nueva_pass)
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/mis_permisos')
def mis_permisos():
    if not session.get('logeado'):
        return {"logeado": False}
        
    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar = database.obtener_permisos_usuario(usuario)
    
    return {
        "logeado": True,
        "puede_agregar": (rol == 'admin') or bool(db_agregar),
        "puede_editar": (rol == 'admin') or bool(db_editar),
        "puede_agregar_tareas": (rol == 'admin') or bool(db_agregar_tar),
        "puede_marcar_tareas": (rol == 'admin') or bool(db_marcar_tar)
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000 ,debug=True)
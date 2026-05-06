import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

directorio_actual = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(directorio_actual, 'adhesa.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS slots
                 (id INTEGER PRIMARY KEY, nombre_real TEXT, slug TEXT, kml_data TEXT, 
                  creado_en TEXT, visto_por TEXT, visto_en TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT,
                  rol TEXT, puede_agregar INTEGER, ultima_conexion TEXT)''')

    c.execute('PRAGMA table_info(usuarios)')
    columnas_usuarios = [columna[1] for columna in c.fetchall()]
    
    # Inyectamos las columnas nuevas dinámicamente
    if 'puede_editar' not in columnas_usuarios:
        c.execute('ALTER TABLE usuarios ADD COLUMN puede_editar INTEGER DEFAULT 0')
    if 'puede_agregar_tareas' not in columnas_usuarios:
        c.execute('ALTER TABLE usuarios ADD COLUMN puede_agregar_tareas INTEGER DEFAULT 0')
    if 'puede_marcar_tareas' not in columnas_usuarios:
        c.execute('ALTER TABLE usuarios ADD COLUMN puede_marcar_tareas INTEGER DEFAULT 0')
    
    c.execute('SELECT COUNT(*) FROM slots')
    if c.fetchone()[0] == 0:
        for i in range(1, 4):
            c.execute('INSERT INTO slots (id, nombre_real, slug) VALUES (?, ?, ?)', (i, f"Proyecto {i}", f"proyecto-{i}"))
            
    c.execute('SELECT COUNT(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        pass_encriptada = generate_password_hash('password')
        c.execute('''INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', ('admin', pass_encriptada, 'admin', 1, 1, 1, 1))

    # Blindaje del admin
    c.execute('UPDATE usuarios SET puede_agregar = 1, puede_editar = 1, puede_agregar_tareas = 1, puede_marcar_tareas = 1 WHERE rol = "admin"')
    conn.commit()
    conn.close()

def obtener_todos_los_slots():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nombre_real, slug, kml_data, creado_en, visto_por, visto_en FROM slots')
    slots = c.fetchall()
    conn.close()
    return slots

def obtener_slot_por_slug(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nombre_real FROM slots WHERE slug = ?', (slug,))
    resultado = c.fetchone()
    conn.close()
    return resultado

def actualizar_metadatos_slot(slot_id, usuario, fecha):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE slots SET visto_por = ?, visto_en = ? WHERE id = ?', (usuario, fecha, slot_id))
    conn.commit()
    conn.close()

def verificar_usuario(username, password_ingresada):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT password_hash FROM usuarios WHERE username = ?', (username,))
    resultado = c.fetchone()
    conn.close()
    if resultado and check_password_hash(resultado[0], password_ingresada):
        return True
    return False

def guardar_kml_en_slot(slot_id, kml_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('UPDATE slots SET kml_data = ?, creado_en = ? WHERE id = ?', (kml_data, fecha_actual, slot_id))
    conn.commit()
    conn.close()

def obtener_kml_por_id(slot_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT kml_data FROM slots WHERE id = ?', (slot_id,))
    resultado = c.fetchone()
    conn.close()
    if resultado and resultado[0]:
        return resultado[0]
    return None

def vaciar_slot(slot_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE slots SET kml_data = NULL, creado_en = NULL, visto_por = NULL, visto_en = NULL WHERE id = ?''', (slot_id,))
    conn.commit()
    conn.close()

def verificar_usuario_y_obtener_datos(username, password_ingresada):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios WHERE username = ?', (username,))
    resultado = c.fetchone()
    conn.close()
    if resultado and check_password_hash(resultado[0], password_ingresada):
        return True, resultado[1], resultado[2], resultado[3], resultado[4], resultado[5]
    return False, None, None, None, None, None

def actualizar_ultima_conexion(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('UPDATE usuarios SET ultima_conexion = ? WHERE username = ?', (fecha, username))
    conn.commit()
    conn.close()

def obtener_todos_los_usuarios():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, rol, puede_agregar, ultima_conexion, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios')
    usuarios = c.fetchall()
    conn.close()
    return usuarios

def obtener_permisos_usuario(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios WHERE username = ?', (username,))
    resultado = c.fetchone()
    conn.close()
    if resultado:
        return resultado[0], resultado[1], resultado[2], resultado[3], resultado[4]
    return 'user', 0, 0, 0, 0

def crear_nuevo_usuario(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        pass_hash = generate_password_hash(password)
        c.execute('INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                  (username, pass_hash, 'user', 1, 0, 0, 0))
        conn.commit()
    except sqlite3.IntegrityError:
        pass 
    finally:
        conn.close()

def eliminar_usuario(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM usuarios WHERE id = ? AND rol != "admin"', (user_id,)) 
    conn.commit()
    conn.close()

def alternar_permiso_lotes(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE usuarios SET puede_agregar = CASE WHEN puede_agregar = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
    conn.commit()
    conn.close()

def alternar_permiso_edicion(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE usuarios SET puede_editar = CASE WHEN puede_editar = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
    conn.commit()
    conn.close()

def alternar_permiso_agregar_tareas(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE usuarios SET puede_agregar_tareas = CASE WHEN puede_agregar_tareas = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
    conn.commit()
    conn.close()

def alternar_permiso_marcar_tareas(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE usuarios SET puede_marcar_tareas = CASE WHEN puede_marcar_tareas = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
    conn.commit()
    conn.close()

def cambiar_password_usuario(user_id, nueva_password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pass_hash = generate_password_hash(nueva_password)
    c.execute('UPDATE usuarios SET password_hash = ? WHERE id = ?', (pass_hash, user_id))
    conn.commit()
    conn.close()
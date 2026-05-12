import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        """Crea y retorna una conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Inicializa las tablas y las columnas necesarias."""
        with self._get_connection() as conn:
            c = conn.cursor()
            
            # Tabla de Slots
            c.execute('''CREATE TABLE IF NOT EXISTS slots
                         (id INTEGER PRIMARY KEY, nombre_real TEXT, slug TEXT, kml_data TEXT, 
                          creado_en TEXT, visto_por TEXT, visto_en TEXT)''')
            
            # Tabla de Usuarios
            c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                         (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT,
                          rol TEXT, puede_agregar INTEGER, ultima_conexion TEXT)''')

            # Tabla de Logs (Auditoría)
            c.execute('''CREATE TABLE IF NOT EXISTS logs
                         (id INTEGER PRIMARY KEY, usuario TEXT, accion TEXT, 
                          detalles TEXT, fecha TEXT)''')

            # Verificación de columnas nuevas (Migración automática)
            c.execute('PRAGMA table_info(usuarios)')
            columnas = [col[1] for col in c.fetchall()]
            
            nuevas_columnas = {
                'puede_editar': 'INTEGER DEFAULT 0',
                'puede_agregar_tareas': 'INTEGER DEFAULT 0',
                'puede_marcar_tareas': 'INTEGER DEFAULT 0'
            }
            
            for col, tipo in nuevas_columnas.items():
                if col not in columnas:
                    c.execute(f'ALTER TABLE usuarios ADD COLUMN {col} {tipo}')
            
            # Inicialización de Slots base
            c.execute('SELECT COUNT(*) FROM slots')
            if c.fetchone()[0] == 0:
                for i in range(1, 4):
                    c.execute('INSERT INTO slots (id, nombre_real, slug) VALUES (?, ?, ?)', 
                              (i, f"Proyecto {i}", f"proyecto-{i}"))
            
            # Usuario Admin por defecto
            c.execute('SELECT COUNT(*) FROM usuarios')
            if c.fetchone()[0] == 0:
                pass_encriptada = generate_password_hash('password')
                c.execute('''INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)''', ('admin', pass_encriptada, 'admin', 1, 1, 1, 1))

            # Asegurar que el admin siempre tenga todo al iniciar
            c.execute('UPDATE usuarios SET puede_agregar=1, puede_editar=1, puede_agregar_tareas=1, puede_marcar_tareas=1 WHERE rol="admin"')
            conn.commit()

    # --- MÉTODOS DE USUARIOS ---

    def verificar_usuario(self, username, password_ingresada):
        """Versión simple que solo valida si la contraseña es correcta."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT password_hash FROM usuarios WHERE username = ?', (username,))
            resultado = c.fetchone()
            if resultado and check_password_hash(resultado[0], password_ingresada):
                return True
        return False

    def verificar_usuario_y_obtener_datos(self, username, password):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios WHERE username = ?', (username,))
            res = c.fetchone()
            if res and check_password_hash(res[0], password):
                return True, res[1], res[2], res[3], res[4], res[5]
        return False, None, None, None, None, None

    def obtener_permisos_usuario(self, username):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios WHERE username = ?', (username,))
            res = c.fetchone()
            return res if res else ('user', 0, 0, 0, 0)

    def obtener_todos_los_usuarios(self):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, username, rol, puede_agregar, ultima_conexion, puede_editar, puede_agregar_tareas, puede_marcar_tareas FROM usuarios')
            return c.fetchall()

    def actualizar_ultima_conexion(self, username):
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('UPDATE usuarios SET ultima_conexion = ? WHERE username = ?', (fecha, username))
            conn.commit()

    def alternar_permiso(self, user_id, columna):
        """Método genérico para cambiar permisos (lotes, edición, tareas, etc.)"""
        validas = ['puede_agregar', 'puede_editar', 'puede_agregar_tareas', 'puede_marcar_tareas']
        if columna not in validas: return
        
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute(f'UPDATE usuarios SET {columna} = CASE WHEN {columna} = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
            conn.commit()

    # --- WRAPPERS DE COMPATIBILIDAD (Para no romper el frontend/rutas) ---
    
    def alternar_permiso_lotes(self, user_id):
        self.alternar_permiso(user_id, 'puede_agregar')

    def alternar_permiso_edicion(self, user_id):
        self.alternar_permiso(user_id, 'puede_editar')

    def alternar_permiso_agregar_tareas(self, user_id):
        self.alternar_permiso(user_id, 'puede_agregar_tareas')

    def alternar_permiso_marcar_tareas(self, user_id):
        self.alternar_permiso(user_id, 'puede_marcar_tareas')

    # --- MÉTODOS DE SLOTS Y MAPA ---

    def obtener_todos_los_slots(self):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, nombre_real, slug, kml_data, creado_en, visto_por, visto_en FROM slots')
            return c.fetchall()

    def obtener_slot_por_slug(self, slug):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, nombre_real FROM slots WHERE slug = ?', (slug,))
            return c.fetchone()

    def actualizar_metadatos_slot(self, slot_id, usuario, fecha):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE slots SET visto_por = ?, visto_en = ? WHERE id = ?', (usuario, fecha, slot_id))
            conn.commit()

    def guardar_kml_en_slot(self, slot_id, kml_data):
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('UPDATE slots SET kml_data = ?, creado_en = ? WHERE id = ?', (kml_data, fecha, slot_id))
            conn.commit()

    def vaciar_slot(self, slot_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''UPDATE slots SET kml_data = NULL, creado_en = NULL, visto_por = NULL, visto_en = NULL WHERE id = ?''', (slot_id,))
            conn.commit()

    def obtener_kml_por_id(self, slot_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT kml_data FROM slots WHERE id = ?', (slot_id,))
            resultado = c.fetchone()
            if resultado and resultado[0]:
                return resultado[0]
            return None

    # --- MÉTODOS DE ADMINISTRACIÓN DE USUARIOS ---

    def crear_nuevo_usuario(self, username, password):
        with self._get_connection() as conn:
            c = conn.cursor()
            try:
                pass_hash = generate_password_hash(password)
                c.execute('INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                          (username, pass_hash, 'user', 1, 0, 0, 0))
                conn.commit()
            except sqlite3.IntegrityError:
                pass # El usuario ya existe

    def eliminar_usuario(self, user_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM usuarios WHERE id = ? AND rol != "admin"', (user_id,)) 
            conn.commit()

    def cambiar_password_usuario(self, user_id, nueva_password):
        with self._get_connection() as conn:
            c = conn.cursor()
            pass_hash = generate_password_hash(nueva_password)
            c.execute('UPDATE usuarios SET password_hash = ? WHERE id = ?', (pass_hash, user_id))
            conn.commit()

    # --- MÉTODOS DE AUDITORÍA (LOGS) ---

    def registrar_log(self, usuario, accion, detalles=""):
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('INSERT INTO logs (usuario, accion, detalles, fecha) VALUES (?, ?, ?, ?)', (usuario, accion, detalles, fecha))
            conn.commit()

    def obtener_logs_por_rango(self, rango):
        ahora = datetime.now()
        if rango == 'dia':
            inicio = ahora.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        elif rango == 'semana':
            lunes = ahora - timedelta(days=ahora.weekday())
            inicio = lunes.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        elif rango == 'mes':
            inicio = ahora.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        else:
            inicio = "2000-01-01 00:00:00"

        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT usuario, accion, detalles, fecha FROM logs WHERE fecha >= ? ORDER BY fecha DESC', (inicio,))
            return c.fetchall()

# --- INSTANCIA GLOBAL ---
directorio_actual = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(directorio_actual, 'adhesa.db')
db = DatabaseManager(DB_PATH)
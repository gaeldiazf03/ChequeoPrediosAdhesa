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
            
            # === NUEVAS TABLAS PARA CONTROL DE ACCESO ===
            
            # Tabla de Roles
            c.execute('''CREATE TABLE IF NOT EXISTS roles
                         (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, descripcion TEXT, fecha_creacion TEXT)''')
            
            # Tabla de Permisos
            c.execute('''CREATE TABLE IF NOT EXISTS permisos
                         (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, descripcion TEXT, categoria TEXT)''')
            
            # Tabla de Relación Roles-Permisos
            c.execute('''CREATE TABLE IF NOT EXISTS roles_permisos
                         (id INTEGER PRIMARY KEY, rol_id INTEGER NOT NULL, permiso_id INTEGER NOT NULL, 
                          UNIQUE(rol_id, permiso_id), FOREIGN KEY(rol_id) REFERENCES roles(id),
                          FOREIGN KEY(permiso_id) REFERENCES permisos(id))''')
            
            # Tabla de Relación Usuario-Roles
            c.execute('''CREATE TABLE IF NOT EXISTS usuario_roles
                         (id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, rol_id INTEGER NOT NULL,
                          fecha_asignacion TEXT, UNIQUE(usuario_id, rol_id),
                          FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
                          FOREIGN KEY(rol_id) REFERENCES roles(id))''')
            
            # Tabla de Auditoría de Accesos (datos sensibles)
            c.execute('''CREATE TABLE IF NOT EXISTS auditoria_accesos
                         (id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, usuario_nombre TEXT,
                          accion TEXT NOT NULL, recurso TEXT, resultado TEXT,
                          ip_address TEXT, fecha TEXT, detalles TEXT,
                          FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
            
            # === TABLA DE ACTIVIDADES PROGRAMADAS (FASE 1) ===
            c.execute('''CREATE TABLE IF NOT EXISTS actividades_programadas
                         (id INTEGER PRIMARY KEY, 
                          slot_id INTEGER NOT NULL,
                          nombre TEXT NOT NULL,
                          descripcion TEXT,
                          tipo_actividad TEXT,
                          estado TEXT DEFAULT 'pendiente',
                          fecha_programada TEXT,
                          fecha_vencimiento TEXT,
                          responsable TEXT,
                          completada_en TEXT,
                          dias_desde_siembra INTEGER,
                          prioridad TEXT DEFAULT 'normal',
                          metadata_json TEXT,
                          creada_en TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            # Verificación de columnas nuevas (Migración automática)
            c.execute('PRAGMA table_info(usuarios)')
            columnas = [col[1] for col in c.fetchall()]
            
            nuevas_columnas = {
                'puede_editar': 'INTEGER DEFAULT 0',
                'puede_agregar_tareas': 'INTEGER DEFAULT 0',
                'puede_marcar_tareas': 'INTEGER DEFAULT 0',
                'puede_ver_costos': 'INTEGER DEFAULT 0',
                'puede_descargar_mapa': 'INTEGER DEFAULT 0',
                'puede_descargar_logs': 'INTEGER DEFAULT 0'
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
                c.execute('''INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', ('admin', pass_encriptada, 'admin', 1, 1, 1, 1, 1, 1, 1))

            # Asegurar que el admin siempre tenga todo al iniciar
            c.execute('UPDATE usuarios SET puede_agregar=1, puede_editar=1, puede_agregar_tareas=1, puede_marcar_tareas=1, puede_ver_costos=1, puede_descargar_mapa=1, puede_descargar_logs=1 WHERE rol="admin"')
            
            # === INICIALIZACIÓN DE ROLES Y PERMISOS ===
            
            # Insertar roles por defecto
            roles_por_defecto = [
                ('administrador', 'Acceso total a todas las funciones'),
                ('supervisor', 'Supervisión de operaciones y reportes'),
                ('operario', 'Ejecución de actividades y registro de datos'),
                ('consultor', 'Solo lectura de datos no sensibles')
            ]
            
            for nombre, desc in roles_por_defecto:
                try:
                    c.execute('INSERT INTO roles (nombre, descripcion, fecha_creacion) VALUES (?, ?, ?)',
                              (nombre, desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                except sqlite3.IntegrityError:
                    pass
            
            # Insertar permisos por defecto
            permisos_por_defecto = [
                # Permisos de visualización
                ('ver_dashboard', 'Ver dashboard principal', 'visualizacion'),
                ('ver_mapa', 'Ver mapa de lotes', 'visualizacion'),
                ('ver_lotes', 'Ver datos de lotes', 'visualizacion'),
                ('ver_actividades', 'Ver timeline de actividades', 'visualizacion'),
                
                # Permisos sensibles - Costos
                ('ver_costos', 'Ver datos de costos', 'costos'),
                ('editar_costos', 'Registrar y editar costos', 'costos'),
                ('exportar_costos', 'Exportar reportes de costos', 'costos'),
                
                # Permisos sensibles - Inventario
                ('ver_inventario', 'Ver inventario de materiales', 'inventario'),
                ('editar_inventario', 'Registrar entradas y salidas', 'inventario'),
                ('exportar_inventario', 'Exportar reportes de inventario', 'inventario'),
                
                # Permisos sensibles - Datos personales
                ('ver_datos_personales', 'Ver datos personales de usuarios', 'usuarios'),
                ('gestionar_usuarios', 'CRUD de usuarios y roles', 'usuarios'),
                ('editar_permisos', 'Asignar/revocar permisos', 'usuarios'),
                
                # Permisos de operación
                ('crear_actividades', 'Crear tareas y cronogramas', 'operacion'),
                ('completar_actividades', 'Marcar actividades como completadas', 'operacion'),
                ('registrar_cosecha', 'Registrar datos de cosecha', 'operacion'),
                
                # Permisos de capas satelitales/sensibles
                ('ver_ndvi', 'Ver capas NDVI y vegetación', 'satelital'),
                ('ver_meteorologia', 'Ver datos meteorológicos', 'satelital'),
                ('ver_alertas', 'Ver alertas del sistema', 'alertas'),
                ('generar_alertas', 'Generar y configurar alertas', 'alertas'),
                
                # Permisos de reportes
                ('generar_reportes', 'Generar reportes PDF', 'reportes'),
                ('exportar_reportes', 'Descargar y exportar reportes', 'reportes'),
                
                # Permisos de auditoría
                ('ver_auditoria', 'Ver logs de acceso y auditoría', 'auditoria'),
                ('ver_logs', 'Ver logs de actividades', 'auditoria'),
            ]
            
            for nombre, desc, categoria in permisos_por_defecto:
                try:
                    c.execute('INSERT INTO permisos (nombre, descripcion, categoria) VALUES (?, ?, ?)',
                              (nombre, desc, categoria))
                except sqlite3.IntegrityError:
                    pass
            
            # Asignar permisos a roles
            # Administrador tiene todos los permisos
            self._asignar_permisos_role_completo(c, 'administrador')
            
            # Supervisor: ver todo pero no editar sensibles
            permisos_supervisor = [
                'ver_dashboard', 'ver_mapa', 'ver_lotes', 'ver_actividades',
                'ver_costos', 'ver_inventario', 'ver_datos_personales',
                'crear_actividades', 'completar_actividades', 'generar_reportes',
                'exportar_reportes', 'ver_auditoria', 'ver_logs', 'ver_ndvi',
                'ver_meteorologia', 'ver_alertas'
            ]
            self._asignar_permisos_role(c, 'supervisor', permisos_supervisor)
            
            # Operario: ejecución de tareas
            permisos_operario = [
                'ver_dashboard', 'ver_mapa', 'ver_lotes', 'ver_actividades',
                'crear_actividades', 'completar_actividades', 'registrar_cosecha',
                'ver_alertas'
            ]
            self._asignar_permisos_role(c, 'operario', permisos_operario)
            
            # Consultor: solo lectura no sensible
            permisos_consultor = [
                'ver_dashboard', 'ver_mapa', 'ver_lotes', 'ver_actividades'
            ]
            self._asignar_permisos_role(c, 'consultor', permisos_consultor)
            
            conn.commit()
    
    def _asignar_permisos_role_completo(self, cursor, nombre_rol):
        """Asigna todos los permisos a un rol."""
        try:
            cursor.execute('SELECT id FROM roles WHERE nombre = ?', (nombre_rol,))
            rol = cursor.fetchone()
            if rol:
                cursor.execute('SELECT id FROM permisos')
                permisos = cursor.fetchall()
                for permiso in permisos:
                    try:
                        cursor.execute('INSERT INTO roles_permisos (rol_id, permiso_id) VALUES (?, ?)',
                                      (rol[0], permiso[0]))
                    except sqlite3.IntegrityError:
                        pass
        except Exception:
            pass
    
    def _asignar_permisos_role(self, cursor, nombre_rol, nombres_permisos):
        """Asigna permisos específicos a un rol."""
        try:
            cursor.execute('SELECT id FROM roles WHERE nombre = ?', (nombre_rol,))
            rol = cursor.fetchone()
            if rol:
                for nombre_permiso in nombres_permisos:
                    cursor.execute('SELECT id FROM permisos WHERE nombre = ?', (nombre_permiso,))
                    permiso = cursor.fetchone()
                    if permiso:
                        try:
                            cursor.execute('INSERT INTO roles_permisos (rol_id, permiso_id) VALUES (?, ?)',
                                          (rol[0], permiso[0]))
                        except sqlite3.IntegrityError:
                            pass
        except Exception:
            pass

    # --- MÉTODOS DE USUARIOS ---

    def verificar_usuario_y_obtener_datos(self, username, password):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs FROM usuarios WHERE username = ?', (username,))
            res = c.fetchone()
            if res and check_password_hash(res[0], password):
                return True, res[1], res[2], res[3], res[4], res[5], res[6], res[7], res[8]
        return False, None, None, None, None, None, None, None, None

    def obtener_permisos_usuario(self, username):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs FROM usuarios WHERE username = ?', (username,))
            res = c.fetchone()
            return res if res else ('user', 0, 0, 0, 0, 0, 0, 0)

    def obtener_todos_los_usuarios(self):
        with self._get_connection() as conn:
            c = conn.cursor()
            # Añadimos los nuevos permisos al final para mantener compatibilidad de índices en templates
            c.execute('SELECT id, username, rol, puede_agregar, ultima_conexion, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs FROM usuarios')
            return c.fetchall()

    def alternar_permiso(self, user_id, columna):
        # Añadimos el nuevo permiso a la lista de columnas permitidas
        validas = ['puede_agregar', 'puede_editar', 'puede_agregar_tareas', 'puede_marcar_tareas', 'puede_ver_costos', 'puede_descargar_mapa', 'puede_descargar_logs']
        if columna not in validas: return

        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute(f'UPDATE usuarios SET {columna} = CASE WHEN {columna} = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
            conn.commit()

    def crear_nuevo_usuario(self, username, password):
        with self._get_connection() as conn:
            c = conn.cursor()
            try:
                pass_hash = generate_password_hash(password)
                # Añadimos puede_ver_costos y permisos de descarga con valores por defecto
                c.execute('INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                          (username, pass_hash, 'user', 1, 0, 0, 0, 0, 0, 0))
                conn.commit()
            except sqlite3.IntegrityError:
                pass

    def actualizar_ultima_conexion(self, username):
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('UPDATE usuarios SET ultima_conexion = ? WHERE username = ?', (fecha, username))
            conn.commit()

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

    # === MÉTODOS DE ROLES Y PERMISOS ===

    def obtener_todos_los_roles(self):
        """Retorna lista de todos los roles con sus permisos."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, nombre, descripcion FROM roles ORDER BY nombre')
            return c.fetchall()

    def obtener_permisos_de_rol(self, rol_id):
        """Retorna lista de permisos asignados a un rol."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT p.id, p.nombre, p.descripcion, p.categoria 
                         FROM permisos p
                         INNER JOIN roles_permisos rp ON p.id = rp.permiso_id
                         WHERE rp.rol_id = ?''', (rol_id,))
            return c.fetchall()

    def obtener_permisos_de_usuario(self, usuario_id):
        """Retorna lista de permisos de un usuario según sus roles."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT DISTINCT p.id, p.nombre, p.descripcion, p.categoria 
                         FROM permisos p
                         INNER JOIN roles_permisos rp ON p.id = rp.permiso_id
                         INNER JOIN usuario_roles ur ON rp.rol_id = ur.rol_id
                         WHERE ur.usuario_id = ?
                         ORDER BY p.categoria, p.nombre''', (usuario_id,))
            return c.fetchall()

    def obtener_nombres_permisos_usuario(self, usuario_id):
        """Retorna solo los nombres de permisos de un usuario."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT DISTINCT p.nombre 
                         FROM permisos p
                         INNER JOIN roles_permisos rp ON p.id = rp.permiso_id
                         INNER JOIN usuario_roles ur ON rp.rol_id = ur.rol_id
                         WHERE ur.usuario_id = ?''', (usuario_id,))
            result = c.fetchall()
            return [row[0] for row in result]

    def usuario_tiene_permiso(self, usuario_id, nombre_permiso):
        """Verifica si un usuario tiene un permiso específico."""
        permisos = self.obtener_nombres_permisos_usuario(usuario_id)
        return nombre_permiso in permisos

    def asignar_rol_a_usuario(self, usuario_id, rol_id):
        """Asigna un rol a un usuario."""
        with self._get_connection() as conn:
            c = conn.cursor()
            try:
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute('INSERT INTO usuario_roles (usuario_id, rol_id, fecha_asignacion) VALUES (?, ?, ?)',
                          (usuario_id, rol_id, fecha))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def revocar_rol_de_usuario(self, usuario_id, rol_id):
        """Revoca un rol de un usuario."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM usuario_roles WHERE usuario_id = ? AND rol_id = ?', (usuario_id, rol_id))
            conn.commit()

    def obtener_roles_de_usuario(self, usuario_id):
        """Retorna roles asignados a un usuario."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT r.id, r.nombre, r.descripcion, ur.fecha_asignacion 
                         FROM roles r
                         INNER JOIN usuario_roles ur ON r.id = ur.rol_id
                         WHERE ur.usuario_id = ?''', (usuario_id,))
            return c.fetchall()

    def asignar_permiso_a_rol(self, rol_id, permiso_id):
        """Asigna un permiso a un rol."""
        with self._get_connection() as conn:
            c = conn.cursor()
            try:
                c.execute('INSERT INTO roles_permisos (rol_id, permiso_id) VALUES (?, ?)',
                          (rol_id, permiso_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def revocar_permiso_de_rol(self, rol_id, permiso_id):
        """Revoca un permiso de un rol."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM roles_permisos WHERE rol_id = ? AND permiso_id = ?', (rol_id, permiso_id))
            conn.commit()

    # === MÉTODOS DE AUDITORÍA DE ACCESOS ===

    def registrar_acceso(self, usuario_id, usuario_nombre, accion, recurso="", resultado="", ip_address="", detalles=""):
        """Registra un acceso a datos sensibles en auditoría."""
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('''INSERT INTO auditoria_accesos 
                             (usuario_id, usuario_nombre, accion, recurso, resultado, ip_address, fecha, detalles)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (usuario_id, usuario_nombre, accion, recurso, resultado, ip_address, fecha, detalles))
                conn.commit()
            except Exception as e:
                print(f"Error registrando acceso: {e}")

    def obtener_auditoria_accesos(self, filtro_usuario=None, filtro_accion=None, filtro_recurso=None, dias=7):
        """Retorna registros de auditoría con filtros opcionales."""
        ahora = datetime.now()
        inicio = (ahora - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        
        with self._get_connection() as conn:
            c = conn.cursor()
            query = 'SELECT id, usuario_nombre, accion, recurso, resultado, ip_address, fecha, detalles FROM auditoria_accesos WHERE fecha >= ?'
            params = [inicio]
            
            if filtro_usuario:
                query += ' AND usuario_nombre LIKE ?'
                params.append(f'%{filtro_usuario}%')
            
            if filtro_accion:
                query += ' AND accion LIKE ?'
                params.append(f'%{filtro_accion}%')
            
            if filtro_recurso:
                query += ' AND recurso LIKE ?'
                params.append(f'%{filtro_recurso}%')
            
            query += ' ORDER BY fecha DESC'
            c.execute(query, params)
            return c.fetchall()

    def obtener_estadisticas_accesos(self, dias=7):
        """Retorna estadísticas de accesos a datos sensibles."""
        ahora = datetime.now()
        inicio = (ahora - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        
        with self._get_connection() as conn:
            c = conn.cursor()
            
            # Total accesos
            c.execute('SELECT COUNT(*) FROM auditoria_accesos WHERE fecha >= ?', (inicio,))
            total = c.fetchone()[0]
            
            # Por acción
            c.execute('SELECT accion, COUNT(*) FROM auditoria_accesos WHERE fecha >= ? GROUP BY accion', (inicio,))
            por_accion = c.fetchall()
            
            # Por usuario
            c.execute('SELECT usuario_nombre, COUNT(*) FROM auditoria_accesos WHERE fecha >= ? GROUP BY usuario_nombre', (inicio,))
            por_usuario = c.fetchall()
            
            # Accesos rechazados
            c.execute('SELECT COUNT(*) FROM auditoria_accesos WHERE fecha >= ? AND resultado = "denegado"', (inicio,))
            denegados = c.fetchone()[0]
            
            return {
                'total': total,
                'por_accion': por_accion,
                'por_usuario': por_usuario,
                'denegados': denegados
            }

    # === MÉTODOS DE ACTIVIDADES PROGRAMADAS (FASE 1) ===

    def crear_actividad(self, slot_id, nombre, descripcion="", tipo_actividad="", 
                       fecha_programada="", dias_desde_siembra=0, prioridad="normal", responsable=""):
        """Crea una nueva actividad programada para un slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('''INSERT INTO actividades_programadas 
                             (slot_id, nombre, descripcion, tipo_actividad, fecha_programada, 
                              dias_desde_siembra, prioridad, responsable, creada_en, estado)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (slot_id, nombre, descripcion, tipo_actividad, fecha_programada,
                           dias_desde_siembra, prioridad, responsable, fecha_creacion, 'pendiente'))
                conn.commit()
                return c.lastrowid
            except Exception as e:
                print(f"Error creando actividad: {e}")
                return None

    def obtener_actividades_por_slot(self, slot_id, filtro_estado=None):
        """Obtiene todas las actividades de un slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            if filtro_estado:
                c.execute('''SELECT id, slot_id, nombre, descripcion, tipo_actividad, estado,
                                    fecha_programada, fecha_vencimiento, responsable, completada_en,
                                    dias_desde_siembra, prioridad, creada_en
                             FROM actividades_programadas 
                             WHERE slot_id = ? AND estado = ?
                             ORDER BY dias_desde_siembra ASC''', (slot_id, filtro_estado))
            else:
                c.execute('''SELECT id, slot_id, nombre, descripcion, tipo_actividad, estado,
                                    fecha_programada, fecha_vencimiento, responsable, completada_en,
                                    dias_desde_siembra, prioridad, creada_en
                             FROM actividades_programadas 
                             WHERE slot_id = ?
                             ORDER BY dias_desde_siembra ASC''', (slot_id,))
            return c.fetchall()

    def obtener_actividades_proximas(self, dias=7):
        """Obtiene actividades próximas (pendientes en los próximos N días)."""
        ahora = datetime.now()
        fecha_limite = (ahora + timedelta(days=dias)).strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, nombre, descripcion, tipo_actividad, estado,
                                fecha_programada, fecha_vencimiento, responsable, completada_en,
                                dias_desde_siembra, prioridad, creada_en
                         FROM actividades_programadas 
                         WHERE estado IN ('pendiente', 'en_progreso')
                         AND fecha_vencimiento <= ?
                         ORDER BY fecha_vencimiento ASC''', (fecha_limite,))
            return c.fetchall()

    def marcar_actividad_completada(self, actividad_id):
        """Marca una actividad como completada."""
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha_completada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''UPDATE actividades_programadas 
                         SET estado = 'completada', completada_en = ?
                         WHERE id = ?''', (fecha_completada, actividad_id))
            conn.commit()

    def cambiar_estado_actividad(self, actividad_id, nuevo_estado):
        """Cambia el estado de una actividad."""
        estados_validos = ['pendiente', 'en_progreso', 'completada', 'cancelada']
        if nuevo_estado not in estados_validos:
            return False
        
        with self._get_connection() as conn:
            c = conn.cursor()
            if nuevo_estado == 'completada':
                fecha_completada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute('''UPDATE actividades_programadas 
                             SET estado = ?, completada_en = ?
                             WHERE id = ?''', (nuevo_estado, fecha_completada, actividad_id))
            else:
                c.execute('''UPDATE actividades_programadas 
                             SET estado = ?
                             WHERE id = ?''', (nuevo_estado, actividad_id))
            conn.commit()
            return True

    def obtener_actividad_por_id(self, actividad_id):
        """Obtiene una actividad específica."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, nombre, descripcion, tipo_actividad, estado,
                                fecha_programada, fecha_vencimiento, responsable, completada_en,
                                dias_desde_siembra, prioridad, creada_en
                         FROM actividades_programadas 
                         WHERE id = ?''', (actividad_id,))
            return c.fetchone()

    def eliminar_actividad(self, actividad_id):
        """Elimina una actividad."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM actividades_programadas WHERE id = ?', (actividad_id,))
            conn.commit()

    def obtener_estadisticas_actividades(self, slot_id):
        """Obtiene estadísticas de actividades de un slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            
            c.execute('SELECT COUNT(*) FROM actividades_programadas WHERE slot_id = ?', (slot_id,))
            total = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM actividades_programadas WHERE slot_id = ? AND estado = "pendiente"', (slot_id,))
            pendientes = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM actividades_programadas WHERE slot_id = ? AND estado = "en_progreso"', (slot_id,))
            en_progreso = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM actividades_programadas WHERE slot_id = ? AND estado = "completada"', (slot_id,))
            completadas = c.fetchone()[0]
            
            return {
                'total': total,
                'pendientes': pendientes,
                'en_progreso': en_progreso,
                'completadas': completadas
            }

    def obtener_todas_las_actividades_para_kpis(self):
        """Obtiene todas las actividades para cálculo de KPIs globales."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT COUNT(*) as total, 
                                SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
                                SUM(CASE WHEN estado = 'en_progreso' THEN 1 ELSE 0 END) as en_progreso,
                                SUM(CASE WHEN estado = 'completada' THEN 1 ELSE 0 END) as completadas
                         FROM actividades_programadas''')
            resultado = c.fetchone()
            return {
                'total': resultado[0] or 0,
                'pendientes': resultado[1] or 0,
                'en_progreso': resultado[2] or 0,
                'completadas': resultado[3] or 0
            }

# --- INSTANCIA GLOBAL ---
directorio_actual = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(directorio_actual, 'adhesa.db')
db = DatabaseManager(DB_PATH)
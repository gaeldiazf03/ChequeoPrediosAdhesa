import sqlite3
import os
import unicodedata
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
                          rol TEXT, puede_agregar INTEGER, ultima_conexion TEXT,
                          correo TEXT)''')

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

            # === TABLAS SMART MAP Y ALERTAS (FASE 2) ===
            c.execute('''CREATE TABLE IF NOT EXISTS telemetria_maquinaria
                         (id INTEGER PRIMARY KEY,
                          slot_id INTEGER NOT NULL,
                          unidad_id TEXT NOT NULL,
                          lat REAL NOT NULL,
                          lng REAL NOT NULL,
                          velocidad_kmh REAL DEFAULT 0,
                          estado_motor TEXT DEFAULT 'encendido',
                          nivel_bateria REAL DEFAULT 100,
                          timestamp TEXT,
                          metadata_json TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            c.execute('''CREATE TABLE IF NOT EXISTS alertas_sistema
                         (id INTEGER PRIMARY KEY,
                          slot_id INTEGER,
                          tipo TEXT NOT NULL,
                          severidad TEXT DEFAULT 'media',
                          titulo TEXT NOT NULL,
                          mensaje TEXT,
                          estado TEXT DEFAULT 'activa',
                          origen TEXT DEFAULT 'smart_map',
                          atendida_por TEXT,
                          creada_en TEXT,
                          atendida_en TEXT,
                          metadata_json TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            c.execute('''CREATE TABLE IF NOT EXISTS alertas_reglas
                         (id INTEGER PRIMARY KEY,
                          slot_id INTEGER NOT NULL,
                          nombre TEXT NOT NULL,
                          tipo TEXT NOT NULL,
                          umbral REAL NOT NULL,
                          severidad TEXT DEFAULT 'media',
                          activa INTEGER DEFAULT 1,
                          creada_por TEXT,
                          creada_en TEXT,
                          actualizada_en TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            c.execute('''CREATE TABLE IF NOT EXISTS tipos_alerta
                         (id INTEGER PRIMARY KEY,
                          nombre TEXT UNIQUE NOT NULL,
                          descripcion TEXT,
                          activa INTEGER DEFAULT 1,
                          creada_en TEXT,
                          actualizada_en TEXT)''')

            # === TABLA DE TRACTORES / UNIDADES (ADMIN CRUD) ===
            c.execute('''CREATE TABLE IF NOT EXISTS tractores
                         (id INTEGER PRIMARY KEY,
                          placa TEXT UNIQUE NOT NULL,
                          modelo TEXT,
                          ano INTEGER,
                          estado TEXT DEFAULT 'activo',
                          slot_id INTEGER,
                          metadata_json TEXT,
                          creada_en TEXT,
                          actualizada_en TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            # Si en una migración anterior no existía la columna unidad_id, la añadimos
            c.execute('PRAGMA table_info(tractores)')
            cols = [r[1] for r in c.fetchall()]
            if 'unidad_id' not in cols:
                try:
                    c.execute('ALTER TABLE tractores ADD COLUMN unidad_id TEXT')
                except Exception:
                    pass

            # === TABLA DE PLANES (FUTUROS / PASADOS) ===
            c.execute('''CREATE TABLE IF NOT EXISTS planes
                         (id INTEGER PRIMARY KEY,
                          slot_id INTEGER NOT NULL,
                          nombre TEXT NOT NULL,
                          descripcion TEXT,
                          fecha_inicio TEXT,
                          fecha_fin TEXT,
                          estado TEXT DEFAULT 'programado',
                          creada_en TEXT,
                          actualizada_en TEXT,
                          metadata_json TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')

            c.execute('''CREATE TABLE IF NOT EXISTS catalogo_actividades
                         (id INTEGER PRIMARY KEY,
                          nombre TEXT NOT NULL UNIQUE,
                          etapa TEXT,
                          descripcion TEXT,
                          como_se_realiza TEXT,
                          programacion_recomendada TEXT,
                          activa INTEGER DEFAULT 1,
                          creada_en TEXT,
                          actualizada_en TEXT)''')

            c.execute('PRAGMA table_info(catalogo_actividades)')
            catalogo_cols = [r[1] for r in c.fetchall()]
            if 'etapa' not in catalogo_cols:
                c.execute('ALTER TABLE catalogo_actividades ADD COLUMN etapa TEXT')
            if 'descripcion' not in catalogo_cols:
                c.execute('ALTER TABLE catalogo_actividades ADD COLUMN descripcion TEXT')
            if 'como_se_realiza' not in catalogo_cols:
                c.execute('ALTER TABLE catalogo_actividades ADD COLUMN como_se_realiza TEXT')
            if 'programacion_recomendada' not in catalogo_cols:
                c.execute('ALTER TABLE catalogo_actividades ADD COLUMN programacion_recomendada TEXT')

            self._sembrar_catalogo_actividades_default(c)

            c.execute('''CREATE TABLE IF NOT EXISTS reportes_programados
                         (id INTEGER PRIMARY KEY,
                          nombre TEXT NOT NULL,
                          frecuencia_dias INTEGER NOT NULL,
                          destinatarios_json TEXT NOT NULL,
                          formato TEXT DEFAULT 'csv',
                          activo INTEGER DEFAULT 1,
                          creado_por TEXT,
                          creado_en TEXT,
                          ultimo_envio TEXT,
                          proximo_envio TEXT)''')

            c.execute('SELECT COUNT(*) FROM tipos_alerta')
            if c.fetchone()[0] == 0:
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tipos_base = [
                    ('velocidad_mayor', 'Velocidad mayor al umbral configurado'),
                    ('bateria_menor', 'Nivel de batería menor al umbral configurado'),
                    ('conexion_perdida', 'Pérdida de comunicación con la unidad'),
                    ('zona_restringida', 'Unidad fuera de zona permitida'),
                ]
                for nombre, descripcion in tipos_base:
                    c.execute('''INSERT OR IGNORE INTO tipos_alerta (nombre, descripcion, activa, creada_en, actualizada_en)
                                 VALUES (?, ?, 1, ?, ?)''', (nombre, descripcion, ahora, ahora))

            # Verificación de columnas nuevas (Migración automática)
            c.execute('PRAGMA table_info(usuarios)')
            columnas = [col[1] for col in c.fetchall()]
            
            nuevas_columnas = {
                'puede_editar': 'INTEGER DEFAULT 0',
                'puede_agregar_tareas': 'INTEGER DEFAULT 0',
                'puede_marcar_tareas': 'INTEGER DEFAULT 0',
                'puede_ver_costos': 'INTEGER DEFAULT 0',
                'puede_descargar_mapa': 'INTEGER DEFAULT 0',
                'puede_descargar_logs': 'INTEGER DEFAULT 0',
                'correo': 'TEXT DEFAULT NULL'
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
            
            # === TABLA DE NOTIFICACIONES ENVIADAS ===
            c.execute('''CREATE TABLE IF NOT EXISTS notificaciones
                         (id INTEGER PRIMARY KEY,
                          slot_id INTEGER,
                          canal TEXT,
                          destino TEXT,
                          tipo TEXT,
                          titulo TEXT,
                          mensaje TEXT,
                          resultado_json TEXT,
                          creada_en TEXT,
                          origen TEXT DEFAULT 'alerta',
                          estado TEXT DEFAULT 'pendiente',
                          intentos INTEGER DEFAULT 0,
                          ultimo_intento_en TEXT,
                          FOREIGN KEY(slot_id) REFERENCES slots(id))''')
            # Asegurar columnas en migraciones previas
            c.execute('PRAGMA table_info(notificaciones)')
            noti_cols = [r[1] for r in c.fetchall()]
            if 'estado' not in noti_cols:
                try:
                    c.execute('ALTER TABLE notificaciones ADD COLUMN estado TEXT DEFAULT "pendiente"')
                except Exception:
                    pass
            if 'intentos' not in noti_cols:
                try:
                    c.execute('ALTER TABLE notificaciones ADD COLUMN intentos INTEGER DEFAULT 0')
                except Exception:
                    pass
            if 'origen' not in noti_cols:
                try:
                    c.execute('ALTER TABLE notificaciones ADD COLUMN origen TEXT DEFAULT "alerta"')
                except Exception:
                    pass
            if 'ultimo_intento_en' not in noti_cols:
                try:
                    c.execute('ALTER TABLE notificaciones ADD COLUMN ultimo_intento_en TEXT')
                except Exception:
                    pass
    
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
            c.execute('SELECT id, username, rol, puede_agregar, ultima_conexion, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs, correo FROM usuarios')
            return c.fetchall()

    def obtener_correos_usuarios(self):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT DISTINCT correo
                         FROM usuarios
                         WHERE correo IS NOT NULL AND TRIM(correo) != ''
                         ORDER BY correo''')
            return [fila[0] for fila in c.fetchall() if fila and fila[0]]

    def alternar_permiso(self, user_id, columna):
        # Añadimos el nuevo permiso a la lista de columnas permitidas
        validas = ['puede_agregar', 'puede_editar', 'puede_agregar_tareas', 'puede_marcar_tareas', 'puede_ver_costos', 'puede_descargar_mapa', 'puede_descargar_logs']
        if columna not in validas: return

        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute(f'UPDATE usuarios SET {columna} = CASE WHEN {columna} = 1 THEN 0 ELSE 1 END WHERE id = ? AND rol != "admin"', (user_id,))
            conn.commit()

    def crear_nuevo_usuario(self, username, password, correo=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            try:
                pass_hash = generate_password_hash(password)
                # Añadimos puede_ver_costos y permisos de descarga con valores por defecto
                correo = (correo or '').strip() or None
                c.execute('INSERT INTO usuarios (username, password_hash, rol, puede_agregar, puede_editar, puede_agregar_tareas, puede_marcar_tareas, puede_ver_costos, puede_descargar_mapa, puede_descargar_logs, correo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                          (username, pass_hash, 'user', 1, 0, 0, 0, 0, 0, 0, correo))
                conn.commit()
            except sqlite3.IntegrityError:
                pass

    def _sembrar_catalogo_actividades_default(self, cursor):
        """Inserta catálogo base solo si está vacío, respetando orden/ID de Excel."""
        cursor.execute('SELECT COUNT(*) FROM catalogo_actividades')
        if (cursor.fetchone()[0] or 0) > 0:
            return

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        registros = self._leer_catalogo_desde_excel_default()
        if not registros:
            registros = self._catalogo_fallback_minimo()

        for orden, item in enumerate(registros, start=1):
            cursor.execute('''INSERT INTO catalogo_actividades
                              (id, nombre, etapa, descripcion, como_se_realiza, programacion_recomendada, activa, creada_en, actualizada_en)
                              VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
                           (
                               orden,
                               item.get('nombre') or '',
                               item.get('etapa') or '',
                               item.get('descripcion') or '',
                               item.get('como_se_realiza') or '',
                               item.get('programacion_recomendada') or '',
                               ahora,
                               ahora,
                           ))

    def _normalizar_texto_cabecera(self, texto):
        texto = (texto or '').strip().lower()
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
        return texto

    def _leer_catalogo_desde_excel_default(self):
        """Lee RESUMEN/Control acts. ADEHSA.xlsx y retorna filas ordenadas."""
        try:
            from openpyxl import load_workbook
        except Exception:
            return []

        excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RESUMEN', 'Control acts. ADEHSA.xlsx')
        if not os.path.exists(excel_path):
            return []

        try:
            wb = load_workbook(excel_path, data_only=True)
        except Exception:
            return []

        if 'Resumen Procesos' not in wb.sheetnames:
            return []

        ws = wb['Resumen Procesos']

        header_row = None
        header_map = {}
        for r in range(1, min(ws.max_row, 100) + 1):
            row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
            normalizados = [self._normalizar_texto_cabecera(str(v) if v is not None else '') for v in row_vals]
            if 'proceso' in normalizados:
                header_row = r
                for idx, val in enumerate(normalizados, start=1):
                    if val:
                        header_map[val] = idx
                break

        if not header_row or 'proceso' not in header_map:
            return []

        idx_etapa = header_map.get('etapa')
        idx_nombre = header_map.get('proceso')
        idx_descripcion = None
        idx_como = None
        idx_programacion = None

        for key, idx in header_map.items():
            if 'descripcion' in key and idx_descripcion is None:
                idx_descripcion = idx
            if 'como se realiza' in key and idx_como is None:
                idx_como = idx
            if 'programacion recomendada' in key and idx_programacion is None:
                idx_programacion = idx

        registros = []
        for r in range(header_row + 1, ws.max_row + 1):
            nombre = ws.cell(row=r, column=idx_nombre).value
            nombre = str(nombre).strip() if nombre is not None else ''
            if not nombre:
                continue

            etapa = ws.cell(row=r, column=idx_etapa).value if idx_etapa else ''
            descripcion = ws.cell(row=r, column=idx_descripcion).value if idx_descripcion else ''
            como = ws.cell(row=r, column=idx_como).value if idx_como else ''
            programacion = ws.cell(row=r, column=idx_programacion).value if idx_programacion else ''

            registros.append({
                'nombre': str(nombre).strip(),
                'etapa': str(etapa).strip() if etapa is not None else '',
                'descripcion': str(descripcion).strip() if descripcion is not None else '',
                'como_se_realiza': str(como).strip() if como is not None else '',
                'programacion_recomendada': str(programacion).strip() if programacion is not None else '',
            })

        return registros

    def _catalogo_fallback_minimo(self):
        """Fallback mínimo cuando no se puede leer el Excel en inicialización."""
        return [
            {'nombre': 'Reconocimiento del predio', 'etapa': 'Diagnóstico', 'descripcion': '', 'como_se_realiza': '', 'programacion_recomendada': ''},
            {'nombre': 'Análisis de suelo', 'etapa': 'Diagnóstico', 'descripcion': '', 'como_se_realiza': '', 'programacion_recomendada': ''},
            {'nombre': 'Preparación de terreno', 'etapa': 'Preparación', 'descripcion': '', 'como_se_realiza': '', 'programacion_recomendada': ''},
        ]

    def actualizar_correo_usuario(self, user_id, correo=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            correo = (correo or '').strip() or None
            c.execute('UPDATE usuarios SET correo = ? WHERE id = ?', (correo, user_id))
            conn.commit()
            return c.rowcount > 0

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

    def actualizar_nombre_slot(self, slot_id, nuevo_nombre):
        with self._get_connection() as conn:
            c = conn.cursor()
            nombre = (nuevo_nombre or '').strip()
            if not nombre:
                return False
            c.execute('UPDATE slots SET nombre_real = ? WHERE id = ?', (nombre, slot_id))
            conn.commit()
            return c.rowcount > 0

    def actualizar_metadatos_slot(self, slot_id, usuario, fecha):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE slots SET visto_por = ?, visto_en = ? WHERE id = ?', (usuario, fecha, slot_id))
            conn.commit()

    def guardar_kml_en_slot(self, slot_id, kml_data):
        with self._get_connection() as conn:
            c = conn.cursor()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
            # Protección: si por error se recibe una página HTML (traceback del servidor), no la guardamos
            if isinstance(kml_data, str) and (kml_data.lstrip().lower().startswith('<!doctype') or '<html' in kml_data.lower()):
                return False

            c.execute('UPDATE slots SET kml_data = ?, creado_en = ? WHERE id = ?', (kml_data, fecha, slot_id))
            conn.commit()
            return True

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

    def existe_notificacion_reciente(self, slot_id, canal, tipo, mensaje, ventana_minutos=10):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, creada_en
                         FROM notificaciones
                         WHERE slot_id = ? AND canal = ? AND tipo = ? AND mensaje = ?
                         ORDER BY creada_en DESC
                         LIMIT 10''', (slot_id, canal, tipo, mensaje))
            filas = c.fetchall()
            if not filas:
                return None
            limite_segundos = ventana_minutos * 60
            ahora = datetime.now()
            for fila in filas:
                try:
                    creada = datetime.strptime(fila[1], "%Y-%m-%d %H:%M:%S")
                    if (ahora - creada).total_seconds() <= limite_segundos:
                        return fila
                except Exception:
                    continue
            return None

    def crear_notificacion(self, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json='', origen='alerta', forzar=False, cooldown_minutos=10):
        with self._get_connection() as conn:
            c = conn.cursor()
            creada_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                if not forzar:
                    reciente = self.existe_notificacion_reciente(slot_id, canal, tipo, mensaje, cooldown_minutos)
                    if reciente:
                        return reciente[0]
                c.execute('''INSERT INTO notificaciones (slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, ultimo_intento_en)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, None))
                conn.commit()
                return c.lastrowid
            except Exception:
                return None

    def obtener_notificacion_por_id(self, notificacion_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en
                         FROM notificaciones WHERE id = ?''', (notificacion_id,))
            return c.fetchone()

    def actualizar_notificacion_resultado(self, notificacion_id, resultado_json, nuevo_estado=None, incrementar_intentos=False, actualizar_ultimo_intento=True):
        with self._get_connection() as conn:
            c = conn.cursor()
            campos = []
            params = []
            campos.append('resultado_json = ?')
            params.append(resultado_json)
            if nuevo_estado is not None:
                campos.append('estado = ?')
                params.append(nuevo_estado)
            if incrementar_intentos:
                campos.append('intentos = intentos + 1')
            if actualizar_ultimo_intento:
                campos.append('ultimo_intento_en = ?')
                params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            params.append(notificacion_id)
            query = f"UPDATE notificaciones SET {', '.join(campos)} WHERE id = ?"
            c.execute(query, tuple(params))
            conn.commit()
            return c.rowcount > 0

    def obtener_notificaciones_por_slot(self, slot_id, limite=100, canal=None, estado=None, desde=None, hasta=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            query = '''SELECT id, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en
                       FROM notificaciones WHERE slot_id = ?'''
            params = [slot_id]
            if canal:
                query += ' AND canal = ?'
                params.append(canal)
            if estado:
                query += ' AND estado = ?'
                params.append(estado)
            if desde:
                query += ' AND creada_en >= ?'
                params.append(desde)
            if hasta:
                query += ' AND creada_en <= ?'
                params.append(hasta)
            query += ' ORDER BY creada_en DESC LIMIT ?'
            params.append(limite)
            c.execute(query, tuple(params))
            return c.fetchall()

    def obtener_notificaciones_para_reintento(self, max_intentos=3, limite=50):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en
                         FROM notificaciones
                         WHERE estado = 'fallo' AND intentos < ?
                         ORDER BY creada_en ASC
                         LIMIT ?''', (max_intentos, limite))
            return c.fetchall()

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

    def obtener_logs_desde(self, fecha_inicio, limite=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            query = 'SELECT usuario, accion, detalles, fecha FROM logs WHERE fecha >= ? ORDER BY fecha DESC'
            params = [fecha_inicio]
            if limite is not None:
                query += ' LIMIT ?'
                params.append(int(limite))
            c.execute(query, tuple(params))
            return c.fetchall()

    def obtener_logs_entre(self, fecha_inicio, fecha_fin):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT usuario, accion, detalles, fecha
                         FROM logs
                         WHERE fecha >= ? AND fecha <= ?
                         ORDER BY fecha DESC''', (fecha_inicio, fecha_fin))
            return c.fetchall()

    # === MÉTODOS DE REPORTES PROGRAMADOS ===

    def crear_reporte_programado(self, nombre, frecuencia_dias, destinatarios_json, formato='csv', creado_por=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now()
            fecha_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")
            proximo_envio = (ahora + timedelta(days=int(frecuencia_dias))).strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''INSERT INTO reportes_programados
                         (nombre, frecuencia_dias, destinatarios_json, formato, activo, creado_por, creado_en, ultimo_envio, proximo_envio)
                         VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)''',
                      (nombre, int(frecuencia_dias), destinatarios_json, formato, creado_por, fecha_actual, None, proximo_envio))
            conn.commit()
            return c.lastrowid

    def obtener_reportes_programados(self, activo=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            query = 'SELECT id, nombre, frecuencia_dias, destinatarios_json, formato, activo, creado_por, creado_en, ultimo_envio, proximo_envio FROM reportes_programados'
            params = []
            if activo is not None:
                query += ' WHERE activo = ?'
                params.append(1 if activo else 0)
            query += ' ORDER BY proximo_envio ASC, id DESC'
            c.execute(query, tuple(params))
            return c.fetchall()

    def obtener_reportes_programados_vencidos(self, limite=20):
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''SELECT id, nombre, frecuencia_dias, destinatarios_json, formato, activo, creado_por, creado_en, ultimo_envio, proximo_envio
                         FROM reportes_programados
                         WHERE activo = 1 AND proximo_envio IS NOT NULL AND proximo_envio <= ?
                         ORDER BY proximo_envio ASC
                         LIMIT ?''', (ahora, int(limite)))
            return c.fetchall()

    def marcar_reporte_programado_enviado(self, reporte_id, ultimo_envio=None, proximo_envio=None):
        with self._get_connection() as conn:
            c = conn.cursor()
            ultimo_envio = ultimo_envio or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            campos = ['ultimo_envio = ?', 'proximo_envio = ?']
            params = [ultimo_envio, proximo_envio]
            params.append(reporte_id)
            c.execute(f'''UPDATE reportes_programados
                          SET {', '.join(campos)}
                          WHERE id = ?''', tuple(params))
            conn.commit()
            return c.rowcount > 0

    def actualizar_estado_reporte_programado(self, reporte_id, activo):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE reportes_programados SET activo = ? WHERE id = ?', (1 if activo else 0, reporte_id))
            conn.commit()
            return c.rowcount > 0

    def eliminar_reporte_programado(self, reporte_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM reportes_programados WHERE id = ?', (reporte_id,))
            conn.commit()
            return c.rowcount > 0

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

    # === MÉTODOS DE GESTIÓN DE TRACTORES ===

    def crear_tractor(self, placa, modelo=None, ano=None, estado='activo', slot_id=None, metadata_json=''):
        """Crea un registro de tractor/unidad."""
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('''INSERT INTO tractores (placa, modelo, ano, estado, slot_id, metadata_json, creada_en, actualizada_en)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (placa, modelo, ano, estado, slot_id, metadata_json, ahora, ahora))
                conn.commit()
                return c.lastrowid
            except sqlite3.IntegrityError:
                return None

    def obtener_todos_los_tractores(self, slot_id=None):
        """Retorna lista de tractores, opcionalmente filtrados por slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            if slot_id is None:
                c.execute('SELECT id, placa, modelo, ano, estado, slot_id, metadata_json, creada_en, actualizada_en FROM tractores ORDER BY id DESC')
            else:
                c.execute('SELECT id, placa, modelo, ano, estado, slot_id, metadata_json, creada_en, actualizada_en FROM tractores WHERE slot_id = ? ORDER BY id DESC', (slot_id,))
            return c.fetchall()

    def obtener_tractor_por_id(self, tractor_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, placa, modelo, ano, estado, slot_id, metadata_json, creada_en, actualizada_en FROM tractores WHERE id = ?', (tractor_id,))
            return c.fetchone()

    def actualizar_tractor(self, tractor_id, placa=None, modelo=None, ano=None, estado=None, slot_id=None, metadata_json=None):
        """Actualiza campos proporcionados de un tractor."""
        campos = []
        params = []
        if placa is not None:
            campos.append('placa = ?')
            params.append(placa)
        if modelo is not None:
            campos.append('modelo = ?')
            params.append(modelo)
        if ano is not None:
            campos.append('ano = ?')
            params.append(ano)
        if estado is not None:
            campos.append('estado = ?')
            params.append(estado)
        if slot_id is not None:
            campos.append('slot_id = ?')
            params.append(slot_id)
        if metadata_json is not None:
            campos.append('metadata_json = ?')
            params.append(metadata_json)

        if not campos:
            return False

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        campos.append('actualizada_en = ?')
        params.append(ahora)
        params.append(tractor_id)

        with self._get_connection() as conn:
            c = conn.cursor()
            query = f"UPDATE tractores SET {', '.join(campos)} WHERE id = ?"
            c.execute(query, tuple(params))
            conn.commit()
            return c.rowcount > 0

    def eliminar_tractor(self, tractor_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM tractores WHERE id = ?', (tractor_id,))
            conn.commit()
            return c.rowcount > 0

    def vincular_tractor(self, tractor_id, unidad_id):
        """Asigna un unidad_id a un tractor (vinculación manual)."""
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('UPDATE tractores SET unidad_id = ?, actualizada_en = ? WHERE id = ?', (unidad_id, ahora, tractor_id))
                conn.commit()
                return c.rowcount > 0
            except Exception:
                return False

    def desvincular_tractor(self, tractor_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('UPDATE tractores SET unidad_id = NULL, actualizada_en = ? WHERE id = ?', (ahora, tractor_id))
            conn.commit()
            return c.rowcount > 0

    def obtener_tractor_por_unidad(self, unidad_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, placa, modelo, ano, estado, slot_id, metadata_json, unidad_id, creada_en, actualizada_en FROM tractores WHERE unidad_id = ?', (unidad_id,))
            return c.fetchone()

    # === MÉTODOS DE GESTIÓN DE PLANES ===

    def crear_plan(self, slot_id, nombre, descripcion='', fecha_inicio=None, fecha_fin=None, estado='programado', metadata_json=''):
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('''INSERT INTO planes (slot_id, nombre, descripcion, fecha_inicio, fecha_fin, estado, creada_en, actualizada_en, metadata_json)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (slot_id, nombre, descripcion, fecha_inicio, fecha_fin, estado, ahora, ahora, metadata_json))
                conn.commit()
                return c.lastrowid
            except Exception:
                return None

    def obtener_planes_por_slot(self, slot_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, nombre, descripcion, fecha_inicio, fecha_fin, estado, creada_en, actualizada_en, metadata_json
                         FROM planes WHERE slot_id = ? ORDER BY fecha_inicio DESC''', (slot_id,))
            return c.fetchall()

    def obtener_plan_por_id(self, plan_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, slot_id, nombre, descripcion, fecha_inicio, fecha_fin, estado, creada_en, actualizada_en, metadata_json
                         FROM planes WHERE id = ?''', (plan_id,))
            return c.fetchone()

    def actualizar_plan(self, plan_id, nombre=None, descripcion=None, fecha_inicio=None, fecha_fin=None, estado=None, metadata_json=None):
        campos = []
        params = []
        if nombre is not None:
            campos.append('nombre = ?'); params.append(nombre)
        if descripcion is not None:
            campos.append('descripcion = ?'); params.append(descripcion)
        if fecha_inicio is not None:
            campos.append('fecha_inicio = ?'); params.append(fecha_inicio)
        if fecha_fin is not None:
            campos.append('fecha_fin = ?'); params.append(fecha_fin)
        if estado is not None:
            campos.append('estado = ?'); params.append(estado)
        if metadata_json is not None:
            campos.append('metadata_json = ?'); params.append(metadata_json)

        if not campos:
            return False

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        campos.append('actualizada_en = ?'); params.append(ahora)
        params.append(plan_id)

        with self._get_connection() as conn:
            c = conn.cursor()
            query = f"UPDATE planes SET {', '.join(campos)} WHERE id = ?"
            c.execute(query, tuple(params))
            conn.commit()
            return c.rowcount > 0

    def eliminar_plan(self, plan_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM planes WHERE id = ?', (plan_id,))
            conn.commit()
            return c.rowcount > 0

    # === MÉTODOS DE CATÁLOGO DE ACTIVIDADES (GLOBAL) ===

    def obtener_catalogo_actividades(self, solo_activas=False):
        with self._get_connection() as conn:
            c = conn.cursor()
            if solo_activas:
                c.execute('''SELECT id, nombre, etapa, descripcion, como_se_realiza, programacion_recomendada, activa, creada_en, actualizada_en
                             FROM catalogo_actividades
                             WHERE activa = 1
                             ORDER BY id ASC''')
            else:
                c.execute('''SELECT id, nombre, etapa, descripcion, como_se_realiza, programacion_recomendada, activa, creada_en, actualizada_en
                             FROM catalogo_actividades
                             ORDER BY id ASC''')
            return c.fetchall()

    def crear_actividad_catalogo(self, nombre, activa=1, etapa='', descripcion='', como_se_realiza='', programacion_recomendada=''):
        nombre_limpio = (nombre or '').strip()
        if not nombre_limpio:
            return None

        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute('''INSERT INTO catalogo_actividades
                             (nombre, etapa, descripcion, como_se_realiza, programacion_recomendada, activa, creada_en, actualizada_en)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (nombre_limpio, (etapa or '').strip(), (descripcion or '').strip(), (como_se_realiza or '').strip(), (programacion_recomendada or '').strip(), int(bool(activa)), ahora, ahora))
                conn.commit()
                return c.lastrowid
            except sqlite3.IntegrityError:
                return None

    def obtener_actividad_catalogo_por_id(self, actividad_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, nombre, etapa, descripcion, como_se_realiza, programacion_recomendada, activa, creada_en, actualizada_en
                         FROM catalogo_actividades
                         WHERE id = ?''', (actividad_id,))
            return c.fetchone()

    def actualizar_actividad_catalogo(self, actividad_id, nombre=None, activa=None, etapa=None, descripcion=None, como_se_realiza=None, programacion_recomendada=None):
        campos = []
        params = []

        if nombre is not None:
            nombre_limpio = str(nombre).strip()
            if not nombre_limpio:
                return False
            campos.append('nombre = ?')
            params.append(nombre_limpio)

        if activa is not None:
            campos.append('activa = ?')
            params.append(int(bool(activa)))

        if etapa is not None:
            campos.append('etapa = ?')
            params.append(str(etapa).strip())

        if descripcion is not None:
            campos.append('descripcion = ?')
            params.append(str(descripcion).strip())

        if como_se_realiza is not None:
            campos.append('como_se_realiza = ?')
            params.append(str(como_se_realiza).strip())

        if programacion_recomendada is not None:
            campos.append('programacion_recomendada = ?')
            params.append(str(programacion_recomendada).strip())

        if not campos:
            return False

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        campos.append('actualizada_en = ?')
        params.append(ahora)
        params.append(actividad_id)

        with self._get_connection() as conn:
            c = conn.cursor()
            query = f"UPDATE catalogo_actividades SET {', '.join(campos)} WHERE id = ?"
            try:
                c.execute(query, tuple(params))
                conn.commit()
                return c.rowcount > 0
            except sqlite3.IntegrityError:
                return False

    def eliminar_actividad_catalogo(self, actividad_id):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM catalogo_actividades WHERE id = ?', (actividad_id,))
            conn.commit()
            return c.rowcount > 0

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

    # === MÉTODOS SMART MAP Y ALERTAS (FASE 2) ===

    def insertar_telemetria(self, slot_id, unidad_id, lat, lng, velocidad_kmh=0,
                            estado_motor='encendido', nivel_bateria=100, metadata_json=''):
        """Inserta un punto de telemetría para una unidad."""
        with self._get_connection() as conn:
            c = conn.cursor()
            marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''INSERT INTO telemetria_maquinaria
                         (slot_id, unidad_id, lat, lng, velocidad_kmh, estado_motor,
                          nivel_bateria, timestamp, metadata_json)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (slot_id, unidad_id, lat, lng, velocidad_kmh, estado_motor,
                       nivel_bateria, marca_tiempo, metadata_json))
            conn.commit()
            return c.lastrowid

    def obtener_ultima_posicion_unidades(self, slot_id):
        """Obtiene la última posición registrada por cada unidad del slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT t.id, t.slot_id, t.unidad_id, t.lat, t.lng, t.velocidad_kmh,
                                t.estado_motor, t.nivel_bateria, t.timestamp, t.metadata_json
                         FROM telemetria_maquinaria t
                         INNER JOIN (
                            SELECT unidad_id, MAX(timestamp) AS max_ts
                            FROM telemetria_maquinaria
                            WHERE slot_id = ?
                            GROUP BY unidad_id
                         ) ult
                         ON t.unidad_id = ult.unidad_id AND t.timestamp = ult.max_ts
                         WHERE t.slot_id = ?
                         ORDER BY t.unidad_id ASC''', (slot_id, slot_id))
            return c.fetchall()

    def obtener_unidades_con_ultima_posicion(self, slot_id):
        """Retorna lista de unidades con su última posición y datos de tractor si existe."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT t.unidad_id, t.lat, t.lng, t.velocidad_kmh, t.estado_motor, t.nivel_bateria, t.timestamp,
                                tr.id as tractor_id, tr.placa, tr.modelo
                         FROM telemetria_maquinaria t
                         LEFT JOIN tractores tr ON tr.placa = t.unidad_id
                         INNER JOIN (
                            SELECT unidad_id, MAX(timestamp) AS max_ts
                            FROM telemetria_maquinaria
                            WHERE slot_id = ?
                            GROUP BY unidad_id
                         ) ult
                         ON t.unidad_id = ult.unidad_id AND t.timestamp = ult.max_ts
                         WHERE t.slot_id = ?
                         ORDER BY t.unidad_id ASC''', (slot_id, slot_id))
            return c.fetchall()

    def crear_alerta(self, slot_id, tipo, titulo, mensaje, severidad='media', metadata_json=''):
        """Crea una alerta del sistema."""
        with self._get_connection() as conn:
            c = conn.cursor()
            creada_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''INSERT INTO alertas_sistema
                         (slot_id, tipo, severidad, titulo, mensaje, estado, origen, creada_en, metadata_json)
                         VALUES (?, ?, ?, ?, ?, 'activa', 'smart_map', ?, ?)''',
                      (slot_id, tipo, severidad, titulo, mensaje, creada_en, metadata_json))
            conn.commit()
            return c.lastrowid

    def obtener_alertas_activas(self, slot_id=None, limite=20):
        """Obtiene alertas activas, opcionalmente filtradas por slot."""
        with self._get_connection() as conn:
            c = conn.cursor()
            if slot_id is None:
                c.execute('''SELECT id, slot_id, tipo, severidad, titulo, mensaje, estado,
                                    origen, atendida_por, creada_en, atendida_en, metadata_json
                             FROM alertas_sistema
                             WHERE estado = 'activa'
                             ORDER BY creada_en DESC
                             LIMIT ?''', (limite,))
            else:
                c.execute('''SELECT id, slot_id, tipo, severidad, titulo, mensaje, estado,
                                    origen, atendida_por, creada_en, atendida_en, metadata_json
                             FROM alertas_sistema
                             WHERE estado = 'activa' AND slot_id = ?
                             ORDER BY creada_en DESC
                             LIMIT ?''', (slot_id, limite))
            return c.fetchall()

    def atender_alerta(self, alerta_id, atendida_por=''):
        """Marca una alerta como atendida."""
        with self._get_connection() as conn:
            c = conn.cursor()
            atendida_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''UPDATE alertas_sistema
                         SET estado = 'atendida', atendida_por = ?, atendida_en = ?
                         WHERE id = ?''', (atendida_por, atendida_en, alerta_id))
            conn.commit()
            return c.rowcount > 0

    def obtener_reglas_alerta(self, slot_id, solo_activas=False):
        """Obtiene reglas de alerta configuradas para un lote."""
        with self._get_connection() as conn:
            c = conn.cursor()
            if solo_activas:
                c.execute('''SELECT id, slot_id, nombre, tipo, umbral, severidad, activa,
                                    creada_por, creada_en, actualizada_en
                             FROM alertas_reglas
                             WHERE slot_id = ? AND activa = 1
                             ORDER BY id DESC''', (slot_id,))
            else:
                c.execute('''SELECT id, slot_id, nombre, tipo, umbral, severidad, activa,
                                    creada_por, creada_en, actualizada_en
                             FROM alertas_reglas
                             WHERE slot_id = ?
                             ORDER BY id DESC''', (slot_id,))
            return c.fetchall()

    def crear_regla_alerta(self, slot_id, nombre, tipo, umbral, severidad='media', creada_por=''):
        """Crea una regla de alerta para un lote."""
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''INSERT INTO alertas_reglas
                         (slot_id, nombre, tipo, umbral, severidad, activa, creada_por, creada_en, actualizada_en)
                         VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)''',
                      (slot_id, nombre, tipo, umbral, severidad, creada_por, ahora, ahora))
            conn.commit()
            return c.lastrowid

    def actualizar_estado_regla_alerta(self, regla_id, activa):
        """Activa o desactiva una regla de alerta."""
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''UPDATE alertas_reglas
                         SET activa = ?, actualizada_en = ?
                         WHERE id = ?''', (1 if activa else 0, ahora, regla_id))
            conn.commit()
            return c.rowcount > 0

    def obtener_tipos_alerta(self, solo_activos=False):
        """Obtiene el catálogo de tipos de alerta."""
        with self._get_connection() as conn:
            c = conn.cursor()
            if solo_activos:
                c.execute('''SELECT id, nombre, descripcion, activa, creada_en, actualizada_en
                             FROM tipos_alerta
                             WHERE activa = 1
                             ORDER BY nombre ASC''')
            else:
                c.execute('''SELECT id, nombre, descripcion, activa, creada_en, actualizada_en
                             FROM tipos_alerta
                             ORDER BY nombre ASC''')
            return c.fetchall()

    def crear_tipo_alerta(self, nombre, descripcion=""):
        """Crea un nuevo tipo de alerta."""
        with self._get_connection() as conn:
            c = conn.cursor()
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''INSERT INTO tipos_alerta (nombre, descripcion, activa, creada_en, actualizada_en)
                         VALUES (?, ?, 1, ?, ?)''', (nombre, descripcion, ahora, ahora))
            conn.commit()
            return c.lastrowid

    def eliminar_tipo_alerta(self, tipo_alerta_id):
        """Elimina un tipo de alerta del catálogo."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM tipos_alerta WHERE id = ?', (tipo_alerta_id,))
            conn.commit()
            return c.rowcount > 0

# --- INSTANCIA GLOBAL ---
directorio_actual = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(directorio_actual, 'adhesa.db')
db = DatabaseManager(DB_PATH)
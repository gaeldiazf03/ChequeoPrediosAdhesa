"""
Servicio de roles: gestión de roles, permisos y asignaciones.
"""

from database import db
from datetime import datetime

class GestorRoles:
    """Gestor centralizado de roles y permisos."""
    
    @staticmethod
    def obtener_rol_completo(rol_id):
        """Obtiene información completa de un rol con todos sus permisos."""
        rol = db.obtener_todos_los_roles()
        rol_info = None
        for r in rol:
            if r[0] == rol_id:
                rol_info = {'id': r[0], 'nombre': r[1], 'descripcion': r[2]}
                break
        
        if not rol_info:
            return None
        
        permisos = db.obtener_permisos_de_rol(rol_id)
        rol_info['permisos'] = [
            {'id': p[0], 'nombre': p[1], 'descripcion': p[2], 'categoria': p[3]}
            for p in permisos
        ]
        
        return rol_info
    
    @staticmethod
    def crear_rol_personalizado(nombre, descripcion, nombres_permisos):
        """
        Crea un nuevo rol personalizado con permisos específicos.
        
        Args:
            nombre: Nombre único del rol
            descripcion: Descripción del rol
            nombres_permisos: Lista de nombres de permisos a asignar
        
        Returns:
            rol_id si éxito, False si falla
        """
        try:
            with db._get_connection() as conn:
                c = conn.cursor()
                
                # Crear rol
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute('INSERT INTO roles (nombre, descripcion, fecha_creacion) VALUES (?, ?, ?)',
                          (nombre, descripcion, fecha))
                conn.commit()
                
                # Obtener ID del rol creado
                c.execute('SELECT id FROM roles WHERE nombre = ?', (nombre,))
                rol_id = c.fetchone()[0]
                
                # Asignar permisos
                for nombre_permiso in nombres_permisos:
                    c.execute('SELECT id FROM permisos WHERE nombre = ?', (nombre_permiso,))
                    permiso = c.fetchone()
                    if permiso:
                        try:
                            c.execute('INSERT INTO roles_permisos (rol_id, permiso_id) VALUES (?, ?)',
                                      (rol_id, permiso[0]))
                            conn.commit()
                        except:
                            pass
                
                return rol_id
        except Exception as e:
            print(f"Error creando rol: {e}")
            return False
    
    @staticmethod
    def asignar_rol_a_usuario(usuario_id, rol_id):
        """Asigna un rol a un usuario."""
        return db.asignar_rol_a_usuario(usuario_id, rol_id)
    
    @staticmethod
    def revocar_rol_de_usuario(usuario_id, rol_id):
        """Revoca un rol de un usuario."""
        db.revocar_rol_de_usuario(usuario_id, rol_id)
    
    @staticmethod
    def obtener_permisos_usuario_agrupados(usuario_id):
        """Retorna permisos del usuario agrupados por categoría."""
        permisos = db.obtener_permisos_de_usuario(usuario_id)
        
        agrupados = {}
        for p in permisos:
            categoria = p[3]
            if categoria not in agrupados:
                agrupados[categoria] = []
            agrupados[categoria].append({
                'id': p[0],
                'nombre': p[1],
                'descripcion': p[2]
            })
        
        return agrupados
    
    @staticmethod
    def comparar_permisos_usuarios(user_id_1, user_id_2):
        """Compara permisos entre dos usuarios."""
        permisos_1 = set(db.obtener_nombres_permisos_usuario(user_id_1))
        permisos_2 = set(db.obtener_nombres_permisos_usuario(user_id_2))
        
        return {
            'usuario_1_total': len(permisos_1),
            'usuario_2_total': len(permisos_2),
            'compartidos': list(permisos_1 & permisos_2),
            'solo_usuario_1': list(permisos_1 - permisos_2),
            'solo_usuario_2': list(permisos_2 - permisos_1)
        }
    
    @staticmethod
    def replicar_permisos(usuario_origen_id, usuario_destino_id):
        """Copia los permisos de un usuario a otro."""
        try:
            # Obtener roles del usuario origen
            roles_origen = db.obtener_roles_de_usuario(usuario_origen_id)
            
            # Limpiar roles del usuario destino y asignar los del origen
            roles_destino = db.obtener_roles_de_usuario(usuario_destino_id)
            for rol in roles_destino:
                db.revocar_rol_de_usuario(usuario_destino_id, rol[0])
            
            # Asignar roles del origen
            for rol in roles_origen:
                db.asignar_rol_a_usuario(usuario_destino_id, rol[0])
            
            return True
        except Exception as e:
            print(f"Error replicando permisos: {e}")
            return False
    
    @staticmethod
    def obtener_usuarios_con_permiso(nombre_permiso):
        """Obtiene todos los usuarios que tienen un permiso específico."""
        usuarios = db.obtener_todos_los_usuarios()
        usuarios_con_permiso = []
        
        for usuario in usuarios:
            user_id = usuario[0]
            if db.usuario_tiene_permiso(user_id, nombre_permiso):
                usuarios_con_permiso.append({
                    'id': user_id,
                    'username': usuario[1],
                    'rol': usuario[2]
                })
        
        return usuarios_con_permiso
    
    @staticmethod
    def validar_permisos_rol(rol_id):
        """Verifica que un rol tenga permisos válidos (no eliminados)."""
        permisos = db.obtener_permisos_de_rol(rol_id)
        return len(permisos) > 0
    
    @staticmethod
    def obtener_estadisticas_roles():
        """Retorna estadísticas de roles y permisos."""
        roles = db.obtener_todos_los_roles()
        usuarios = db.obtener_todos_los_usuarios()
        
        # Contar permisos por rol
        permisos_por_rol = {}
        for rol in roles:
            permisos = db.obtener_permisos_de_rol(rol[0])
            permisos_por_rol[rol[1]] = len(permisos)
        
        # Contar usuarios por rol
        usuarios_por_rol = {}
        for usuario in usuarios:
            roles_usuario = db.obtener_roles_de_usuario(usuario[0])
            for rol in roles_usuario:
                nombre_rol = rol[1]
                if nombre_rol not in usuarios_por_rol:
                    usuarios_por_rol[nombre_rol] = 0
                usuarios_por_rol[nombre_rol] += 1
        
        return {
            'total_roles': len(roles),
            'permisos_por_rol': permisos_por_rol,
            'usuarios_por_rol': usuarios_por_rol,
            'total_usuarios': len(usuarios)
        }

class ValidadorAcceso:
    """Validador para verificaciones complejas de acceso."""
    
    @staticmethod
    def puede_ver_costos(usuario_id):
        """Verifica si usuario puede ver costos."""
        return db.usuario_tiene_permiso(usuario_id, 'ver_costos')
    
    @staticmethod
    def puede_editar_costos(usuario_id):
        """Verifica si usuario puede editar costos."""
        return db.usuario_tiene_permiso(usuario_id, 'editar_costos')
    
    @staticmethod
    def puede_ver_inventario(usuario_id):
        """Verifica si usuario puede ver inventario."""
        return db.usuario_tiene_permiso(usuario_id, 'ver_inventario')
    
    @staticmethod
    def puede_editar_inventario(usuario_id):
        """Verifica si usuario puede editar inventario."""
        return db.usuario_tiene_permiso(usuario_id, 'editar_inventario')
    
    @staticmethod
    def puede_ver_datos_personales(usuario_id):
        """Verifica si usuario puede ver datos personales."""
        return db.usuario_tiene_permiso(usuario_id, 'ver_datos_personales')
    
    @staticmethod
    def puede_gestionar_usuarios(usuario_id):
        """Verifica si usuario puede gestionar otros usuarios."""
        return db.usuario_tiene_permiso(usuario_id, 'gestionar_usuarios')
    
    @staticmethod
    def puede_generar_reportes(usuario_id):
        """Verifica si usuario puede generar reportes."""
        return db.usuario_tiene_permiso(usuario_id, 'generar_reportes')
    
    @staticmethod
    def puede_exportar_reportes(usuario_id):
        """Verifica si usuario puede exportar/descargar reportes."""
        return db.usuario_tiene_permiso(usuario_id, 'exportar_reportes')
    
    @staticmethod
    def puede_ver_auditoria(usuario_id):
        """Verifica si usuario puede ver logs de auditoría."""
        return db.usuario_tiene_permiso(usuario_id, 'ver_auditoria')
    
    @staticmethod
    def puede_ver_capas_satelitales(usuario_id):
        """Verifica si usuario puede ver capas NDVI/satelitales."""
        return db.usuario_tiene_permiso(usuario_id, 'ver_ndvi')
    
    @staticmethod
    def es_supervisor_o_admin(usuario_id):
        """Verifica si usuario es supervisor o admin."""
        permisos_requeridos = ['ver_costos', 'generar_reportes']
        tiene_todos = all(
            db.usuario_tiene_permiso(usuario_id, p)
            for p in permisos_requeridos
        )
        return tiene_todos
    
    @staticmethod
    def es_operario(usuario_id):
        """Verifica si usuario es operario (permisos básicos)."""
        permisos_basicos = ['ver_actividades', 'completar_actividades']
        tiene_basicos = any(
            db.usuario_tiene_permiso(usuario_id, p)
            for p in permisos_basicos
        )
        return tiene_basicos

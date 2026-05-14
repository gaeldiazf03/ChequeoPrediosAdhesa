"""
Rutas de administración: gestión de roles, permisos, usuarios y auditoría.
Todas estas rutas requieren permiso 'gestionar_usuarios' (solo administrador).
"""

from flask import Blueprint, render_template, request, jsonify, session
from database import db
from services.seguridad import require_permission, registrar_accion_sensible
from services.roles import GestorRoles, ValidadorAcceso

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# === VALIDACIÓN DE PERMISOS ===

def obtener_usuario_actual():
    return session.get('username')

def obtener_id_usuario_actual():
    return session.get('user_id')

# === RUTAS PRINCIPALES ===

@admin_bp.route('/roles', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_roles():
    """Lista todos los roles con sus permisos."""
    try:
        roles = db.obtener_todos_los_roles()
        roles_con_permisos = []
        
        for rol in roles:
            permisos = db.obtener_permisos_de_rol(rol[0])
            roles_con_permisos.append({
                'id': rol[0],
                'nombre': rol[1],
                'descripcion': rol[2],
                'permisos_count': len(permisos)
            })
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'listar_roles', 'roles'
        )
        
        if request.accept_mimetypes.best == 'application/json':
            return jsonify(roles_con_permisos)
        
        # Renderizar HTML si es HTML request
        return render_template('admin/roles.html', roles=roles_con_permisos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/roles/<int:rol_id>', methods=['GET'])
@require_permission('gestionar_usuarios')
def ver_rol(rol_id):
    """Ver detalles de un rol específico."""
    try:
        rol_completo = GestorRoles.obtener_rol_completo(rol_id)
        
        if not rol_completo:
            return jsonify({'error': 'Rol no encontrado'}), 404
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'ver_rol', f'rol_id:{rol_id}'
        )
        
        if request.accept_mimetypes.best == 'application/json':
            return jsonify(rol_completo)
        
        return render_template('admin/rol_detalle.html', rol=rol_completo)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/roles', methods=['POST'])
@require_permission('gestionar_usuarios')
def crear_rol():
    """Crea un nuevo rol con permisos especificados."""
    try:
        datos = request.get_json()
        nombre = datos.get('nombre')
        descripcion = datos.get('descripcion', '')
        nombres_permisos = datos.get('permisos', [])
        
        if not nombre:
            return jsonify({'error': 'Nombre de rol requerido'}), 400
        
        rol_id = GestorRoles.crear_rol_personalizado(nombre, descripcion, nombres_permisos)
        
        if not rol_id:
            return jsonify({'error': 'Error creando rol'}), 500
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'crear_rol', f'rol:{nombre}',
            detalles=f'Permisos: {", ".join(nombres_permisos)}'
        )
        
        return jsonify({
            'mensaje': 'Rol creado',
            'rol_id': rol_id
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/usuarios/<int:usuario_id>/roles', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_roles_usuario(usuario_id):
    """Lista roles asignados a un usuario."""
    try:
        roles = db.obtener_roles_de_usuario(usuario_id)
        
        roles_datos = [{
            'id': r[0],
            'nombre': r[1],
            'descripcion': r[2],
            'fecha_asignacion': r[3]
        } for r in roles]
        
        usuario_id_actual = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id_actual, obtener_usuario_actual(),
            'listar_roles_usuario', f'usuario_id:{usuario_id}'
        )
        
        return jsonify(roles_datos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/usuarios/<int:usuario_id>/roles', methods=['POST'])
@require_permission('gestionar_usuarios')
def asignar_rol_usuario(usuario_id):
    """Asigna un rol a un usuario."""
    try:
        datos = request.get_json()
        rol_id = datos.get('rol_id')
        
        if not rol_id:
            return jsonify({'error': 'rol_id requerido'}), 400
        
        success = GestorRoles.asignar_rol_a_usuario(usuario_id, rol_id)
        
        if success:
            usuario_actual_id = obtener_id_usuario_actual()
            registrar_accion_sensible(
                usuario_actual_id, obtener_usuario_actual(),
                'asignar_rol', f'usuario_id:{usuario_id}, rol_id:{rol_id}',
                resultado='exitoso'
            )
            return jsonify({'mensaje': 'Rol asignado'}), 200
        else:
            return jsonify({'error': 'Error asignando rol (posiblemente ya asignado)'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/usuarios/<int:usuario_id>/roles/<int:rol_id>', methods=['DELETE'])
@require_permission('gestionar_usuarios')
def revocar_rol_usuario(usuario_id, rol_id):
    """Revoca un rol de un usuario."""
    try:
        GestorRoles.revocar_rol_de_usuario(usuario_id, rol_id)
        
        usuario_actual_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_actual_id, obtener_usuario_actual(),
            'revocar_rol', f'usuario_id:{usuario_id}, rol_id:{rol_id}',
            resultado='exitoso'
        )
        
        return jsonify({'mensaje': 'Rol revocado'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/permisos', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_permisos():
    """Lista todos los permisos disponibles."""
    try:
        # Obtener todos los permisos desde BD (necesitamos hacerlo directamente)
        with db._get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id, nombre, descripcion, categoria FROM permisos ORDER BY categoria, nombre')
            permisos = c.fetchall()
        
        permisos_datos = [{
            'id': p[0],
            'nombre': p[1],
            'descripcion': p[2],
            'categoria': p[3]
        } for p in permisos]
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'listar_permisos', 'permisos'
        )
        
        return jsonify(permisos_datos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/usuarios/<int:usuario_id>/permisos', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_permisos_usuario(usuario_id):
    """Lista permisos de un usuario (agrupados por categoría)."""
    try:
        permisos_agrupados = GestorRoles.obtener_permisos_usuario_agrupados(usuario_id)
        
        usuario_id_actual = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id_actual, obtener_usuario_actual(),
            'listar_permisos_usuario', f'usuario_id:{usuario_id}'
        )
        
        return jsonify(permisos_agrupados)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === AUDITORÍA ===

@admin_bp.route('/auditoria', methods=['GET'])
@require_permission('ver_auditoria')
def listar_auditoria():
    """Lista eventos de auditoría de accesos a datos sensibles."""
    try:
        dias = request.args.get('dias', 7, type=int)
        filtro_usuario = request.args.get('usuario')
        filtro_accion = request.args.get('accion')
        filtro_recurso = request.args.get('recurso')
        
        eventos = db.obtener_auditoria_accesos(
            filtro_usuario=filtro_usuario,
            filtro_accion=filtro_accion,
            filtro_recurso=filtro_recurso,
            dias=dias
        )
        
        eventos_datos = [{
            'id': e[0],
            'usuario': e[1],
            'accion': e[2],
            'recurso': e[3],
            'resultado': e[4],
            'ip': e[5],
            'fecha': e[6],
            'detalles': e[7]
        } for e in eventos]
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'listar_auditoria', 'auditoria'
        )
        
        if request.accept_mimetypes.best == 'application/json':
            return jsonify(eventos_datos)
        
        return render_template('admin/auditoria.html', eventos=eventos_datos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/auditoria/estadisticas', methods=['GET'])
@require_permission('ver_auditoria')
def estadisticas_auditoria():
    """Obtiene estadísticas de accesos a datos sensibles."""
    try:
        dias = request.args.get('dias', 7, type=int)
        stats = db.obtener_estadisticas_accesos(dias=dias)
        
        stats_datos = {
            'total': stats['total'],
            'denegados': stats['denegados'],
            'permitidos': stats['total'] - stats['denegados'],
            'por_accion': [{'accion': a[0], 'count': a[1]} for a in stats['por_accion']],
            'por_usuario': [{'usuario': u[0], 'count': u[1]} for u in stats['por_usuario']]
        }
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'ver_estadisticas_auditoria', 'auditoria'
        )
        
        return jsonify(stats_datos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === ESTADÍSTICAS ===

@admin_bp.route('/estadisticas/roles', methods=['GET'])
@require_permission('gestionar_usuarios')
def estadisticas_roles():
    """Obtiene estadísticas de roles y permisos."""
    try:
        stats = GestorRoles.obtener_estadisticas_roles()
        
        usuario_id = obtener_id_usuario_actual()
        registrar_accion_sensible(
            usuario_id, obtener_usuario_actual(),
            'ver_estadisticas_roles', 'roles'
        )
        
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === AYUDA Y DOCUMENTACIÓN ===

@admin_bp.route('/permisos/ayuda', methods=['GET'])
@require_permission('gestionar_usuarios')
def ayuda_permisos():
    """Retorna documentación de permisos disponibles."""
    permisos_doc = {
        'visualizacion': {
            'descripcion': 'Permisos básicos de visualización',
            'permisos': [
                'ver_dashboard: Acceso al dashboard principal',
                'ver_mapa: Acceso al visor de mapa',
                'ver_lotes: Ver datos de lotes',
                'ver_actividades: Ver cronograma de actividades'
            ]
        },
        'costos': {
            'descripcion': 'Permisos para gestión de costos (SENSIBLE)',
            'permisos': [
                'ver_costos: Visualizar costos de lotes',
                'editar_costos: Registrar y modificar costos',
                'exportar_costos: Descargar reportes de costos'
            ]
        },
        'inventario': {
            'descripcion': 'Permisos para gestión de inventario (SENSIBLE)',
            'permisos': [
                'ver_inventario: Visualizar inventario',
                'editar_inventario: Registrar entradas/salidas',
                'exportar_inventario: Descargar reportes'
            ]
        },
        'usuarios': {
            'descripcion': 'Permisos para gestión de usuarios (SENSIBLE)',
            'permisos': [
                'ver_datos_personales: Ver información personal',
                'gestionar_usuarios: CRUD de usuarios',
                'editar_permisos: Asignar permisos'
            ]
        },
        'satelital': {
            'descripcion': 'Permisos para capas satelitales (SENSIBLE)',
            'permisos': [
                'ver_ndvi: Ver capas NDVI',
                'ver_meteorologia: Ver datos meteorológicos'
            ]
        },
        'reportes': {
            'descripcion': 'Permisos para reportes',
            'permisos': [
                'generar_reportes: Crear reportes',
                'exportar_reportes: Descargar reportes'
            ]
        }
    }
    
    return jsonify(permisos_doc)

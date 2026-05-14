"""
Servicio de seguridad: decoradores y funciones para verificación de permisos.
Control de acceso basado en roles y permisos granulares.
"""

from functools import wraps
from flask import session, redirect, url_for, jsonify, request
from database import db

def obtener_usuario_actual():
    """Obtiene el usuario actual de la sesión."""
    return session.get('username')

def obtener_id_usuario_actual():
    """Obtiene el ID del usuario actual de la sesión."""
    return session.get('user_id')

def obtener_ip_cliente(request_obj):
    """Extrae IP del cliente (considerando proxies)."""
    if request_obj.headers.getlist("X-Forwarded-For"):
        return request_obj.headers.getlist("X-Forwarded-For")[0]
    return request_obj.remote_addr

def require_permission(permiso_requerido):
    """
    Decorador para proteger rutas que requieren un permiso específico.
    
    Uso:
    @app.route('/api/costos')
    @require_permission('ver_costos')
    def ver_costos():
        return {"costos": [...]}
    
    Si el usuario no tiene permiso:
    - Para JSON: retorna 403 + mensaje
    - Para HTML: redirige a página de acceso denegado
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            usuario = obtener_usuario_actual()
            user_id = obtener_id_usuario_actual()
            
            # Si no está autenticado
            if not usuario:
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({'error': 'No autenticado'}), 401
                return redirect(url_for('index'))
            
            # Verificar si tiene permiso
            if not db.usuario_tiene_permiso(user_id, permiso_requerido):
                ip = obtener_ip_cliente(request)
                db.registrar_acceso(
                    user_id, usuario, 'acceso_denegado',
                    recurso=f'ruta:{request.endpoint}',
                    resultado='denegado',
                    ip_address=ip,
                    detalles=f'Permiso requerido: {permiso_requerido}'
                )
                
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({
                        'error': 'Acceso denegado',
                        'mensaje': f'Requiere permiso: {permiso_requerido}'
                    }), 403
                
                return redirect(url_for('acceso_denegado', permiso=permiso_requerido))
            
            # Registrar acceso exitoso (solo para accesos sensibles)
            if _es_acceso_sensible(permiso_requerido):
                ip = obtener_ip_cliente(request)
                db.registrar_acceso(
                    user_id, usuario, f'acceso_permitido:{permiso_requerido}',
                    recurso=f'ruta:{request.endpoint}',
                    resultado='permitido',
                    ip_address=ip
                )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_permissions_any(*permisos_opcionales):
    """
    Decorador para requerir AL MENOS UNO de varios permisos.
    
    Uso:
    @require_permissions_any('ver_costos', 'gestionar_usuarios')
    def dashboard_admin():
        return render_template('admin.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            usuario = obtener_usuario_actual()
            user_id = obtener_id_usuario_actual()
            
            if not usuario:
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({'error': 'No autenticado'}), 401
                return redirect(url_for('index'))
            
            # Verificar si tiene al menos uno de los permisos
            tiene_permiso = any(
                db.usuario_tiene_permiso(user_id, p) 
                for p in permisos_opcionales
            )
            
            if not tiene_permiso:
                ip = obtener_ip_cliente(request)
                db.registrar_acceso(
                    user_id, usuario, 'acceso_denegado',
                    recurso=f'ruta:{request.endpoint}',
                    resultado='denegado',
                    ip_address=ip,
                    detalles=f'Permisos requeridos (cualquiera): {", ".join(permisos_opcionales)}'
                )
                
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({
                        'error': 'Acceso denegado',
                        'mensaje': f'Requiere uno de estos permisos: {", ".join(permisos_opcionales)}'
                    }), 403
                
                return redirect(url_for('acceso_denegado'))
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_permissions_all(*permisos_requeridos):
    """
    Decorador para requerir TODOS los permisos especificados.
    
    Uso:
    @require_permissions_all('ver_inventario', 'editar_inventario')
    def actualizar_inventario():
        return update_inventory()
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            usuario = obtener_usuario_actual()
            user_id = obtener_id_usuario_actual()
            
            if not usuario:
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({'error': 'No autenticado'}), 401
                return redirect(url_for('index'))
            
            # Verificar si tiene TODOS los permisos
            tiene_permisos = all(
                db.usuario_tiene_permiso(user_id, p) 
                for p in permisos_requeridos
            )
            
            if not tiene_permisos:
                ip = obtener_ip_cliente(request)
                db.registrar_acceso(
                    user_id, usuario, 'acceso_denegado',
                    recurso=f'ruta:{request.endpoint}',
                    resultado='denegado',
                    ip_address=ip,
                    detalles=f'Permisos requeridos (todos): {", ".join(permisos_requeridos)}'
                )
                
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({
                        'error': 'Acceso denegado',
                        'mensaje': f'Requiere todos estos permisos: {", ".join(permisos_requeridos)}'
                    }), 403
                
                return redirect(url_for('acceso_denegado'))
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def filtrar_datos_por_permiso(datos, usuario_id, campos_sensibles):
    """
    Filtra datos sensibles según permisos del usuario.
    
    Uso:
    resultado = {
        'nombre': 'Lote 1',
        'edad': 45,
        'costo_total': 5000,  # sensible
        'fertilizante_costo': 500  # sensible
    }
    
    resultado_filtrado = filtrar_datos_por_permiso(
        resultado, user_id,
        campos_sensibles=['costo_total', 'fertilizante_costo']
    )
    
    Si no tiene 'ver_costos', esos campos se ocultan.
    """
    if db.usuario_tiene_permiso(usuario_id, 'ver_costos'):
        return datos
    
    # Si no tiene permiso, eliminar campos sensibles
    datos_filtrados = dict(datos)
    for campo in campos_sensibles:
        if campo in datos_filtrados:
            del datos_filtrados[campo]
    
    return datos_filtrados

def _es_acceso_sensible(permiso):
    """Determina si un permiso es de datos sensibles."""
    permisos_sensibles = {
        'ver_costos', 'editar_costos', 'exportar_costos',
        'ver_inventario', 'editar_inventario', 'exportar_inventario',
        'ver_datos_personales', 'gestionar_usuarios', 'editar_permisos',
        'ver_ndvi', 'ver_meteorologia', 'ver_auditoria'
    }
    return permiso in permisos_sensibles

def check_admin():
    """Verifica si el usuario actual es administrador."""
    usuario = obtener_usuario_actual()
    if not usuario:
        return False
    
    # Verifica si tiene el permiso de administrador (o todos los permisos)
    user_id = obtener_id_usuario_actual()
    return db.usuario_tiene_permiso(user_id, 'gestionar_usuarios')

def get_permisos_usuario_json(usuario_id):
    """Retorna permisos del usuario como JSON para el frontend."""
    permisos = db.obtener_nombres_permisos_usuario(usuario_id)
    return {
        'permisos': permisos,
        'es_admin': 'gestionar_usuarios' in permisos
    }

def registrar_accion_sensible(usuario_id, usuario_nombre, accion, recurso, resultado="exitoso", detalles=""):
    """Helper para registrar acciones en datos sensibles."""
    ip = obtener_ip_cliente(request)
    db.registrar_acceso(
        usuario_id, usuario_nombre, accion,
        recurso=recurso, resultado=resultado,
        ip_address=ip, detalles=detalles
    )

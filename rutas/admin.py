"""
Rutas de administración: gestión de usuarios, permisos operativos y auditoría.
Todas estas rutas requieren permiso 'gestionar_usuarios' (solo administrador).
"""

from flask import Blueprint, render_template, request, jsonify, session
from database import db
from services.seguridad import require_permission, registrar_accion_sensible

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# === VALIDACIÓN DE PERMISOS ===

def obtener_usuario_actual():
    return session.get('username')

def obtener_id_usuario_actual():
    return session.get('user_id')

# === RUTAS PRINCIPALES ===

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


# === RUTAS CRUD: TRACTORES (ADMIN) ===


@admin_bp.route('/tractores', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_tractores():
    try:
        slot_id = request.args.get('slot_id', type=int)
        tractores = db.obtener_todos_los_tractores(slot_id=slot_id)

        tractores_datos = [{
            'id': t[0],
            'placa': t[1],
            'modelo': t[2],
            'ano': t[3],
            'estado': t[4],
            'slot_id': t[5],
            'metadata_json': t[6],
            'creada_en': t[7],
            'actualizada_en': t[8]
        } for t in tractores]

        if request.accept_mimetypes.best == 'application/json':
            return jsonify(tractores_datos)

        return render_template('admin/tractores.html', tractores=tractores_datos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores', methods=['POST'])
@require_permission('gestionar_usuarios')
def crear_tractor():
    try:
        datos = request.get_json() or request.form
        placa = datos.get('placa')
        if not placa:
            return jsonify({'error': 'placa requerida'}), 400
        modelo = datos.get('modelo')
        ano = datos.get('ano')
        slot_id = datos.get('slot_id')

        nuevo_id = db.crear_tractor(placa=placa, modelo=modelo, ano=ano, slot_id=slot_id)
        if not nuevo_id:
            return jsonify({'error': 'No se pudo crear (placa ya existe?)'}), 400
        return jsonify({'mensaje': 'Tractor creado', 'id': nuevo_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores/<int:tractor_id>', methods=['GET'])
@require_permission('gestionar_usuarios')
def ver_tractor(tractor_id):
    try:
        t = db.obtener_tractor_por_id(tractor_id)
        if not t:
            return jsonify({'error': 'No encontrado'}), 404
        datos = {'id': t[0], 'placa': t[1], 'modelo': t[2], 'ano': t[3], 'estado': t[4], 'slot_id': t[5], 'metadata_json': t[6], 'creada_en': t[7], 'actualizada_en': t[8]}
        return jsonify(datos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores/<int:tractor_id>', methods=['PATCH'])
@require_permission('gestionar_usuarios')
def actualizar_tractor_route(tractor_id):
    try:
        datos = request.get_json() or {}
        success = db.actualizar_tractor(
            tractor_id,
            placa=datos.get('placa'),
            modelo=datos.get('modelo'),
            ano=datos.get('ano'),
            estado=datos.get('estado'),
            slot_id=datos.get('slot_id'),
            metadata_json=datos.get('metadata_json')
        )
        if not success:
            return jsonify({'error': 'No se actualizó'}), 400
        return jsonify({'mensaje': 'Actualizado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores/<int:tractor_id>', methods=['DELETE'])
@require_permission('gestionar_usuarios')
def eliminar_tractor_route(tractor_id):
    try:
        success = db.eliminar_tractor(tractor_id)
        if not success:
            return jsonify({'error': 'No se eliminó (quizá no existe)'}), 400
        return jsonify({'mensaje': 'Eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores/<int:tractor_id>/vincular', methods=['POST'])
@require_permission('gestionar_usuarios')
def vincular_tractor_route(tractor_id):
    try:
        datos = request.get_json() or request.form
        unidad_id = datos.get('unidad_id')
        if not unidad_id:
            return jsonify({'error': 'unidad_id requerido'}), 400
        ok = db.vincular_tractor(tractor_id, unidad_id)
        if not ok:
            return jsonify({'error': 'No se pudo vincular'}), 400
        db.registrar_log(obtener_usuario_actual(), f'Vincular tractor', f'Tractor {tractor_id} -> unidad {unidad_id}')
        return jsonify({'ok': True, 'tractor_id': tractor_id, 'unidad_id': unidad_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tractores/<int:tractor_id>/desvincular', methods=['POST'])
@require_permission('gestionar_usuarios')
def desvincular_tractor_route(tractor_id):
    try:
        ok = db.desvincular_tractor(tractor_id)
        if not ok:
            return jsonify({'error': 'No se pudo desvincular'}), 400
        db.registrar_log(obtener_usuario_actual(), f'Desvincular tractor', f'Tractor {tractor_id}')
        return jsonify({'ok': True, 'tractor_id': tractor_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# === RUTAS CRUD: PLANES (ADMIN) ===


@admin_bp.route('/planes', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_planes():
    try:
        return render_template('admin/planes.html', planes=[])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actividades-catalogo', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_actividades_catalogo_route():
    try:
        solo_activas = request.args.get('solo_activas', '0') in ('1', 'true', 'True')
        actividades = db.obtener_catalogo_actividades(solo_activas=solo_activas)
        actividades_datos = [{
            'id': a[0],
            'nombre': a[1],
            'etapa': a[2],
            'descripcion': a[3],
            'como_se_realiza': a[4],
            'programacion_recomendada': a[5],
            'activa': bool(a[6]),
            'creada_en': a[7],
            'actualizada_en': a[8]
        } for a in actividades]
        return jsonify(actividades_datos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actividades-catalogo', methods=['POST'])
@require_permission('gestionar_usuarios')
def crear_actividad_catalogo_route():
    try:
        datos = request.get_json() or request.form
        nombre = (datos.get('nombre') or '').strip()
        if not nombre:
            return jsonify({'error': 'nombre es requerido'}), 400

        activa_raw = datos.get('activa', True)
        activa = activa_raw in (True, 1, '1', 'true', 'True', 'on')
        etapa = (datos.get('etapa') or '').strip()
        descripcion = (datos.get('descripcion') or '').strip()
        como_se_realiza = (datos.get('como_se_realiza') or '').strip()
        programacion_recomendada = (datos.get('programacion_recomendada') or '').strip()

        nuevo_id = db.crear_actividad_catalogo(
            nombre=nombre,
            activa=activa,
            etapa=etapa,
            descripcion=descripcion,
            como_se_realiza=como_se_realiza,
            programacion_recomendada=programacion_recomendada
        )
        if not nuevo_id:
            return jsonify({'error': 'No se pudo crear la actividad (posible duplicado)'}), 400

        db.registrar_log(obtener_usuario_actual(), 'Crear actividad catálogo', f'ID: {nuevo_id}, nombre: {nombre}')
        return jsonify({'mensaje': 'Actividad creada', 'id': nuevo_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actividades-catalogo/<int:actividad_id>', methods=['GET'])
@require_permission('gestionar_usuarios')
def ver_actividad_catalogo_route(actividad_id):
    try:
        a = db.obtener_actividad_catalogo_por_id(actividad_id)
        if not a:
            return jsonify({'error': 'No encontrado'}), 404
        return jsonify({
            'id': a[0],
            'nombre': a[1],
            'etapa': a[2],
            'descripcion': a[3],
            'como_se_realiza': a[4],
            'programacion_recomendada': a[5],
            'activa': bool(a[6]),
            'creada_en': a[7],
            'actualizada_en': a[8]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actividades-catalogo/<int:actividad_id>', methods=['PATCH'])
@require_permission('gestionar_usuarios')
def actualizar_actividad_catalogo_route(actividad_id):
    try:
        datos = request.get_json() or {}
        activa = datos.get('activa')
        if activa is not None:
            activa = activa in (True, 1, '1', 'true', 'True', 'on')

        success = db.actualizar_actividad_catalogo(
            actividad_id,
            nombre=datos.get('nombre'),
            activa=activa,
            etapa=datos.get('etapa'),
            descripcion=datos.get('descripcion'),
            como_se_realiza=datos.get('como_se_realiza'),
            programacion_recomendada=datos.get('programacion_recomendada')
        )
        if not success:
            return jsonify({'error': 'No se actualizó'}), 400
        db.registrar_log(obtener_usuario_actual(), 'Actualizar actividad catálogo', f'ID: {actividad_id}')
        return jsonify({'mensaje': 'Actualizado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actividades-catalogo/<int:actividad_id>', methods=['DELETE'])
@require_permission('gestionar_usuarios')
def eliminar_actividad_catalogo_route(actividad_id):
    try:
        success = db.eliminar_actividad_catalogo(actividad_id)
        if not success:
            return jsonify({'error': 'No se eliminó (quizá no existe)'}), 400
        db.registrar_log(obtener_usuario_actual(), 'Eliminar actividad catálogo', f'ID: {actividad_id}')
        return jsonify({'mensaje': 'Eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# === RUTAS: NOTIFICACIONES (ADMIN) ===


@admin_bp.route('/notificaciones', methods=['GET'])
@require_permission('ver_auditoria')
def listar_notificaciones():
    try:
        slot_id = request.args.get('slot_id', type=int)
        canal = request.args.get('canal', type=str)
        estado = request.args.get('estado', type=str)
        desde = request.args.get('desde', type=str)
        hasta = request.args.get('hasta', type=str)
        if slot_id is None:
            # Renderizar la plantilla y dejar que JS pida el slot
            if request.accept_mimetypes.best == 'application/json':
                return jsonify([])
            return render_template('admin/notificaciones.html', notificaciones=[])

        filas = db.obtener_notificaciones_por_slot(slot_id, canal=canal, estado=estado, desde=desde, hasta=hasta)
        datos = [{
            'id': f[0], 'slot_id': f[1], 'canal': f[2], 'destino': f[3], 'tipo': f[4],
            'titulo': f[5], 'mensaje': f[6], 'resultado_json': f[7], 'creada_en': f[8],
            'origen': f[9], 'estado': f[10], 'intentos': f[11], 'ultimo_intento_en': f[12]
        } for f in filas]

        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'slot_id': slot_id, 'total': len(datos), 'notificaciones': datos})

        return render_template('admin/notificaciones.html', notificaciones=datos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/notificaciones/<int:notificacion_id>/reintentar', methods=['POST'])
@require_permission('ver_auditoria')
def reintentar_notificacion(notificacion_id):
    try:
        # Obtener notificación original
        n = db.obtener_notificacion_por_id(notificacion_id)
        if not n:
            return jsonify({'error': 'Notificación no encontrada'}), 404

        # Mapear campos
        _, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en = n

        # Construir payload para reintento
        payload = {
            'slot_id': slot_id,
            'tipo': tipo,
            'titulo': titulo,
            'mensaje': mensaje,
            'telefono': destino,
            'retries': 1
        }

        # Enviar por el canal original
        from services.multicanal import enviar_canal
        resultado = enviar_canal(canal, mensaje, destino=destino)

        # Actualizar registro original: incrementar intentos y actualizar resultado/estado
        resultado_json_n = json.dumps(resultado)
        nuevo_estado = 'enviado' if resultado.get('ok') else 'fallo'
        db.actualizar_notificacion_resultado(notificacion_id, resultado_json_n, nuevo_estado=nuevo_estado, incrementar_intentos=True)

        # Además, crear registro nuevo si se desea (audit trail) - opcional
        db.crear_notificacion(slot_id, canal or 'multicanal', destino, tipo, titulo, mensaje, resultado_json_n, origen='reintento_manual', forzar=True)

        return jsonify({'ok': True, 'resultado': resultado}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# === RUTAS: UNIDADES DETECTADAS (ADMIN) ===


@admin_bp.route('/unidades', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_unidades():
    try:
        slot_id = request.args.get('slot_id', type=int)
        if slot_id is None:
            # Renderizar página y dejar que JS pida el slot
            if request.accept_mimetypes.best == 'application/json':
                return jsonify([])
            return render_template('admin/unidades.html', unidades=[])

        unidades = db.obtener_unidades_con_ultima_posicion(slot_id)
        unidades_datos = [{
            'unidad_id': u[0],
            'lat': u[1],
            'lng': u[2],
            'velocidad_kmh': u[3],
            'estado_motor': u[4],
            'nivel_bateria': u[5],
            'timestamp': u[6],
            'tractor_id': u[7],
            'tractor_placa': u[8],
            'tractor_modelo': u[9]
        } for u in unidades]

        if request.accept_mimetypes.best == 'application/json':
            return jsonify(unidades_datos)

        return render_template('admin/unidades.html', unidades=unidades_datos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/unidades/<unidad_id>/vincular', methods=['POST'])
@require_permission('gestionar_usuarios')
def vincular_unidad(unidad_id):
    try:
        datos = request.get_json() or request.form
        tractor_id = datos.get('tractor_id')
        if not tractor_id:
            return jsonify({'error': 'tractor_id requerido'}), 400
        # asegurar integer
        try:
            tractor_id = int(tractor_id)
        except Exception:
            return jsonify({'error': 'tractor_id inválido'}), 400

        ok = db.vincular_tractor(tractor_id, unidad_id)
        if not ok:
            return jsonify({'error': 'No se pudo vincular (revisar tractor_id)'}), 400
        db.registrar_log(obtener_usuario_actual(), 'Vincular unidad', f'Unidad {unidad_id} -> Tractor {tractor_id}')
        return jsonify({'ok': True, 'unidad_id': unidad_id, 'tractor_id': tractor_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/unidades/no_vinculadas', methods=['GET'])
@require_permission('gestionar_usuarios')
def listar_unidades_no_vinculadas():
    try:
        slot_id = request.args.get('slot_id', type=int)
        if slot_id is None:
            return jsonify({'error': 'slot_id requerido'}), 400

        filas = db.obtener_unidades_con_ultima_posicion(slot_id)
        unidades = []
        for f in filas:
            tractor_id = f[7]
            if tractor_id is None:
                unidades.append({
                    'unidad_id': f[0],
                    'lat': f[1],
                    'lng': f[2],
                    'velocidad_kmh': f[3],
                    'nivel_bateria': f[5],
                    'timestamp': f[6]
                })

        return jsonify({'slot_id': slot_id, 'total': len(unidades), 'unidades': unidades}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/unidades/bulk_vincular', methods=['POST'])
@require_permission('gestionar_usuarios')
def bulk_vincular_unidades():
    try:
        data = request.get_json() or {}
        mappings = data.get('mappings') or data.get('vinculaciones')
        if not mappings or not isinstance(mappings, list):
            return jsonify({'error': 'Se requiere lista de mappings en "mappings"'}), 400

        procesadas = 0
        exitosas = 0
        errores = []

        for m in mappings:
            procesadas += 1
            unidad = m.get('unidad_id')
            tractor_id = m.get('tractor_id')
            if not unidad or tractor_id is None:
                errores.append({'mapping': m, 'error': 'unidad_id o tractor_id faltante'})
                continue
            try:
                ok = db.vincular_tractor(int(tractor_id), unidad)
                if ok:
                    exitosas += 1
                else:
                    errores.append({'mapping': m, 'error': 'vinculación fallida (revisar tractor_id)'})
            except Exception as e:
                errores.append({'mapping': m, 'error': str(e)})

        db.registrar_log(obtener_usuario_actual(), 'Vinculación masiva', f'procesadas={procesadas} exitosas={exitosas}')
        return jsonify({'ok': True, 'procesadas': procesadas, 'exitosas': exitosas, 'errors': errores}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

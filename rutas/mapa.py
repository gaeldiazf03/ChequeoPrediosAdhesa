from flask import Blueprint, render_template, session, redirect, url_for, request, make_response, send_file, Response, jsonify
from database import db
from utils.funciones import convertir_geojson_a_kml
from utils.funciones import convertir_kml_a_geojson
import io
from datetime import datetime
from services.reportes import generar_csv_logs, generar_csv_mapa, generar_excel_avance_por_predio, generar_word_mapa
from services.seguridad import require_permission
from services.notificaciones import enviar_alerta_email, correo_habilitado, enviar_correo_con_adjunto
from services.multicanal import enviar_multicanal
from services.multicanal import enviar_telegram
from services.clima import servicio_clima
import json
import random
import os
import threading
import urllib.request
import urllib.error
import ssl

mapa_bp = Blueprint('mapa', __name__)
SMARTMAP_ALERTAS_HABILITADO = os.environ.get('ENABLE_SMARTMAP_ALERTS', '0') == '1'

# Telemetría viva en memoria para evitar write-locks continuos en SQLite.
posiciones_flota = {}
posiciones_flota_lock = threading.Lock()


def _smartmap_desactivado_response():
    return jsonify({
        'ok': False,
        'error': 'Modulo SmartMap desactivado por reestructuracion del sistema.'
    }), 410


def _actualizar_cache_flotas(slot_id, unidad_id, lat, lng, velocidad_kmh=0, estado_motor='encendido', nivel_bateria=None, metadata_json=''):
    marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registro = {
        'slot_id': slot_id,
        'unidad_id': str(unidad_id),
        'lat': float(lat),
        'lng': float(lng),
        'velocidad_kmh': float(velocidad_kmh or 0),
        'estado_motor': estado_motor or 'desconocido',
        'nivel_bateria': float(nivel_bateria) if nivel_bateria is not None else None,
        'timestamp': marca_tiempo,
        'metadata_json': metadata_json or ''
    }

    with posiciones_flota_lock:
        cache_slot = posiciones_flota.setdefault(int(slot_id), {})
        cache_slot[str(unidad_id)] = registro

    return registro


def _obtener_cache_flotas(slot_id):
    with posiciones_flota_lock:
        cache_slot = posiciones_flota.get(int(slot_id), {})
        return list(cache_slot.values())


def _volcar_cache_flotas_a_bd(slot_id=None):
    """Persistencia resumida opcional de la telemetría en RAM hacia SQLite."""
    with posiciones_flota_lock:
        slots = [int(slot_id)] if slot_id is not None else list(posiciones_flota.keys())
        snapshot = {sid: list(posiciones_flota.get(sid, {}).values()) for sid in slots}

    guardadas = 0
    for sid, registros in snapshot.items():
        for reg in registros:
            try:
                db.insertar_telemetria(
                    sid,
                    reg['unidad_id'],
                    reg['lat'],
                    reg['lng'],
                    reg.get('velocidad_kmh', 0),
                    reg.get('estado_motor', 'desconocido'),
                    reg.get('nivel_bateria'),
                    reg.get('metadata_json', '')
                )
                guardadas += 1
            except Exception:
                continue
    return guardadas


def _disparar_tarea_en_hilo(funcion, *args, **kwargs):
    hilo = threading.Thread(target=funcion, args=args, kwargs=kwargs, daemon=True)
    hilo.start()
    return hilo

# Intentar importar shapely para contenciones precisas; si no está, usaremos fallback por bbox
try:
    from shapely.geometry import shape as _shape
    HAS_SHAPELY = True
except Exception:
    _shape = None
    HAS_SHAPELY = False


def _puede_guardar_mapa(rol, *permisos):
    return rol == 'admin' or any(bool(permiso) for permiso in permisos)


def _armar_permisos_mapa(rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos):
    return {
        "puede_agregar": rol == 'admin' or bool(db_agregar),
        "puede_editar": rol == 'admin' or bool(db_editar),
        "puede_agregar_tareas": rol == 'admin' or bool(db_agregar_tar),
        "puede_marcar_tareas": rol == 'admin' or bool(db_marcar_tar),
        "puede_ver_costos": rol == 'admin' or bool(db_costos),
        "puede_descargar_mapa": rol == 'admin' or False,
        "puede_descargar_logs": rol == 'admin' or False,
    }

@mapa_bp.route('/adhesa/<slug>')
def visor(slug):
    if not session.get('logeado'): 
        return redirect(url_for('login.index'))
    
    slot_info = db.obtener_slot_por_slug(slug)
    if not slot_info:
        return redirect(url_for('dashboard.index'))
        
    slot_id = slot_info[0]
    nombre_real = slot_info[1]
    usuario = session.get('usuario', 'Desconocido')
    user_id = session.get('user_id')
    
    kml_contenido = db.obtener_kml_por_id(slot_id)
    
    db.actualizar_metadatos_slot(slot_id, usuario, datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    rol, db_add, db_edit, db_tar, db_check, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)

    permisos = _armar_permisos_mapa(rol, db_add, db_edit, db_tar, db_check, db_costos)
    # Ajustar permisos específicos de descarga basados en DB
    permisos['puede_descargar_mapa'] = rol == 'admin' or bool(db_desc_mapa)
    permisos['puede_descargar_logs'] = rol == 'admin' or bool(db_desc_logs)
    permisos['puede_ver_alertas'] = bool(user_id and db.usuario_tiene_permiso(user_id, 'ver_alertas'))

    return render_template('mapa.html', 
                           slot_id=slot_id, 
                           nombre_mapa=nombre_real, 
                           kml_data=kml_contenido,
                           usuario_actual=usuario,
                           es_admin=(rol == 'admin'),
                           usuarios_lista_json=json.dumps([u[1] for u in db.obtener_todos_los_usuarios()]),
                           **permisos)

@mapa_bp.route('/api/guardar_kml/<int:slot_id>', methods=['POST'])
def guardar(slot_id):
    if not session.get('logeado'):
        return {"ok": False, "error": "Acceso denegado"}, 401

    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)

    puede_guardar = _puede_guardar_mapa(rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos)
    
    if not puede_guardar:
        return {"ok": False, "error": "Sin permisos"}, 403

    data = request.get_json(silent=True)
    if data:
        # Antes de convertir a KML, intentar asignar padres automáticos si corresponde
        try:
            _asignar_padres_geojson_inplace(data)
            _asegurar_tareas_padre_geojson_inplace(data)
            _asegurar_tareas_hijo_geojson_inplace(data)
        except Exception:
            pass
        try:
            kml_str = convertir_geojson_a_kml(data)
        except Exception as e:
            return {"ok": False, "error": f"Error al convertir GeoJSON a KML: {str(e)}"}, 500

        saved = db.guardar_kml_en_slot(slot_id, kml_str)
        if not saved:
            return {"ok": False, "error": "Contenido inválido; no guardado."}, 400

        db.registrar_log(usuario, "Modificación de Mapa", f"Slot ID: {slot_id}")

    return {"ok": True}


def _asignar_padres_geojson_inplace(geojson_obj, principales=None):
    """
    Modifica in-place el GeoJSON añadiendo `properties.parent` cuando un feature queda contenido
    dentro de un feature cuyo nombre está en `principales`.
    Si no se provee `principales`, se usa una lista por defecto basada en requerimiento del usuario.
    """
    if not geojson_obj or 'features' not in geojson_obj:
        return 0

    principales_default = ['Casa Blanca','Mango','Guzman','Paisabel','Isleta','Tamante']
    principales = principales or principales_default

    feats = geojson_obj.get('features', [])
    # Mapear nombres a features
    name_to_feat = {}
    for f in feats:
        try:
            name = f.get('properties', {}).get('name')
            if name:
                name_to_feat[name] = f
        except Exception:
            continue

    asignadas = 0

    for pname in principales:
        pfeat = name_to_feat.get(pname)
        if not pfeat:
            continue
        pgeom = pfeat.get('geometry')
        if not pgeom:
            continue

        # Construir objeto geom para shapely o bbox
        if HAS_SHAPELY:
            try:
                pshape = _shape(pgeom)
            except Exception:
                pshape = None
        else:
            pshape = None
            # calcular bbox del principal
            try:
                coords = _extract_all_coords(pgeom)
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                pminx, pmaxx = min(xs), max(xs)
                pminy, pmaxy = min(ys), max(ys)
            except Exception:
                pminx = pmaxx = pminy = pmaxy = None

        for other in feats:
            if other is pfeat:
                continue
            try:
                # si ya tiene parent skip
                if other.get('properties', {}).get('parent'):
                    continue

                oname = other.get('properties', {}).get('name')
                if oname and oname in principales:
                    continue

                og = other.get('geometry')
                if not og:
                    continue

                contained = False
                if HAS_SHAPELY and pshape is not None:
                    try:
                        oshape = _shape(og)
                        contained = _cobertura_mayor_al_umbral(pshape, oshape, 0.6)
                    except Exception:
                        contained = False
                else:
                    # fallback por bbox intersección (conservative: require other bbox inside principal bbox)
                    coords_o = _extract_all_coords(og)
                    if not coords_o or pminx is None:
                        contained = False
                    else:
                        xs_o = [c[0] for c in coords_o]
                        ys_o = [c[1] for c in coords_o]
                        ominx, omaxx = min(xs_o), max(xs_o)
                        ominy, omaxy = min(ys_o), max(ys_o)
                        if (ominx >= pminx and omaxx <= pmaxx and ominy >= pminy and omaxy <= pmaxy):
                            contained = True

                if contained:
                    if 'properties' not in other or other['properties'] is None:
                        other['properties'] = {}
                    other['properties']['parent'] = pname
                    asignadas += 1
            except Exception:
                continue

    return asignadas


def _asegurar_tareas_padre_geojson_inplace(geojson_obj, principales=None):
    """Agrega tareas agrícolas por defecto a los predios padre si no tienen tareas."""
    if not geojson_obj or 'features' not in geojson_obj:
        return 0

    principales_default = ['Casa Blanca', 'Mango', 'Guzman', 'Paisabel', 'Isleta', 'Tamante']
    principales = principales or principales_default
    tareas_default = [
        {'texto': 'Subsuelo', 'estado': 'rojo', 'completada': False},
        {'texto': 'Arado', 'estado': 'rojo', 'completada': False},
        {'texto': 'Rastra', 'estado': 'rojo', 'completada': False},
        {'texto': 'Barbecho', 'estado': 'rojo', 'completada': False},
    ]

    asignadas = 0
    for feature in geojson_obj.get('features', []):
        try:
            props = feature.get('properties', {}) or {}
            nombre = props.get('name')
            if not nombre or str(nombre).strip() not in principales:
                continue

            tareas = props.get('tareas')
            if not isinstance(tareas, list) or len(tareas) == 0:
                props['tareas'] = [dict(t) for t in tareas_default]
                feature['properties'] = props
                asignadas += 1
        except Exception:
            continue

    return asignadas


def _asegurar_tareas_hijo_geojson_inplace(geojson_obj):
    """Agrega actividades básicas a los predios hijos si aún no tienen tareas."""
    if not geojson_obj or 'features' not in geojson_obj:
        return 0

    tareas_basicas = [
        {'texto': 'Riego inicial', 'estado': 'rojo', 'completada': False},
        {'texto': 'Fertilización básica', 'estado': 'rojo', 'completada': False},
        {'texto': 'Monitoreo de crecimiento', 'estado': 'rojo', 'completada': False},
        {'texto': 'Control de maleza', 'estado': 'rojo', 'completada': False},
    ]

    asignadas = 0
    for feature in geojson_obj.get('features', []):
        try:
            props = feature.get('properties', {}) or {}
            if not props.get('parent'):
                continue
            tareas = props.get('tareas')
            if not isinstance(tareas, list) or len(tareas) == 0:
                props['tareas'] = [dict(t) for t in tareas_basicas]
                feature['properties'] = props
                asignadas += 1
        except Exception:
            continue

    return asignadas


def _cobertura_mayor_al_umbral(parent_shape, child_shape, umbral=0.6):
    """Retorna True si la intersección cubre al menos el umbral del área del hijo."""
    try:
        if not parent_shape or not child_shape:
            return False
        area_hijo = float(child_shape.area or 0.0)
        if area_hijo <= 0:
            return False
        area_interseccion = float(parent_shape.intersection(child_shape).area or 0.0)
        return (area_interseccion / area_hijo) >= float(umbral)
    except Exception:
        return False


def _extract_all_coords(geom):
    """Extrae todos los pares [lon,lat] de una geometría GeoJSON de forma plana."""
    if not geom or 'type' not in geom:
        return []
    t = geom['type']
    coords = []
    try:
        if t == 'Point':
            c = geom.get('coordinates')
            if isinstance(c, (list,tuple)) and len(c) >= 2:
                coords.append([float(c[0]), float(c[1])])
        elif t == 'Polygon':
            for ring in geom.get('coordinates', []):
                for pt in ring:
                    coords.append([float(pt[0]), float(pt[1])])
        elif t == 'MultiPolygon':
            for poly in geom.get('coordinates', []):
                for ring in poly:
                    for pt in ring:
                        coords.append([float(pt[0]), float(pt[1])])
        else:
            # LineString, MultiLineString, etc.
            for part in geom.get('coordinates', []):
                if isinstance(part[0], (float, int)):
                    coords.append([float(part[0]), float(part[1])])
                else:
                    for pt in part:
                        coords.append([float(pt[0]), float(pt[1])])
    except Exception:
        return []
    return coords

@mapa_bp.route('/admin/reporte/<rango>')
def reporte(rango):
    usuario = session.get('username') or session.get('usuario')
    if not usuario:
        return "Acceso denegado", 403

    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)
    if rol != 'admin' and not bool(db_desc_logs):
        return "Acceso denegado", 403

    logs = db.obtener_logs_por_rango(rango)
    csv_str = generar_csv_logs(logs)
    nombre = f"reporte_{rango}.csv"
    
    resp = make_response('\ufeff' + csv_str)
    resp.headers["Content-Disposition"] = f"attachment; filename={nombre}"
    resp.headers["Content-type"] = "text/csv; charset=utf-8"
    return resp

@mapa_bp.route('/exportar_kml', methods=['POST'])
def exportar_kml():
    try:
        data = request.json
        kml_str = convertir_geojson_a_kml(data)
        mem_file = io.BytesIO()
        mem_file.write(kml_str.encode('utf-8'))
        mem_file.seek(0)
        return send_file(mem_file, mimetype='application/vnd.google-earth.kml+xml', as_attachment=True, download_name='mapa_modificado.kml')
    except Exception as e:
        # Registrar y devolver error claro en texto/JSON para evitar que el debugger HTML sea devuelto al cliente
        try:
            usuario = session.get('usuario')
            db.registrar_log(usuario or 'anonimo', 'Exportar KML - error', str(e))
        except Exception:
            pass
        return jsonify({'ok': False, 'error': 'Error al generar KML', 'details': str(e)}), 500

@mapa_bp.route('/api/kml/<int:slot_id>')
def api_obtener_kml(slot_id):
    if not session.get('logeado'):
        return "Acceso denegado", 401
    kml_texto = db.obtener_kml_por_id(slot_id)
    if kml_texto:
        return Response(kml_texto, mimetype='application/vnd.google-earth.kml+xml')
    return "KML no encontrado", 404

@mapa_bp.route('/api/mis_permisos')
def mis_permisos():
    if not session.get('logeado'):
        return {"logeado": False}

    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)
    return {
        "logeado": True,
        **_armar_permisos_mapa(rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos),
        "puede_descargar_mapa": rol == 'admin' or bool(db_desc_mapa),
        "puede_descargar_logs": rol == 'admin' or bool(db_desc_logs)
    }

@mapa_bp.route('/api/reporte_word/<int:slot_id>', methods=['POST'])
def reporte_word(slot_id):
    if not session.get('logeado'): return "No autorizado", 401
    
    data = request.get_json(silent=True)
    if not data: return "Sin datos", 400

    target, nombre_archivo = generar_word_mapa(data, slot_id)
    return send_file(
        target,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@mapa_bp.route('/api/reporte_mapa/<int:slot_id>', methods=['POST'])
def reporte_mapa(slot_id):
    if not session.get('logeado'): return "No autorizado", 401

    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)
    if rol != 'admin' and not bool(db_desc_logs):
        return jsonify({'ok': False, 'error': 'Sin permisos para descargar logs'}), 403

    data = request.get_json(silent=True)
    if not data:
        return "Sin datos", 400

    try:
        target, nombre_archivo = generar_excel_avance_por_predio(data, slot_id)
        resp = send_file(
            target,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        return resp
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@mapa_bp.route('/api/reporte_email/<int:slot_id>', methods=['POST'])
def reporte_email(slot_id):
    if not session.get('logeado'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401

    payload = request.get_json(silent=True) or {}
    data = payload.get('geojson', payload)
    if not data:
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400

    usuario = session.get('usuario')
    if not usuario:
        return jsonify({'ok': False, 'error': 'Acceso denegado'}), 403

    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar, db_costos, db_desc_mapa, db_desc_logs = db.obtener_permisos_usuario(usuario)
    if rol != 'admin' and not bool(db_desc_mapa):
        return jsonify({'ok': False, 'error': 'Sin permisos para enviar reportes por correo'}), 403

    formato = str(payload.get('formato', 'word')).strip().lower()
    destinatarios = db.obtener_correos_usuarios()
    if not destinatarios:
        fallback = os.environ.get('ALERT_EMAIL_TO', '')
        destinatarios = [x.strip() for x in fallback.replace(';', ',').split(',') if x.strip()]

    if not destinatarios:
        return jsonify({'ok': False, 'error': 'No hay correos configurados en usuarios ni destinatarios globales.'}), 400

    try:
        if formato == 'csv':
            contenido, nombre_archivo = generar_csv_mapa(data, slot_id)
            adjunto_bytes = contenido.encode('utf-8')
            asunto = f'Reporte CSV de avances - Slot {slot_id}'
            cuerpo = 'Adjunto encontrarás el reporte CSV de avances generado desde ADHESA Smart Map.'
            mimetype = 'text/csv'
        else:
            target, nombre_archivo = generar_word_mapa(data, slot_id)
            adjunto_bytes = target.getvalue()
            asunto = f'Reporte de avances - Slot {slot_id}'
            cuerpo = 'Adjunto encontrarás el reporte de avances generado desde ADHESA Smart Map.'
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        usuario_log = usuario

        def _enviar_reporte():
            envio = enviar_correo_con_adjunto(asunto, cuerpo, destinatarios, adjunto_bytes, nombre_archivo, mimetype)
            estado = 'enviado' if envio.get('ok') else 'fallo'
            db.registrar_log(usuario_log, 'Enviar reporte por correo', f'Slot ID: {slot_id}, formato: {formato}, estado={estado}, destinatarios: {len(destinatarios)}')

        _disparar_tarea_en_hilo(_enviar_reporte)
        return jsonify({'ok': True, 'estado': 'en_proceso', 'destinatarios': destinatarios, 'formato': formato}), 202
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# === SMART MAP (FASE 2) ===

def _seed_telemetria_demo(slot_id):
    """Reservado para integración futura con la API real de unidades."""
    # TODO: Integrar aquí la API externa de unidades cuando exista.
    return None


def _seed_reglas_demo(slot_id, usuario='sistema'):
    """Genera reglas base para Alert System fase 2."""
    reglas_actuales = db.obtener_reglas_alerta(slot_id)
    if reglas_actuales:
        return

    db.crear_regla_alerta(slot_id, 'Velocidad alta de maquinaria', 'velocidad_mayor', 36, 'alta', usuario)
    db.crear_regla_alerta(slot_id, 'Batería crítica de unidad', 'bateria_menor', 20, 'media', usuario)


def _evaluar_reglas_y_generar_alertas(slot_id, unidad_id, velocidad, bateria):
    """Evalúa reglas activas y crea alertas cuando se cumplen."""
    reglas = db.obtener_reglas_alerta(slot_id, solo_activas=True)
    generadas = 0

    for regla in reglas:
        _, _, nombre, tipo, umbral, severidad, activa, _, _, _ = regla
        if not activa:
            continue

        disparada = False
        mensaje = ''

        if tipo == 'velocidad_mayor' and velocidad > float(umbral):
            disparada = True
            mensaje = f'La unidad {unidad_id} reporta {round(velocidad, 1)} km/h (umbral: {umbral}).'

        if tipo == 'bateria_menor' and bateria < float(umbral):
            disparada = True
            mensaje = f'La unidad {unidad_id} reporta batería {round(bateria, 1)}% (umbral: {umbral}%).'

        if disparada:
            payload_alerta = {
                'slot_id': slot_id,
                'unidad_id': unidad_id,
                'tipo': tipo,
                'severidad': severidad or 'media',
                'titulo': f'[{nombre}] {unidad_id}',
                'mensaje': mensaje,
            }

            db.crear_alerta(
                slot_id=slot_id,
                tipo=tipo,
                severidad=severidad or 'media',
                titulo=payload_alerta['titulo'],
                mensaje=payload_alerta['mensaje'],
                metadata_json=json.dumps({
                    'regla': nombre,
                    'tipo': tipo,
                    'umbral': umbral,
                    'unidad_id': unidad_id
                })
            )

            usuario_log = session.get('username', 'sistema')

            # Canal externo inicial de Fase 2: correo electrónico.
            # No interrumpe el flujo principal si falla SMTP.
            def _enviar_alerta_correo():
                envio = enviar_alerta_email(payload_alerta)
                if not envio.get('ok'):
                    db.registrar_log(
                        usuario_log,
                        'Envio correo alerta (fallo/no-config)',
                        f"Slot {slot_id} unidad {unidad_id} motivo={envio.get('motivo', 'desconocido')}"
                    )

            _disparar_tarea_en_hilo(_enviar_alerta_correo)

            generadas += 1
            # Intentar enviar por canales adicionales (Telegram, WhatsApp placeholder)
            def _enviar_multicanal_alerta():
                try:
                    resultados = enviar_multicanal(payload_alerta)
                    try:
                        for canal, res in resultados.items():
                            destino = ''
                            mensaje_log = json.dumps(res)
                            notificacion_id = db.crear_notificacion(slot_id, canal, destino, tipo, payload_alerta['titulo'], payload_alerta['mensaje'], mensaje_log, origen='alerta')
                            if notificacion_id:
                                estado_final = 'enviado' if res.get('ok') else 'fallo'
                                db.actualizar_notificacion_resultado(notificacion_id, mensaje_log, nuevo_estado=estado_final, incrementar_intentos=not res.get('ok'))
                    except Exception:
                        pass
                except Exception:
                    pass

            _disparar_tarea_en_hilo(_enviar_multicanal_alerta)

    return generadas


@mapa_bp.route('/api/smartmap/telemetria/<int:slot_id>', methods=['GET'])
@require_permission('ver_mapa')
def smartmap_telemetria(slot_id):
    """Retorna última posición de unidades del lote para visualización en tiempo real."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        _seed_reglas_demo(slot_id, session.get('username', 'sistema'))

        # Intentar obtener la última telemetría almacenada en BD
        filas = db.obtener_unidades_con_ultima_posicion(slot_id)
        unidades = []
        for f in filas:
            unidades.append({
                'unidad_id': f[0],
                'lat': float(f[1]),
                'lng': float(f[2]),
                'velocidad_kmh': float(f[3]) if f[3] is not None else 0,
                'estado_motor': f[4],
                'nivel_bateria': float(f[5]) if f[5] is not None else None,
                'timestamp': f[6],
                'tractor_id': f[7],
                'placa': f[8],
                'modelo': f[9]
            })

        return jsonify({
            'slot_id': slot_id,
            'total_unidades': len(unidades),
            'unidades': unidades,
            'api_unidades_pendiente': False,
            'actualizado_en': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/sync_unidades/<int:slot_id>', methods=['POST'])
@require_permission('ver_mapa')
def smartmap_sync_unidades(slot_id):
    """Sincroniza unidades desde una API externa configurada en variables de entorno.

    Variables esperadas: `UNITS_API_URL` y opcional `UNITS_API_KEY`.
    El endpoint acepta JSON con una lista de unidades cuando se desea subir manualmente.
    """
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        payload = request.get_json(silent=True)
        unidades_origen = None

        # Si se envía payload con unidades, usarlo
        if payload and isinstance(payload, dict) and payload.get('unidades'):
            unidades_origen = payload.get('unidades')

        # llamar al helper interno que hace el trabajo
        result = _sync_unidades_internal(slot_id, unidades_origen)
        return jsonify(result), 200 if result.get('ok') else 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


def _sync_unidades_internal(slot_id, unidades_origen=None):
    """Lógica reutilizable para sincronizar unidades (llamada por endpoint y scheduler)."""
    try:
        unidades_list = []
        if unidades_origen is None:
            api_url = os.environ.get('UNITS_API_URL')
            api_key = os.environ.get('UNITS_API_KEY')
            if not api_url:
                return {'ok': False, 'error': 'UNITS_API_URL no configurada'}

            req = urllib.request.Request(api_url)
            if api_key:
                req.add_header('Authorization', f'Bearer {api_key}')
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                raw = resp.read()
                unidades_origen = json.loads(raw.decode('utf-8'))

        if isinstance(unidades_origen, dict) and unidades_origen.get('data'):
            unidades_list = unidades_origen.get('data')
        elif isinstance(unidades_origen, list):
            unidades_list = unidades_origen
        else:
            unidades_list = []

        guardadas = 0
        cache_actualizada = 0

        for u in unidades_list:
            unidad_id = u.get('unidad_id') or u.get('id') or u.get('device_id') or u.get('placa')
            if not unidad_id:
                continue
            lat = u.get('lat') or u.get('latitude') or u.get('latitud')
            lng = u.get('lng') or u.get('longitude') or u.get('longitud')
            velocidad = u.get('velocidad') or u.get('speed') or u.get('vel') or 0
            bateria = u.get('bateria') or u.get('battery') or u.get('battery_level') or None

            try:
                creado = db.crear_tractor(placa=str(unidad_id), modelo=u.get('modelo') or u.get('model'), ano=u.get('ano') or u.get('year'), slot_id=slot_id)
                if creado:
                    guardadas += 1
            except Exception:
                pass

            try:
                if lat is not None and lng is not None:
                    _actualizar_cache_flotas(
                        slot_id,
                        str(unidad_id),
                        float(lat),
                        float(lng),
                        float(velocidad or 0),
                        'desconocido',
                        float(bateria) if bateria is not None else None,
                        json.dumps(u)
                    )
                    cache_actualizada += 1
            except Exception:
                pass

        # Registrar log sin requerir contexto de request
        try:
            from flask import has_request_context, session as _flask_session
            usuario_log = _flask_session.get('username') if has_request_context() else 'sistema'
        except Exception:
            usuario_log = 'sistema'
        db.registrar_log(usuario_log, 'Sync unidades', f'Slot {slot_id} procesadas={len(unidades_list)}')
        return {'ok': True, 'guardadas_creadas': guardadas, 'cache_actualizada': cache_actualizada, 'procesadas': len(unidades_list)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# Scheduler ligero para sincronización de unidades (opcional, activar con ENABLE_UNITS_SYNC=1)
def _start_units_sync_scheduler():
    if not SMARTMAP_ALERTAS_HABILITADO:
        return
    import threading, time
    def worker():
        interval = int(os.environ.get('UNITS_SYNC_INTERVAL', '60'))
        while True:
            try:
                # sincronizar para todos los slots
                slots = db.obtener_todos_los_slots()
                for s in slots:
                    sid = s[0]
                    try:
                        _sync_unidades_internal(sid)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(interval)

    try:
        if os.environ.get('ENABLE_UNITS_SYNC') == '1':
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
    except Exception:
        pass


@mapa_bp.route('/api/smartmap/notificaciones/telegram/prueba/<int:slot_id>', methods=['POST'])
def telegram_prueba(slot_id):
    """Endpoint de prueba para enviar notificación por Telegram."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        usuario = session.get('username', 'sistema') if session.get('username') else 'sistema'
        mensaje = f"Prueba Telegram - slot {slot_id} - usuario: {usuario} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        resultado = {'ok': True, 'estado': 'en_proceso'}

        def _enviar():
            enviar_telegram(mensaje)

        _disparar_tarea_en_hilo(_enviar)
        return jsonify(resultado), 202
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/notificaciones/prueba_multicanal/<int:slot_id>', methods=['POST'])
def prueba_multicanal(slot_id):
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        payload_alerta = {
            'slot_id': slot_id,
            'tipo': 'prueba_multicanal',
            'titulo': f'Prueba multicanal slot {slot_id}',
            'mensaje': f'Prueba multicanal para slot {slot_id} en {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        }
        usuario_log = session.get('username', 'sistema') if session.get('username') else 'sistema'

        def _enviar():
            resultados = enviar_multicanal(payload_alerta)
            try:
                for canal, res in resultados.items():
                    resultado_json = json.dumps(res)
                    notificacion_id = db.crear_notificacion(slot_id, canal, '', payload_alerta['tipo'], payload_alerta['titulo'], payload_alerta['mensaje'], resultado_json, origen='prueba_multicanal')
                    if notificacion_id:
                        db.actualizar_notificacion_resultado(
                            notificacion_id,
                            resultado_json,
                            nuevo_estado='enviado' if res.get('ok') else 'fallo',
                            incrementar_intentos=not res.get('ok')
                        )
            except Exception:
                pass
            db.registrar_log(usuario_log, 'Prueba multicanal', f'Slot {slot_id}')

        _disparar_tarea_en_hilo(_enviar)
        return jsonify({'ok': True, 'estado': 'en_proceso'}), 202
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# Iniciar scheduler si aplica
_start_units_sync_scheduler()


@mapa_bp.route('/api/smartmap/simular/<int:slot_id>', methods=['POST'])
@require_permission('generar_alertas')
def smartmap_simular_movimiento(slot_id):
    """Simula movimiento de unidades y genera alertas automáticas básicas."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        _seed_reglas_demo(slot_id, session.get('username', 'sistema'))
        # TODO: Cuando la API real de unidades esté lista, este endpoint deberá consumirla
        # para evaluar reglas sobre telemetría real y disparar alertas desde ese flujo.
        alertas_generadas = 0

        db.registrar_log(session.get('username', 'sistema'), 'Simular telemetría SmartMap', f'Slot {slot_id}')

        return jsonify({
            'ok': True,
            'slot_id': slot_id,
            'unidades_actualizadas': 0,
            'alertas_generadas': alertas_generadas,
            'api_unidades_pendiente': True,
            'simulado_en': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/alertas/<int:slot_id>', methods=['GET'])
@require_permission('ver_alertas')
def smartmap_alertas(slot_id):
    """Retorna alertas activas del Smart Map para un lote."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        limite = int(request.args.get('limite', 20))
        alertas = db.obtener_alertas_activas(slot_id=slot_id, limite=limite)
        data = [{
            'id': a[0],
            'slot_id': a[1],
            'tipo': a[2],
            'severidad': a[3],
            'titulo': a[4],
            'mensaje': a[5],
            'estado': a[6],
            'origen': a[7],
            'atendida_por': a[8],
            'creada_en': a[9],
            'atendida_en': a[10],
        } for a in alertas]
        return jsonify({'slot_id': slot_id, 'total': len(data), 'alertas': data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@mapa_bp.route('/api/smartmap/alertas/<int:alerta_id>/atender', methods=['PATCH'])
@require_permission('generar_alertas')
def smartmap_atender_alerta(alerta_id):
    """Marca una alerta como atendida."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        usuario = session.get('username', 'desconocido')
        ok = db.atender_alerta(alerta_id, atendida_por=usuario)
        if not ok:
            return jsonify({'error': 'Alerta no encontrada'}), 404

        db.registrar_log(usuario, 'Atender alerta SmartMap', f'Alerta {alerta_id}')
        return jsonify({'ok': True, 'alerta_id': alerta_id, 'atendida_por': usuario}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/reglas/<int:slot_id>', methods=['GET'])
@require_permission('ver_alertas')
def smartmap_reglas(slot_id):
    """Obtiene reglas configuradas para el lote."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        _seed_reglas_demo(slot_id, session.get('username', 'sistema'))
        reglas = db.obtener_reglas_alerta(slot_id)
        data = [{
            'id': r[0],
            'slot_id': r[1],
            'nombre': r[2],
            'tipo': r[3],
            'umbral': r[4],
            'severidad': r[5],
            'activa': bool(r[6]),
            'creada_por': r[7],
            'creada_en': r[8],
            'actualizada_en': r[9]
        } for r in reglas]
        return jsonify({'slot_id': slot_id, 'total': len(data), 'reglas': data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/reglas/<int:slot_id>', methods=['POST'])
@require_permission('generar_alertas')
def smartmap_crear_regla(slot_id):
    """Crea una nueva regla de alerta para el lote."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        payload = request.get_json(silent=True) or {}
        nombre = (payload.get('nombre') or '').strip()
        tipo = (payload.get('tipo') or '').strip()
        severidad = (payload.get('severidad') or 'media').strip().lower()

        try:
            umbral = float(payload.get('umbral'))
        except Exception:
            return jsonify({'error': 'Umbral inválido'}), 400

        tipos_validos = {'velocidad_mayor', 'bateria_menor'}
        if not nombre:
            return jsonify({'error': 'Nombre requerido'}), 400
        if tipo not in tipos_validos:
            return jsonify({'error': 'Tipo de regla no soportado'}), 400
        if severidad not in {'baja', 'media', 'alta'}:
            severidad = 'media'

        regla_id = db.crear_regla_alerta(
            slot_id=slot_id,
            nombre=nombre,
            tipo=tipo,
            umbral=umbral,
            severidad=severidad,
            creada_por=session.get('username', 'desconocido')
        )

        db.registrar_log(session.get('username', 'desconocido'), 'Crear regla SmartMap', f'Regla {regla_id} en slot {slot_id}')
        return jsonify({'ok': True, 'regla_id': regla_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/reglas/<int:regla_id>/toggle', methods=['PATCH'])
@require_permission('generar_alertas')
def smartmap_toggle_regla(regla_id):
    """Activa o desactiva una regla de alerta."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        payload = request.get_json(silent=True) or {}
        activa = bool(payload.get('activa'))
        ok = db.actualizar_estado_regla_alerta(regla_id, activa)
        if not ok:
            return jsonify({'error': 'Regla no encontrada'}), 404

        db.registrar_log(session.get('username', 'desconocido'), 'Toggle regla SmartMap', f'Regla {regla_id} activa={activa}')
        return jsonify({'ok': True, 'regla_id': regla_id, 'activa': activa}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/tipos-alerta', methods=['GET'])
@require_permission('ver_alertas')
def smartmap_tipos_alerta():
    """Obtiene el catálogo de tipos de alerta."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        tipos = db.obtener_tipos_alerta()
        data = [{
            'id': t[0],
            'nombre': t[1],
            'descripcion': t[2],
            'activa': bool(t[3]),
            'creada_en': t[4],
            'actualizada_en': t[5],
        } for t in tipos]
        return jsonify({'total': len(data), 'tipos': data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/tipos-alerta', methods=['POST'])
@require_permission('generar_alertas')
def smartmap_crear_tipo_alerta():
    """Crea un tipo de alerta. Reservado para administradores."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        if session.get('rol') != 'admin':
            return jsonify({'error': 'Acceso denegado'}), 403

        payload = request.get_json(silent=True) or {}
        nombre = (payload.get('nombre') or '').strip()
        descripcion = (payload.get('descripcion') or '').strip()

        if not nombre:
            return jsonify({'error': 'Nombre requerido'}), 400

        tipo_id = db.crear_tipo_alerta(nombre, descripcion)
        db.registrar_log(session.get('username', 'desconocido'), 'Crear tipo de alerta', f'Tipo {tipo_id}: {nombre}')
        return jsonify({'ok': True, 'tipo_id': tipo_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/tipos-alerta/<int:tipo_alerta_id>', methods=['DELETE'])
@require_permission('generar_alertas')
def smartmap_eliminar_tipo_alerta(tipo_alerta_id):
    """Elimina un tipo de alerta. Reservado para administradores."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        if session.get('rol') != 'admin':
            return jsonify({'error': 'Acceso denegado'}), 403

        ok = db.eliminar_tipo_alerta(tipo_alerta_id)
        if not ok:
            return jsonify({'error': 'Tipo de alerta no encontrado'}), 404

        db.registrar_log(session.get('username', 'desconocido'), 'Eliminar tipo de alerta', f'Tipo {tipo_alerta_id}')
        return jsonify({'ok': True, 'tipo_alerta_id': tipo_alerta_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/smartmap/notificaciones/email/prueba/<int:slot_id>', methods=['POST'])
@require_permission('generar_alertas')
def smartmap_enviar_prueba_email(slot_id):
    """Envía correo de prueba para validar configuración SMTP de alertas."""
    if not SMARTMAP_ALERTAS_HABILITADO:
        return _smartmap_desactivado_response()
    try:
        payload = {
            'slot_id': slot_id,
            'unidad_id': 'PRUEBA',
            'tipo': 'prueba_email',
            'severidad': 'media',
            'titulo': 'Prueba de canal correo - SmartMap',
            'mensaje': 'Este es un correo de prueba de Fase 2 para validar notificaciones externas.'
        }

        if not correo_habilitado():
            return jsonify({
                'ok': False,
                'mensaje': 'Configuración de correo incompleta. Revisar variables SMTP_* y ALERT_EMAIL_TO.'
            }), 400

        usuario_log = session.get('username', 'desconocido')

        def _enviar_prueba():
            envio = enviar_alerta_email(payload)
            if not envio.get('ok'):
                db.registrar_log(usuario_log, 'Prueba correo SmartMap', f"Slot {slot_id} error={envio.get('error', envio.get('motivo'))}")

        _disparar_tarea_en_hilo(_enviar_prueba)

        db.registrar_log(usuario_log, 'Prueba correo SmartMap', f'Slot {slot_id}')
        return jsonify({'ok': True, 'estado': 'en_proceso', 'destinatarios': db.obtener_correos_usuarios()}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= CLIMA API =============
@mapa_bp.route('/api/clima/<float:lat>/<float:lon>', methods=['GET'])
def obtener_clima(lat, lon):
    """
    Obtiene datos de clima para coordenadas específicas.
    Fuente: Open-Meteo API (gratuita, sin autenticación)

    Args:
        lat: Latitud en grados decimales
        lon: Longitud en grados decimales

    Returns:
        JSON con: temperatura, humedad, probabilidad_lluvia, zona_horaria, actualizado_en
    """
    try:
        # Validar rangos de coordenadas
        if lat < -90 or lat > 90 or lon < -180 or lon > 180:
            return jsonify({'error': 'Coordenadas inválidas'}), 400

        datos = servicio_clima.obtener_clima(lat, lon)
        return jsonify(datos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mapa_bp.route('/api/clima_interpretacion/<int:codigo>', methods=['GET'])
def interpretacion_clima(codigo):
    """
    Interpreta un código de clima WMO (World Meteorological Organization).

    Args:
        codigo: Código WMO del clima (0-99)

    Returns:
        JSON con: nombre, descripcion, emoji
    """
    try:
        datos = servicio_clima.interpretacion_clima(codigo)
        return jsonify(datos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
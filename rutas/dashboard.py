import json
import io
from datetime import datetime

from flask import Blueprint, render_template, request, session, redirect, url_for, send_file
from database import db
from services.seguridad import require_permission
from services.reportes import generar_csv_logs
from utils.funciones import convertir_kml_a_geojson, convertir_geojson_a_kml

dashboard_bp = Blueprint('dashboard', __name__)

# === RUTAS ORIGINALES ===

@dashboard_bp.route('/dashboard')
def index():
    if not session.get('logeado'): 
        return redirect(url_for('login.index')) 
    
    slots = db.obtener_todos_los_slots()
    usuarios = db.obtener_todos_los_usuarios() if session.get('rol') == 'admin' else []
    reportes_programados = []
    if session.get('rol') == 'admin':
        for reporte in db.obtener_reportes_programados():
            destinatarios_raw = reporte[3] or ''
            formato_raw = reporte[4] or ''
            try:
                destinatarios = json.loads(destinatarios_raw) if destinatarios_raw else []
            except Exception:
                destinatarios = [x.strip() for x in str(destinatarios_raw).replace(';', ',').split(',') if x.strip()]
            try:
                formatos = json.loads(formato_raw) if formato_raw and str(formato_raw).strip().startswith('[') else []
            except Exception:
                formatos = [x.strip().lower() for x in str(formato_raw).replace(';', ',').split(',') if x.strip()]
            if not isinstance(formatos, list):
                formatos = [str(formatos).strip().lower()] if str(formatos).strip() else []
            formatos = [x for x in formatos if x]
            reportes_programados.append({
                'id': reporte[0],
                'nombre': reporte[1],
                'frecuencia_dias': reporte[2],
                'destinatarios': destinatarios,
                'formato': formatos,
                'formato_texto': ' + '.join(f.upper() for f in formatos) if formatos else 'CSV',
                'activo': bool(reporte[5]),
                'creado_por': reporte[6],
                'creado_en': reporte[7],
                'ultimo_envio': reporte[8],
                'proximo_envio': reporte[9],
            })
    # Passthrough para mostrar resultado de carga KML (diagnóstico rápido)
    kml_saved = request.args.get('kml_saved')
    return render_template('dashboard.html', slots=slots, usuarios=usuarios, reportes_programados=reportes_programados, rol_actual=session.get('rol'), kml_saved=kml_saved)

@dashboard_bp.route('/')
def root_redirect():
    """Redirige la raíz a dashboard o dashboard-main si no está en sesión."""
    if not session.get('logeado'):
        return redirect(url_for('login.index'))
    return redirect(url_for('dashboard.dashboard_main'))

@dashboard_bp.route('/cargar_kml/<int:slot_id>', methods=['POST'])
def cargar(slot_id):
    if not session.get('logeado'): return redirect(url_for('login.index'))
    
    archivo = request.files.get('kml_file')
    if archivo and archivo.filename.endswith('.kml'):
        content = archivo.read()
        try:
            text = content.decode('utf-8', errors='replace')
        except Exception:
            text = str(content)
        # Intentar convertir KML a GeoJSON para ejecutar la asignación automática de padres
        try:
            geo = convertir_kml_a_geojson(text)
        except Exception:
            geo = None

        if geo:
            try:
                # asignar padres en servidor (método importado desde rutas.mapa no disponible aquí),
                # usar la conversión y volver a generar KML para persistir
                from rutas.mapa import _asignar_padres_geojson_inplace
                from rutas.mapa import _asegurar_tareas_padre_geojson_inplace
                from rutas.mapa import _asegurar_tareas_hijo_geojson_inplace
                try:
                    _asignar_padres_geojson_inplace(geo)
                    _asegurar_tareas_padre_geojson_inplace(geo)
                    _asegurar_tareas_hijo_geojson_inplace(geo)
                except Exception:
                    pass
                new_kml = convertir_geojson_a_kml(geo)
                saved = db.guardar_kml_en_slot(slot_id, new_kml)
            except Exception:
                # en caso de fallo al convertir/guardar, guardar el KML original
                saved = db.guardar_kml_en_slot(slot_id, text)
        else:
            saved = db.guardar_kml_en_slot(slot_id, text)
        db.registrar_log(session.get('usuario'), "Carga KML", f"Slot ID: {slot_id}, filename:{archivo.filename}, size:{len(content)}, saved:{bool(saved)}")
        if saved:
            return redirect(url_for('dashboard.index', kml_saved='1'))
        else:
            return redirect(url_for('dashboard.index', kml_saved='0'))

    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/eliminar_kml/<int:slot_id>', methods=['POST'])
def eliminar(slot_id):
    if not session.get('logeado'): return redirect(url_for('login.index'))
    
    password_ingresada = request.form.get('password')
    usuario_actual = session.get('usuario')
    
    if db.verificar_usuario_y_obtener_datos(usuario_actual, password_ingresada)[0]:
        db.vaciar_slot(slot_id)
        db.registrar_log(usuario_actual, "Eliminación KML", f"Slot ID: {slot_id}")
        
    return redirect(url_for('dashboard.index'))

# Envoltorios (Wrappers) para no romper los botones del dashboard.html original
@dashboard_bp.route('/admin/toggle_permiso/<int:user_id>', methods=['POST'])
def admin_toggle_permiso(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_agregar')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_edicion/<int:user_id>', methods=['POST'])
def admin_toggle_edicion(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_editar')
    return redirect(url_for('dashboard.index'))

# === NUEVAS RUTAS PARA FASE 1 ===

@dashboard_bp.route('/dashboard-main')
@require_permission('ver_dashboard')
def dashboard_main():
    """
    Dashboard principal mejorado con KPIs, gráficos y timeline.
    Protegido por: ver_dashboard
    """
    if not session.get('logeado'):
        return redirect(url_for('login.index'))
    
    return render_template('dashboard_main.html', usuario=session.get('username'))


@dashboard_bp.route('/admin/reporte/logins', methods=['POST'])
def reporte_logins_rango():
    if session.get('rol') != 'admin':
        return redirect(url_for('dashboard.index'))

    fecha_inicio_raw = (request.form.get('fecha_inicio') or '').strip()
    fecha_fin_raw = (request.form.get('fecha_fin') or '').strip()

    if not fecha_inicio_raw or not fecha_fin_raw:
        return redirect(url_for('dashboard.index'))

    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio_raw, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin_raw, '%Y-%m-%d')
    except ValueError:
        return redirect(url_for('dashboard.index'))

    if fecha_fin_dt < fecha_inicio_dt:
        fecha_inicio_dt, fecha_fin_dt = fecha_fin_dt, fecha_inicio_dt

    fecha_inicio = fecha_inicio_dt.strftime('%Y-%m-%d 00:00:00')
    fecha_fin = fecha_fin_dt.strftime('%Y-%m-%d 23:59:59')

    logs = db.obtener_logs_entre(fecha_inicio, fecha_fin)
    logs_csv = [(fila[0], fila[1], fila[2], fila[3]) for fila in logs]
    csv_texto = generar_csv_logs(logs_csv)

    buffer = io.BytesIO(csv_texto.encode('utf-8'))
    buffer.seek(0)
    nombre_archivo = f"reporte_logins_{fecha_inicio_dt.strftime('%Y%m%d')}_{fecha_fin_dt.strftime('%Y%m%d')}.csv"

    db.registrar_log(session.get('usuario'), 'Generar reporte logins', f'{fecha_inicio} a {fecha_fin}, registros={len(logs_csv)}')

    return send_file(
        buffer,
        mimetype='text/csv',
        as_attachment=True,
        download_name=nombre_archivo
    )

@dashboard_bp.route('/dashboard/timeline/<int:slot_id>')
@require_permission('ver_actividades')
def timeline_lote(slot_id):
    """
    Vista de timeline para un lote específico.
    Protegido por: ver_actividades
    """
    if not session.get('logeado'):
        return redirect(url_for('login.index'))
    
    slot = None
    for s in db.obtener_todos_los_slots():
        if s[0] == slot_id:
            slot = s
            break
    
    if not slot:
        return render_template('error_404.html'), 404
    
    return render_template('timeline.html', slot=slot)


@dashboard_bp.route('/admin/toggle_agregar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_agregar_tareas(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_agregar_tareas')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_marcar_tareas/<int:user_id>', methods=['POST'])
def admin_toggle_marcar_tareas(user_id):
    if session.get('rol') == 'admin': db.alternar_permiso(user_id, 'puede_marcar_tareas')
    return redirect(url_for('dashboard.index'))

# --- RUTAS DE ADMINISTRADOR RECUPERADAS ---
@dashboard_bp.route('/admin/crear_usuario', methods=['POST'])
def crear_usuario():
    if session.get('rol') == 'admin':
        # Cambiado 'nuevo_username' por 'nuevo_usuario' para coincidir con el HTML
        username = request.form.get('nuevo_usuario') 
        password = request.form.get('nueva_password')
        correo = request.form.get('nuevo_correo', '').strip() or None
        if username and password:
            db.crear_nuevo_usuario(username, password, correo=correo)
            db.registrar_log(session.get('usuario'), "Crear Usuario", f"Usuario: {username}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/eliminar_usuario/<int:user_id>', methods=['POST'])
def admin_eliminar_usuario(user_id):
    if session.get('rol') == 'admin':
        db.eliminar_usuario(user_id)
        db.registrar_log(session.get('usuario'), "Eliminar Usuario", f"ID: {user_id}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/cambiar_password/<int:user_id>', methods=['POST'])
def admin_cambiar_password(user_id):
    if session.get('rol') == 'admin':
        nueva_pass = request.form.get('nueva_password')
        if nueva_pass:
            db.cambiar_password_usuario(user_id, nueva_pass)
            db.registrar_log(session.get('usuario'), "Cambio Password", f"Usuario ID: {user_id}")
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/cambiar_correo/<int:user_id>', methods=['POST'])
def admin_cambiar_correo(user_id):
    if session.get('rol') == 'admin':
        nuevo_correo = request.form.get('nuevo_correo', '').strip()
        if db.actualizar_correo_usuario(user_id, nuevo_correo):
            db.registrar_log(session.get('usuario'), "Cambio Correo", f"Usuario ID: {user_id}, correo: {nuevo_correo or 'Sin correo'}")
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/admin/toggle_grupo/<grupo>/<int:user_id>', methods=['POST'])
def toggle_grupo(grupo, user_id):
    if session.get('rol') == 'admin':
        if grupo == 'lotes':
            db.alternar_permiso(user_id, 'puede_agregar')
            db.alternar_permiso(user_id, 'puede_editar')
        elif grupo == 'tareas':
            db.alternar_permiso(user_id, 'puede_agregar_tareas')
            db.alternar_permiso(user_id, 'puede_marcar_tareas')
        elif grupo == 'costos':
            db.alternar_permiso(user_id, 'puede_ver_costos')
        elif grupo == 'reportes':
            db.alternar_permiso(user_id, 'puede_descargar_mapa')
            db.alternar_permiso(user_id, 'puede_descargar_logs')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/toggle_descargar_mapa/<int:user_id>', methods=['POST'])
def admin_toggle_descargar_mapa(user_id):
    if session.get('rol') == 'admin':
        db.alternar_permiso(user_id, 'puede_descargar_mapa')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/toggle_descargar_logs/<int:user_id>', methods=['POST'])
def admin_toggle_descargar_logs(user_id):
    if session.get('rol') == 'admin':
        db.alternar_permiso(user_id, 'puede_descargar_logs')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/programar_reporte_actividad', methods=['POST'])
def programar_reporte_actividad():
    if session.get('rol') != 'admin':
        return redirect(url_for('dashboard.index'))

    nombre = (request.form.get('nombre') or '').strip()
    try:
        frecuencia_dias = int(request.form.get('frecuencia_dias', '5'))
    except Exception:
        frecuencia_dias = 5
    if frecuencia_dias < 1:
        frecuencia_dias = 5

    formatos = request.form.getlist('formatos')
    if not formatos:
        formato_unico = (request.form.get('formato') or '').strip().lower()
        if formato_unico:
            formatos = [formato_unico]
    formatos_normalizados = []
    for formato in formatos:
        formato = (formato or '').strip().lower()
        if formato in ('csv', 'word') and formato not in formatos_normalizados:
            formatos_normalizados.append(formato)
    if not formatos_normalizados:
        formatos_normalizados = ['csv']

    usuarios_seleccionados = request.form.getlist('destinatarios_usuarios')
    usuarios_por_id = {}
    for usuario in db.obtener_todos_los_usuarios():
        correo = usuario[11] if len(usuario) > 11 else None
        if correo:
            usuarios_por_id[str(usuario[0])] = correo.strip()

    destinatarios = [usuarios_por_id[user_id] for user_id in usuarios_seleccionados if usuarios_por_id.get(str(user_id))]

    destinatarios_txt = (request.form.get('destinatarios') or '').strip()
    destinatarios.extend([x.strip() for x in destinatarios_txt.replace(';', ',').split(',') if x.strip()])
    destinatarios = list(dict.fromkeys(destinatarios))
    if not destinatarios:
        destinatarios = db.obtener_correos_usuarios()

    if not destinatarios:
        fallback = (request.form.get('destinatarios_global') or '').strip()
        if fallback:
            destinatarios = [x.strip() for x in fallback.replace(';', ',').split(',') if x.strip()]

    if not destinatarios:
        destinatarios = []

    if not nombre:
        nombre = f'Reporte de actividad cada {frecuencia_dias} días'

    reporte_id = db.crear_reporte_programado(
        nombre,
        frecuencia_dias,
        json.dumps(destinatarios, ensure_ascii=False),
        formato=json.dumps(formatos_normalizados, ensure_ascii=False),
        creado_por=session.get('usuario')
    )
    if reporte_id:
        db.registrar_log(session.get('usuario'), 'Programar reporte actividad', f'ID: {reporte_id}, frecuencia={frecuencia_dias}, formatos={"+".join(formatos_normalizados)}, destinatarios={len(destinatarios)}')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/toggle_reporte_programado/<int:reporte_id>', methods=['POST'])
def toggle_reporte_programado(reporte_id):
    if session.get('rol') == 'admin':
        reportes = db.obtener_reportes_programados()
        activo_actual = None
        for reporte in reportes:
            if reporte[0] == reporte_id:
                activo_actual = int(reporte[5] or 0)
                break
        if activo_actual is not None:
            db.actualizar_estado_reporte_programado(reporte_id, not bool(activo_actual))
            db.registrar_log(session.get('usuario'), 'Toggle reporte programado', f'ID: {reporte_id}, activo={int(not bool(activo_actual))}')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/admin/eliminar_reporte_programado/<int:reporte_id>', methods=['POST'])
def eliminar_reporte_programado(reporte_id):
    if session.get('rol') == 'admin':
        db.eliminar_reporte_programado(reporte_id)
        db.registrar_log(session.get('usuario'), 'Eliminar reporte programado', f'ID: {reporte_id}')
    return redirect(url_for('dashboard.index'))
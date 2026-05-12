from flask import Blueprint, render_template, session, redirect, url_for, request, make_response, send_file, Response
from database import db
from utils.funciones import convertir_geojson_a_kml, enviar_reporte_por_correo
import io
from datetime import datetime
from services.reportes import generar_csv_logs, generar_csv_mapa, generar_word_mapa
import json

mapa_bp = Blueprint('mapa', __name__)

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
    
    kml_contenido = db.obtener_kml_por_id(slot_id)
    
    db.actualizar_metadatos_slot(slot_id, usuario, datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    rol, db_add, db_edit, db_tar, db_check = db.obtener_permisos_usuario(usuario)

    return render_template('mapa.html', 
                           slot_id=slot_id, 
                           nombre_mapa=nombre_real, 
                           kml_data=kml_contenido,
                           puede_agregar=(rol == 'admin' or bool(db_add)),
                           puede_editar=(rol == 'admin' or bool(db_edit)),
                           puede_agregar_tareas=(rol == 'admin' or bool(db_tar)),
                           puede_marcar_tareas=(rol == 'admin' or bool(db_check)),
                           usuario_actual=usuario,
                           es_admin=(rol == 'admin'),
                           usuarios_lista_json=json.dumps([u[1] for u in db.obtener_todos_los_usuarios()]))

@mapa_bp.route('/api/guardar_kml/<int:slot_id>', methods=['POST'])
def guardar(slot_id):
    if not session.get('logeado'):
        return {"ok": False, "error": "Acceso denegado"}, 401

    usuario = session.get('usuario')
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar = db.obtener_permisos_usuario(usuario)

    puede_guardar = (rol == 'admin') or bool(db_agregar) or bool(db_editar) or bool(db_agregar_tar) or bool(db_marcar_tar)
    
    if not puede_guardar:
        return {"ok": False, "error": "Sin permisos"}, 403

    data = request.get_json(silent=True)
    if data:
        kml_str = convertir_geojson_a_kml(data)
        db.guardar_kml_en_slot(slot_id, kml_str)
        db.registrar_log(usuario, "Modificación de Mapa", f"Slot ID: {slot_id}")
        
    return {"ok": True}

@mapa_bp.route('/admin/reporte/<rango>')
def reporte(rango):
    if session.get('rol') != 'admin': 
        return "Acceso denegado", 403
        
    logs = db.obtener_logs_por_rango(rango)
    csv_str = generar_csv_logs(logs)
    nombre = f"reporte_{rango}.csv"
    
    enviar_reporte_por_correo(rango, csv_str, nombre, abrir_outlook=True)
    
    resp = make_response('\ufeff' + csv_str)
    resp.headers["Content-Disposition"] = f"attachment; filename={nombre}"
    resp.headers["Content-type"] = "text/csv; charset=utf-8"
    return resp

@mapa_bp.route('/exportar_kml', methods=['POST'])
def exportar_kml():
    data = request.json
    kml_str = convertir_geojson_a_kml(data)
    mem_file = io.BytesIO()
    mem_file.write(kml_str.encode('utf-8'))
    mem_file.seek(0)
    return send_file(mem_file, mimetype='application/vnd.google-earth.kml+xml', as_attachment=True, download_name='mapa_modificado.kml')

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
    rol, db_agregar, db_editar, db_agregar_tar, db_marcar_tar = db.obtener_permisos_usuario(usuario)
    
    return {
        "logeado": True,
        "puede_agregar": (rol == 'admin') or bool(db_agregar),
        "puede_editar": (rol == 'admin') or bool(db_editar),
        "puede_agregar_tareas": (rol == 'admin') or bool(db_agregar_tar),
        "puede_marcar_tareas": (rol == 'admin') or bool(db_marcar_tar)
    }

@mapa_bp.route('/api/reporte_mapa/<int:slot_id>', methods=['POST'])
def reporte_mapa(slot_id):
    if not session.get('logeado'):
        return "Acceso denegado", 401

    payload = request.get_json(silent=True) or {}
    data = payload.get('geojson', payload)
    if not data:
        return "Sin datos", 400

    csv_str, nombre_archivo = generar_csv_mapa(data, slot_id)
    enviar_reporte_por_correo(
        f"Avances del Proyecto {slot_id}",
        csv_str,
        nombre_archivo,
        abrir_outlook=bool(payload.get('abrir_outlook')),
    )

    resp = make_response('\ufeff' + csv_str)
    resp.headers["Content-Disposition"] = f"attachment; filename={nombre_archivo}"
    resp.headers["Content-type"] = "text/csv; charset=utf-8"
    return resp

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
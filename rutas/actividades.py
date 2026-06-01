"""
Rutas de Actividades y Dashboard (FASE 1)
Endpoints protegidos por permisos granulares.
"""

from flask import Blueprint, request, jsonify, session
from database import db
from services.seguridad import require_permission, registrar_accion_sensible
from services.actividades import GeneradorCronograma, CalculadorKPIs

actividades_bp = Blueprint('actividades', __name__, url_prefix='/api')

# === HELPERS ===

def obtener_usuario_actual():
    return session.get('username')

def obtener_id_usuario_actual():
    return session.get('user_id')

# === ENDPOINTS DE DASHBOARD ===

@actividades_bp.route('/dashboard/kpis', methods=['GET'])
@require_permission('ver_dashboard')
def obtener_kpis():
    """
    Obtiene KPIs principales del dashboard.
    Protegido por: ver_dashboard
    """
    try:
        kpis = CalculadorKPIs.obtener_kpis_dashboard()
        
        usuario_id = obtener_id_usuario_actual()
        db.registrar_log(obtener_usuario_actual(), "Ver KPIs dashboard")
        
        return jsonify(kpis), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/dashboard/graficos', methods=['GET'])
@require_permission('ver_dashboard')
def obtener_graficos_dashboard():
    """
    Obtiene datos para gráficos del dashboard.
    Retorna: distribucion de cultivos y estado de actividades
    Protegido por: ver_dashboard
    """
    try:
        grafico_cultivos = CalculadorKPIs.obtener_grafico_distribucion_cultivos()
        grafico_actividades = CalculadorKPIs.obtener_grafico_estado_actividades()
        
        return jsonify({
            'distribucion_cultivos': grafico_cultivos,
            'estado_actividades': grafico_actividades
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/dashboard/proximas', methods=['GET'])
@require_permission('ver_actividades')
def obtener_actividades_proximas():
    """
    Obtiene lista de actividades próximas (próximos 7 días).
    Protegido por: ver_actividades
    """
    try:
        dias = request.args.get('dias', 7, type=int)
        actividades = db.obtener_actividades_proximas(dias=dias)
        
        actividades_list = [{
            'id': a[0],
            'slot_id': a[1],
            'nombre': a[2],
            'descripcion': a[3],
            'tipo': a[4],
            'estado': a[5],
            'fecha_programada': a[6],
            'fecha_vencimiento': a[7],
            'responsable': a[8],
            'prioridad': a[11]
        } for a in actividades]
        
        db.registrar_log(obtener_usuario_actual(), f"Ver actividades próximas ({dias} días)")
        
        return jsonify(actividades_list), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/slots-info', methods=['GET'])
def obtener_slots_info():
    """
    Obtiene información de todos los slots con indicador de cronograma.
    Endpoint público (sin protección de permisos) - información general.
    """
    try:
        slots = db.obtener_todos_los_slots()
        
        slots_info = []
        for slot in slots:
            # Verificar si el slot tiene actividades
            actividades = db.obtener_actividades_por_slot(slot[0])
            tiene_actividades = len(actividades) > 0 if actividades else False
            
            slots_info.append({
                'id': slot[0],
                'nombre': slot[1],
                'slug': slot[2],
                'tiene_actividades': tiene_actividades,
                'fecha_creacion': slot[4] if len(slot) > 4 else None,
                'fecha_ultima_vista': slot[5] if len(slot) > 5 else None
            })
        
        return jsonify(slots_info), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@actividades_bp.route('/slots', methods=['GET'])
def obtener_slots_alias():
    """Alias por compatibilidad con versiones anteriores: /api/slots -> /api/slots-info"""
    return obtener_slots_info()

# === ENDPOINTS DE TIMELINE AUTOMÁTICO ===

@actividades_bp.route('/actividades/generar-cronograma/<int:slot_id>', methods=['POST'])
@require_permission('crear_actividades')
def generar_cronograma(slot_id):
    """
    Genera automáticamente el cronograma de actividades para un lote.
    
    Body JSON esperado:
    {
        "tipo_cultivo": "caña_azucar",
        "fecha_siembra": "2026-05-15"  (opcional)
    }
    
    Protegido por: crear_actividades
    """
    try:
        datos = request.get_json()
        tipo_cultivo = datos.get('tipo_cultivo', 'general')
        fecha_siembra = datos.get('fecha_siembra')
        
        # Verificar que el slot exista
        slot = None
        for s in db.obtener_todos_los_slots():
            if s[0] == slot_id:
                slot = s
                break
        
        if not slot:
            return jsonify({'error': 'Lote no encontrado'}), 404
        
        # Generar cronograma
        resultado = GeneradorCronograma.generar_cronograma(
            slot_id, tipo_cultivo, fecha_siembra
        )
        
        if resultado['exitoso']:
            usuario_id = obtener_id_usuario_actual()
            registrar_accion_sensible(
                usuario_id, obtener_usuario_actual(),
                'generar_cronograma',
                f'slot_id:{slot_id}, tipo_cultivo:{tipo_cultivo}',
                resultado='exitoso',
                detalles=f'Actividades creadas: {resultado["actividades_creadas"]}'
            )
            
            db.registrar_log(
                obtener_usuario_actual(),
                "Generar cronograma",
                f"Slot {slot_id}, cultivo: {tipo_cultivo}, actividades: {resultado['actividades_creadas']}"
            )
            
            return jsonify(resultado), 201
        else:
            return jsonify(resultado), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/por-lote/<int:slot_id>', methods=['GET'])
@require_permission('ver_actividades')
def listar_actividades_lote(slot_id):
    """
    Obtiene todas las actividades de un lote (timeline).
    
    Query params:
    - estado: 'pendiente', 'en_progreso', 'completada' (opcional)
    
    Protegido por: ver_actividades
    """
    try:
        filtro_estado = request.args.get('estado')
        actividades = db.obtener_actividades_por_slot(slot_id, filtro_estado=filtro_estado)
        
        actividades_list = [{
            'id': a[0],
            'slot_id': a[1],
            'nombre': a[2],
            'descripcion': a[3],
            'tipo': a[4],
            'estado': a[5],
            'fecha_programada': a[6],
            'fecha_vencimiento': a[7],
            'responsable': a[8],
            'completada_en': a[9],
            'dias_desde_siembra': a[10],
            'prioridad': a[11],
            'creada_en': a[12]
        } for a in actividades]
        
        return jsonify(actividades_list), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/<int:actividad_id>', methods=['GET'])
@require_permission('ver_actividades')
def obtener_actividad(actividad_id):
    """
    Obtiene detalles de una actividad específica.
    Protegido por: ver_actividades
    """
    try:
        actividad = db.obtener_actividad_por_id(actividad_id)
        
        if not actividad:
            return jsonify({'error': 'Actividad no encontrada'}), 404
        
        actividad_dict = {
            'id': actividad[0],
            'slot_id': actividad[1],
            'nombre': actividad[2],
            'descripcion': actividad[3],
            'tipo': actividad[4],
            'estado': actividad[5],
            'fecha_programada': actividad[6],
            'fecha_vencimiento': actividad[7],
            'responsable': actividad[8],
            'completada_en': actividad[9],
            'dias_desde_siembra': actividad[10],
            'prioridad': actividad[11],
            'creada_en': actividad[12]
        }
        
        return jsonify(actividad_dict), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/<int:actividad_id>/cambiar-estado', methods=['PATCH'])
@require_permission('completar_actividades')
def cambiar_estado_actividad(actividad_id):
    """
    Cambia el estado de una actividad.
    
    Body JSON esperado:
    {
        "estado": "completada"  // 'pendiente', 'en_progreso', 'completada', 'cancelada'
    }
    
    Protegido por: completar_actividades
    """
    try:
        datos = request.get_json()
        nuevo_estado = datos.get('estado')
        
        if not nuevo_estado:
            return jsonify({'error': 'Estado requerido'}), 400
        
        # Verificar que la actividad exista
        actividad = db.obtener_actividad_por_id(actividad_id)
        if not actividad:
            return jsonify({'error': 'Actividad no encontrada'}), 404
        
        # Cambiar estado
        success = db.cambiar_estado_actividad(actividad_id, nuevo_estado)
        
        if success:
            usuario_id = obtener_id_usuario_actual()
            registrar_accion_sensible(
                usuario_id, obtener_usuario_actual(),
                'cambiar_estado_actividad',
                f'actividad_id:{actividad_id}, nuevo_estado:{nuevo_estado}',
                resultado='exitoso'
            )
            
            db.registrar_log(
                obtener_usuario_actual(),
                "Cambiar estado actividad",
                f"Actividad {actividad_id} → {nuevo_estado}"
            )
            
            # Obtener actividad actualizada
            actividad_actualizada = db.obtener_actividad_por_id(actividad_id)
            actividad_dict = {
                'id': actividad_actualizada[0],
                'nombre': actividad_actualizada[2],
                'estado': actividad_actualizada[5],
                'completada_en': actividad_actualizada[9],
                'actualizado_en': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return jsonify({'mensaje': 'Estado actualizado', 'actividad': actividad_dict}), 200
        else:
            return jsonify({'error': 'Estado inválido'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/<int:actividad_id>/completar', methods=['POST'])
@require_permission('completar_actividades')
def completar_actividad(actividad_id):
    """
    Marca una actividad como completada.
    Atajo para cambiar_estado_actividad con estado='completada'.
    
    Protegido por: completar_actividades
    """
    try:
        actividad = db.obtener_actividad_por_id(actividad_id)
        
        if not actividad:
            return jsonify({'error': 'Actividad no encontrada'}), 404
        
        db.marcar_actividad_completada(actividad_id)
        
        usuario_id = obtener_id_usuario_actual()
        db.registrar_log(
            obtener_usuario_actual(),
            "Completar actividad",
            f"Actividad {actividad_id} ({actividad[2]})"
        )
        
        return jsonify({
            'mensaje': 'Actividad completada',
            'actividad_id': actividad_id,
            'completada_en': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/<int:actividad_id>', methods=['DELETE'])
@require_permission('crear_actividades')
def eliminar_actividad(actividad_id):
    """
    Elimina una actividad.
    Protegido por: crear_actividades
    """
    try:
        actividad = db.obtener_actividad_por_id(actividad_id)
        
        if not actividad:
            return jsonify({'error': 'Actividad no encontrada'}), 404
        
        db.eliminar_actividad(actividad_id)
        
        usuario_id = obtener_id_usuario_actual()
        db.registrar_log(
            obtener_usuario_actual(),
            "Eliminar actividad",
            f"Actividad {actividad_id}"
        )
        
        return jsonify({'mensaje': 'Actividad eliminada'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === ESTADÍSTICAS Y REPORTES ===

@actividades_bp.route('/actividades/lote/<int:slot_id>/estadisticas', methods=['GET'])
@require_permission('ver_actividades')
def estadisticas_lote(slot_id):
    """
    Obtiene estadísticas de actividades de un lote.
    Protegido por: ver_actividades
    """
    try:
        stats = CalculadorKPIs.obtener_kpis_por_lote(slot_id)
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@actividades_bp.route('/actividades/descargar/<int:slot_id>', methods=['GET'])
@require_permission('ver_actividades')
def descargar_cronograma(slot_id):
    """
    Descarga el cronograma de actividades de un lote como CSV.
    Parámetro query: formato (default: 'csv', opcional: 'json')
    
    Protegido por: ver_actividades
    """
    from datetime import datetime
    from io import StringIO
    from flask import make_response
    
    try:
        formato = request.args.get('formato', 'csv')
        actividades = db.obtener_actividades_por_slot(slot_id)
        
        if not actividades:
            return jsonify({'error': 'No hay actividades para este lote'}), 404
        
        if formato == 'json':
            # Formato JSON
            actividades_list = [{
                'id': a[0],
                'nombre': a[2],
                'tipo': a[4],
                'estado': a[5],
                'fecha_programada': a[6],
                'fecha_vencimiento': a[7],
                'responsable': a[8],
                'prioridad': a[11]
            } for a in actividades]
            
            return jsonify(actividades_list), 200
        
        else:
            # Formato CSV (default)
            output = StringIO()
            output.write('ID,Nombre,Tipo,Estado,Fecha Programada,Fecha Vencimiento,Responsable,Prioridad\n')
            
            for a in actividades:
                output.write(f'{a[0]},"{a[2]}",{a[4]},{a[5]},{a[6]},{a[7]},{a[8]},{a[11]}\n')
            
            output.seek(0)
            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = f'attachment; filename=cronograma_lote_{slot_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            
            db.registrar_log(
                obtener_usuario_actual(),
                "Descargar cronograma",
                f"Lote {slot_id} ({len(actividades)} actividades)"
            )
            
            return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === SINCRONIZAR CON NUEVAS IMPORTACIONES ===
from datetime import datetime

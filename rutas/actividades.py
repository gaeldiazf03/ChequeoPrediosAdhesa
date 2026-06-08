"""
Rutas de Actividades y Dashboard (FASE 1)
Endpoints protegidos por permisos granulares.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, session
from database import db
from services.seguridad import require_permission, registrar_accion_sensible
from services.actividades import GeneradorCronograma, CalculadorKPIs
from utils.funciones import convertir_kml_a_geojson, convertir_geojson_a_kml

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


@actividades_bp.route('/slots-hierarquia', methods=['GET'])
@require_permission('ver_dashboard')
def obtener_slots_hierarquia():
    """Retorna jerarquía real padre/hijos de lotes por slot, extraída del KML almacenado."""
    try:
        resultado = []
        for slot in db.obtener_todos_los_slots():
            slot_id = slot[0]
            nombre_slot = slot[1]
            kml = slot[3] if len(slot) > 3 else None
            geo = convertir_kml_a_geojson(kml) if kml else None

            padres = []
            hijos_por_padre = {}

            if geo and 'features' in geo:
                for feat in geo.get('features', []):
                    props = feat.get('properties') or {}
                    nombre_lote = str(props.get('name') or '').strip()
                    if not nombre_lote:
                        continue
                    parent = str(props.get('parent') or '').strip()
                    if parent:
                        hijos_por_padre.setdefault(parent, []).append(nombre_lote)
                    else:
                        if nombre_lote not in padres:
                            padres.append(nombre_lote)

            padres.sort()
            for p in list(hijos_por_padre.keys()):
                hijos_por_padre[p] = sorted(list(set(hijos_por_padre[p])))

            planes = []
            for plan in db.obtener_planes_por_slot(slot_id):
                meta = {}
                if len(plan) > 9 and plan[9]:
                    try:
                        meta = json.loads(plan[9])
                    except Exception:
                        meta = {}
                planes.append({
                    'id': plan[0],
                    'nombre': plan[2],
                    'fecha_inicio': plan[4],
                    'fecha_fin': plan[5],
                    'estado': plan[6],
                    'lote_padre': meta.get('lote_padre'),
                    'lotes_hijos': meta.get('lotes_hijos', [])
                })

            resultado.append({
                'slot_id': slot_id,
                'slot_nombre': nombre_slot,
                'padres': padres,
                'hijos_por_padre': hijos_por_padre,
                'planes': planes
            })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@actividades_bp.route('/planes/aplicar', methods=['POST'])
@require_permission('crear_actividades')
def crear_y_aplicar_plan():
    """Crea un plan y aplica tareas automáticamente a lote padre e hijos seleccionados."""
    try:
        data = request.get_json() or {}
        slot_id_raw = data.get('slot_id')
        try:
            slot_id = int(slot_id_raw)
        except (TypeError, ValueError):
            return jsonify({'error': 'slot_id inválido'}), 400
        nombre = str(data.get('nombre') or '').strip()
        lote_padre = str(data.get('lote_padre') or '').strip()
        lotes_hijos = data.get('lotes_hijos') or []
        fecha_inicio = str(data.get('fecha_inicio') or '').strip()

        if not nombre or not lote_padre:
            return jsonify({'error': 'nombre y lote_padre son requeridos'}), 400

        if not fecha_inicio:
            fecha_inicio = datetime.now().strftime('%Y-%m-%d')

        try:
            inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'fecha_inicio inválida, use YYYY-MM-DD'}), 400

        lotes_hijos = [str(x).strip() for x in lotes_hijos if str(x).strip()]

        slot = None
        for s in db.obtener_todos_los_slots():
            if s[0] == slot_id:
                slot = s
                break
        if not slot:
            return jsonify({'error': 'slot no encontrado'}), 404

        kml = slot[3]
        if not kml:
            return jsonify({'error': 'El slot no tiene KML cargado'}), 400

        geo = convertir_kml_a_geojson(kml)
        if not geo or 'features' not in geo:
            return jsonify({'error': 'No se pudo leer el KML del slot'}), 400

        objetivos = [lote_padre] + lotes_hijos
        objetivos_set = set(objetivos)

        # Catálogo predefinido: se aplica en orden de ID y agrupado por etapa.
        catalogo = db.obtener_catalogo_actividades(solo_activas=True)
        if not catalogo:
            return jsonify({'error': 'No hay actividades predefinidas en el catálogo'}), 400

        tareas_plan = []
        etapas_resumen = {}
        offset_dias = 0
        etapa_anterior = None
        timestamp_base = int(datetime.now().timestamp())

        for pos, actividad in enumerate(catalogo, start=1):
            proceso = str(actividad[1] or '').strip()
            etapa = str(actividad[2] or '').strip() or 'General'
            descripcion = str(actividad[3] or '').strip()
            como_se_realiza = str(actividad[4] or '').strip()
            programacion = str(actividad[5] or '').strip()

            if not proceso:
                continue

            if etapa_anterior is not None and etapa != etapa_anterior:
                # Separador temporal entre etapas para que en gantt sea más legible.
                offset_dias += 1

            ini = inicio_dt + timedelta(days=offset_dias)
            fin = ini
            tareas_plan.append({
                'id': f"plan-{timestamp_base}-{pos}",
                'texto': proceso,
                'etapa': etapa,
                'descripcion': descripcion,
                'como_se_realiza': como_se_realiza,
                'programacion_recomendada': programacion,
                'estado': 'no_iniciada',
                'completada': False,
                'fecha_inicio': ini.strftime('%Y-%m-%d'),
                'fecha_fin': fin.strftime('%Y-%m-%d')
            })
            etapas_resumen[etapa] = etapas_resumen.get(etapa, 0) + 1
            etapa_anterior = etapa
            offset_dias += 1

        if not tareas_plan:
            return jsonify({'error': 'El catálogo no contiene procesos válidos'}), 400

        aplicados = []
        for feat in geo.get('features', []):
            props = feat.get('properties') or {}
            nombre_lote = str(props.get('name') or '').strip()
            if nombre_lote in objetivos_set:
                props['tareas'] = [dict(t) for t in tareas_plan]
                feat['properties'] = props
                aplicados.append(nombre_lote)

        if not aplicados:
            return jsonify({'error': 'No se encontraron lotes objetivo en el KML'}), 400

        meta = {
            'lote_padre': lote_padre,
            'lotes_hijos': lotes_hijos,
            'tareas_generadas': len(tareas_plan),
            'etapas': etapas_resumen,
            'lotes_aplicados': aplicados,
            'fecha_inicio': fecha_inicio
        }

        plan_id = db.crear_plan(
            slot_id=slot_id,
            nombre=nombre,
            descripcion=f'Plan aplicado a {lote_padre} y {len(lotes_hijos)} lotes hijos',
            fecha_inicio=fecha_inicio,
            fecha_fin=tareas_plan[-1]['fecha_fin'] if tareas_plan else fecha_inicio,
            metadata_json=json.dumps(meta, ensure_ascii=False)
        )

        if not plan_id:
            return jsonify({'error': 'No se pudo crear el plan en base de datos'}), 500

        nuevo_kml = convertir_geojson_a_kml(geo)
        if not db.guardar_kml_en_slot(slot_id, nuevo_kml):
            return jsonify({'error': 'No se pudo guardar el KML actualizado'}), 500

        db.registrar_log(obtener_usuario_actual(), 'Crear y aplicar plan', f'slot={slot_id}, plan={plan_id}, lotes={",".join(aplicados)}')

        return jsonify({
            'ok': True,
            'plan_id': plan_id,
            'slot_id': slot_id,
            'lotes_aplicados': aplicados,
            'tareas_generadas': len(tareas_plan)
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@actividades_bp.route('/slots', methods=['GET'])
def obtener_slots_alias():
    """Alias por compatibilidad con versiones anteriores: /api/slots -> /api/slots-info"""
    return obtener_slots_info()


@actividades_bp.route('/catalogo/etapas-resumen', methods=['GET'])
@require_permission('crear_actividades')
def catalogo_etapas_resumen():
    """Retorna resumen de actividades activas agrupadas por etapa."""
    try:
        actividades = db.obtener_catalogo_actividades(solo_activas=True)
        etapas = {}
        orden = []

        for actividad in actividades:
            etapa = str(actividad[2] or '').strip() or 'Sin etapa'
            if etapa not in etapas:
                etapas[etapa] = 0
                orden.append(etapa)
            etapas[etapa] += 1

        data = [{
            'etapa': etapa,
            'cantidad': etapas[etapa]
        } for etapa in orden]

        return jsonify({
            'total_actividades': len(actividades),
            'etapas': data
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

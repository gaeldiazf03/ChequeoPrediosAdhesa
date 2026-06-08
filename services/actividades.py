"""
Servicio de actividades: Generación automática de cronogramas según ciclos agrícolas.
"""

import math
from database import db
from datetime import datetime, timedelta
from utils.funciones import convertir_kml_a_geojson

class GeneradorCronograma:
    """Genera automáticamente cronogramas de actividades según tipo de cultivo."""
    
    # Ciclos agrícolas por cultivo (duración en días)
    CICLOS_CULTIVO = {
        'caña_azucar': 730,  # 2 años
        'caña_soca': 365,    # 1 año
        'maiz': 120,         # 4 meses
        'frijol': 90,        # 3 meses
        'sorgo': 150,        # 5 meses
        'general': 365       # 1 año genérico
    }
    
    # Actividades por ciclo (días desde siembra + duración)
    ACTIVIDADES_CAÑA = [
        {'dias': 0, 'nombre': 'Siembra', 'tipo': 'siembra', 'duracion': 3},
        {'dias': 5, 'nombre': 'Riego inicial (Riego 1)', 'tipo': 'riego', 'duracion': 2},
        {'dias': 7, 'nombre': 'Herbicida preemergente', 'tipo': 'herbicida', 'duracion': 1},
        {'dias': 20, 'nombre': 'Fertilización 1', 'tipo': 'fertilizacion', 'duracion': 2},
        {'dias': 30, 'nombre': 'Herbicida postemergente', 'tipo': 'herbicida', 'duracion': 1},
        {'dias': 45, 'nombre': 'Primera evaluación', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 60, 'nombre': 'Riego 2', 'tipo': 'riego', 'duracion': 2},
        {'dias': 80, 'nombre': 'Fertilización 2', 'tipo': 'fertilizacion', 'duracion': 2},
        {'dias': 120, 'nombre': 'Segunda evaluación', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 150, 'nombre': 'Riego 3', 'tipo': 'riego', 'duracion': 2},
        {'dias': 180, 'nombre': 'Fertilización 3', 'tipo': 'fertilizacion', 'duracion': 2},
        {'dias': 240, 'nombre': 'Tercera evaluación', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 300, 'nombre': 'Riego 4', 'tipo': 'riego', 'duracion': 2},
        {'dias': 330, 'nombre': 'Control de plagas', 'tipo': 'sanidad', 'duracion': 1},
        {'dias': 360, 'nombre': 'Fertilización final', 'tipo': 'fertilizacion', 'duracion': 2},
        {'dias': 480, 'nombre': 'Evaluación previa a cosecha', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 540, 'nombre': 'Cosecha', 'tipo': 'cosecha', 'duracion': 5},
        {'dias': 600, 'nombre': 'Post-cosecha (preparación socas)', 'tipo': 'post_cosecha', 'duracion': 3},
    ]
    
    ACTIVIDADES_MAIZ = [
        {'dias': 0, 'nombre': 'Siembra de maíz', 'tipo': 'siembra', 'duracion': 2},
        {'dias': 3, 'nombre': 'Riego de establecimiento', 'tipo': 'riego', 'duracion': 1},
        {'dias': 7, 'nombre': 'Herbicida preemergente', 'tipo': 'herbicida', 'duracion': 1},
        {'dias': 15, 'nombre': 'Fertilización 1', 'tipo': 'fertilizacion', 'duracion': 1},
        {'dias': 25, 'nombre': 'Aporque/Control de maleza', 'tipo': 'maleza', 'duracion': 2},
        {'dias': 35, 'nombre': 'Fertilización 2', 'tipo': 'fertilizacion', 'duracion': 1},
        {'dias': 45, 'nombre': 'Evaluación de desarrollo', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 60, 'nombre': 'Riego en floración', 'tipo': 'riego', 'duracion': 2},
        {'dias': 70, 'nombre': 'Control de plagas y enfermedades', 'tipo': 'sanidad', 'duracion': 1},
        {'dias': 100, 'nombre': 'Cosecha', 'tipo': 'cosecha', 'duracion': 3},
    ]
    
    ACTIVIDADES_FRIJOL = [
        {'dias': 0, 'nombre': 'Siembra de frijol', 'tipo': 'siembra', 'duracion': 1},
        {'dias': 2, 'nombre': 'Riego inicial', 'tipo': 'riego', 'duracion': 1},
        {'dias': 5, 'nombre': 'Herbicida selectivo', 'tipo': 'herbicida', 'duracion': 1},
        {'dias': 15, 'nombre': 'Fertilización', 'tipo': 'fertilizacion', 'duracion': 1},
        {'dias': 25, 'nombre': 'Riego en V4-V6', 'tipo': 'riego', 'duracion': 1},
        {'dias': 35, 'nombre': 'Control de plagas', 'tipo': 'sanidad', 'duracion': 1},
        {'dias': 50, 'nombre': 'Riego en floración', 'tipo': 'riego', 'duracion': 2},
        {'dias': 65, 'nombre': 'Evaluación de vainas', 'tipo': 'evaluacion', 'duracion': 1},
        {'dias': 80, 'nombre': 'Cosecha', 'tipo': 'cosecha', 'duracion': 2},
    ]
    
    @staticmethod
    def obtener_actividades_para_cultivo(tipo_cultivo):
        """Retorna el listado de actividades para un tipo de cultivo."""
        tipo_cultivo_normalizado = tipo_cultivo.lower().replace(' ', '_').replace('-', '_')
        
        if 'caña' in tipo_cultivo_normalizado:
            return GeneradorCronograma.ACTIVIDADES_CAÑA
        elif 'maiz' in tipo_cultivo_normalizado or 'maíz' in tipo_cultivo_normalizado:
            return GeneradorCronograma.ACTIVIDADES_MAIZ
        elif 'frijol' in tipo_cultivo_normalizado or 'bean' in tipo_cultivo_normalizado:
            return GeneradorCronograma.ACTIVIDADES_FRIJOL
        else:
            # Por defecto, usar actividades genéricas simplificadas
            return [
                {'dias': 0, 'nombre': 'Preparación del terreno', 'tipo': 'preparacion', 'duracion': 2},
                {'dias': 3, 'nombre': 'Siembra', 'tipo': 'siembra', 'duracion': 2},
                {'dias': 10, 'nombre': 'Primer riego', 'tipo': 'riego', 'duracion': 1},
                {'dias': 20, 'nombre': 'Primera fertilización', 'tipo': 'fertilizacion', 'duracion': 1},
                {'dias': 50, 'nombre': 'Evaluación', 'tipo': 'evaluacion', 'duracion': 1},
                {'dias': 100, 'nombre': 'Cosecha', 'tipo': 'cosecha', 'duracion': 3},
            ]
    
    @staticmethod
    def generar_cronograma(slot_id, tipo_cultivo, fecha_siembra_str=None):
        """
        Genera automáticamente el cronograma completo para un lote.
        
        Args:
            slot_id: ID del lote
            tipo_cultivo: Tipo de cultivo (ej: 'caña_azucar', 'maiz')
            fecha_siembra_str: Fecha de siembra (ej: '2026-05-15'). Si no se da, usa hoy.
        
        Returns:
            Diccionario con resultado: {'exitoso': True, 'actividades_creadas': 18, 'detalles': [...]}
        """
        try:
            # Determinar fecha de siembra
            if fecha_siembra_str:
                fecha_siembra = datetime.strptime(fecha_siembra_str, "%Y-%m-%d")
            else:
                fecha_siembra = datetime.now()
            
            # Obtener actividades para el cultivo
            actividades = GeneradorCronograma.obtener_actividades_para_cultivo(tipo_cultivo)
            
            actividades_creadas = []
            
            for actividad in actividades:
                # Calcular fecha de programación
                dias_offset = actividad['dias']
                fecha_programada = fecha_siembra + timedelta(days=dias_offset)
                fecha_vencimiento = fecha_programada + timedelta(days=actividad['duracion'])
                
                # Determinar prioridad según tipo
                prioridad_map = {
                    'siembra': 'crítica',
                    'riego': 'alta',
                    'fertilizacion': 'alta',
                    'herbicida': 'media',
                    'evaluacion': 'media',
                    'cosecha': 'crítica',
                    'sanidad': 'alta'
                }
                prioridad = prioridad_map.get(actividad['tipo'], 'normal')
                
                # Crear actividad en BD
                actividad_id = db.crear_actividad(
                    slot_id=slot_id,
                    nombre=actividad['nombre'],
                    descripcion=f"Actividad de {actividad['tipo']} para {tipo_cultivo}",
                    tipo_actividad=actividad['tipo'],
                    fecha_programada=fecha_programada.strftime("%Y-%m-%d"),
                    dias_desde_siembra=dias_offset,
                    prioridad=prioridad,
                    responsable=""
                )
                
                if actividad_id:
                    actividades_creadas.append({
                        'id': actividad_id,
                        'nombre': actividad['nombre'],
                        'tipo': actividad['tipo'],
                        'fecha': fecha_programada.strftime("%Y-%m-%d"),
                        'dias': dias_offset
                    })
            
            return {
                'exitoso': True,
                'actividades_creadas': len(actividades_creadas),
                'actividades': actividades_creadas,
                'fecha_siembra': fecha_siembra.strftime("%Y-%m-%d"),
                'tipo_cultivo': tipo_cultivo
            }
        
        except Exception as e:
            return {
                'exitoso': False,
                'error': str(e),
                'actividades_creadas': 0
            }

class CalculadorKPIs:
    """Calcula KPIs del dashboard."""

    @staticmethod
    def _es_productiva(props):
        valor = (props or {}).get('productiva', True)
        if isinstance(valor, bool):
            return valor
        texto = str(valor).strip().lower()
        return texto not in ('false', '0', 'no', 'n', 'improductiva')

    @staticmethod
    def _ring_area_m2(ring):
        if not ring or len(ring) < 3:
            return 0.0

        # Proyección equirectangular local para estimar área en m2
        lat0 = sum(float(pt[1]) for pt in ring) / len(ring)
        cos_lat0 = math.cos(math.radians(lat0))
        radius = 6378137.0

        projected = []
        for pt in ring:
            lon = float(pt[0])
            lat = float(pt[1])
            x = radius * math.radians(lon) * cos_lat0
            y = radius * math.radians(lat)
            projected.append((x, y))

        if projected[0] != projected[-1]:
            projected.append(projected[0])

        area2 = 0.0
        for i in range(len(projected) - 1):
            x1, y1 = projected[i]
            x2, y2 = projected[i + 1]
            area2 += (x1 * y2) - (x2 * y1)

        return abs(area2) / 2.0

    @staticmethod
    def _geometry_area_hectareas(geometry):
        if not geometry:
            return 0.0

        gtype = geometry.get('type')
        coords = geometry.get('coordinates') or []

        if gtype == 'Polygon':
            if not coords:
                return 0.0
            exterior = CalculadorKPIs._ring_area_m2(coords[0])
            holes = sum(CalculadorKPIs._ring_area_m2(ring) for ring in coords[1:])
            return max(exterior - holes, 0.0) / 10000.0

        if gtype == 'MultiPolygon':
            total_m2 = 0.0
            for poly in coords:
                if not poly:
                    continue
                exterior = CalculadorKPIs._ring_area_m2(poly[0])
                holes = sum(CalculadorKPIs._ring_area_m2(ring) for ring in poly[1:])
                total_m2 += max(exterior - holes, 0.0)
            return total_m2 / 10000.0

        return 0.0

    @staticmethod
    def _superficie_desde_kml(kml_texto):
        if not kml_texto:
            return 0.0, 0.0

        geojson = convertir_kml_a_geojson(kml_texto)
        if not geojson:
            return 0.0, 0.0

        total = 0.0
        productiva = 0.0

        for feature in geojson.get('features', []):
            geometry = feature.get('geometry') or {}
            hectareas = CalculadorKPIs._geometry_area_hectareas(geometry)
            if hectareas <= 0:
                continue
            total += hectareas
            if CalculadorKPIs._es_productiva(feature.get('properties') or {}):
                productiva += hectareas

        return total, productiva
    
    @staticmethod
    def obtener_kpis_dashboard():
        """Calcula todos los KPIs principales del dashboard."""
        try:
            # Obtener todos los slots
            slots = db.obtener_todos_los_slots()
            
            total_slots = len(slots)
            superficie_total = 0.0
            superficie_en_operacion = 0.0
            lotes_activos = 0
            lotes_cosechados = 0
            
            for slot in slots:
                if slot[3]:  # Si tiene kml_data
                    lotes_activos += 1
                    total_lote, productiva_lote = CalculadorKPIs._superficie_desde_kml(slot[3])
                    superficie_total += total_lote
                    superficie_en_operacion += productiva_lote

            superficie_improductiva = max(superficie_total - superficie_en_operacion, 0.0)
            
            # Estadísticas de actividades
            stats_actividades = db.obtener_todas_las_actividades_para_kpis()
            
            # Obtener actividades próximas
            actividades_proximas = db.obtener_actividades_proximas(dias=7)
            
            return {
                'slots': {
                    'total': total_slots,
                    'activos': lotes_activos,
                    'cosechados': lotes_cosechados,
                    'vacios': total_slots - lotes_activos
                },
                'superficie': {
                    'total_hectareas': round(superficie_total, 2),
                    'en_operacion': round(superficie_en_operacion, 2),
                    'en_preparacion': round(superficie_improductiva, 2)
                },
                'actividades': {
                    'total': stats_actividades['total'],
                    'pendientes': stats_actividades['pendientes'],
                    'en_progreso': stats_actividades['en_progreso'],
                    'completadas': stats_actividades['completadas']
                },
                'proximas_actividades': len(actividades_proximas),
                'fecha_calculo': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        except Exception as e:
            print(f"Error calculando KPIs: {e}")
            return {
                'error': str(e),
                'slots': {'total': 0},
                'superficie': {'total_hectareas': 0},
                'actividades': {'total': 0}
            }
    
    @staticmethod
    def obtener_kpis_por_lote(slot_id):
        """Calcula KPIs específicos de un lote."""
        try:
            slot = db.obtener_slot_por_slug(f"lote-{slot_id}") or db.obtener_todos_los_slots()[0]
            stats = db.obtener_estadisticas_actividades(slot_id)
            
            return {
                'slot_id': slot_id,
                'nombre_lote': slot[1] if slot else f"Lote {slot_id}",
                'actividades': stats,
                'tasa_completitud': round((stats['completadas'] / stats['total'] * 100) if stats['total'] > 0 else 0, 2)
            }
        
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def obtener_grafico_distribucion_cultivos():
        """Retorna data real para gráfico de distribución de cultivos desde KML en BD."""
        buckets = {}

        for slot in db.obtener_todos_los_slots():
            kml_data = slot[3] if len(slot) > 3 else None
            if not kml_data:
                continue

            geojson = convertir_kml_a_geojson(kml_data)
            if not geojson:
                continue

            for feature in geojson.get('features', []):
                geometry = feature.get('geometry') or {}
                hectareas = CalculadorKPIs._geometry_area_hectareas(geometry)
                if hectareas <= 0:
                    continue

                props = feature.get('properties') or {}
                cultivo = (
                    props.get('cultivo')
                    or props.get('tipo_cultivo')
                    or props.get('crop')
                    or 'Sin cultivo'
                )
                cultivo = str(cultivo).strip() or 'Sin cultivo'
                buckets[cultivo] = buckets.get(cultivo, 0.0) + hectareas

        if not buckets:
            return {
                'labels': ['Sin datos'],
                'data': [1],
                'colors': ['#94a3b8']
            }

        items = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)
        labels = [k for k, _ in items]
        data = [round(v, 2) for _, v in items]
        palette = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#64748b']
        colors = [palette[i % len(palette)] for i in range(len(labels))]

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }
    
    @staticmethod
    def obtener_grafico_estado_actividades():
        """Retorna data para gráfico de estado de actividades."""
        stats = db.obtener_todas_las_actividades_para_kpis()
        
        return {
            'labels': ['Pendiente', 'En Progreso', 'Completada'],
            'data': [stats['pendientes'], stats['en_progreso'], stats['completadas']],
            'colors': ['#f59e0b', '#3b82f6', '#10b981']
        }

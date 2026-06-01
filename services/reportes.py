import csv
import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _estado_tarea(tarea):
	estado = str(tarea.get('estado', '') or '').strip().lower()
	if estado in ('verde', 'amarillo', 'rojo'):
		return estado
	if estado in ('completada', 'completado'):
		return 'verde'
	if estado in ('en_progreso', 'en progreso', 'proceso'):
		return 'amarillo'
	if tarea.get('completada'):
		return 'verde'
	return 'rojo'


def generar_csv_logs(logs):
	si = io.StringIO()
	cw = csv.writer(si)
	cw.writerow(['Usuario', 'Acción', 'Detalles', 'Fecha'])
	cw.writerows(logs)
	return si.getvalue()


def generar_csv_mapa(data, slot_id):
	si = io.StringIO()
	cw = csv.writer(si)
	cw.writerow(['Nombre del Lote', 'Responsable', 'Tarea', 'Estado'])

	if 'features' in data:
		for f in data['features']:
			props = f.get('properties', {})
			nombre = props.get('name', 'Sin nombre')
			resp = props.get('responsable', 'Sin asignar')
			tareas = props.get('tareas', [])

			if not tareas:
				cw.writerow([nombre, resp, 'Sin tareas', '-'])
			else:
				for t in tareas:
					estado_norm = _estado_tarea(t)
					estado = 'Completada' if estado_norm == 'verde' else ('En proceso' if estado_norm == 'amarillo' else 'Pendiente')
					texto = t.get('texto', '')
					cw.writerow([nombre, resp, texto, estado])

	csv_str = si.getvalue()
	nombre_archivo = f"Avances_Proyecto_{slot_id}_{datetime.now().strftime('%Y%m%d')}.csv"
	return csv_str, nombre_archivo


def generar_word_mapa(data, slot_id):
	doc = Document()
	titulo = doc.add_heading('Reporte de Avances de Predios - Adhesa', 0)
	titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER

	doc.add_heading('1. Resumen Ejecutivo', level=1)
	total_tareas = 0
	completadas = 0
	costo_total = 0

	for f in data.get('features', []):
		props = f.get('properties', {})
		tareas = props.get('tareas', [])
		total_tareas += len(tareas)
		completadas += sum(1 for t in tareas if _estado_tarea(t) == 'verde')
		costo_total += float(props.get('costo', 0))

	porcentaje = (completadas / total_tareas * 100) if total_tareas > 0 else 0
	doc.add_paragraph(f"Fecha de Reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
	doc.add_paragraph(f"Porcentaje de Avance Global: {porcentaje:.2f}%")
	doc.add_paragraph(f"Inversión Total Acumulada: ${costo_total:,.2f}")

	doc.add_heading('2. Tablas de Avance por Lote', level=1)
	table = doc.add_table(rows=1, cols=4)
	table.style = 'Table Grid'
	hdr_cells = table.rows[0].cells
	hdr_cells[0].text, hdr_cells[1].text, hdr_cells[2].text, hdr_cells[3].text = 'Lote', 'Responsable', 'Estatus', 'Costo'

	for f in data.get('features', []):
		props = f.get('properties', {})
		row_cells = table.add_row().cells
		row_cells[0].text = props.get('name', 'S/N')
		row_cells[1].text = props.get('responsable', 'Sin asignar')
		row_cells[2].text = f"{len(props.get('tareas', []))} tareas asignadas"
		row_cells[3].text = f"${float(props.get('costo', 0)):,.2f}"

	target = io.BytesIO()
	doc.save(target)
	target.seek(0)
	return target, f"Reporte_Avances_Slot_{slot_id}.docx"

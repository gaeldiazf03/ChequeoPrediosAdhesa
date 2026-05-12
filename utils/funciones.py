import simplekml
import json
import os
import subprocess
import tempfile

def convertir_geojson_a_kml(data):
    kml = simplekml.Kml()
    if data and 'features' in data:
        for feature in data['features']:
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coords = feature['geometry']['coordinates']
                geo_type = feature['geometry']['type']
                if geo_type == 'Polygon':
                    kml_coords = [(pt[0], pt[1]) for pt in coords[0]]
                    if len(kml_coords) > 0 and kml_coords[0] != kml_coords[-1]:
                        kml_coords.append(kml_coords[0])
                    props = feature.get('properties', {})
                    nombre_lote = props.get('name', 'Nuevo Lote')
                    pol = kml.newpolygon(name=nombre_lote)
                    pol.outerboundaryis = kml_coords
                    pol.description = json.dumps(props)
    return kml.kml()


def _escapar_powershell(valor):
    return str(valor).replace("'", "''")

def enviar_reporte_por_correo(rango, csv_string, nombre_archivo, abrir_outlook=False):
    destinatario = os.getenv('MAIL_RECIPIENT') or os.getenv('MAIL_DESTINO') or os.getenv('EMAIL_DESTINO')

    if not destinatario:
        return False

    try:
        if abrir_outlook:
            archivo_temp = tempfile.NamedTemporaryFile(delete=False, suffix='_' + nombre_archivo)
            try:
                archivo_temp.write(('\ufeff' + csv_string).encode('utf-8'))
                archivo_temp.close()

                asunto = f"Reporte Adhesa - {str(rango).capitalize()}"
                cuerpo = f"Se adjunta el reporte de actividad: {rango}."
                script = f"""
$ErrorActionPreference = 'Stop'
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)
$mail.To = '{_escapar_powershell(destinatario)}'
$mail.Subject = '{_escapar_powershell(asunto)}'
$mail.Body = '{_escapar_powershell(cuerpo)}'
$mail.Attachments.Add('{_escapar_powershell(archivo_temp.name)}')
$mail.Display()
"""
                subprocess.run(
                    ['powershell', '-NoProfile', '-STA', '-Command', script],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            finally:
                try:
                    archivo_temp.close()
                except Exception:
                    pass
                try:
                    os.unlink(archivo_temp.name)
                except Exception:
                    pass
        return True
    except Exception as e:
        print(f"Error correo: {e}")
        return False
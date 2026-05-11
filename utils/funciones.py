import simplekml
import json
import os
import smtplib
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

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

def enviar_reporte_por_correo(rango, csv_string, nombre_archivo, root_path):
    ruta_config = os.path.join(root_path, 'config', 'mail.json')
    if not os.path.exists(ruta_config): return False
    
    with open(ruta_config) as f:
        conf = json.load(f)
    
    msg = MIMEMultipart()
    msg['From'] = conf['email_remitente']
    msg['To'] = conf['email_destino']
    msg['Subject'] = f"Reporte Adhesa - {rango.capitalize()}"
    
    body = f"Se adjunta el reporte de actividad: {rango}."
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    part = MIMEBase('application', 'octet-stream')
    csv_bytes = ('\ufeff' + csv_string).encode('utf-8') # UTF-8 con BOM
    part.set_payload(csv_bytes)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename={nombre_archivo}")
    msg.attach(part)
    
    try:
        server = smtplib.SMTP(conf['smtp_server'], conf['smtp_port'])
        server.starttls()
        server.login(conf['email_remitente'], conf['password'])
        server.sendmail(conf['email_remitente'], conf['email_destino'], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error correo: {e}")
        return False
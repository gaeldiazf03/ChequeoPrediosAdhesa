import simplekml
import json
import xml.etree.ElementTree as ET

def convertir_geojson_a_kml(data):
    """
    Convierte datos GeoJSON a formato KML (Keyhole Markup Language).
    
    Args:
        data: Diccionario GeoJSON con estructura {features: [...]}
        
    Returns:
        str: Contenido KML en formato string
    """
    kml = simplekml.Kml()
    if data and 'features' in data:
        for feature in data['features']:
            try:
                if 'geometry' not in feature or 'coordinates' not in feature['geometry']:
                    continue

                coords = feature['geometry']['coordinates']
                geo_type = feature['geometry']['type']

                def _first_two(pt):
                    # Acepta [lon, lat] o [lon, lat, alt] y devuelve (lon, lat)
                    return (float(pt[0]), float(pt[1]))

                if geo_type == 'Polygon':
                    ring = coords[0] if isinstance(coords[0], list) else coords
                    kml_coords = [_first_two(pt) for pt in ring]
                    if len(kml_coords) > 0 and kml_coords[0] != kml_coords[-1]:
                        kml_coords.append(kml_coords[0])
                    props = feature.get('properties', {})
                    nombre_lote = props.get('name', 'Nuevo Lote')
                    pol = kml.newpolygon(name=nombre_lote)
                    pol.outerboundaryis = kml_coords
                    pol.description = json.dumps(props)

                elif geo_type == 'MultiPolygon':
                    # Crear una carpeta para agrupar polígonos
                    carpeta = kml.newfolder(name=feature.get('properties', {}).get('name', 'MultiPolygon'))
                    for poly in coords:
                        ring = poly[0] if isinstance(poly[0], list) else poly
                        k_coords = [_first_two(pt) for pt in ring]
                        if len(k_coords) > 0 and k_coords[0] != k_coords[-1]:
                            k_coords.append(k_coords[0])
                        pol = carpeta.newpolygon(name=feature.get('properties', {}).get('name', 'Polígono'))
                        pol.outerboundaryis = k_coords
                        pol.description = json.dumps(feature.get('properties', {}))

                elif geo_type == 'Point':
                    pt = coords
                    p = kml.newpoint(name=feature.get('properties', {}).get('name', 'Punto'))
                    p.coords = [(_first_two(pt))]
                    p.description = json.dumps(feature.get('properties', {}))

            except Exception:
                # Si alguna geometría falla, la saltamos para no romper toda la conversión
                continue

    return kml.kml()


def convertir_kml_a_geojson(kml_text):
    """
    Convierte un KML simple a GeoJSON minimalista.
    No soporta todos los casos KML complejos, pero maneja Placemark con Polygon, MultiGeometry y Point.
    Devuelve un objeto GeoJSON {'type':'FeatureCollection','features':[...]} o None si no pudo parsear.
    """
    try:
        root = ET.fromstring(kml_text)
    except Exception:
        return None

    def tag_local(t):
        return t.split('}')[-1] if '}' in t else t

    features = []

    for placemark in root.iter():
        if tag_local(placemark.tag) != 'Placemark':
            continue

        name = None
        desc = None
        geom_type = None
        coords_texts = []

        for child in placemark:
            t = tag_local(child.tag)
            if t == 'name':
                name = child.text
            if t == 'description':
                desc = child.text

            # Buscar geometrías interiores
            for g in child.iter():
                gt = tag_local(g.tag)
                if gt == 'Point':
                    geom_type = 'Point'
                if gt == 'Polygon':
                    geom_type = 'Polygon'
                if gt == 'coordinates':
                    if g.text and g.text.strip():
                        coords_texts.append(g.text.strip())

        if not geom_type or not coords_texts:
            # intentar buscar coordenadas directas en el placemark
            for g in placemark.iter():
                if tag_local(g.tag) == 'coordinates' and g.text and g.text.strip():
                    coords_texts.append(g.text.strip())

        if not coords_texts:
            continue

        props = {}
        if name:
            props['name'] = name
        if desc:
            # intentar parsear description como JSON si aplica
            try:
                props.update(json.loads(desc))
            except Exception:
                props['description'] = desc

        # Construir geometría según tipo
        if geom_type == 'Point':
            # tomar la primera coordenada
            parts = coords_texts[0].split()
            if len(parts) >= 1:
                lonlat = parts[0].split(',')
                coords = [float(lonlat[0]), float(lonlat[1])]
                feat = {'type': 'Feature', 'properties': props, 'geometry': {'type': 'Point', 'coordinates': coords}}
                features.append(feat)

        elif geom_type == 'Polygon':
            # tomar la primera block como anillo exterior
            ring_txt = coords_texts[0]
            pts = []
            for part in ring_txt.strip().split():
                comps = part.split(',')
                if len(comps) >= 2:
                    try:
                        lon = float(comps[0]); lat = float(comps[1])
                        pts.append([lon, lat])
                    except Exception:
                        continue
            if len(pts) >= 3:
                feat = {'type':'Feature','properties':props,'geometry':{'type':'Polygon','coordinates':[pts]}}
                features.append(feat)

        else:
            # MultiPolygon o varias geometrías: intentar generar múltiples features
            for block in coords_texts:
                pts = []
                for part in block.strip().split():
                    comps = part.split(',')
                    if len(comps) >= 2:
                        try:
                            lon = float(comps[0]); lat = float(comps[1])
                            pts.append([lon, lat])
                        except Exception:
                            continue
                if len(pts) >= 1:
                    geom = {'type': 'Polygon' if len(pts) >= 3 else 'Point', 'coordinates': [pts] if len(pts) >= 3 else pts[0]}
                    features.append({'type':'Feature','properties':props.copy(),'geometry':geom})

    if not features:
        return None

    return {'type':'FeatureCollection','features':features}
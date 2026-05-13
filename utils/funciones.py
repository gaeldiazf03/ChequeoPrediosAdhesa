import simplekml
import json

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
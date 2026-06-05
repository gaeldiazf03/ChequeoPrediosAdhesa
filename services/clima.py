"""
Servicio de Clima - Integración con Open-Meteo API
Cachea datos de clima por coordenadas para evitar múltiples requests
"""

import urllib.request
import urllib.error
import urllib.parse
import json
from datetime import datetime, timedelta
import logging
import ssl

logger = logging.getLogger(__name__)

# Cache en memoria: {(lat, lon): {'data': {...}, 'timestamp': ...}}
_cache_clima = {}
CACHE_DURACION = 5 * 60  # 5 minutos en segundos

class ServicioClima:
    """
    Cliente para Open-Meteo API (gratuita, sin autenticación)
    Obtiene datos de temperatura y probabilidad de precipitación
    """
    
    URL_BASE = "https://api.open-meteo.com/v1/forecast"
    
    @staticmethod
    def obtener_clima(latitud: float, longitud: float, forzar_actualizar: bool = False) -> dict:
        """
        Obtiene datos de clima para una ubicación específica
        
        Args:
            latitud: Latitud en grados decimales
            longitud: Longitud en grados decimales
            forzar_actualizar: Si True, ignora caché y obtiene datos frescos
            
        Returns:
            Dict con: temperatura, humedad, probabilidad_lluvia, zona_horaria, actualizado_en
        """
        clave = (round(latitud, 4), round(longitud, 4))
        ahora = datetime.now()
        
        # Verificar caché
        if not forzar_actualizar and clave in _cache_clima:
            entrada = _cache_clima[clave]
            edad = (ahora - entrada['timestamp']).total_seconds()
            if edad < CACHE_DURACION:
                logger.debug(f"Clima desde caché para {clave} (edad: {edad}s)")
                return entrada['data']
        
        try:
            # Construir URL con parámetros para Open-Meteo
            params = {
                'latitude': str(latitud),
                'longitude': str(longitud),
                'current': 'temperature_2m,precipitation_probability,relative_humidity_2m,weather_code',
                'temperature_unit': 'celsius',
                'timezone': 'auto'
            }
            
            url_params = urllib.parse.urlencode(params)
            url = f"{ServicioClima.URL_BASE}?{url_params}"
            
            # Crear contexto SSL sin verificación estricta (para sistemas sin certs)
            contexto_ssl = ssl.create_default_context()
            contexto_ssl.check_hostname = False
            contexto_ssl.verify_mode = ssl.CERT_NONE
            
            # Hacer request
            request = urllib.request.Request(url, headers={'User-Agent': 'Python-Adhesa/1.0'})
            with urllib.request.urlopen(request, context=contexto_ssl, timeout=10) as respuesta:
                datos_bytes = respuesta.read()
                datos = json.loads(datos_bytes.decode('utf-8'))
            
            # Extraer datos relevantes
            clima_actual = datos.get('current', {})
            resultado = {
                'temperatura': clima_actual.get('temperature_2m'),
                'humedad': clima_actual.get('relative_humidity_2m'),
                'probabilidad_lluvia': clima_actual.get('precipitation_probability'),
                'codigo_clima': clima_actual.get('weather_code'),
                'zona_horaria': datos.get('timezone', 'UTC'),
                'actualizado_en': ahora.isoformat(),
                'latitud': latitud,
                'longitud': longitud
            }
            
            # Guardar en caché
            _cache_clima[clave] = {
                'data': resultado,
                'timestamp': ahora
            }
            
            logger.info(f"Clima obtenido para {clave}: {resultado['temperatura']}°C")
            return resultado
            
        except urllib.error.URLError as e:
            logger.error(f"Error de conexión al obtener clima para {clave}: {e}")
            return {
                'error': f"Error de conexión: {e}",
                'temperatura': None,
                'humedad': None,
                'probabilidad_lluvia': None,
                'actualizado_en': ahora.isoformat()
            }
        except Exception as e:
            logger.error(f"Error obteniendo clima para {clave}: {e}")
            return {
                'error': str(e),
                'temperatura': None,
                'humedad': None,
                'probabilidad_lluvia': None,
                'actualizado_en': ahora.isoformat()
            }
    
    @staticmethod
    def limpiar_cache_antiguo():
        """Elimina entradas de caché que tengan más de CACHE_DURACION segundos"""
        ahora = datetime.now()
        a_eliminar = []
        
        for clave, entrada in _cache_clima.items():
            edad = (ahora - entrada['timestamp']).total_seconds()
            if edad > CACHE_DURACION:
                a_eliminar.append(clave)
        
        for clave in a_eliminar:
            del _cache_clima[clave]
            
        if a_eliminar:
            logger.debug(f"Limpiados {len(a_eliminar)} entradas de caché de clima")
    
    @staticmethod
    def interpretacion_clima(codigo_clima: int) -> dict:
        """
        Interpreta el código de clima de WMO (World Meteorological Organization)
        
        Args:
            codigo_clima: Código WMO (0-99)
            
        Returns:
            Dict con: nombre, descripcion, emoji
        """
        interpretaciones = {
            0: {'nombre': 'Despejado', 'descripcion': 'Cielo despejado', 'emoji': '☀️'},
            1: {'nombre': 'Principalmente Despejado', 'descripcion': 'Principalmente despejado', 'emoji': '🌤️'},
            2: {'nombre': 'Parcialmente Nublado', 'descripcion': 'Parcialmente nublado', 'emoji': '⛅'},
            3: {'nombre': 'Nublado', 'descripcion': 'Nublado', 'emoji': '☁️'},
            45: {'nombre': 'Niebla', 'descripcion': 'Niebla o depósito de hielo', 'emoji': '🌫️'},
            48: {'nombre': 'Niebla', 'descripcion': 'Niebla con depósito de hielo', 'emoji': '🌫️'},
            51: {'nombre': 'Llovizna Ligera', 'descripcion': 'Llovizna ligera', 'emoji': '🌦️'},
            53: {'nombre': 'Llovizna Moderada', 'descripcion': 'Llovizna moderada', 'emoji': '🌦️'},
            55: {'nombre': 'Llovizna Densa', 'descripcion': 'Llovizna densa', 'emoji': '🌦️'},
            61: {'nombre': 'Lluvia Ligera', 'descripcion': 'Lluvia ligera', 'emoji': '🌧️'},
            63: {'nombre': 'Lluvia Moderada', 'descripcion': 'Lluvia moderada', 'emoji': '🌧️'},
            65: {'nombre': 'Lluvia Intensa', 'descripcion': 'Lluvia intensa', 'emoji': '⛈️'},
            71: {'nombre': 'Nieve Ligera', 'descripcion': 'Nieve ligera', 'emoji': '🌨️'},
            73: {'nombre': 'Nieve Moderada', 'descripcion': 'Nieve moderada', 'emoji': '🌨️'},
            75: {'nombre': 'Nieve Intensa', 'descripcion': 'Nieve intensa', 'emoji': '🌨️'},
            77: {'nombre': 'Nieve', 'descripcion': 'Gránulos de nieve', 'emoji': '🌨️'},
            80: {'nombre': 'Lluvia Ligera', 'descripcion': 'Chaparrón ligero', 'emoji': '🌧️'},
            81: {'nombre': 'Lluvia Moderada', 'descripcion': 'Chaparrón moderado', 'emoji': '⛈️'},
            82: {'nombre': 'Lluvia Intensa', 'descripcion': 'Chaparrón intenso', 'emoji': '⛈️'},
            85: {'nombre': 'Nieve Ligera', 'descripcion': 'Chaparrón de nieve ligero', 'emoji': '🌨️'},
            86: {'nombre': 'Nieve Intensa', 'descripcion': 'Chaparrón de nieve intenso', 'emoji': '🌨️'},
            95: {'nombre': 'Tormenta', 'descripcion': 'Tormenta', 'emoji': '⛈️'},
            96: {'nombre': 'Tormenta con Granizo', 'descripcion': 'Tormenta con granizo ligero', 'emoji': '⛈️'},
            99: {'nombre': 'Tormenta con Granizo', 'descripcion': 'Tormenta con granizo', 'emoji': '⛈️'},
        }
        return interpretaciones.get(codigo_clima, {
            'nombre': 'Desconocido',
            'descripcion': 'Código de clima desconocido',
            'emoji': '❓'
        })


# Instancia global
servicio_clima = ServicioClima()

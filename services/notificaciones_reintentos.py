import os
import threading
import time
from datetime import datetime

from database import db
from services.multicanal import enviar_canal


_scheduler_started = False
_scheduler_lock = threading.Lock()


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def _debe_reintentar(row, base_delay_seconds, max_intentos):
    _, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en = row
    if estado != 'fallo' or intentos >= max_intentos:
        return False
    referencia = _parse_fecha(ultimo_intento_en) or _parse_fecha(creada_en)
    if not referencia:
        return False
    delay = base_delay_seconds * (2 ** max(0, intentos - 1)) if intentos > 0 else base_delay_seconds
    return (datetime.now() - referencia).total_seconds() >= delay


def _procesar_reintentos():
    base_delay_seconds = int(os.environ.get('NOTIFICATION_RETRY_BASE_SECONDS', '300'))
    max_intentos = int(os.environ.get('NOTIFICATION_MAX_RETRIES', '3'))
    filas = db.obtener_notificaciones_para_reintento(max_intentos=max_intentos, limite=100)

    for row in filas:
        if not _debe_reintentar(row, base_delay_seconds, max_intentos):
            continue

        notificacion_id, slot_id, canal, destino, tipo, titulo, mensaje, resultado_json, creada_en, origen, estado, intentos, ultimo_intento_en = row
        resultado = enviar_canal(canal, mensaje, destino=destino)
        resultado_json_n = str(resultado)
        nuevo_estado = 'enviado' if resultado.get('ok') else 'fallo'
        db.actualizar_notificacion_resultado(
            notificacion_id,
            resultado_json_n,
            nuevo_estado=nuevo_estado,
            incrementar_intentos=True,
            actualizar_ultimo_intento=True,
        )


def _loop_scheduler():
    intervalo = int(os.environ.get('NOTIFICATION_RETRY_INTERVAL_SECONDS', '300'))
    while True:
        try:
            _procesar_reintentos()
        except Exception:
            pass
        time.sleep(intervalo)


def iniciar_scheduler_reintentos():
    global _scheduler_started
    if os.environ.get('ENABLE_NOTIFICATION_RETRY_SCHEDULER', '1') == '0':
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        hilo = threading.Thread(target=_loop_scheduler, daemon=True, name='notification-retry-scheduler')
        hilo.start()
        _scheduler_started = True
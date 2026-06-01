import os
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import time


def enviar_telegram(mensaje, chat_id=None):
    """Envía un mensaje por Telegram usando BOT token y CHAT_ID en env.

    Retorna dict {'ok': True, 'result': ...} o {'ok': False, 'error': '...'}
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    default_chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or (not default_chat and not chat_id):
        return {'ok': False, 'error': 'TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados'}

    chat = chat_id or default_chat
    api_url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat,
        'text': mensaje,
        'parse_mode': 'Markdown'
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(api_url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return {'ok': True, 'result': json.loads(raw.decode('utf-8'))}
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8')
            return {'ok': False, 'error': f'HTTPError {he.code}', 'body': body}
        except Exception:
            return {'ok': False, 'error': f'HTTPError {he.code}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def enviar_whatsapp_twilio(message, to_phone=None):
    """Envía un mensaje por WhatsApp usando Twilio REST API.

    Requiere en vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (ej. whatsapp:+14155238886)
    to_phone debe ser número en formato E.164 (ej. +54911xxxx).
    """
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_whatsapp = os.environ.get('TWILIO_WHATSAPP_FROM')
    to = to_phone or os.environ.get('TWILIO_WHATSAPP_TO')

    if not account_sid or not auth_token or not from_whatsapp or not to:
        return {'ok': False, 'error': 'Credenciales Twilio o número destino no configurados'}

    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    body = {
        'From': from_whatsapp,
        'To': f'whatsapp:{to}',
        'Body': message
    }
    data = urllib.parse.urlencode(body).encode('utf-8')

    # Basic Auth header
    auth = f"{account_sid}:{auth_token}"
    auth_b64 = base64.b64encode(auth.encode('utf-8')).decode('ascii')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return {'ok': True, 'result': json.loads(raw.decode('utf-8'))}
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8')
            return {'ok': False, 'error': f'HTTPError {he.code}', 'body': body}
        except Exception:
            return {'ok': False, 'error': f'HTTPError {he.code}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def enviar_multicanal(payload):
    """Envía una notificación por los canales disponibles.

    payload: dict con al menos keys: 'slot_id', 'tipo', 'titulo', 'mensaje', 'destino' (opcional)
    Retorna dict con resultados por canal.
    """
    resultados = {}
    mensaje = payload.get('mensaje') or payload.get('titulo') or ''
    retries = int(payload.get('retries', 1))
    delay = float(payload.get('retry_delay', 1))

    # Telegram (intentar retries)
    for attempt in range(1, retries + 1):
        try:
            res_tg = enviar_telegram(mensaje)
            resultados['telegram'] = res_tg
            if res_tg.get('ok'):
                break
        except Exception as e:
            resultados['telegram'] = {'ok': False, 'error': str(e)}
        if attempt < retries:
            time.sleep(delay * attempt)

    # WhatsApp via Twilio (intentar retries)
    for attempt in range(1, retries + 1):
        try:
            res_wa = enviar_whatsapp_twilio(mensaje, to_phone=payload.get('telefono'))
            resultados['whatsapp'] = res_wa
            if res_wa.get('ok'):
                break
        except Exception as e:
            resultados['whatsapp'] = {'ok': False, 'error': str(e)}
        if attempt < retries:
            time.sleep(delay * attempt)

    return resultados


def enviar_canal(canal, mensaje, destino=None):
    canal_normalizado = (canal or '').strip().lower()
    if canal_normalizado == 'telegram':
        return enviar_telegram(mensaje, chat_id=destino)
    if canal_normalizado == 'whatsapp':
        return enviar_whatsapp_twilio(mensaje, to_phone=destino)
    if canal_normalizado == 'multicanal':
        return enviar_multicanal({'mensaje': mensaje, 'telefono': destino})
    return {'ok': False, 'error': f'Canal no soportado: {canal}'}


# Ejemplo (comentado) de cómo se podría implementar Twilio WhatsApp usando la librería oficial:
# from twilio.rest import Client
# def enviar_whatsapp_twilio(message, to_phone=None):
#     account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
#     auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
#     from_whatsapp = os.environ.get('TWILIO_WHATSAPP_FROM')  # e.g. 'whatsapp:+14155238886'
#     to_whatsapp = f'whatsapp:{to_phone or os.environ.get("TWILIO_WHATSAPP_TO")}'
#     if not account_sid or not auth_token or not from_whatsapp or not to_whatsapp:
#         return {'ok': False, 'error': 'Credenciales Twilio no configuradas'}
#     client = Client(account_sid, auth_token)
#     try:
#         message_obj = client.messages.create(body=message, from_=from_whatsapp, to=to_whatsapp)
#         return {'ok': True, 'sid': message_obj.sid}
#     except Exception as e:
#         return {'ok': False, 'error': str(e)}

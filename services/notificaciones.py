import os
import smtplib
from email.message import EmailMessage
from datetime import datetime


def _limpiar_texto(valor):
    if valor is None:
        return ""
    texto = str(valor).strip()
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in {'"', "'"}:
        texto = texto[1:-1].strip()
    return texto


def _parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _split_destinatarios(valor):
    texto = _limpiar_texto(valor)
    if not texto:
        return []
    texto = texto.replace(";", ",")
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def _obtener_config_smtp():
    return {
        "host": _limpiar_texto(os.environ.get("SMTP_HOST", "")),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": _limpiar_texto(os.environ.get("SMTP_USER", "")),
        "password": _limpiar_texto(os.environ.get("SMTP_PASSWORD", "")),
        "use_tls": _parse_bool(os.environ.get("SMTP_USE_TLS", "true"), True),
        "from_email": _limpiar_texto(os.environ.get("SMTP_FROM", "")),
        "to_emails": _split_destinatarios(os.environ.get("ALERT_EMAIL_TO", "")),
        "app_name": os.environ.get("APP_NAME", "ADHESA Smart Map"),
    }


def correo_habilitado():
    cfg = _obtener_config_smtp()
    obligatorios = [cfg["host"], cfg["from_email"], cfg["to_emails"], cfg["user"], cfg["password"]]
    return bool(all(obligatorios))


def correo_habilitado_para(destinatarios=None):
    cfg = _obtener_config_smtp()
    destinatarios = destinatarios if destinatarios is not None else cfg["to_emails"]
    return bool(cfg["host"] and cfg["from_email"] and cfg["user"] and cfg["password"] and destinatarios)


def enviar_alerta_email(alerta):
    """Envía una alerta por correo. Si falta configuración, no falla la operación principal."""
    cfg = _obtener_config_smtp()

    if not correo_habilitado():
        return {
            "ok": False,
            "motivo": "configuracion_incompleta",
            "error": "Falta SMTP_USER o SMTP_PASSWORD. En Outlook/Microsoft 365 necesitas credenciales SMTP válidas y, si aplica, SMTP AUTH habilitado en el buzón.",
        }

    asunto = f"[{cfg['app_name']}] Alerta {alerta.get('severidad', 'media').upper()} - Slot {alerta.get('slot_id', '-') }"
    cuerpo = (
        "Se detectó una alerta en el sistema.\n\n"
        f"Titulo: {alerta.get('titulo', 'Sin titulo')}\n"
        f"Mensaje: {alerta.get('mensaje', 'Sin mensaje')}\n"
        f"Tipo: {alerta.get('tipo', 'general')}\n"
        f"Severidad: {alerta.get('severidad', 'media')}\n"
        f"Slot: {alerta.get('slot_id', '-')}\n"
        f"Unidad: {alerta.get('unidad_id', '-') }\n"
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = cfg["from_email"]
    msg["To"] = ", ".join(cfg["to_emails"])
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
            if cfg["use_tls"]:
                smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)

        return {
            "ok": True,
            "destinatarios": cfg["to_emails"],
        }
    except Exception as e:
        return {
            "ok": False,
            "motivo": "smtp_error",
            "error": str(e),
        }


def enviar_correo_con_adjunto(asunto, cuerpo, destinatarios, adjunto_bytes, nombre_adjunto, mimetype='application/octet-stream'):
    if adjunto_bytes is None:
        adjuntos = []
    else:
        adjuntos = [(adjunto_bytes, nombre_adjunto, mimetype)]
    return enviar_correo_con_adjuntos(asunto, cuerpo, destinatarios, adjuntos)


def enviar_correo_con_adjuntos(asunto, cuerpo, destinatarios, adjuntos):
    cfg = _obtener_config_smtp()
    destinatarios = [d.strip() for d in (destinatarios or []) if d and d.strip()]

    if not correo_habilitado_para(destinatarios):
        return {
            'ok': False,
            'motivo': 'configuracion_incompleta',
            'error': 'Falta configuración SMTP o no hay destinatarios de correo válidos.'
        }

    msg = EmailMessage()
    msg['Subject'] = asunto
    msg['From'] = cfg['from_email']
    msg['To'] = ', '.join(destinatarios)
    msg.set_content(cuerpo)

    for adjunto in adjuntos or []:
        try:
            adjunto_bytes, nombre_adjunto, mimetype = adjunto
            if adjunto_bytes is None:
                continue
            if isinstance(adjunto_bytes, str):
                adjunto_bytes = adjunto_bytes.encode('utf-8')
            if '/' in mimetype:
                maintype, subtype = mimetype.split('/', 1)
            else:
                maintype, subtype = 'application', 'octet-stream'
            msg.add_attachment(adjunto_bytes, maintype=maintype, subtype=subtype, filename=nombre_adjunto)
        except Exception as e:
            return {'ok': False, 'motivo': 'adjunto_invalido', 'error': str(e)}

    try:
        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=20) as smtp:
            if cfg['use_tls']:
                smtp.starttls()
            smtp.login(cfg['user'], cfg['password'])
            smtp.send_message(msg)

        return {'ok': True, 'destinatarios': destinatarios}
    except Exception as e:
        return {'ok': False, 'motivo': 'smtp_error', 'error': str(e)}

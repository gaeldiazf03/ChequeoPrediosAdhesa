# Deploy a Produccion en IONOS (SFTP)

Este proyecto ya incluye archivos para hosting compartido:
- `passenger_wsgi.py`
- `wsgi.py`
- `.htaccess.example`
- `.env.production.example`

## 1) Preparar entorno local antes de subir

1. Crear archivo `.env` para produccion basado en `.env.production.example`.
2. Definir `SECRET_KEY` real y credenciales SMTP reales.
3. Verificar que `FLASK_DEBUG=0`.
4. Verificar que `RUN_SCHEDULERS=1` solo si quieres tareas en segundo plano en el hosting.

## 2) Archivos que SI debes subir por SFTP

Sube el proyecto con esta estructura minima:
- `app.py`
- `database.py`
- `requirements.txt`
- `rutas/`
- `services/`
- `templates/`
- `static/`
- `utils/`
- `wsgi.py`
- `passenger_wsgi.py`
- `.htaccess` (copiado desde `.htaccess.example` y ya ajustado)
- `.env` (produccion)

No subas:
- `.git/`
- `.venv/`
- `__pycache__/`
- archivos `.db` locales de pruebas (si quieres iniciar limpio)

## 3) Configurar Passenger (IONOS)

1. Copia `.htaccess.example` a `.htaccess`.
2. Edita rutas reales:
   - `PassengerAppRoot`
   - `PassengerPython`
3. Asegura que `PassengerStartupFile` apunte a `passenger_wsgi.py`.

Ejemplo de referencia:

```apache
PassengerEnabled on
PassengerAppType wsgi
PassengerAppRoot /homepages/xx/dxxxxxxxxx/htdocs/ChequeoPrediosAdhesa
PassengerPython /homepages/xx/dxxxxxxxxx/htdocs/ChequeoPrediosAdhesa/.venv/bin/python
PassengerStartupFile passenger_wsgi.py
```

## 4) Instalar dependencias en el servidor (recomendado por SSH)

Si tienes acceso SSH:

```bash
cd /homepages/xx/dxxxxxxxxx/htdocs/ChequeoPrediosAdhesa
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Si no tienes SSH, deja el codigo subido y solicita en IONOS que el entorno Python del dominio use `requirements.txt` y el startup file `passenger_wsgi.py`.

## 5) Variables de entorno criticas

En `.env` de produccion deja como minimo:

```env
SECRET_KEY=CAMBIAR_POR_VALOR_SEGURO
FLASK_DEBUG=0
SQLITE_DB_PATH=adhesa.db
RUN_SCHEDULERS=1
```

Si no quieres hilos de scheduler en hosting compartido:

```env
RUN_SCHEDULERS=0
```

## 6) Verificacion rapida post-despliegue

1. Abrir URL principal y validar login.
2. Validar pagina no encontrada (`/ruta-que-no-existe`) y revisar 404.
3. Validar flujo principal de mapa/dashboard.
4. Revisar logs de error en panel IONOS si la app no levanta.

## 7) Rollback rapido

1. Mantener una copia de la version anterior en una carpeta `releases/`.
2. Si falla, restaurar carpeta anterior por SFTP.
3. Reiniciar app desde panel IONOS.

## Nota de seguridad

Se detecto archivo `.env` local con credenciales reales. Antes de subir a produccion, rota esas credenciales SMTP y usa nuevas claves en el `.env` del servidor.

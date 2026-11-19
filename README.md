# Chequeo de Predios ADHESA

Aplicación web para visualizar predios agrícolas, planificar labores y dar seguimiento a su ejecución. Desde el panel se puede abrir el mapa de un proyecto, cargar un archivo KML con los límites de los predios y consultar el avance de las actividades.

- **Mapa:** visualización y edición de geometrías, guardado y exportación de KML. Smart Map añade telemetría de unidades, reglas de alerta y consulta del clima.
- **Planificación:** catálogo de actividades, aplicación de planes a lotes, cronogramas y seguimiento por estado.
- **Administración:** gestión de usuarios y permisos, vinculación de tractores y unidades, y seguimiento de notificaciones.
- **Reportes:** exportaciones en CSV, Excel o Word según la vista y envíos programados por correo.

El servidor usa **Flask y SQLite**. Las pantallas se renderizan con **Jinja** y usan JavaScript y CSS directamente, sin un paso de compilación con Node.js. El mapa y los gráficos cargan bibliotecas desde CDN, por lo que algunas pantallas necesitan acceso a Internet incluso en desarrollo local.

## Inicio rápido

Desde la raíz del repositorio, en Linux o macOS:

```bash
python3.9 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

La versión objetivo del despliegue actual es Python 3.9; [`.python-version`](.python-version) fija la versión 3.9.18. Arranca el servidor con una base de desarrollo separada y las tareas automáticas desactivadas:

```bash
export SQLITE_DB_PATH=instance/desarrollo.db
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export RUN_SCHEDULERS=0
export ENABLE_UNITS_SYNC=0
export ENABLE_SMARTMAP_ALERTS=0
python -m flask --app app run --debug
```

Abre <http://127.0.0.1:5000/>. Al iniciar con una base vacía, la aplicación crea las tablas, tres proyectos iniciales y el usuario `admin`. Para el primer acceso local, consulta la sección «Usuario Admin por defecto» de [`database.py`](database.py) y cambia esa contraseña desde el panel. No expongas el servidor de desarrollo ni uses la contraseña inicial en producción.

### Configuración que conviene conocer

| Variable | Qué controla |
| --- | --- |
| `SQLITE_DB_PATH` | Ruta del archivo SQLite. También se admite `DB_PATH`; si no se define ninguna, se usa `adhesa.db` junto a `database.py`. |
| `SECRET_KEY` | Clave de firma de las sesiones de Flask. Usa una clave propia y estable en producción; si cambia, las sesiones existentes dejan de ser válidas. |
| `RUN_SCHEDULERS` | Con `0` no se arrancan los procesos en segundo plano de reintentos de notificaciones y reportes programados. |
| `ENABLE_UNITS_SYNC`, `UNITS_API_URL`, `UNITS_API_KEY` | Activación y configuración de la sincronización de unidades con el proveedor externo. |
| `ENABLE_SMARTMAP_ALERTS` | Habilita la generación de alertas de Smart Map con `1`. |
| `SMTP_*`, `ALERT_EMAIL_TO` | Configuración del correo y destinatarios de respaldo. |

Exporta `SQLITE_DB_PATH` y los indicadores de Smart Map **antes de iniciar el proceso**: algunos módulos leen estas variables al importarse, antes de que `create_app()` cargue el `.env`. Mantén las claves y los datos reales fuera de Git; para desarrollo usa datos de prueba y no apuntes las integraciones a destinatarios reales.

## Dónde empezar a editar

[`app.py`](app.py) crea la aplicación y registra los *blueprints* de Flask. Para seguir un cambio de pantalla, busca primero la ruta en [`rutas/`](rutas/), identifica qué plantilla devuelve con `render_template()` y revisa qué JavaScript carga esa plantilla. Si un botón hace una petición HTTP, sigue la URL y el método hasta su endpoint Flask.

| Si necesitas cambiar… | Empieza por… |
| --- | --- |
| Inicio de sesión (`/`) | [`rutas/login.py`](rutas/login.py) y [`templates/login.html`](templates/login.html). |
| Panel y línea de tiempo (`/dashboard`, `/dashboard/timeline/<slot_id>`) | [`rutas/dashboard.py`](rutas/dashboard.py), [`templates/dashboard.html`](templates/dashboard.html), [`static/js/dashboard.js`](static/js/dashboard.js) y [`templates/timeline.html`](templates/timeline.html). |
| Mapa de un proyecto (`/adhesa/<slug>`) | [`rutas/mapa.py`](rutas/mapa.py), [`templates/mapa.html`](templates/mapa.html) y [`static/js/mapa.js`](static/js/mapa.js). El autoguardado y la vigilancia están en [`mapa_autoguardado.js`](static/js/mapa_autoguardado.js) y [`mapa_vigilancia.js`](static/js/mapa_vigilancia.js). Las conversiones KML ↔ GeoJSON están en [`utils/funciones.py`](utils/funciones.py). |
| Planes y cronogramas | [`rutas/actividades.py`](rutas/actividades.py) para la API bajo `/api`, [`services/actividades.py`](services/actividades.py) para la lógica y [`calendario_gantt.js`](static/js/calendario_gantt.js) para el calendario en el mapa. |
| Pantallas de administración (`/admin/...`) | [`rutas/admin.py`](rutas/admin.py) y [`templates/admin/`](templates/admin/). Las acciones de usuarios que se disparan desde el panel también tienen rutas en [`rutas/dashboard.py`](rutas/dashboard.py). |
| Reportes y notificaciones | [`services/reportes.py`](services/reportes.py) genera los archivos; [`services/reportes_programados.py`](services/reportes_programados.py) gestiona los envíos programados y [`services/notificaciones.py`](services/notificaciones.py) configura el correo. |
| Estilos | [`static/css/`](static/css/). Revisa qué hojas carga la plantilla antes de modificar [`common.css`](static/css/common.css), porque varias pantallas lo comparten. |

### Antes de modificar rutas o datos

- **Persistencia:** [`database.py`](database.py) concentra las consultas y ajusta el esquema al arrancar en `DatabaseManager.init_db()`. Si cambias una tabla, prueba tanto con una base vacía como con una copia de una base existente. En el código, `slot_id` identifica el registro del proyecto asociado al KML y a las actividades; el `slug` se usa para abrir el mapa desde la URL.
- **Permisos:** conviven los indicadores históricos de sesión (por ejemplo, `puede_editar`) y los permisos por rol. Revisa [`services/seguridad.py`](services/seguridad.py) y [`services/roles.py`](services/roles.py), y aplica el control de acceso en el servidor, no solo ocultando botones.
- **Comprobación manual:** en la misma terminal donde exportaste las variables puedes ejecutar `python -m flask --app app routes` para listar rutas y métodos. Prueba el flujo editado desde la interfaz con datos de desarrollo. Si tocaste permisos, comprueba el resultado tanto con una cuenta autorizada como con una sin acceso.

## Despliegue

Para publicar en IONOS con Passenger, consulta la [guía de despliegue por SFTP](DEPLOY_IONOS_SFTP.md). El servidor de desarrollo del inicio rápido no sustituye la configuración de producción.

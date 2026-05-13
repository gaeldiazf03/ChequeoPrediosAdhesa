# Estructura y Separación de Responsabilidades

## 📁 Arquitectura del Proyecto

```
PruebasChequeoAdhesa/
├── 🔵 PYTHON (Backend/Lógica)
│   ├── app.py                    # Inicialización Flask, registro de blueprints
│   ├── database.py               # Clase DatabaseManager - Todas operaciones BD
│   └── rutas/
│       ├── login.py              # Blueprint: Autenticación
│       ├── dashboard.py          # Blueprint: Administración de usuarios/slots
│       └── mapa.py               # Blueprint: Visor de mapa y API endpoints
│
├── 🟡 SERVICIOS (Generación de reportes)
│   └── services/reportes.py      # Funciones para generar CSV y DOCX
│
├── 🟢 UTILIDADES (Funciones compartidas)
│   └── utils/funciones.py        # convertir_geojson_a_kml()
│
├── 🔴 HTML (Plantillas)
│   └── templates/
│       ├── login.html            # Formulario de login
│       ├── dashboard.html        # Panel administrativo
│       └── mapa.html             # Visor de mapa interactivo
│
├── 🟣 CSS (Estilos)
│   └── static/css/
│       ├── login.css             # Estilos página login
│       ├── dashboard.css         # Estilos dashboard
│       └── mapa.css              # Estilos mapa
│
├── 🔵 JAVASCRIPT (Frontend)
│   └── static/js/
│       ├── login.js              # DEPRECADO (vacío - lógica en backend)
│       ├── dashboard.js          # Modales, handlers del dashboard
│       └── mapa.js               # Leaflet, dibujo, edición de lotes
│
└── requirements.txt              # Dependencias Python
```

---

## 🎯 Responsabilidades por Archivo

### BACKEND - Python

#### `app.py` (líneas: 1-17)
```
RESPONSABLE DE:
  ✓ Crear instancia Flask
  ✓ Configurar secret_key
  ✓ Registrar blueprints (login, dashboard, mapa)
  ✓ Iniciar servidor
```

#### `database.py` (líneas: 1-230)
```
RESPONSABLE DE:
  ✓ Crear tablas en SQLite
  ✓ Gestionar usuarios (crear, eliminar, cambiar contraseña)
  ✓ Gestionar slots/proyectos
  ✓ Gestionar KML
  ✓ Registrar logs/auditoría
  ✓ Validar credenciales
  ✓ Alternar permisos
```

#### `rutas/login.py` (líneas: 1-35)
```
RESPONSABLE DE:
  ✓ Renderizar formulario login (GET)
  ✓ Procesar autenticación (POST)
  ✓ Actualizar última conexión
  ✓ Registrar en logs
  ✓ Gestionar sesión
  ✓ Logout
```

#### `rutas/dashboard.py` (líneas: 1-100)
```
RESPONSABLE DE:
  ✓ Renderizar dashboard (GET)
  ✓ Carga de archivos KML
  ✓ Eliminación de KML
  ✓ Gestión de usuarios (crear, eliminar, cambiar password)
  ✓ Alternar permisos de usuarios
  ✓ Registrar operaciones en logs
```

#### `rutas/mapa.py` (líneas: 1-135)
```
RESPONSABLE DE:
  ✓ Renderizar visor de mapa
  ✓ APIs REST:
    - POST /api/guardar_kml/<id>
    - GET /api/kml/<id>
    - GET /api/mis_permisos
    - POST /api/reporte_mapa/<id>
    - POST /api/reporte_word/<id>
    - POST /exportar_kml
  ✓ Validar permisos
  ✓ Registrar cambios en logs
```

#### `services/reportes.py` (líneas: 1-100)
```
RESPONSABLE DE:
  ✓ Generar CSV de logs de auditoría
  ✓ Generar CSV con avances de lotes
  ✓ Generar DOCX con reporte completo
```

#### `utils/funciones.py` (líneas: 1-25)
```
RESPONSABLE DE:
  ✓ Convertir GeoJSON a KML
```

---

### FRONTEND - HTML/CSS/JS

#### `templates/login.html`
```
RESPONSABLE DE:
  ✓ Estructura HTML del formulario login
  ✓ Campos: username, password, submit
  ✓ Mostrar errores
```

#### `static/css/login.css`
```
RESPONSABLE DE:
  ✓ Centrado y spacing del formulario
  ✓ Estilos de inputs
  ✓ Estilos de botones
  ✓ Colores y tipografía
```

#### `static/js/login.js` [DEPRECADO]
```
ESTADO: VACÍO
RAZÓN: Toda lógica manejada por backend
```

---

#### `templates/dashboard.html`
```
RESPONSABLE DE:
  ✓ Estructura de slots/proyectos
  ✓ Tabla de usuarios (admin)
  ✓ Modales para operaciones (eliminar KML, cambiar password)
  ✓ Botones de acción
```

#### `static/css/dashboard.css`
```
RESPONSABLE DE:
  ✓ Layout de slots en grid
  ✓ Estilos de tarjetas
  ✓ Estilos de botones
  ✓ Estilos de tabla de usuarios
```

#### `static/js/dashboard.js` (líneas: 1-50)
```
RESPONSABLE DE:
  ✓ abrirModal/cerrarModal - Control de modal eliminar KML
  ✓ abrirModalPass/cerrarModalPass - Control de modal cambiar contraseña
  ✓ mostrarSpinnerYEnviar - Feedback visual carga de archivo
  ✓ window.onclick - Cerrar modales al hacer click en fondo
```

---

#### `templates/mapa.html`
```
RESPONSABLE DE:
  ✓ Contenedor del mapa (div#map)
  ✓ Pasar datos al JavaScript mediante dataset attributes
  ✓ Botones de acción (crear lote, guardar, exportar)
  ✓ Indicador de estado de guardado
```

#### `static/css/mapa.css`
```
RESPONSABLE DE:
  ✓ Altura y ancho del mapa
  ✓ Estilos de botones
  ✓ Body spacing
```

#### `static/js/mapa.js` (líneas: 1-450)
```
RESPONSABLE DE:
  ✓ Inicializar mapa Leaflet
  ✓ Dibujar polígonos
  ✓ Crear y editar popups (ficha del lote)
  ✓ Gestionar tareas dentro de lotes
  ✓ Actualizar datos agrícolas
  ✓ Guardar cambios en servidor
  ✓ Exportar KML
  ✓ Descargar reportes
  ✓ Validar permisos en tiempo real
  ✓ Autoguardado periódico
```

---

## 🔄 Flujo de Datos

### Autenticación
```
HTML (login.html) 
  ↓ POST /
Backend (login.py: index)
  ↓ Validar credenciales
Database.py: verificar_usuario_y_obtener_datos()
  ↓ Session actualizada
Redirect → dashboard.html
```

### Cargar KML
```
HTML (dashboard.html) 
  ↓ POST /cargar_kml/<id>
Backend (dashboard.py: cargar)
  ↓ Guardar archivo
Database.py: guardar_kml_en_slot()
  ↓ Registrar log
Database.py: registrar_log()
Redirect → dashboard.html
```

### Editar Mapa
```
HTML (mapa.html) 
  ↓ Frontend event (prepararCapa, actualizarDato)
JavaScript (mapa.js: guardarAutomaticamente)
  ↓ POST /api/guardar_kml/<id>
Backend (mapa.py: guardar)
  ↓ Convertir GeoJSON a KML
Utils.funciones.py: convertir_geojson_a_kml()
  ↓ Guardar en BD
Database.py: guardar_kml_en_slot()
  ↓ JSON response {ok: true}
Frontend: Actualizar estado visual
```

### Generar Reporte
```
HTML (mapa.html) 
  ↓ Click botón "Descargar Reporte"
JavaScript (mapa.js: descargarReporte)
  ↓ POST /api/reporte_word/<id>
Backend (mapa.py: reporte_word)
  ↓ Generar documento
Services.reportes.py: generar_word_mapa()
  ↓ Enviar como descarga
Frontend: Se descarga archivo .docx
```

---

## 📋 Checklist de Buenas Prácticas

### Python
- ✅ Métodos privados con `_` en DatabaseManager
- ✅ Docstrings claros (mejorado en utils/funciones.py)
- ✅ Validación de permisos en cada ruta
- ✅ Logs registrados de todas las operaciones
- ✅ Encriptación de contraseñas con werkzeug

### HTML
- ✅ Semántica HTML5 correcta
- ✅ Data attributes para pasar datos a JS
- ✅ IDs únicos en elementos importantes
- ✅ Accesibilidad: labels con inputs

### CSS
- ✅ Separación por página (login, dashboard, mapa)
- ✅ Colores consistentes
- ⚠️ Podría optimizarse con SCSS o consolidarse

### JavaScript
- ✅ DRY aplicado en mapa.js (variables de estilos)
- ✅ Funciones bien nombradas
- ✅ Validación de sesión en tiempo real
- ✅ Autoguardado implementado
- ⚠️ Podría usar TypeScript para mayor seguridad

---

## 🚀 Recomendaciones Futuras

1. **Consolidar CSS**: Usar preprocesador SCSS
2. **API Documentation**: Agregar Swagger/OpenAPI
3. **Testing**: Agregar pytest para Python
4. **Environment Variables**: Usar .env para configuración
5. **Logging**: Mejorar sistema de logs
6. **Frontend Testing**: Jest para JavaScript
7. **Database Migrations**: Usar Alembic

---

**Última actualización:** 13/05/2026

// Variables de entorno recuperadas mediante HTML dataset
var mapContainer = document.getElementById('map');
var slotId = mapContainer ? mapContainer.dataset.slotId : null;
var puedeAgregar = mapContainer ? mapContainer.dataset.puedeAgregar === 'true' : false;
var puedeEditar = mapContainer ? mapContainer.dataset.puedeEditar === 'true' : false;
var esAdmin = mapContainer ? mapContainer.dataset.esAdmin === 'true' : false;
var puedeMarcarTareas = mapContainer ? mapContainer.dataset.puedeMarcarTareas === 'true' : false;
var puedeAgregarTareas = mapContainer ? mapContainer.dataset.puedeAgregarTareas === 'true' : false;
var usuarioActual = mapContainer ? mapContainer.dataset.usuarioActual : '';
var usuariosLista = mapContainer && mapContainer.dataset.usuariosLista ? JSON.parse(mapContainer.dataset.usuariosLista) : [];
var puedeVerCostos = mapContainer ? mapContainer.dataset.puedeVerCostos === 'true' : false;
var puedeDescargarMapa = mapContainer ? mapContainer.dataset.puedeDescargarMapa === 'true' : false;
var puedeDescargarLogs = mapContainer ? mapContainer.dataset.puedeDescargarLogs === 'true' : false;
var puedeVerAlertas = mapContainer ? mapContainer.dataset.puedeVerAlertas === 'true' : false;

// Inicializar mapa
var map = L.map('map').setView([22.2331, -97.8611], 13); // Centrado en Tampico
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
}).addTo(map);

// Capa donde se guardarán los dibujos y el KML cargado
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var cambiosPendientes = false;
var guardando = false;
var cargaInicialCompleta = false;
var capaActualPopup = null; // Rastrea qué globo está abierto

// Resaltado de hijos cuando se abre el popup del padre
var _highlightedChildren = [];
var _originalStyles = new WeakMap();
var _parentPopupView = null;

function _clearHighlightedChildren() {
    _highlightedChildren.forEach(function(l) {
        try {
            if (_originalStyles.has(l) && typeof l.setStyle === 'function') {
                var s = _originalStyles.get(l);
                l.setStyle(s);
            }
        } catch (e) { console.warn('Error restaurando estilo hijo', e); }
    });
    _highlightedChildren = [];
}

function _coberturaMayorAlUmbral(parentGeo, childGeo, umbral) {
    umbral = typeof umbral === 'number' ? umbral : 0.6;
    try {
        var areaChild = turf.area(childGeo);
        if (!areaChild || areaChild <= 0) return false;

        var interseccion = turf.intersect(parentGeo, childGeo);
        if (!interseccion) return false;

        var areaInterseccion = turf.area(interseccion);
        return (areaInterseccion / areaChild) >= umbral;
    } catch (e) {
        console.warn('Error calculando cobertura', e);
        return false;
    }
}

async function enviarReportePorCorreo(btn) {
    if (!slotId) {
        alert('No hay slot activo para enviar el reporte.');
        return;
    }

    var textoOriginal = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = 'Enviando...';
        btn.disabled = true;
    }

    try {
        var geojson = drawnItems.toGeoJSON();
        var response = await fetch('/api/reporte_email/' + slotId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ geojson: geojson, formato: 'word' })
        });

        var data = await response.json();
        if (!response.ok || !data.ok) {
            alert(data.error || data.mensaje || 'No se pudo enviar el reporte por correo.');
            return;
        }

        alert('Reporte enviado a: ' + (data.destinatarios || []).join(', '));
    } catch (error) {
        console.error('Error enviando reporte por correo:', error);
        alert('No se pudo enviar el reporte por correo.');
    } finally {
        if (btn) {
            btn.innerHTML = textoOriginal || '📧 Enviar por correo';
            btn.disabled = false;
        }
    }
}

function _highlightChildrenOf(parentLayer) {
    _clearHighlightedChildren();
    _parentPopupView = null;
    if (!parentLayer || !parentLayer.feature || !parentLayer.feature.properties) return;
    var parentName = parentLayer.feature.properties.name;
    if (!parentName) return;

    drawnItems.eachLayer(function(other){
        try {
            if (!other.feature || !other.feature.properties) return;
            var p = other.feature.properties.parent;
            if (p && String(p) === String(parentName)) {
                if (typeof other.setStyle === 'function') {
                    try {
                        var orig = { color: other.options.color, fillColor: other.options.fillColor, weight: other.options.weight, fillOpacity: other.options.fillOpacity };
                        _originalStyles.set(other, orig);
                        other.setStyle({ color: '#c0392b', fillColor: '#f1948a', weight: 3, fillOpacity: 0.85 });
                        _highlightedChildren.push(other);
                    } catch (e) { console.warn('No se pudo resaltar hijo', e); }
                }
            }
        } catch (e) { }
    });
}

function _ordenarCapasPorJerarquia() {
    drawnItems.eachLayer(function (layer) {
        try {
            var props = layer && layer.feature && layer.feature.properties ? layer.feature.properties : null;
            if (props && props.parent && typeof layer.bringToFront === 'function') {
                layer.bringToFront();
            }
        } catch (e) { }
    });
}

function _asignarPadresLocales() {
    var principales = ['Casa Blanca', 'Mango', 'Guzman', 'Paisabel', 'Isleta', 'Tamante'];
    var capas = [];

    drawnItems.eachLayer(function (layer) {
        if (layer && layer.feature && layer.feature.geometry) {
            capas.push(layer);
        }
    });

    var principalesLayers = capas.filter(function (layer) {
        var nombre = layer.feature && layer.feature.properties ? layer.feature.properties.name : '';
        return nombre && principales.indexOf(nombre) !== -1;
    });

    capas.forEach(function (childLayer) {
        var props = childLayer.feature && childLayer.feature.properties ? childLayer.feature.properties : null;
        if (!props || props.parent) return;
        if (principales.indexOf(props.name) !== -1) return;

        var childGeo = childLayer.toGeoJSON();
        for (var i = 0; i < principalesLayers.length; i++) {
            var parentLayer = principalesLayers[i];
            var parentGeo = parentLayer.toGeoJSON();
            try {
                if (_coberturaMayorAlUmbral(parentGeo, childGeo, 0.6)) {
                    props.parent = parentLayer.feature.properties.name;
                    break;
                }
            } catch (e) { }
        }
    });
}

var opcionesPoligono = {
    shapeOptions: { color: '#b8860b', fillColor: '#E1AD01', fillOpacity: 0.5, weight: 2 }
};
var polygonDrawer = new L.Draw.Polygon(map, opcionesPoligono);

var estilosPopup = {
    contenedor: 'min-width: 250px; max-height: 400px; overflow-y: auto; font-family: sans-serif; padding-right: 5px;',
    titulo: 'margin-top: 0; color: #2E7D32; border-bottom: 2px solid #81C784; padding-bottom: 5px;',
    etiqueta: 'font-size: 12px; font-weight: bold; color: #666;',
    etiquetaPequena: 'font-size: 11px; font-weight: bold;',
    input: 'width:100%; margin-bottom:8px; padding:4px; box-sizing: border-box;'
};

function escaparHtml(valor) {
    return String(valor == null ? '' : valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function construirOpcionesHTML(opciones, valorSeleccionado) {
    return (opciones || []).map(function (opcion) {
        var seleccionado = opcion.valor === valorSeleccionado ? 'selected' : '';
        return '<option value="' + escaparHtml(opcion.valor) + '" ' + seleccionado + '>' + escaparHtml(opcion.texto) + '</option>';
    }).join('');
}

function crearFilaDosColumnas(columnaIzquierda, columnaDerecha) {
    return '<div style="display: flex; gap: 5px; margin-bottom:8px;">' +
        '<div style="flex: 1;">' + columnaIzquierda + '</div>' +
        '<div style="flex: 1;">' + columnaDerecha + '</div>' +
        '</div>';
}

function _esPredioPadreDefault(nombre) {
    if (!nombre) return false;
    var nombres = ['Casa Blanca', 'Mango', 'Guzman', 'Paisabel', 'Isleta', 'Tamante'];
    return nombres.indexOf(String(nombre).trim()) !== -1;
}

function _tareasPredioPadreDefault() {
    return [
        { texto: 'Subsuelo', estado: 'rojo', completada: false },
        { texto: 'Arado', estado: 'rojo', completada: false },
        { texto: 'Rastra', estado: 'rojo', completada: false },
        { texto: 'Barbecho', estado: 'rojo', completada: false }
    ];
}

function _tareasBasicasHijoDefault() {
    return [
        { texto: 'Riego inicial', estado: 'rojo', completada: false },
        { texto: 'Fertilización básica', estado: 'rojo', completada: false },
        { texto: 'Monitoreo de crecimiento', estado: 'rojo', completada: false },
        { texto: 'Control de maleza', estado: 'rojo', completada: false }
    ];
}

function _normalizarEstadoTarea(tarea) {
    if (!tarea) return 'rojo';
    var estado = (tarea.estado || '').toString().toLowerCase().trim();
    if (estado === 'verde' || estado === 'amarillo' || estado === 'rojo') return estado;
    if (estado === 'completada' || estado === 'completado') return 'verde';
    if (estado === 'en_proceso' || estado === 'proceso' || estado === 'en progreso') return 'amarillo';
    if (estado === 'pendiente' || estado === 'no_realizada' || estado === 'no realizada') return 'rojo';
    if (tarea.completada === true) return 'verde';
    return 'rojo';
}

function _estadoTareaTexto(estado) {
    if (estado === 'verde') return 'Verde - Completado';
    if (estado === 'amarillo') return 'Amarillo - En proceso';
    return 'Rojo - No realizado';
}

function _colorEstadoTarea(estado) {
    if (estado === 'verde') return '#198754';
    if (estado === 'amarillo') return '#ffc107';
    return '#dc3545';
}

function _asegurarTareasPredioPadre(layer) {
    if (!layer || !layer.feature || !layer.feature.properties) return;
    var props = layer.feature.properties;
    if (_esPredioPadreDefault(props.name) && (!Array.isArray(props.tareas) || props.tareas.length === 0)) {
        props.tareas = _tareasPredioPadreDefault();
    }
    if (props.parent && (!Array.isArray(props.tareas) || props.tareas.length === 0)) {
        props.tareas = _tareasBasicasHijoDefault();
    }
}

function _resumenFichaHtml(props) {
    // Mantener función para compatibilidad, pero la ficha completa ya no se mostrará en el sidebar principal.
    var piezas = [];
    piezas.push('<div class="sidebar-section"><div class="sidebar-title"><h3>' + escaparHtml(props.name || 'Lote') + '</h3>' + (props.parent ? '<span class="sidebar-badge">Hijo</span>' : '<span class="sidebar-badge">Padre</span>') + '</div>');
    piezas.push('<div class="sidebar-meta"><strong>Responsable:</strong> ' + escaparHtml(props.responsable || 'Sin responsable') + '</div>');
    piezas.push('<div class="sidebar-meta"><strong>Incidencias:</strong><br>' + escaparHtml(props.incidencias || 'Sin incidencias') + '</div></div>');
    return piezas.join('');
}

function _renderSidebarContenido(layer) {
    var infoEl = document.getElementById('sidebar-info');
    var sidebar = document.getElementById('lote-sidebar');
    if (!infoEl && !sidebar) return;
    var props = layer && layer.feature && layer.feature.properties ? layer.feature.properties : {};

    // Mostrar información compacta: nombre, hectáreas y responsable
    var nombre = escaparHtml(props.name || 'Lote');
    var responsable = escaparHtml(props.responsable || 'Sin responsable');
    var hect = '';
    try {
        if (props.hectareas !== undefined && props.hectareas !== null) {
            hect = Number(props.hectareas).toFixed(2) + ' ha';
        } else if (layer && layer.feature && typeof turf === 'object') {
            var areaM2 = turf.area(layer.feature || {});
            hect = (areaM2 / 10000).toFixed(2) + ' ha';
        }
    } catch (e) { hect = '' }

    var html = '<div class="sidebar-section"><div class="sidebar-title"><h3>' + nombre + '</h3></div>';
    if (hect) html += '<div class="sidebar-meta"><strong>Hectáreas:</strong> ' + hect + '</div>';
    html += '<div class="sidebar-meta"><strong>Responsable:</strong> ' + responsable + '</div>';
    html += '</div>';

    if (infoEl) infoEl.innerHTML = html; else sidebar.innerHTML = html;
}

function abrirFichaEnSidebar(layer) {
    capaActualPopup = layer;
    _renderSidebarContenido(layer);
}

function prepararCapa(layer) {
    if (!layer.feature) layer.feature = { type: 'Feature', properties: {} };

    if (layer.feature.properties && layer.feature.properties.description) {
        try {
            var datosExtras = JSON.parse(layer.feature.properties.description);
            Object.assign(layer.feature.properties, datosExtras);
        } catch (e) { }
    }

    var p = layer.feature.properties || {};
    if (!p.name) p.name = 'Nuevo Lote';
    if (!p.responsable) p.responsable = '';
    if (!Array.isArray(p.tareas)) p.tareas = [];
    _asegurarTareasPredioPadre(layer);

    layer.on('mouseover', function () { if (typeof this.setStyle === 'function') this.setStyle({ fillOpacity: 0.8, weight: 3 }); });
    layer.on('mouseout', function () { if (typeof this.setStyle === 'function') this.setStyle({ fillOpacity: 0.5, weight: 2 }); });

    layer.on('click', function () {
        abrirFichaEnSidebar(layer);
        if (typeof this.openPopup === 'function') {
            this.openPopup();
        }
    });

    layer.bindPopup(crearContenidoPopup(layer));
    layer.on('popupopen', function () {
        capaActualPopup = layer;
        _highlightChildrenOf(layer);
    });
    layer.on('popupclose', function () {
        capaActualPopup = null;
        _clearHighlightedChildren();
    });
}

function crearContenidoPopup(layer) {
    var props = layer && layer.feature && layer.feature.properties ? layer.feature.properties : {};
    var puedeGestionarTareas = esAdmin || puedeAgregarTareas;
    var puedeMarcar = esAdmin || puedeMarcarTareas || usuarioActual === props.responsable;
    // Incluir hectáreas si están presentes o calcular desde la geometría
    var hect = '';
    try {
        if (props.hectareas !== undefined && props.hectareas !== null) hect = Number(props.hectareas).toFixed(2) + ' ha';
        else if (layer && layer.feature && typeof turf === 'object') {
            var areaM2 = turf.area(layer.feature || {});
            hect = (areaM2 / 10000).toFixed(2) + ' ha';
        }
    } catch (e) { hect = ''; }

    var html = `<div style="${estilosPopup.contenedor}; min-width: 220px;">`;
    if (hect) html += `<div style="margin-bottom:6px;"><strong>Hectáreas:</strong> ${hect}</div>`;
    // Si es hijo, mostrar enlace para ver tareas del predio padre
    if (props.parent) {
        html += `<div style="margin-bottom:8px;"><strong>Padre:</strong> <a href="#" onclick="mostrarTareasPadre('${escaparHtml(props.parent)}'); return false;">${escaparHtml(props.parent)}</a></div>`;
    }
    // Mostrar resumen de tareas asignadas y botón para gestionarlas desde calendario/Gantt
    var tareasCount = (props.tareas || []).length;
    html += `<div style="margin-bottom:8px; font-size:13px; color:#374151;"><strong>Tareas asignadas:</strong> ${tareasCount}</div>`;
    // Mostrar lista compacta de tareas con estado (solo lectura)
    if (props.tareas && props.tareas.length) {
        html += '<ul style="padding-left: 0; list-style: none; margin-top: 5px; margin-bottom: 8px;">';
        props.tareas.forEach(function(t, idx){
            var est = _normalizarEstadoTarea(t);
            var color = _colorEstadoTarea(est);
            var texto = escaparHtml(t.texto || 'Sin descripción');
            html += `<li style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
                        <span style="width:10px; height:10px; border-radius:50%; background:${color}; display:inline-block;"></span>
                        <span style="flex:1; color:#111; font-size:13px;">${texto}</span>
                     </li>`;
        });
        html += '</ul>';
    }

    html += `<div style="margin-top:8px; display:flex; gap:8px;"><button class="map-button map-button-info" onclick="abrirFichaEnSidebar(capaActualPopup); return false;">Gestionar tareas</button></div>`;
    html += `</div>`;
    return html;
}

// --- FUNCIONES INTERNAS DEL GLOBO ---
function actualizarDato(clave, valor) {
    actualizarPopupActual(function (layer) {
        layer.feature.properties[clave] = valor;
    });
}

function actualizarEstadoTarea(index, estado) {
    actualizarPopupActual(function (layer) {
        if (!layer.feature.properties.tareas[index]) return;
        layer.feature.properties.tareas[index].estado = estado;
        layer.feature.properties.tareas[index].completada = (estado === 'verde');
    });
}

function actualizarPopupActual(mutador) {
    if (!capaActualPopup || typeof mutador !== 'function') return;
    mutador(capaActualPopup);
    _asegurarTareasPredioPadre(capaActualPopup);
    if (typeof capaActualPopup.setPopupContent === 'function') {
        capaActualPopup.setPopupContent(crearContenidoPopup(capaActualPopup));
    }
    _renderSidebarContenido(capaActualPopup);
    if (typeof registrarCambio === 'function') registrarCambio();
}

function eliminarTarea(index) {
    actualizarPopupActual(function (layer) {
        layer.feature.properties.tareas.splice(index, 1);
    });
}

function agregarTarea() {
    if (!capaActualPopup) return;
    var input = document.getElementById('inputNuevaTarea');
    if (!input.value.trim()) return;

    actualizarPopupActual(function (layer) {
        layer.feature.properties.tareas.push({
            texto: input.value.trim(),
            estado: 'rojo',
            completada: false
        });
    });
}

// --- EVENTOS DEL MAPA ---
map.on(L.Draw.Event.CREATED, function (event) {
    var layer = event.layer;
    prepararCapa(layer); // Le inyectamos la lógica del globo
    drawnItems.addLayer(layer);
    if (typeof registrarCambio === 'function') registrarCambio();

    var btn = document.getElementById('btnCrearLote');
    if (btn && puedeAgregar) {
        btn.innerText = "Crear Lote";
        btn.style.backgroundColor = "#28a745";
    }
});

map.on('draw:drawstop', function (e) {
    var btn = document.getElementById('btnCrearLote');
    if (btn && puedeAgregar) {
        btn.innerText = "Crear Lote";
        btn.style.backgroundColor = "#28a745";
    }
});

var drawControl = new L.Control.Draw({
    edit: puedeEditar ? { featureGroup: drawnItems, remove: true } : false,
    draw: false
});
if (puedeEditar) map.addControl(drawControl);

map.on('draw:edited', function (e) { if (typeof registrarCambio === 'function') registrarCambio(); });
map.on('draw:deleted', function (e) { if (typeof registrarCambio === 'function') registrarCambio(); });

// Resaltar hijos cuando se abran popups (captura global en el mapa)
map.on('popupopen', function(e){
    try {
        var layer = e.popup && e.popup._source;
        if (layer) _highlightChildrenOf(layer);
    } catch (err) { console.warn('popupopen highlight error', err); }
});

map.on('popupclose', function(e){
    try {
        _clearHighlightedChildren();
    } catch (err) { }
    _parentPopupView = null;
});

// Auto-carga desde la BD
if (slotId) {
    var urlAPI = "/api/kml/" + slotId;
    console.info('Cargando KML desde', urlAPI);
    var kmlLayer = omnivore.kml(urlAPI)
        .on('ready', function () {
            kmlLayer.eachLayer(function (layer) {
                drawnItems.addLayer(layer);
            });
            _asignarPadresLocales();
            _ordenarCapasPorJerarquia();
            drawnItems.eachLayer(function (layer) {
                prepararCapa(layer); // Inyectamos la lógica a los polígonos ya guardados
            });
            if (drawnItems.getLayers().length) {
                map.fitBounds(drawnItems.getBounds());
            }
            cargaInicialCompleta = true;
            if (typeof actualizarEstado === 'function') actualizarEstado('Mapa cargado');
        })
        .on('error', function (err) {
            cargaInicialCompleta = true;
            console.error('Error al cargar KML con Omnivore:', err);
            // Intento de diagnóstico: consultar el endpoint manualmente para ver status/texto
            fetch(urlAPI, { credentials: 'same-origin' })
                .then(function (resp) {
                    console.info('Diagnóstico KML - status:', resp.status, resp.statusText);
                    return resp.text();
                })
                .then(function (text) {
                    console.info('Diagnóstico KML - content preview:', text ? text.slice(0, 1000) : '(vacío)');
                })
                .catch(function (fetchErr) {
                    console.error('Diagnóstico KML - fallo al obtener el endpoint:', fetchErr);
                });

            if (typeof actualizarEstado === 'function') actualizarEstado('Mapa listo');
        });
} else {
    cargaInicialCompleta = true;
}

// Vigilante de permisos: movido a mapa_vigilancia.js

function exportarKML() {
    var geojsonData = drawnItems.toGeoJSON();
    fetch('/exportar_kml', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geojsonData)
    })
        .then(response => response.blob())
        .then(blob => {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = "mapa_modificado.kml";
            document.body.appendChild(a);
            a.click();
            a.remove();
        })
        .catch(error => console.error('Error al exportar:', error));
}

function descargarReporte(btn) {
    var textoOriginal = btn.innerHTML;
    btn.innerHTML = "Generando documento...";
    btn.disabled = true;

    var geojson = drawnItems.toGeoJSON();

    // Asegúrate de apuntar a /api/reporte_word/ o /api/reporte_mapa/ según lo que necesites bajar
    fetch('/api/reporte_word/' + slotId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geojson)
    })
    .then(res => {
        if (!res.ok) throw new Error("Error en el servidor");
        return res.blob();
    })
    .then(blob => {
        var fileName = "Reporte_Avances_Slot_" + slotId + ".docx";
        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        
        btn.innerHTML = textoOriginal;
        btn.disabled = false;
        alert("¡Reporte descargado con éxito en tu equipo!");
    })
    .catch(error => {
        console.error(error);
        alert("Ocurrió un error al generar el reporte.");
        btn.innerHTML = textoOriginal;
        btn.disabled = false;
    });
}

function descargarReporteExcel(btn) {
    if (!puedeDescargarMapa && !esAdmin) {
        alert('No tienes permiso para descargar este Excel.');
        return;
    }

    var textoOriginal = btn.innerHTML;
    btn.innerHTML = "Generando Excel...";
    btn.disabled = true;

    var geojson = drawnItems.toGeoJSON();

    fetch('/api/reporte_mapa/' + slotId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geojson)
    })
    .then(res => {
        if (!res.ok) throw new Error("Error en el servidor");
        return res.blob();
    })
    .then(blob => {
        var fileName = "Tabla_Avance_Predio_" + slotId + ".xlsx";
        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();

        btn.innerHTML = textoOriginal;
        btn.disabled = false;
        alert("¡Excel descargado con éxito en tu equipo!");
    })
    .catch(error => {
        console.error(error);
        alert("Ocurrió un error al generar el Excel.");
        btn.innerHTML = textoOriginal;
        btn.disabled = false;
    });
}

// --- ANÁLISIS DE CONTENCIONES (USANDO Turf.js) ---
function analizarContenciones() {
    if (drawnItems.getLayers().length === 0) {
        Swal.fire('Sin polígonos', 'No hay polígonos cargados para analizar.', 'info');
        return;
    }

    var geo = drawnItems.toGeoJSON();
    var feats = geo.features || [];
    var nombres = feats.map(function(f, idx){
        var n = (f.properties && f.properties.name) ? f.properties.name : ('#' + (idx+1));
        return n;
    });

    var relaciones = {};
    for (var i = 0; i < feats.length; i++) {
        relaciones[nombres[i]] = [];
    }

    for (var i = 0; i < feats.length; i++) {
        for (var j = 0; j < feats.length; j++) {
            if (i === j) continue;
            try {
                var A = feats[i];
                var B = feats[j];
                if (_coberturaMayorAlUmbral(A, B, 0.6)) {
                    relaciones[nombres[i]].push(nombres[j]);
                }
            } catch (e) {
                console.warn('Error en contención turf entre', nombres[i], nombres[j], e);
            }
        }
    }

    // Construir HTML resumen
    var html = '<div style="text-align:left; max-height:400px; overflow:auto;">';
    Object.keys(relaciones).forEach(function(k){
        var arr = relaciones[k];
        if (arr.length === 0) {
            html += '<p><strong>' + escaparHtml(k) + ':</strong> (no contiene otros polígonos)</p>';
        } else {
            html += '<p><strong>' + escaparHtml(k) + ':</strong> contiene ' + arr.map(escaparHtml).join(', ') + '</p>';
        }
    });
    html += '</div>';

    Swal.fire({
        title: 'Resultados de contenciones',
        html: html,
        width: 700,
        allowOutsideClick: true
    });
}

// --- ASIGNACIÓN AUTOMÁTICA DE PADRES ---
function asignarPadresAutomaticoPrompt() {
    // Lista por defecto de predios principales (puedes editarla antes de confirmar)
    var principalesDefault = [
        'Casa Blanca','Mango','Guzman','Paisabel','Isleta','Tamante'
    ];

    Swal.fire({
        title: 'Asignar padres automáticamente',
        html: `<p>Lista actual de predios principales (coma-separated):</p>
               <textarea id="swal-main-list" style="width:100%; height:80px;">${principalesDefault.join(',')}</textarea>`,
        showCancelButton: true,
        confirmButtonText: 'Asignar y Guardar',
        preConfirm: function() {
            var val = document.getElementById('swal-main-list').value || '';
            return val.split(',').map(function(s){ return s.trim(); }).filter(Boolean);
        }
    }).then(function(result){
        if (result.isConfirmed) {
            asignarPadresAutomatico(result.value);
        }
    });
}

function asignarPadresAutomatico(listaPrincipales) {
    if (!slotId) {
        Swal.fire('Error','Slot no definido en la página','error');
        return;
    }
    var geo = drawnItems.toGeoJSON();
    var feats = geo.features || [];
    if (feats.length === 0) {
        Swal.fire('Sin polígonos','No hay polígonos para procesar','info');
        return;
    }

    var principales = listaPrincipales.map(function(s){ return s.trim(); }).filter(Boolean);
    var asignaciones = [];

    for (var i=0;i<feats.length;i++){
        var A = feats[i];
        var nameA = (A.properties && A.properties.name) ? A.properties.name : null;
        if (!nameA) continue;
        if (principales.indexOf(nameA) === -1) continue;
        for (var j=0;j<feats.length;j++){
            if (i===j) continue;
            var B = feats[j];
            var nameB = (B.properties && B.properties.name) ? B.properties.name : null;
            if (nameB && principales.indexOf(nameB) !== -1) continue;
            try {
                if (_coberturaMayorAlUmbral(A, B, 0.6)) {
                    if (!B.properties) B.properties = {};
                    B.properties.parent = nameA;
                    asignaciones.push({child: (B.properties.name||('#'+(j+1))), parent: nameA});
                }
            } catch(e){ console.warn('Error calculando cobertura', e); }
        }
    }

    if (asignaciones.length === 0) {
        Swal.fire('Resultado','No se encontraron asignaciones automáticas con la lista dada.','info');
        return;
    }

    // Mostrar resumen y confirmar persistencia
    var html = '<div style="text-align:left; max-height:300px; overflow:auto;">';
    asignaciones.forEach(function(a){ html += `<p><strong>${escaparHtml(a.child)}</strong> → ${escaparHtml(a.parent)}</p>`; });
    html += '</div>';

    Swal.fire({
        title: 'Asignaciones encontradas',
        html: html,
        showCancelButton: true,
        confirmButtonText: 'Guardar en servidor'
    }).then(function(res){
        if (res.isConfirmed) {
            // Guardar en servidor
            fetch('/api/guardar_kml/' + slotId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(geo),
                credentials: 'same-origin'
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.ok) {
                    Swal.fire('Guardado','Asignaciones guardadas con éxito.','success').then(()=> location.reload());
                } else {
                    Swal.fire('Error', (data && data.error) ? data.error : 'Error desconocido', 'error');
                }
            })
            .catch(err => {
                console.error('Error guardar asignaciones:', err);
                Swal.fire('Error','Fallo al guardar en servidor','error');
            });
        }
    });
}

// Ajuste responsive: invalidar tamaño del mapa al cambiar tamaño de ventana
window.addEventListener('resize', function () {
    try {
        if (typeof map !== 'undefined' && map && typeof map.invalidateSize === 'function') {
            // Pequeño delay para esperar a que el layout termine
            setTimeout(function () { map.invalidateSize(); }, 200);
        }
    } catch (e) { console.warn('Error al invalidar tamaño del mapa:', e); }
});

// === SMARTMAP (FASE 2) ELIMINADO - Migrando a calendario y gantt ===
function abrirFichaEnSidebar(layer) {
    capaActualPopup = layer;
    _renderSidebarContenido(layer);
    
    // Actualizar clima basado en coordenadas del lote
    if (typeof actualizarClimaDesdeFeature === 'function') {
        actualizarClimaDesdeFeature(layer);
    }
    
    // Actualizar tareas del lote en calendario/gantt
    if (layer && layer.feature && layer.feature.properties) {
        const nombreLote = layer.feature.properties.name || '';
        const tareas = layer.feature.properties.tareas || [];
        if (typeof actualizarTareasDelLote === 'function') {
            actualizarTareasDelLote(nombreLote, tareas);
        }
    }
}

// Buscar una capa en drawnItems por su nombre
function buscarCapaPorNombre(nombre) {
    var encontrada = null;
    try {
        if (window.drawnItems) {
            window.drawnItems.eachLayer(function(layer){
                try {
                    if (layer.feature && layer.feature.properties && String(layer.feature.properties.name) === String(nombre)) {
                        encontrada = layer;
                    }
                } catch(e){}
            });
        }
    } catch(e){}
    return encontrada;
}

// Devuelve lista de nombres de predios padre (capas sin propiedad 'parent')
window.getPrediosPadreList = function() {
    var list = [];
    try {
        if (window.drawnItems) {
            window.drawnItems.eachLayer(function(layer){
                try {
                    if (!layer.feature || !layer.feature.properties) return;
                    var props = layer.feature.properties;
                    if (!props.parent) {
                        var n = props.name || '';
                        if (n && list.indexOf(n) === -1) list.push(n);
                    }
                } catch(e){}
            });
        }
    } catch(e){}
    return list;
};

// Devuelve lista de nombres de hijos para un predio padre dado
window.getHijosDePadre = function(parentName) {
    var list = [];
    try {
        if (window.drawnItems) {
            window.drawnItems.eachLayer(function(layer){
                try {
                    if (!layer.feature || !layer.feature.properties) return;
                    var props = layer.feature.properties;
                    if (props.parent && String(props.parent) === String(parentName)) {
                        var n = props.name || '';
                        if (n && list.indexOf(n) === -1) list.push(n);
                    }
                } catch(e){}
            });
        }
    } catch(e){}
    return list;
};

// Mostrar tareas del predio padre en la UI (sidebar, calendario, gantt)
function mostrarTareasPadre(nombrePadre) {
    if (!nombrePadre) return;
    var layer = buscarCapaPorNombre(nombrePadre);
    if (layer) {
        abrirFichaEnSidebar(layer);
        if (typeof layer.openPopup === 'function') {
            layer.openPopup();
        }
        return;
    }

    // Fallback: buscar en el GeoJSON y actualizar tareas directamente
    try {
        var geo = (window.drawnItems && typeof window.drawnItems.toGeoJSON === 'function') ? window.drawnItems.toGeoJSON() : (window.map ? window.map._geojson : null);
        if (geo && geo.features) {
            var f = geo.features.find(function(fe){ return fe.properties && String(fe.properties.name) === String(nombrePadre); });
            if (f) {
                var tareas = f.properties.tareas || [];
                if (typeof actualizarTareasDelLote === 'function') actualizarTareasDelLote(nombrePadre, tareas);
                if (typeof Swal !== 'undefined') Swal.fire('Tareas cargadas', 'Se han cargado las tareas del predio padre en el calendario.', 'info');
                return;
            }
        }
    } catch(e){}

    if (typeof Swal !== 'undefined') Swal.fire('No encontrado', 'No se encontró el predio padre en el mapa.', 'warning');
}

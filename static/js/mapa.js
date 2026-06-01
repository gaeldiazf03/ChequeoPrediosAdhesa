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

    var bounds = null;

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
                        if (typeof other.getBounds === 'function') {
                            var otherBounds = other.getBounds();
                            if (otherBounds && otherBounds.isValid && otherBounds.isValid()) {
                                bounds = bounds ? bounds.extend(otherBounds) : L.latLngBounds(otherBounds);
                            }
                        }
                    } catch (e) { console.warn('No se pudo resaltar hijo', e); }
                }
            }
        } catch (e) { }
    });

    if (bounds && bounds.isValid && bounds.isValid()) {
        try {
            _parentPopupView = {
                center: map.getCenter(),
                zoom: map.getZoom()
            };
            map.fitBounds(bounds.pad(0.18), { animate: true, duration: 0.35 });
        } catch (e) {
            console.warn('No se pudo enfocar a los hijos', e);
        }
    }
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
    if (!_esPredioPadreDefault(props.name)) return;
    if (!Array.isArray(props.tareas) || props.tareas.length === 0) {
        props.tareas = _tareasPredioPadreDefault();
    }
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

    layer.bindPopup(crearContenidoPopup(layer));
    layer.on('popupopen', function () {
        capaActualPopup = layer;
        _highlightChildrenOf(layer);
    });
    layer.on('popupclose', function () {
        capaActualPopup = null;
        _clearHighlightedChildren();
        if (_parentPopupView) {
            try { map.setView(_parentPopupView.center, _parentPopupView.zoom, { animate: true }); } catch (e) { }
            _parentPopupView = null;
        }
    });
}

function crearContenidoPopup(layer) {
    var props = layer && layer.feature && layer.feature.properties ? layer.feature.properties : {};
    var puedeGestionarTareas = esAdmin || puedeAgregarTareas;
    var puedeMarcar = esAdmin || puedeMarcarTareas || usuarioActual === props.responsable;
    var opcionesSuelo = [
        { valor: '', texto: 'Seleccione...' },
        { valor: 'Arcilloso', texto: 'Arcilloso' },
        { valor: 'Arenoso', texto: 'Arenoso' },
        { valor: 'Franco', texto: 'Franco' },
        { valor: 'Limoso', texto: 'Limoso' }
    ];
    var opcionesRiego = [
        { valor: '', texto: 'Seleccione...' },
        { valor: 'Temporal', texto: 'Temporal' },
        { valor: 'Goteo', texto: 'Goteo' },
        { valor: 'Gravedad', texto: 'Gravedad' },
        { valor: 'Aspersión', texto: 'Aspersión' }
    ];
    var opcionesMaleza = [
        { valor: 'Bajo', texto: 'Bajo' },
        { valor: 'Medio', texto: 'Medio' },
        { valor: 'Alto', texto: 'Alto' }
    ];
    var opcionesHumedad = [
        { valor: 'Seco', texto: 'Seco' },
        { valor: 'Óptimo', texto: 'Óptimo' },
        { valor: 'Saturado', texto: 'Saturado' }
    ];
    var opcionesSanidad = [
        { valor: 'Sano', texto: '🟢 Sano' },
        { valor: 'Prevención', texto: '🟡 En Prevención' },
        { valor: 'Plaga', texto: '🔴 Plaga' },
        { valor: 'Enfermedad', texto: '🔴 Enfermedad' }
    ];

    var html = `<div style="${estilosPopup.contenedor}">`;
    html += `<h4 style="${estilosPopup.titulo}">🚜 Ficha del Lote</h4>`;

    if (props.parent) {
        html += `<div style="margin-bottom:10px; padding:8px 10px; background:#f5f7f5; border:1px solid #d7e7d7; border-radius:6px;">
                    <label style="${estilosPopup.etiquetaPequena}; display:block; margin-bottom:4px; color:#2E7D32;">Lote Padre</label>
                    <input type="text" value="${escaparHtml(props.parent)}" disabled style="width:100%; padding:6px; background:#eef7ee; border:1px solid #c9ddc9; box-sizing:border-box; font-weight:700; color:#1f4d1f;">
                 </div>`;
    }

    if (puedeEditar) {
        html += `<input type="text" value="${escaparHtml(props.name)}" onchange="actualizarDato('name', this.value)" style="${estilosPopup.input} font-weight: bold; margin-bottom: 10px; padding: 5px;">`;
    } else {
        html += `<h3 style="margin-top:0; color:#333;">${escaparHtml(props.name)}</h3>`;
    }

    html += `<label style="${estilosPopup.etiqueta}">Responsable:</label><br>`;
    if (puedeEditar) {
        html += `<select onchange="actualizarDato('responsable', this.value)" style="width: 100%; margin-bottom: 15px; padding: 5px;">`;
        html += `<option value="">Sin Responsable</option>`;
        html += usuariosLista.map(function (u) {
            var seleccionado = u === props.responsable ? 'selected' : '';
            return `<option value="${escaparHtml(u)}" ${seleccionado}>${escaparHtml(u)}</option>`;
        }).join('');
        html += `</select>`;
    } else {
        html += `<p style="margin: 0 0 15px 0; font-weight: bold; color: #007bff;">${escaparHtml(props.responsable || 'Sin Responsable')}</p>`;
    }

    html += `<label style="${estilosPopup.etiqueta}">Tareas:</label>\n             <ul style="padding-left: 0; list-style: none; margin-top: 5px; margin-bottom: 15px;">`;
    (props.tareas || []).forEach(function (tarea, index) {
        var estado = _normalizarEstadoTarea(tarea);
        var colorEstado = _colorEstadoTarea(estado);
        var disableCheck = puedeMarcar ? '' : 'disabled';
        var estiloTexto = estado === 'verde' ? 'text-decoration: line-through; color: #aaa;' : 'color: #333;';

        html += `<li style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">\n                    <select ${disableCheck} onchange="actualizarEstadoTarea(${index}, this.value)" style="min-width: 180px; padding: 4px 6px; border: 1px solid ${colorEstado}; background: #fff; border-radius: 4px; color: #333;">\n                        <option value="verde" ${estado === 'verde' ? 'selected' : ''}>Verde - Completado</option>\n                        <option value="amarillo" ${estado === 'amarillo' ? 'selected' : ''}>Amarillo - En proceso</option>\n                        <option value="rojo" ${estado === 'rojo' ? 'selected' : ''}>Rojo - No realizado</option>\n                    </select>\n                    <span style="flex: 1; ${estiloTexto}">${escaparHtml(tarea.texto)}</span>`;

        if (puedeGestionarTareas) {
            html += ` <button onclick="eliminarTarea(${index})" style="color: white; background: #dc3545; border: none; cursor: pointer; border-radius: 3px; padding: 2px 6px; font-size: 10px; margin-left: 5px;">X</button>`;
        }
        html += `</li>`;
    });
    html += `</ul>`;

    if (puedeGestionarTareas) {
        html += `<div style="display: flex; gap: 5px; border-top: 1px solid #eee; padding-top: 10px; margin-bottom: 15px;">\n                    <input type="text" id="inputNuevaTarea" placeholder="Nueva tarea..." style="flex: 1; padding: 5px;">\n                    <button onclick="agregarTarea()" style="padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer;">Add</button>\n                </div>`;
    }

    html += `<div style="background: #f9f9f9; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">\n                <h5 style="margin-top: 0; margin-bottom: 10px; color: #444;">Datos Agrícolas</h5>`;

    if (esAdmin || puedeVerCostos) {
        html += `<label style="${estilosPopup.etiquetaPequena}">Costo Estimado ($):</label>\n                 <input type="number" value="${escaparHtml(props.costo || 0)}" onchange="actualizarDato('costo', this.value)" style="${estilosPopup.input}">`;
    }

    html += `<label style="${estilosPopup.etiquetaPequena}">Variedad de Caña:</label>\n             <input type="text" placeholder="Ej. CP 72-2086" value="${escaparHtml(props.variedad_cana || '')}" onchange="actualizarDato('variedad_cana', this.value)" style="${estilosPopup.input}">`;
    html += `<label style="${estilosPopup.etiquetaPequena}">Edad de Cultivo (Meses):</label>\n             <input type="number" min="0" value="${escaparHtml(props.edad_cultivo || '')}" onchange="actualizarDato('edad_cultivo', this.value)" style="${estilosPopup.input}">`;
    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Suelo:</label>\n             <select onchange="actualizarDato('tipo_suelo', this.value)" style="${estilosPopup.input}">\n                 ${construirOpcionesHTML(opcionesSuelo, props.tipo_suelo || '')}\n             </select>`;
    html += crearFilaDosColumnas(
        `<label style="${estilosPopup.etiquetaPequena}">Siembra:</label>\n         <input type="date" value="${escaparHtml(props.fecha_siembra || '')}" onchange="actualizarDato('fecha_siembra', this.value)" style="${estilosPopup.input}">`,
        `<label style="${estilosPopup.etiquetaPequena}">Últ. Aplic.:</label>\n         <input type="date" value="${escaparHtml(props.ultima_aplicacion || '')}" onchange="actualizarDato('ultima_aplicacion', this.value)" style="${estilosPopup.input}">`
    );

    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Riego:</label>\n             <select onchange="actualizarDato('tipo_riego', this.value)" style="${estilosPopup.input}">\n                 ${construirOpcionesHTML(opcionesRiego, props.tipo_riego || '')}\n             </select>`;
    html += `<label style="${estilosPopup.etiquetaPequena}">Rendimiento Esperado (TCH):</label>\n             <input type="number" step="0.1" value="${escaparHtml(props.rendimiento_tch || '')}" onchange="actualizarDato('rendimiento_tch', this.value)" style="${estilosPopup.input}">`;
    html += crearFilaDosColumnas(
        `<label style="${estilosPopup.etiquetaPequena}">Maleza:</label>\n         <select onchange="actualizarDato('nivel_maleza', this.value)" style="${estilosPopup.input}">\n             ${construirOpcionesHTML(opcionesMaleza, props.nivel_maleza || '')}\n         </select>`,
        `<label style="${estilosPopup.etiquetaPequena}">Humedad:</label>\n         <select onchange="actualizarDato('nivel_humedad', this.value)" style="${estilosPopup.input}">\n             ${construirOpcionesHTML(opcionesHumedad, props.nivel_humedad || '')}\n         </select>`
    );

    html += `<label style="${estilosPopup.etiquetaPequena}">Estatus Sanitario:</label>\n             <select onchange="actualizarDato('estatus_sanitario', this.value)" style="${estilosPopup.input}">\n                 ${construirOpcionesHTML(opcionesSanidad, props.estatus_sanitario || 'Sano')}\n             </select>`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Fertilización:</label>\n             <input type="text" placeholder="Ej. Urea, NPK..." value="${escaparHtml(props.tipo_fertilizacion || '')}" onchange="actualizarDato('tipo_fertilizacion', this.value)" style="${estilosPopup.input}">`;
    html += `<label style="${estilosPopup.etiquetaPequena}">Incidencias / Notas / Historial:</label>\n             <textarea onchange="actualizarDato('incidencias', this.value)" style="${estilosPopup.input} height:60px;">${escaparHtml(props.incidencias || '')}</textarea>`;

    html += `</div></div>`;
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
        if (_parentPopupView) {
            map.setView(_parentPopupView.center, _parentPopupView.zoom, { animate: true });
        }
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

function descargarReporteCsv(btn) {
    if (!puedeDescargarMapa && !esAdmin) {
        alert('No tienes permiso para descargar este CSV.');
        return;
    }

    var textoOriginal = btn.innerHTML;
    btn.innerHTML = "Generando CSV...";
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
        var fileName = "Avances_Proyecto_" + slotId + ".csv";
        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();

        btn.innerHTML = textoOriginal;
        btn.disabled = false;
        alert("¡CSV descargado con éxito en tu equipo!");
    })
    .catch(error => {
        console.error(error);
        alert("Ocurrió un error al generar el CSV.");
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

// === SMART MAP (FASE 2) ===
var smartMapLayer = L.layerGroup().addTo(map);
var smartMapMarkers = {};

function _colorMarcadorPorVelocidad(velocidad) {
    if (velocidad >= 30) return '#dc2626';
    if (velocidad >= 15) return '#d97706';
    return '#16a34a';
}

function _setText(id, texto) {
    var el = document.getElementById(id);
    if (el) el.textContent = texto;
}

function _renderUnidadesSmartMap(unidades) {
    if (!smartMapLayer || typeof smartMapLayer.clearLayers !== 'function') return;
    smartMapLayer.clearLayers();

    if (!Array.isArray(unidades) || unidades.length === 0) {
        _setText('smartmap-kpi-unidades', '0');
        _setText('smartmap-kpi-velocidad', '0 km/h');
        return;
    }

    var velocidadTotal = 0;
    var countVel = 0;

    unidades.forEach(function (u) {
        try {
            var lat = Number(u.lat);
            var lng = Number(u.lng);
            var velocidad = Number(u.velocidad_kmh || 0);
            var bateria = u.nivel_bateria != null ? Number(u.nivel_bateria) : null;
            var unidadId = u.unidad_id || (u.placa ? u.placa : 'N/A');

            velocidadTotal += velocidad;
            countVel++;

            var color = _colorMarcadorPorVelocidad(velocidad);
            var marker = L.circleMarker([lat, lng], { radius: 8, color: color, fillColor: color, fillOpacity: 0.9 });
            var popupHtml = `<strong>${escaparHtml(unidadId)}</strong><br/>Velocidad: ${escaparHtml(String(velocidad))} km/h`;
            if (bateria != null) popupHtml += `<br/>Batería: ${escaparHtml(String(bateria))}%`;
            if (u.placa) popupHtml += `<br/>Placa: ${escaparHtml(u.placa)}`;
            marker.bindPopup(popupHtml);
            marker.addTo(smartMapLayer);

            // Mantener referencia para actualizaciones futuras
            if (u.unidad_id) smartMapMarkers[u.unidad_id] = marker;
        } catch (e) { console.warn('Error render unidad', e); }
    });

    _setText('smartmap-kpi-unidades', String(unidades.length));
    _setText('smartmap-kpi-velocidad', (countVel ? (velocidadTotal / countVel).toFixed(1) : '0') + ' km/h');
}

async function cargarTelemetriaSmartMap() {
    if (!slotId) return;
    try {
        var response = await fetch('/api/smartmap/telemetria/' + slotId, {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) return;
            throw new Error('HTTP ' + response.status);
        }

        var data = await response.json();
        var unidades = data.unidades || [];
        _renderUnidadesSmartMap(unidades);
        _setText('smartmap-kpi-updated', data.actualizado_en || '--');
        // TODO: Cuando exista la API de unidades, usar data.unidades para pintar marcadores reales.
    } catch (error) {
        console.error('Error cargando telemetría SmartMap:', error);
    }
}

function _alertaCardHtml(alerta) {
    var severidad = (alerta.severidad || 'media').toLowerCase();
    return '<article class="smartmap-alerta ' + severidad + '">' +
        '<div class="smartmap-alerta-head">' +
        '<strong>' + escaparHtml(alerta.titulo || 'Alerta') + '</strong>' +
        '<button class="map-button map-button-primary" style="padding:4px 10px;" onclick="atenderAlertaSmartMap(' + alerta.id + ')">Atender</button>' +
        '</div>' +
        '<p>' + escaparHtml(alerta.mensaje || '') + '</p>' +
        '<p style="font-size:11px; margin-top:4px; color:#64748b;">Severidad: ' + escaparHtml(severidad) + ' | ' + escaparHtml(alerta.creada_en || '--') + '</p>' +
        '</article>';
}

async function cargarAlertasSmartMap() {
    if (!slotId) return;
    var contenedor = document.getElementById('smartmap-alertas-lista');
    if (!puedeVerAlertas) {
        if (contenedor) contenedor.innerHTML = '<p class="smartmap-empty">Sin permiso para ver alertas.</p>';
        _setText('smartmap-kpi-alertas', '0');
        return;
    }
    try {
        var response = await fetch('/api/smartmap/alertas/' + slotId + '?limite=20', {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) {
                if (contenedor) contenedor.innerHTML = '<p class="smartmap-empty">Sin permiso para ver alertas.</p>';
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        var data = await response.json();
        var alertas = data.alertas || [];
        _setText('smartmap-kpi-alertas', String(alertas.length));

        if (!contenedor) return;
        if (!alertas.length) {
            contenedor.innerHTML = '<p class="smartmap-empty">No hay alertas activas.</p>';
            return;
        }
        contenedor.innerHTML = alertas.map(_alertaCardHtml).join('');
    } catch (error) {
        console.error('Error cargando alertas SmartMap:', error);
        if (contenedor) contenedor.innerHTML = '<p class="smartmap-empty">Error cargando alertas.</p>';
    }
}

function _reglaCardHtml(regla) {
    var estadoTexto = regla.activa ? 'Activa' : 'Inactiva';
    var estadoClase = regla.activa ? 'estado-activa' : 'estado-inactiva';
    var textoToggle = regla.activa ? 'Desactivar' : 'Activar';

    return '<article class="smartmap-regla">' +
        '<div>' +
        '<strong>' + escaparHtml(regla.nombre) + '</strong><br>' +
        '<small>Tipo: ' + escaparHtml(regla.tipo) + ' | Umbral: ' + Number(regla.umbral).toFixed(1) + ' | Severidad: ' + escaparHtml(regla.severidad) + '</small><br>' +
        '<small class="' + estadoClase + '">' + estadoTexto + '</small>' +
        '</div>' +
        '<button class="map-button map-button-warning" style="padding:6px 10px;" onclick="toggleReglaSmartMap(' + regla.id + ', ' + (!regla.activa) + ')">' + textoToggle + '</button>' +
        '</article>';
}

async function cargarReglasSmartMap() {
    if (!slotId) return;
    var contenedor = document.getElementById('smartmap-reglas-lista');
    try {
        var response = await fetch('/api/smartmap/reglas/' + slotId, {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) {
                if (contenedor) contenedor.innerHTML = '<p class="smartmap-empty">Sin permiso para ver reglas.</p>';
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        var data = await response.json();
        var reglas = data.reglas || [];
        if (!contenedor) return;

        if (!reglas.length) {
            contenedor.innerHTML = '<p class="smartmap-empty">No hay reglas configuradas.</p>';
            return;
        }

        contenedor.innerHTML = reglas.map(_reglaCardHtml).join('');
    } catch (error) {
        console.error('Error cargando reglas SmartMap:', error);
        if (contenedor) contenedor.innerHTML = '<p class="smartmap-empty">Error cargando reglas.</p>';
    }
}

function _tipoAlertaHtml(tipo) {
    return '<article class="smartmap-regla">' +
        '<div>' +
        '<strong>' + escaparHtml(tipo.nombre) + '</strong><br>' +
        '<small>' + escaparHtml(tipo.descripcion || '') + '</small><br>' +
        '<span class="smartmap-tipo-alerta-badge">' + (tipo.activa ? 'Activa' : 'Inactiva') + '</span>' +
        '</div>' +
        '<button class="map-button map-button-warning" style="padding:6px 10px;" onclick="eliminarTipoAlerta(' + tipo.id + ')">Eliminar</button>' +
        '</article>';
}

async function cargarTiposAlerta() {
    var contenedor = document.getElementById('tipos-alerta-lista');
    if (!contenedor) return;

    try {
        var response = await fetch('/api/smartmap/tipos-alerta', {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) {
                contenedor.innerHTML = '<p class="smartmap-empty">Sin permiso para ver tipos de alerta.</p>';
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        var data = await response.json();
        var tipos = data.tipos || [];
        if (!tipos.length) {
            contenedor.innerHTML = '<p class="smartmap-empty">No hay tipos de alerta.</p>';
            return;
        }

        contenedor.innerHTML = tipos.map(_tipoAlertaHtml).join('');
    } catch (error) {
        console.error('Error cargando tipos de alerta:', error);
        contenedor.innerHTML = '<p class="smartmap-empty">Error cargando tipos de alerta.</p>';
    }
}

async function crearTipoAlerta(event) {
    event.preventDefault();
    var nombre = document.getElementById('tipo-alerta-nombre').value.trim();
    var descripcion = document.getElementById('tipo-alerta-descripcion').value.trim();
    var btn = document.getElementById('btnCrearTipoAlerta');

    if (!nombre) {
        alert('Escribe el nombre del tipo de alerta.');
        return;
    }

    var original = btn ? btn.textContent : '';
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Creando...';
    }

    try {
        var response = await fetch('/api/smartmap/tipos-alerta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ nombre: nombre, descripcion: descripcion })
        });

        var data = await response.json();
        if (!response.ok) {
            alert(data.error || 'No se pudo crear el tipo de alerta.');
            return;
        }

        document.getElementById('tipo-alerta-nombre').value = '';
        document.getElementById('tipo-alerta-descripcion').value = '';
        await cargarTiposAlerta();
    } catch (error) {
        console.error('Error creando tipo de alerta:', error);
        alert('No se pudo crear el tipo de alerta.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = original || 'Crear Tipo';
        }
    }
}

async function eliminarTipoAlerta(tipoId) {
    if (!confirm('¿Eliminar este tipo de alerta?')) return;
    try {
        var response = await fetch('/api/smartmap/tipos-alerta/' + tipoId, {
            method: 'DELETE',
            headers: { 'Accept': 'application/json' }
        });

        var data = await response.json();
        if (!response.ok) {
            alert(data.error || 'No se pudo eliminar el tipo de alerta.');
            return;
        }

        await cargarTiposAlerta();
    } catch (error) {
        console.error('Error eliminando tipo de alerta:', error);
        alert('No se pudo eliminar el tipo de alerta.');
    }
}

async function crearReglaSmartMap(event) {
    event.preventDefault();
    if (!slotId) return;

    var nombre = document.getElementById('regla-nombre').value.trim();
    var tipo = document.getElementById('regla-tipo').value;
    var umbral = Number(document.getElementById('regla-umbral').value);
    var severidad = document.getElementById('regla-severidad').value;
    var btn = document.getElementById('btnCrearRegla');

    if (!nombre || Number.isNaN(umbral)) {
        alert('Completa nombre y umbral válidos.');
        return;
    }

    var original = btn ? btn.textContent : '';
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Creando...';
    }

    try {
        var response = await fetch('/api/smartmap/reglas/' + slotId, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                nombre: nombre,
                tipo: tipo,
                umbral: umbral,
                severidad: severidad
            })
        });

        if (!response.ok) {
            if (response.status === 403) {
                alert('No tienes permiso para crear reglas.');
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        document.getElementById('regla-nombre').value = '';
        document.getElementById('regla-umbral').value = '';
        await cargarReglasSmartMap();
    } catch (error) {
        console.error('Error creando regla SmartMap:', error);
        alert('No se pudo crear la regla.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = original || 'Crear Regla';
        }
    }
}

async function toggleReglaSmartMap(reglaId, activa) {
    try {
        var response = await fetch('/api/smartmap/reglas/' + reglaId + '/toggle', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ activa: activa })
        });

        if (!response.ok) {
            if (response.status === 403) {
                alert('No tienes permiso para editar reglas.');
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        await cargarReglasSmartMap();
    } catch (error) {
        console.error('Error actualizando regla SmartMap:', error);
        alert('No se pudo actualizar la regla.');
    }
}

async function simularMovimientoSmartMap(btn) {
    if (!slotId) return;
    var boton = btn || document.getElementById('btnSimularSmartMap');
    var textoOriginal = boton ? boton.textContent : '';
    if (boton) {
        boton.disabled = true;
        boton.textContent = 'Simulando...';
    }

    try {
        var response = await fetch('/api/smartmap/simular/' + slotId, {
            method: 'POST',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) {
                alert('No tienes permiso para simular telemetría.');
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        await cargarTelemetriaSmartMap();
        await cargarAlertasSmartMap();
    } catch (error) {
        console.error('Error simulando telemetría SmartMap:', error);
        alert('No se pudo ejecutar la simulación.');
    } finally {
        if (boton) {
            boton.disabled = false;
            boton.textContent = textoOriginal || 'Simular Telemetría';
        }
    }
}

async function atenderAlertaSmartMap(alertaId) {
    try {
        var response = await fetch('/api/smartmap/alertas/' + alertaId + '/atender', {
            method: 'PATCH',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 403) {
                alert('No tienes permiso para atender alertas.');
                return;
            }
            throw new Error('HTTP ' + response.status);
        }

        await cargarAlertasSmartMap();
    } catch (error) {
        console.error('Error atendiendo alerta SmartMap:', error);
        alert('No se pudo atender la alerta.');
    }
}

async function probarCorreoSmartMap(btn) {
    if (!slotId) return;

    var boton = btn || document.getElementById('btnPruebaCorreo');
    var textoOriginal = boton ? boton.textContent : '';
    if (boton) {
        boton.disabled = true;
        boton.textContent = 'Enviando...';
    }

    try {
        var response = await fetch('/api/smartmap/notificaciones/email/prueba/' + slotId, {
            method: 'POST',
            headers: { 'Accept': 'application/json' }
        });

        var data = await response.json();

        if (!response.ok) {
            alert(data.mensaje || data.error || 'No se pudo enviar el correo de prueba.');
            return;
        }

        alert('Correo de prueba enviado a: ' + (data.destinatarios || []).join(', '));
    } catch (error) {
        console.error('Error enviando correo de prueba:', error);
        alert('No se pudo enviar el correo de prueba.');
    } finally {
        if (boton) {
            boton.disabled = false;
            boton.textContent = textoOriginal || 'Probar Correo';
        }
    }
}

function iniciarSmartMapFase2() {
    if (!slotId) return;
    cargarTelemetriaSmartMap();
    cargarAlertasSmartMap();
    cargarReglasSmartMap();
    cargarTiposAlerta();
    setInterval(cargarTelemetriaSmartMap, 15000);
    setInterval(cargarAlertasSmartMap, 20000);
    setInterval(cargarReglasSmartMap, 45000);
    setInterval(cargarTiposAlerta, 60000);
}

iniciarSmartMapFase2();

// Variables de entorno recuperadas mediante HTML dataset
var mapContainer = document.getElementById('map');
var slotId = mapContainer.dataset.slotId;
var puedeAgregar = mapContainer.dataset.puedeAgregar === 'true';
var puedeEditar = mapContainer.dataset.puedeEditar === 'true';
var esAdmin = mapContainer.dataset.esAdmin === 'true';
var puedeMarcarTareas = mapContainer.dataset.puedeMarcarTareas === 'true';
var puedeAgregarTareas = mapContainer.dataset.puedeAgregarTareas === 'true';
var usuarioActual = mapContainer.dataset.usuarioActual;
var usuariosLista = mapContainer.dataset.usuariosLista ? JSON.parse(mapContainer.dataset.usuariosLista) : [];
var puedeVerCostos = mapContainer.dataset.puedeVerCostos === 'true';

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
        .replace(/"/g, '&quot;');
}

function construirOpcionesHTML(opciones, valorSeleccionado) {
    return opciones.map(function (opcion) {
        var seleccionado = opcion.valor === valorSeleccionado ? 'selected' : '';
        return `<option value="${escaparHtml(opcion.valor)}" ${seleccionado}>${opcion.texto}</option>`;
    }).join('');
}

function actualizarPopupActual(mutador) {
    if (!capaActualPopup) return;
    mutador(capaActualPopup);
    registrarCambio();
    guardarAutomaticamente();
    capaActualPopup.setPopupContent(crearContenidoPopup(capaActualPopup));
}

function tienePermisoDeGuardado() {
    return puedeAgregar || puedeEditar;
}

function crearFilaDosColumnas(columnaIzquierda, columnaDerecha) {
    return `<div style="display: flex; gap: 5px; margin-bottom:8px;">
                <div style="flex: 1;">${columnaIzquierda}</div>
                <div style="flex: 1;">${columnaDerecha}</div>
             </div>`;
}

function toggleDibujo() {
    if (!puedeAgregar) return;
    var btn = document.getElementById('btnCrearLote');
    if (btn.innerText === "Crear Lote") {
        polygonDrawer.enable();
        btn.innerText = "Finalizar Lote (Cancelar)";
        btn.style.backgroundColor = "#dc3545";
    } else {
        polygonDrawer.disable();
        btn.innerText = "Crear Lote";
        btn.style.backgroundColor = "#28a745";
    }
}

// --- SISTEMA DEL GLOBO (POPUP) Y HOVER ---
function prepararCapa(layer) {
    if (!layer.feature) layer.feature = { type: 'Feature', properties: {} };

    if (layer.feature.properties.description) {
        try {
            // Extraemos las tareas y responsable ocultos
            var datosExtras = JSON.parse(layer.feature.properties.description);
            // Los fusionamos SIN borrar el "name" que Omnivore ya rescató del KML
            Object.assign(layer.feature.properties, datosExtras);
        } catch (e) { }
    }

    var p = layer.feature.properties;

    // IMPORTANTE: Evaluamos 'name', que es la traducción automática del <name> del KML
    if (!p.name) p.name = "Nuevo Lote";
    if (!p.responsable) p.responsable = "";
    if (!p.tareas) p.tareas = [];

    // Efecto Hover
    layer.on('mouseover', function () { this.setStyle({ fillOpacity: 0.8, weight: 3 }); });
    layer.on('mouseout', function () { this.setStyle({ fillOpacity: 0.5, weight: 2 }); });

    // Conectar el Globo emergente
    layer.bindPopup(crearContenidoPopup(layer));
    layer.on('popupopen', function () { capaActualPopup = layer; });
    layer.on('popupclose', function () { capaActualPopup = null; });
}

function crearContenidoPopup(layer) {
    var props = layer.feature.properties;
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

    html += `<label style="${estilosPopup.etiqueta}">Tareas:</label>
             <ul style="padding-left: 0; list-style: none; margin-top: 5px; margin-bottom: 15px;">`;

    props.tareas.forEach(function (tarea, index) {
        var checkAttr = tarea.completada ? 'checked' : '';
        var disableCheck = puedeMarcar ? '' : 'disabled';
        var estiloTexto = tarea.completada ? 'text-decoration: line-through; color: #aaa;' : 'color: #333;';

        html += `<li style="margin-bottom: 8px; display: flex; align-items: center;">
                    <input type="checkbox" ${checkAttr} ${disableCheck} onchange="toggleTarea(${index}, this.checked)" style="margin-right: 8px; cursor: pointer;">
                    <span style="flex: 1; ${estiloTexto}">${escaparHtml(tarea.texto)}</span>`;

        if (puedeGestionarTareas) {
            html += ` <button onclick="eliminarTarea(${index})" style="color: white; background: #dc3545; border: none; cursor: pointer; border-radius: 3px; padding: 2px 6px; font-size: 10px; margin-left: 5px;">X</button>`;
        }
        html += `</li>`;
    });
    html += `</ul>`;

    if (puedeGestionarTareas) {
        html += `<div style="display: flex; gap: 5px; border-top: 1px solid #eee; padding-top: 10px; margin-bottom: 15px;">
                    <input type="text" id="inputNuevaTarea" placeholder="Nueva tarea..." style="flex: 1; padding: 5px;">
                    <button onclick="agregarTarea()" style="padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer;">Add</button>
                </div>`;
    }

    html += `<div style="background: #f9f9f9; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">
                <h5 style="margin-top: 0; margin-bottom: 10px; color: #444;">Datos Agrícolas</h5>`;

    if (esAdmin || puedeVerCostos) {
        html += `<label style="${estilosPopup.etiquetaPequena}">Costo Estimado ($):</label>
                 <input type="number" value="${escaparHtml(props.costo || 0)}" onchange="actualizarDato('costo', this.value)" style="${estilosPopup.input}">`;
    }

    html += `<label style="${estilosPopup.etiquetaPequena}">Variedad de Caña:</label>
             <input type="text" placeholder="Ej. CP 72-2086" value="${escaparHtml(props.variedad_cana || '')}" onchange="actualizarDato('variedad_cana', this.value)" style="${estilosPopup.input}">`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Edad de Cultivo (Meses):</label>
             <input type="number" min="0" value="${escaparHtml(props.edad_cultivo || '')}" onchange="actualizarDato('edad_cultivo', this.value)" style="${estilosPopup.input}">`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Suelo:</label>
             <select onchange="actualizarDato('tipo_suelo', this.value)" style="${estilosPopup.input}">
                 ${construirOpcionesHTML(opcionesSuelo, props.tipo_suelo || '')}
             </select>`;

    html += crearFilaDosColumnas(
        `<label style="${estilosPopup.etiquetaPequena}">Siembra:</label>
         <input type="date" value="${escaparHtml(props.fecha_siembra || '')}" onchange="actualizarDato('fecha_siembra', this.value)" style="${estilosPopup.input}">`,
        `<label style="${estilosPopup.etiquetaPequena}">Últ. Aplic.:</label>
         <input type="date" value="${escaparHtml(props.ultima_aplicacion || '')}" onchange="actualizarDato('ultima_aplicacion', this.value)" style="${estilosPopup.input}">`
    );

    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Riego:</label>
             <select onchange="actualizarDato('tipo_riego', this.value)" style="${estilosPopup.input}">
                 ${construirOpcionesHTML(opcionesRiego, props.tipo_riego || '')}
             </select>`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Rendimiento Esperado (TCH):</label>
             <input type="number" step="0.1" value="${escaparHtml(props.rendimiento_tch || '')}" onchange="actualizarDato('rendimiento_tch', this.value)" style="${estilosPopup.input}">`;

    html += crearFilaDosColumnas(
        `<label style="${estilosPopup.etiquetaPequena}">Maleza:</label>
         <select onchange="actualizarDato('nivel_maleza', this.value)" style="${estilosPopup.input}">
             ${construirOpcionesHTML(opcionesMaleza, props.nivel_maleza || '')}
         </select>`,
        `<label style="${estilosPopup.etiquetaPequena}">Humedad:</label>
         <select onchange="actualizarDato('nivel_humedad', this.value)" style="${estilosPopup.input}">
             ${construirOpcionesHTML(opcionesHumedad, props.nivel_humedad || '')}
         </select>`
    );

    html += `<label style="${estilosPopup.etiquetaPequena}">Estatus Sanitario:</label>
             <select onchange="actualizarDato('estatus_sanitario', this.value)" style="${estilosPopup.input}">
                 ${construirOpcionesHTML(opcionesSanidad, props.estatus_sanitario || 'Sano')}
             </select>`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Tipo de Fertilización:</label>
             <input type="text" placeholder="Ej. Urea, NPK..." value="${escaparHtml(props.tipo_fertilizacion || '')}" onchange="actualizarDato('tipo_fertilizacion', this.value)" style="${estilosPopup.input}">`;

    html += `<label style="${estilosPopup.etiquetaPequena}">Incidencias / Notas / Historial:</label>
             <textarea onchange="actualizarDato('incidencias', this.value)" style="${estilosPopup.input} height:60px;">${escaparHtml(props.incidencias || '')}</textarea>`;

    html += `</div></div>`;
    return html;
}

// --- FUNCIONES INTERNAS DEL GLOBO ---
function actualizarDato(clave, valor) {
    actualizarPopupActual(function (layer) {
        layer.feature.properties[clave] = valor;
    });
}

function toggleTarea(index, completada) {
    actualizarPopupActual(function (layer) {
        layer.feature.properties.tareas[index].completada = completada;
    });
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
            completada: false
        });
    });
}

// --- EVENTOS DEL MAPA ---
map.on(L.Draw.Event.CREATED, function (event) {
    var layer = event.layer;
    prepararCapa(layer); // Le inyectamos la lógica del globo
    drawnItems.addLayer(layer);
    registrarCambio();

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

// Autoguardado y controles de Leaflet
function registrarCambio() {
    if (!cargaInicialCompleta) return;
    cambiosPendientes = true;
    actualizarEstado('Cambios pendientes de guardado');
}

function actualizarEstado(texto) {
    var estado = document.getElementById('estadoGuardado');
    if (estado) estado.innerText = texto;
}

function guardarAutomaticamente() {
    if (!slotId || !cambiosPendientes || guardando) return;
    if (!tienePermisoDeGuardado()) return;

    guardando = true;
    actualizarEstado('Guardando...');

    fetch('/api/guardar_kml/' + slotId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(drawnItems.toGeoJSON())
    })
        .then(function (response) {
            if (!response.ok) throw new Error('No se pudo guardar el mapa');
            return response.json();
        })
        .then(function () {
            cambiosPendientes = false;
            actualizarEstado('Guardado automáticamente');
        })
        .catch(function (error) {
            console.error('Error al guardar:', error);
            actualizarEstado('Error al guardar');
        })
        .finally(function () { guardando = false; });
}

function guardarManual() {
    if (!slotId || guardando) return;
    if (!tienePermisoDeGuardado()) return;

    cambiosPendientes = true;
    guardarAutomaticamente();

    var btn = document.getElementById('btnGuardarManual');
    if (btn) {
        var textoOriginal = btn.innerText;
        btn.innerText = "¡Guardado!";
        btn.style.backgroundColor = "#20c997";
        setTimeout(function () {
            btn.innerText = textoOriginal;
            btn.style.backgroundColor = "#17a2b8";
        }, 2000);
    }
}

var drawControl = new L.Control.Draw({
    edit: puedeEditar ? { featureGroup: drawnItems, remove: true } : false,
    draw: false
});
if (puedeEditar) map.addControl(drawControl);

map.on('draw:edited', registrarCambio);
map.on('draw:deleted', registrarCambio);

setInterval(guardarAutomaticamente, 60000);

// Auto-carga desde la BD
if (slotId) {
    var urlAPI = "/api/kml/" + slotId;
    var kmlLayer = omnivore.kml(urlAPI)
        .on('ready', function () {
            kmlLayer.eachLayer(function (layer) {
                prepararCapa(layer); // Inyectamos la lógica a los polígonos ya guardados
                drawnItems.addLayer(layer);
            });
            if (drawnItems.getLayers().length) {
                map.fitBounds(drawnItems.getBounds());
            }
            cargaInicialCompleta = true;
            actualizarEstado('Mapa cargado');
        })
        .on('error', function () {
            cargaInicialCompleta = true;
            actualizarEstado('Mapa listo');
        });
} else {
    cargaInicialCompleta = true;
}

// Vigilante de permisos
setInterval(function () {
    fetch('/api/mis_permisos')
        .then(response => response.json())
        .then(data => {
            if (!data.logeado) { window.location.href = '/'; return; }
            if (!data.puede_agregar && puedeAgregar) {
                puedeAgregar = false;
                var btn = document.getElementById('btnCrearLote');
                if (btn) {
                    polygonDrawer.disable();
                    btn.innerText = "Crear Lote (sin permiso)";
                    btn.style.backgroundColor = "#adb5bd";
                    btn.disabled = true;
                    btn.style.cursor = "not-allowed";
                }
            }
            if (!data.puede_editar && puedeEditar) {
                puedeEditar = false;
                if (drawControl) map.removeControl(drawControl);
            }
        })
        .catch(error => console.error("Error validando permisos:", error));
}, 60000);

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
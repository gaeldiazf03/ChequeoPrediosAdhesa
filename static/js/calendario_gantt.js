// =============================================================================
// CALENDARIO Y GANTT - calendario_gantt.js
// =============================================================================

let calendario = null;
let tareasDelLote = [];
let loteActual = null;

// ============= MANEJO DE TABS =============
function mostrarTab(tabName) {
    // Ocultar todos los tabs
    document.querySelectorAll('.sidebar-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.sidebar-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Mostrar el tab seleccionado
    const trigger = arguments[1] || (window.event ? window.event.target : null);
    const tab = document.getElementById(`tab-${tabName}`);
    if (tab) {
        tab.classList.add('active');
        if (trigger && trigger.classList) {
            trigger.classList.add('active');
        }
    }

    // Inicializar si es necesario
    if (tabName === 'visor' && !calendario) {
        inicializarCalendario();
    }
    if (tabName === 'gantt') {
        inicializarGantt();
    }
}

// ============= CALENDARIO (FullCalendar) =============
function inicializarCalendario() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl || calendario) return;

    calendario = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'es',
        selectable: true,
        editable: true,
        eventStartEditable: true,
        eventDurationEditable: true,
        eventResizableFromStart: true,
        selectMirror: true,
        unselectAuto: false,
        dayMaxEvents: true,
        height: 'auto',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek'
        },
        events: cargarEventosDelCalendario,
        select: function(info) {
            seleccionarRangoFechas(info.startStr, info.endStr);
            abrirDialogoNuevaActividad(info.startStr, info.endStr);
        },
        dateClick: function(info) {
            var target = info.jsEvent && info.jsEvent.target ? info.jsEvent.target : null;
            if (target && target.classList && target.classList.contains('fc-day-checkbox')) {
                toggleDateSelection(info.dateStr, info.jsEvent);
                return;
            }
            abrirDialogoNuevaActividad(info.dateStr);
        },
        eventClick: function(info) {
            editarActividad(info.event);
        },
        eventDrop: function(info) {
            actualizarTareaDesdeEvento(info.event);
        },
        eventResize: function(info) {
            actualizarTareaDesdeEvento(info.event);
        },
        eventContent: function(arg) {
            var title = arg.event.title || 'Sin título';
            var estado = (arg.event.extendedProps && arg.event.extendedProps.estado) || 'no_iniciada';
            return {
                html: `<div class="fc-task-chip fc-task-${escaparCss(estado)}"><span class="fc-task-title">${escaparHtml(title)}</span></div>`
            };
        },
        dayCellDidMount: function(info) {
            try {
                var box = document.createElement('input');
                box.type = 'checkbox';
                box.className = 'fc-day-checkbox';
                box.dataset.date = info.dateStr;
                box.addEventListener('click', function(ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    toggleDateSelection(info.dateStr, ev);
                });
                if (window.calendarSelectedDates && window.calendarSelectedDates.has(info.dateStr)) box.checked = true;
                info.el.style.position = 'relative';
                var dayTop = info.el.querySelector('.fc-daygrid-day-top') || info.el;
                dayTop.style.position = 'relative';
                dayTop.appendChild(box);

                var dayNumber = info.el.querySelector('.fc-daygrid-day-number');
                if (dayNumber) {
                    dayNumber.style.paddingLeft = '22px';
                    dayNumber.style.display = 'inline-block';
                }
            } catch(e){ console.warn('dayCellDidMount error', e); }
        }
    });

    calendario.render();
    _syncSelectionUI();
        // actualizar select de padres al abrir lote
        try {
            var sel = document.getElementById('parent-select');
            if (sel && typeof window.getPrediosPadreList === 'function') {
                // limpiar manteniendo la primera opción
                while (sel.options.length > 1) sel.remove(1);
                var padres = window.getPrediosPadreList() || [];
                padres.forEach(function(p){ var opt = document.createElement('option'); opt.value = p; opt.textContent = p; sel.appendChild(opt); });
            }
        } catch(e) {}
}

// Selection helpers
window.calendarSelectedDates = window.calendarSelectedDates || new Set();
window._calendarLastSelectedDate = window._calendarLastSelectedDate || null;
window._calendarSelectionOrder = window._calendarSelectionOrder || [];

function _syncSelectionUI() {
    try {
        document.querySelectorAll('.fc-day-checkbox').forEach(function(cb){
            cb.checked = window.calendarSelectedDates.has(cb.dataset.date);
        });

        document.querySelectorAll('.fc-daygrid-day').forEach(function(dayEl){
            var dateAttr = dayEl.getAttribute('data-date');
            if (!dateAttr) return;
            if (window.calendarSelectedDates.has(dateAttr)) dayEl.classList.add('fc-day-selected');
            else dayEl.classList.remove('fc-day-selected');
        });

        document.querySelectorAll('.fc-timegrid-col').forEach(function(colEl){
            var dateAttr = colEl.getAttribute('data-date');
            if (!dateAttr) return;
            if (window.calendarSelectedDates.has(dateAttr)) colEl.classList.add('fc-day-selected');
            else colEl.classList.remove('fc-day-selected');
        });
    } catch(e){}
}

function _resetSelectionTo(dateStr) {
    window.calendarSelectedDates.clear();
    window.calendarSelectedDates.add(dateStr);
    window._calendarSelectionOrder = [dateStr];
    window._calendarLastSelectedDate = dateStr;
    _syncSelectionUI();
    updateTaskEditorSelectionUI();
}

function _renderTaskTable() {
    var tbody = document.querySelector('#tasks-table tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    var tareas = Array.isArray(tareasDelLote) ? tareasDelLote : [];
    if (!tareas.length) {
        var emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="5" style="color:#64748b; text-align:center; padding:14px;">No hay actividades para mostrar</td>';
        tbody.appendChild(emptyRow);
        return;
    }

    tareas.forEach(function(tarea) {
        var row = document.createElement('tr');
        var duracion = '-';
        try {
            if (tarea.fecha_inicio && tarea.fecha_fin) {
                var inicio = new Date(tarea.fecha_inicio + 'T00:00:00');
                var fin = new Date(tarea.fecha_fin + 'T00:00:00');
                if (!isNaN(inicio.getTime()) && !isNaN(fin.getTime())) {
                    var dias = Math.max(1, Math.round((fin - inicio) / 86400000) + 1);
                    duracion = dias + ' días';
                }
            }
        } catch(e) {}

        row.innerHTML = `
            <td>${escaparHtml(tarea.texto || 'Sin título')}</td>
            <td>${escaparHtml(tarea.observaciones || tarea.incidencias || '')}</td>
            <td>${duracion}</td>
            <td>${escaparHtml(tarea.fecha_inicio || '')}</td>
            <td>${escaparHtml((tarea.fecha_inicio || '') + ' → ' + (tarea.fecha_fin || ''))}</td>
        `;
        tbody.appendChild(row);
    });
}

function _renderTaskTable() {
    var tbody = document.querySelector('#tasks-table tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    var tareas = Array.isArray(tareasDelLote) ? tareasDelLote : [];
    if (!tareas.length) {
        var emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="5" style="color:#64748b; text-align:center; padding:14px;">No hay actividades para mostrar</td>';
        tbody.appendChild(emptyRow);
        return;
    }

    tareas.forEach(function(tarea) {
        var row = document.createElement('tr');
        var duracion = '-';
        try {
            if (tarea.fecha_inicio && tarea.fecha_fin) {
                var inicio = new Date(tarea.fecha_inicio + 'T00:00:00');
                var fin = new Date(tarea.fecha_fin + 'T00:00:00');
                if (!isNaN(inicio.getTime()) && !isNaN(fin.getTime())) {
                    var dias = Math.max(1, Math.round((fin - inicio) / 86400000) + 1);
                    duracion = dias + ' días';
                }
            }
        } catch(e) {}

        row.innerHTML = `
            <td>${escaparHtml(tarea.texto || 'Sin título')}</td>
            <td>${escaparHtml(tarea.observaciones || tarea.incidencias || '')}</td>
            <td>${duracion}</td>
            <td>${escaparHtml(tarea.fecha_inicio || '')}</td>
            <td>${escaparHtml((tarea.fecha_inicio || '') + ' → ' + (tarea.fecha_fin || ''))}</td>
        `;
        tbody.appendChild(row);
    });
}

function _setSelectionRange(startStr, endStrExclusive) {
    window.calendarSelectedDates.clear();
    window._calendarSelectionOrder = [];

    var start = new Date(startStr);
    var end = new Date(endStrExclusive);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) return;
    if (start > end) {
        var tmp = start;
        start = end;
        end = tmp;
    }

    var cur = new Date(start);
    while (cur < end) {
        var d = cur.toISOString().split('T')[0];
        window.calendarSelectedDates.add(d);
        window._calendarSelectionOrder.push(d);
        cur.setDate(cur.getDate() + 1);
    }

    window._calendarLastSelectedDate = window._calendarSelectionOrder.length ? window._calendarSelectionOrder[window._calendarSelectionOrder.length - 1] : null;
    _syncSelectionUI();
    updateTaskEditorSelectionUI();
}

function seleccionarRangoFechas(startStr, endStrExclusive) {
    _setSelectionRange(startStr, endStrExclusive);
}

function toggleDateSelection(dateStr, jsEvent) {
    try {
        var shift = jsEvent && jsEvent.shiftKey;
        if (shift && window._calendarLastSelectedDate) {
            // select range between last and dateStr
            var a = new Date(window._calendarLastSelectedDate);
            var b = new Date(dateStr);
            if (a > b) { var tmp = a; a = b; b = tmp; }
            var cur = new Date(a);
            while (cur <= b) {
                var d = cur.toISOString().split('T')[0];
                window.calendarSelectedDates.add(d);
                if (window._calendarSelectionOrder.indexOf(d) === -1) window._calendarSelectionOrder.push(d);
                cur.setDate(cur.getDate() + 1);
            }
            window._calendarLastSelectedDate = dateStr;
        } else {
            if (window.calendarSelectedDates.has(dateStr)) {
                window.calendarSelectedDates.delete(dateStr);
                window._calendarSelectionOrder = window._calendarSelectionOrder.filter(function(d){ return d !== dateStr; });
            } else {
                window.calendarSelectedDates.add(dateStr);
                if (window._calendarSelectionOrder.indexOf(dateStr) === -1) window._calendarSelectionOrder.push(dateStr);
                window._calendarLastSelectedDate = dateStr;
            }
        }

        _syncSelectionUI();

        // Update task editor UI to reflect selection
        updateTaskEditorSelectionUI();
    } catch(e) { console.warn('toggleDateSelection error', e); }
}

function clearCalendarSelection() {
    window.calendarSelectedDates.clear();
    window._calendarLastSelectedDate = null;
    window._calendarSelectionOrder = [];
    document.querySelectorAll('.fc-day-checkbox').forEach(function(cb){ cb.checked = false; });
    document.querySelectorAll('.fc-daygrid-day.fc-day-selected, .fc-timegrid-col.fc-day-selected').forEach(function(el){ el.classList.remove('fc-day-selected'); });
    updateTaskEditorSelectionUI();
}

function getSelectedDateRange() {
    var arr = Array.from(window.calendarSelectedDates).sort();
    if (arr.length === 0) return null;
    return { start: arr[0], end: arr[arr.length-1], dates: arr };
}

function updateTaskEditorSelectionUI() {
    var editor = document.getElementById('task-editor');
    if (!editor) return;
    var sel = getSelectedDateRange();
    var extraHtml = '';
    if (sel) {
        extraHtml += `<div style="margin-bottom:8px;"><strong>Fechas seleccionadas:</strong> ${sel.start} ${sel.start!==sel.end? '→ ' + sel.end : ''} (${sel.dates.length} días)</div>`;
        // parent and child selects will be added by mostrarEditorTarea when saving
    }
    // Keep existing form if present: try to update a container
    var selectionContainer = document.getElementById('te-selection-info');
    if (!selectionContainer) {
        selectionContainer = document.createElement('div');
        selectionContainer.id = 'te-selection-info';
        editor.insertBefore(selectionContainer, editor.firstChild);
    }
    selectionContainer.innerHTML = extraHtml;
}

// Clear selection when clicking outside the calendar / editor area
document.addEventListener('click', function(ev){
    try {
        var target = ev.target;
        if (!target) return;
        var insideCalendar = !!target.closest('.fc');
        var insideEditor = !!target.closest('#task-editor');
        if (!insideCalendar && !insideEditor) {
            clearCalendarSelection();
        }
    } catch(e){}
});

function cargarEventosDelCalendario() {
    if (!loteActual) return [];

    // Obtener actividades del lote actual desde el GeoJSON
    let eventos = [];
    // Preferir drawnItems (estado actual) y si no existe, fallback a map._geojson
    let features = null;
    try {
        if (window.drawnItems && typeof window.drawnItems.toGeoJSON === 'function') {
            const geo = window.drawnItems.toGeoJSON();
            features = geo && geo.features ? geo : null;
        }
    } catch(e) { features = null; }

    if (!features) {
        try { features = window.map ? window.map._geojson : null; } catch(e) { features = null; }
    }

    if (features && features.features) {
        features.features.forEach(feature => {
            if ((feature.properties && feature.properties.name) === loteActual) {
                const tareas = (feature.properties && feature.properties.tareas) || [];
                tareas.forEach(tarea => {
                    const fechaInicio = tarea.fecha_inicio || new Date().toISOString().split('T')[0];
                    const fechaFin = tarea.fecha_fin || fechaInicio;
                    eventos.push({
                        id: tarea.id || Math.random(),
                        title: tarea.texto || 'Sin título',
                        start: fechaInicio,
                        end: sumarDiaISO(fechaFin),
                        allDay: true,
                        backgroundColor: obtenerColorPorEstado(tarea.estado),
                        extendedProps: tarea
                    });
                });
            }
        });
    }

    return eventos;
}

function obtenerColorPorEstado(estado) {
    const mapa = {
        'completada': '#10b981',
        'en_progreso': '#f59e0b',
        'pendiente': '#ef4444',
        'no_iniciada': '#94a3b8'
    };
    return mapa[estado] || '#94a3b8';
}

function abrirDialogoNuevaActividad(fechaInicio, fechaFinExclusiva) {
    var fechaFin = fechaFinExclusiva ? new Date(fechaFinExclusiva) : null;
    if (fechaFin && !isNaN(fechaFin.getTime())) {
        fechaFin.setDate(fechaFin.getDate() - 1);
    }
    mostrarEditorTarea(null, fechaInicio, fechaFin ? fechaFin.toISOString().split('T')[0] : fechaInicio);
}

function editarActividad(evento) {
    clearCalendarSelection();
    mostrarEditorTarea(evento.extendedProps);
}

function mostrarEditorTarea(tarea, fechaPrefill, fechaFinPrefill) {
    var editor = document.getElementById('task-editor');
    if (!editor) return;

    var isNew = !tarea || !tarea.id;
    var id = tarea && tarea.id ? tarea.id : `tarea-${Date.now()}`;
    var texto = tarea && tarea.texto ? tarea.texto : '';
    var fecha_inicio = tarea && tarea.fecha_inicio ? tarea.fecha_inicio : (fechaPrefill || new Date().toISOString().split('T')[0]);
    var fecha_fin = tarea && tarea.fecha_fin ? tarea.fecha_fin : (fechaFinPrefill || fechaPrefill || new Date().toISOString().split('T')[0]);
    var estado = tarea && tarea.estado ? tarea.estado : 'no_iniciada';

    editor.innerHTML = `
        <h4 style="margin-top:0;">${isNew ? 'Nueva actividad' : 'Editar actividad'}</h4>
        <div id="te-selection-placeholder"></div>
        <label>Nombre</label>
        <input id="te-texto" type="text" value="${escaparAtributo(texto)}">
        <label>Fecha inicio</label>
        <input id="te-fecha-inicio" type="date" value="${fecha_inicio}">
        <label>Fecha fin</label>
        <input id="te-fecha-fin" type="date" value="${fecha_fin}">
        <label>Estado</label>
        <select id="te-estado">
            <option value="no_iniciada" ${estado === 'no_iniciada' ? 'selected' : ''}>No iniciada</option>
            <option value="en_progreso" ${estado === 'en_progreso' ? 'selected' : ''}>En progreso</option>
            <option value="completada" ${estado === 'completada' ? 'selected' : ''}>Completada</option>
        </select>
        <div style="margin-top:8px; display:flex; gap:8px;">
            <button id="te-save" class="map-button map-button-primary">Guardar</button>
            <button id="te-cancel" class="map-button map-button-info">Cancelar</button>
            ${isNew ? '' : '<button id="te-delete" class="map-button map-button-warning">Eliminar</button>'}
        </div>
    `;

    // If there is a date selection, inject parent/child selectors
    try {
        var sel = getSelectedDateRange();
        if (sel) {
            var placeholder = document.getElementById('te-selection-placeholder');
            var padres = (typeof window.getPrediosPadreList === 'function') ? window.getPrediosPadreList() : [];
            var htmlSel = `<div style="margin-bottom:8px;"><strong>Asignar a:</strong><br>`;
            htmlSel += `<label>Predio padre</label><select id="te-target-parent"><option value="">(ninguno)</option>`;
            padres.forEach(function(p){ htmlSel += `<option value="${escaparHtml(p)}">${escaparHtml(p)}</option>`; });
            htmlSel += `</select>`;
            htmlSel += `<label>Lote hijo</label><select id="te-target-child"><option value="">(usar lote actual)</option></select>`;
            htmlSel += `</div>`;
            placeholder.innerHTML = htmlSel;

            // When parent changes, populate children
            document.getElementById('te-target-parent').onchange = function(){
                var p = this.value;
                var kids = (typeof window.getHijosDePadre === 'function') ? window.getHijosDePadre(p) : [];
                var selChild = document.getElementById('te-target-child');
                selChild.innerHTML = '<option value="">(usar lote actual)</option>' + kids.map(function(k){ return `<option value="${escaparHtml(k)}">${escaparHtml(k)}</option>`; }).join('');
            };
        }
    } catch(e) { console.warn('editor selection inject error', e); }

    document.getElementById('te-cancel').onclick = function(){ clearCalendarSelection(); editor.innerHTML = ''; };
    document.getElementById('te-save').onclick = function(){
        var nuevo = {
            id: id,
            texto: document.getElementById('te-texto').value || 'Sin título',
            fecha_inicio: document.getElementById('te-fecha-inicio').value,
            fecha_fin: document.getElementById('te-fecha-fin').value,
            estado: document.getElementById('te-estado').value,
            completada: (document.getElementById('te-estado').value === 'completada')
        };

        // If there is a calendar selection, use it to set dates and assign to selected lote
        var sel = getSelectedDateRange();
        if (sel) {
            nuevo.fecha_inicio = sel.start;
            nuevo.fecha_fin = sel.end;
        }

        // If the user selected a target child lote in the editor, assign directly to that lote
        var targetChild = document.getElementById('te-target-child');
        if (targetChild && targetChild.value) {
            var targetName = targetChild.value;
            var layer = (typeof buscarCapaPorNombre === 'function') ? buscarCapaPorNombre(targetName) : null;
            if (layer && layer.feature && layer.feature.properties) {
                if (!Array.isArray(layer.feature.properties.tareas)) layer.feature.properties.tareas = [];
                layer.feature.properties.tareas.push(nuevo);
            }
        } else {
            if (isNew) {
                tareasDelLote.push(nuevo);
            } else {
                var idx = tareasDelLote.findIndex(t => t.id === id);
                if (idx >= 0) tareasDelLote[idx] = nuevo;
                else tareasDelLote.push(nuevo);
            }
        }

        // Refrescar vistas
        if (calendario) calendario.refetchEvents();
        try { inicializarGantt(); } catch(e){}
        _renderTaskTable();
        try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e){}
        try { if (typeof guardarManual === 'function') guardarManual(); } catch(e){}
        if (typeof registrarCambio === 'function') registrarCambio();
        clearCalendarSelection();
        editor.innerHTML = '';
    };

    if (!isNew) {
        document.getElementById('te-delete').onclick = function(){
            var idx = tareasDelLote.findIndex(t => t.id === id);
            if (idx >= 0) tareasDelLote.splice(idx,1);
            if (calendario) calendario.refetchEvents();
            try { inicializarGantt(); } catch(e){}
            _renderTaskTable();
            try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e){}
            try { if (typeof guardarManual === 'function') guardarManual(); } catch(e){}
            if (typeof registrarCambio === 'function') registrarCambio();
            clearCalendarSelection();
            editor.innerHTML = '';
        };
    }
    // After rendering editor, update selection UI
    updateTaskEditorSelectionUI();
}

function actualizarTareaDesdeEvento(evento) {
    if (!evento || !evento.id) return;

    var idx = tareasDelLote.findIndex(function(t) { return String(t.id) === String(evento.id); });
    if (idx < 0) return;

    var start = evento.start ? evento.start.toISOString().split('T')[0] : tareasDelLote[idx].fecha_inicio;
    var endDate = evento.end ? new Date(evento.end) : new Date(evento.start || tareasDelLote[idx].fecha_fin || tareasDelLote[idx].fecha_inicio);
    if (evento.allDay !== false && evento.end) {
        endDate.setDate(endDate.getDate() - 1);
    }
    var end = endDate.toISOString().split('T')[0];

    tareasDelLote[idx].fecha_inicio = start;
    tareasDelLote[idx].fecha_fin = end;
    tareasDelLote[idx].texto = evento.title || tareasDelLote[idx].texto;
    tareasDelLote[idx].estado = (evento.extendedProps && evento.extendedProps.estado) || tareasDelLote[idx].estado || 'no_iniciada';

    try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e){}
    try { if (typeof guardarManual === 'function') guardarManual(); } catch(e){}
    if (typeof registrarCambio === 'function') registrarCambio();
    if (calendario) calendario.refetchEvents();
    try { inicializarGantt(); } catch(e){}
}

function escaparHtml(texto) {
    return String(texto || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escaparAtributo(texto) {
    return escaparHtml(texto).replace(/`/g, '&#96;');
}

function escaparCss(texto) {
    return String(texto || '').replace(/[^a-z0-9_-]/gi, '-');
}

function sumarDiaISO(fechaISO) {
    var fecha = new Date(fechaISO + 'T00:00:00');
    if (isNaN(fecha.getTime())) return fechaISO;
    fecha.setDate(fecha.getDate() + 1);
    return fecha.toISOString().split('T')[0];
}

// ============= DIAGRAMA DE GANTT =============
function inicializarGantt() {
    const ganttContainer = document.getElementById('gantt-container');
    if (!ganttContainer || !loteActual) return;

    // Limpiar contenedor
    ganttContainer.innerHTML = '';

    // Preparar datos para Gantt
    const tasks = tareasDelLote.map((tarea, idx) => ({
        id: tarea.id || `task-${idx}`,
        name: tarea.texto || 'Sin nombre',
        start: tarea.fecha_inicio,
        end: tarea.fecha_fin,
        progress: (tarea.estado === 'completada' ? 100 : 
                  tarea.estado === 'en_progreso' ? 50 : 0),
        dependencies: [],
        custom_class: `estado-${escaparCss(tarea.estado || 'no_iniciada')}`
    }));

    if (tasks.length === 0) {
        ganttContainer.innerHTML = '<p style="text-align: center; color: #94a3b8; padding: 20px;">No hay actividades para mostrar en Gantt</p>';
        return;
    }

    try {
        ganttContainer.classList.add('gantt-style-reference');
        const gantt = new Gantt(ganttContainer, tasks, {
            header_height: 60,
            column_width: 42,
            step: 24 * 60 * 60 * 1000,
            view_modes: ['Day', 'Week', 'Month'],
            bar_height: 24,
            bar_corner_radius: 5,
            arrow_curve: 5,
            padding: 20,
            view_mode: 'Month',
            date_format: 'YYYY-MM-DD',
            custom_popup_html: null,
            on_click: function(task) {
                console.log('Tarea seleccionada:', task);
            },
            on_date_change: function(task, start, end) {
                console.log('Fecha modificada:', task.name, start, end);
                // Actualizar en la lista local
                const idx = tareasDelLote.findIndex(t => t.id === task.id);
                if (idx >= 0) {
                    tareasDelLote[idx].fecha_inicio = start.toISOString().split('T')[0];
                    tareasDelLote[idx].fecha_fin = end.toISOString().split('T')[0];
                    try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e){}
                    guardarManual();
                }
            },
            on_progress_change: function(task, progress) {
                console.log('Progreso modificado:', task.name, progress);
                const idx = tareasDelLote.findIndex(t => t.id === task.id);
                if (idx >= 0) {
                    if (progress === 0) tareasDelLote[idx].estado = 'no_iniciada';
                    else if (progress === 100) tareasDelLote[idx].estado = 'completada';
                    else tareasDelLote[idx].estado = 'en_progreso';
                    try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e){}
                    guardarManual();
                }
            }
        });
    } catch (e) {
        console.warn('Error al inicializar Gantt:', e);
        ganttContainer.innerHTML = '<p style="color: #ef4444;">Error al mostrar diagrama de Gantt</p>';
    }
}

// ============= CLIMA =============
async function actualizarClima() {
    try {
        // Ubicación fija solicitada: Pánuco, Veracruz, México
        const lat = 22.0556;
        const lon = -98.1833;
        
        // Llamar a API abierta de clima (ej: Open-Meteo o similar)
        const response = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,precipitation_probability,weather_code&temperature_unit=celsius`);
        const data = await response.json();
        
        if (data.current) {
            const temp = Math.round(data.current.temperature_2m);
            const lluvia = data.current.precipitation_probability || 0;
            
            document.getElementById('temp-display').textContent = `${temp}°C`;
            document.getElementById('lluvia-display').textContent = `${lluvia}% lluvia`;
            actualizarIconoClima(data.current);
        }
    } catch (e) {
        console.warn('Error al obtener clima:', e);
        document.getElementById('temp-display').textContent = '--°C';
        document.getElementById('lluvia-display').textContent = '--% lluvia';
        actualizarIconoClima(null);
    }
}

// ============= FUNCIONES AUXILIARES =============
function volverAlterior() {
    if (window.history && window.history.length > 1) {
        window.history.back();
    } else {
        window.location.href = '/dashboard';
    }
}

function actualizarTareasDelLote(nombreLote, tareas) {
    loteActual = nombreLote;
    tareasDelLote = tareas || [];

    // Refrescar vistas si están abiertas
    if (calendario) {
        calendario.refetchEvents();
    }
    const ganttContainer = document.getElementById('gantt-container');
    if (ganttContainer) {
        // Siempre intentar inicializar/actualizar el Gantt cuando cambian las tareas
        try { inicializarGantt(); } catch(e) { console.warn('Inicializar Gantt error', e); }
    }
    _renderTaskTable();
        // actualizar select de padres cuando se cargan tareas
        try {
            var sel = document.getElementById('parent-select');
            if (sel && typeof window.getPrediosPadreList === 'function') {
                // limpiar manteniendo la primera opción
                while (sel.options.length > 1) sel.remove(1);
                var padres = window.getPrediosPadreList() || [];
                padres.forEach(function(p){ var opt = document.createElement('option'); opt.value = p; opt.textContent = p; sel.appendChild(opt); });
            }
        } catch(e) {}
}

// Exponer función que sincroniza tareas del calendario hacia las propiedades GeoJSON
window.syncTareasToFeatures = function() {
    try {
        if (!loteActual || !Array.isArray(tareasDelLote)) return;
        if (!window.drawnItems) return;

        window.drawnItems.eachLayer(function(layer){
            try {
                if (!layer.feature || !layer.feature.properties) return;
                if (String(layer.feature.properties.name) === String(loteActual)) {
                    // Clonar tareasDelLote para evitar referencias compartidas
                    layer.feature.properties.tareas = (tareasDelLote || []).map(function(t){ return Object.assign({}, t); });
                }
            } catch(e) { console.warn('syncTareasToFeatures error', e); }
        });
    } catch(e) { console.warn('syncTareasToFeatures fatal', e); }
};

// ============= INICIALIZACION =============
document.addEventListener('DOMContentLoaded', function() {
    inicializarCalendario();
    actualizarClima();
    
    // Actualizar clima cada 30 minutos
    setInterval(actualizarClima, 30 * 60 * 1000);
});
let coordenadasActuales = { lat: 22.0556, lon: -98.1833 }; // Panuco, Veracruz, Mexico
let cacheClima = { timestamp: 0, data: null };
const CACHE_DURACION = 5 * 60 * 1000; // 5 minutos

const ICONOS_CLIMA = {
    soleado: 'https://cdn.jsdelivr.net/gh/basmilius/weather-icons/production/fill/all/clear-day.svg',
    parcial: 'https://cdn.jsdelivr.net/gh/basmilius/weather-icons/production/fill/all/partly-cloudy-day.svg',
    nublado: 'https://cdn.jsdelivr.net/gh/basmilius/weather-icons/production/fill/all/overcast-day.svg',
    lluvia: 'https://cdn.jsdelivr.net/gh/basmilius/weather-icons/production/fill/all/rain.svg',
    tormenta: 'https://cdn.jsdelivr.net/gh/basmilius/weather-icons/production/fill/all/thunderstorms-rain.svg'
};

async function actualizarClima(lat = coordenadasActuales.lat, lon = coordenadasActuales.lon) {
    try {
        // Verificar caché
        const ahora = Date.now();
        if (cacheClima.timestamp && (ahora - cacheClima.timestamp) < CACHE_DURACION && 
            cacheClima.data && cacheClima.coords && 
            cacheClima.coords.lat === lat && cacheClima.coords.lon === lon) {
            // Usar datos del caché
            mostrarClima(cacheClima.data);
            return;
        }
        
        // Llamar a API abierta de clima (Open-Meteo - gratuita, sin autenticación)
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,precipitation_probability,weather_code&timezone=auto`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Guardar en caché
        cacheClima = {
            timestamp: ahora,
            data: data.current,
            coords: { lat, lon }
        };
        
        mostrarClima(data.current);
    } catch (e) {
        console.warn('Error al obtener clima:', e);
        mostrarClima(null);
    }
}

function mostrarClima(datos) {
    const tempEl = document.getElementById('temp-display');
    const lluviaEl = document.getElementById('lluvia-display');
    const iconoEl = document.getElementById('clima-icono');
    
    if (!tempEl || !lluviaEl || !iconoEl) return;
    
    if (datos && datos.temperature_2m !== undefined) {
        const temp = Math.round(datos.temperature_2m);
        const lluvia = datos.precipitation_probability || 0;
        
        tempEl.textContent = `${temp}°C`;
        lluviaEl.textContent = `${lluvia}% lluvia`;
        actualizarIconoClima(datos);
    } else {
        tempEl.textContent = '--°C';
        lluviaEl.textContent = '--% lluvia';
        actualizarIconoClima(null);
    }
}

function actualizarIconoClima(datos) {
    const iconoEl = document.getElementById('clima-icono');
    if (!iconoEl) return;

    const { src, alt } = obtenerIconoClima(datos);
    iconoEl.src = src;
    iconoEl.alt = alt;
    iconoEl.title = alt;
}

function obtenerIconoClima(datos) {
    if (!datos) {
        return {
            src: ICONOS_CLIMA.parcial,
            alt: 'Clima no disponible'
        };
    }

    const codigo = Number(datos.weather_code);
    const lluvia = Number(datos.precipitation_probability || 0);

    if ([95, 96, 99].includes(codigo)) {
        return { src: ICONOS_CLIMA.tormenta, alt: 'Tormenta' };
    }

    if (lluvia >= 40 || [51, 53, 55, 61, 63, 65, 80, 81, 82].includes(codigo)) {
        return { src: ICONOS_CLIMA.lluvia, alt: 'Lluvia' };
    }

    if ([3, 45, 48].includes(codigo)) {
        return { src: ICONOS_CLIMA.nublado, alt: 'Nublado' };
    }

    if ([0].includes(codigo)) {
        return { src: ICONOS_CLIMA.soleado, alt: 'Soleado' };
    }

    return { src: ICONOS_CLIMA.parcial, alt: 'Parcialmente nublado' };
}

function actualizarClimaDesdeFeature(layer) {
    if (!layer || !layer.feature || !layer.feature.geometry) return;
    
    try {
        const geom = layer.feature.geometry;
        let lat, lon;
        
        // Calcular centroide según tipo de geometría
        if (geom.type === 'Polygon' && geom.coordinates && geom.coordinates[0]) {
            const coords = geom.coordinates[0];
            let sumLat = 0, sumLon = 0;
            coords.forEach(coord => {
                sumLon += coord[0];
                sumLat += coord[1];
            });
            lon = sumLon / coords.length;
            lat = sumLat / coords.length;
        } else if (geom.type === 'Point' && geom.coordinates) {
            lon = geom.coordinates[0];
            lat = geom.coordinates[1];
        } else {
            return; // No se puede extraer coordenadas
        }
        
        // Mantener clima fijo en Pánuco (no cambiar por predio seleccionado)
        actualizarClima();
    } catch (e) {
        console.warn('Error al extraer coordenadas del feature:', e);
    }
}

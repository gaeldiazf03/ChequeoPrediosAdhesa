function abrirModal(slotId) {
    var modal = document.getElementById("modalEliminar");
    var form = document.getElementById("formEliminar");

    // Le decimos al formulario a qué ruta de backend debe enviar la contraseña
    form.action = "/eliminar_kml/" + slotId;
    // Mostramos el modal
    modal.style.display = "flex";
}

function cerrarModal() {
    // Ocultamos el modal y limpiamos la contraseña por seguridad
    document.getElementById("modalEliminar").style.display = "none";
    document.querySelector('#formEliminar input[type="password"]').value =
        "";
}

// Funciones para el Modal de Contraseñas
function abrirModalPass(boton) {
    var userId = boton && boton.dataset ? boton.dataset.userId : '';
    var username = boton && boton.dataset ? boton.dataset.username : '';
    document.getElementById('formCambiarPass').action = '/admin/cambiar_password/' + userId;
    document.getElementById('nombreUsuarioPass').innerText = username;
    document.getElementById('modalPass').style.display = 'flex';
}

function cerrarModalPass() {
    document.getElementById('modalPass').style.display = 'none';
    document.querySelector('#formCambiarPass input[name="nueva_password"]').value = '';
}

function abrirModalCorreo(boton) {
    var userId = boton && boton.dataset ? boton.dataset.userId : '';
    var username = boton && boton.dataset ? boton.dataset.username : '';
    var correoActual = boton && boton.dataset ? boton.dataset.email : '';
    document.getElementById('formCambiarCorreo').action = '/admin/cambiar_correo/' + userId;
    document.getElementById('nombreUsuarioCorreo').innerText = username;
    document.querySelector('#formCambiarCorreo input[name="nuevo_correo"]').value = correoActual || '';
    document.getElementById('modalCorreo').style.display = 'flex';
}

function cerrarModalCorreo() {
    document.getElementById('modalCorreo').style.display = 'none';
    document.querySelector('#formCambiarCorreo input[name="nuevo_correo"]').value = '';
}

function abrirModalNombreSlot(boton) {
    var slotId = boton && boton.dataset ? boton.dataset.slotId : '';
    var slotName = boton && boton.dataset ? boton.dataset.slotName : '';
    var form = document.getElementById('formCambiarNombreSlot');
    var input = document.getElementById('nuevoNombreSlotInput');
    var modal = document.getElementById('modalNombreSlot');

    if (!form || !input || !modal || !slotId) {
        return;
    }

    form.action = '/admin/cambiar_nombre_slot/' + slotId;
    input.value = slotName || '';
    modal.style.display = 'flex';

    window.setTimeout(function() {
        try {
            input.focus();
            input.select();
        } catch (e) {}
    }, 0);
}

function cerrarModalNombreSlot() {
    var modal = document.getElementById('modalNombreSlot');
    var input = document.getElementById('nuevoNombreSlotInput');
    if (modal) {
        modal.style.display = 'none';
    }
    if (input) {
        input.value = '';
    }
}

function inicializarModalNombreSlot() {
    var modal = document.getElementById('modalNombreSlot');
    var card = modal ? modal.querySelector('.slot-name-modal') : null;

    if (!modal || !card || modal.dataset.bound === '1') {
        return;
    }

    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            cerrarModalNombreSlot();
        }
    });

    card.addEventListener('click', function(event) {
        event.stopPropagation();
    });

    card.addEventListener('mousedown', function(event) {
        event.stopPropagation();
    });

    modal.dataset.bound = '1';
}

// Función para mostrar el spinner de carga al subir KML
function mostrarSpinnerYEnviar(inputElement) {
    if (inputElement.files && inputElement.files.length > 0) {
        document.getElementById('spinnerCarga').style.display = 'flex';
        inputElement.form.submit();
    }
}

function inicializarSelectorDestinatarios() {
    var picker = document.querySelector('[data-recipient-picker]');
    if (!picker) {
        return;
    }

    var select = picker.querySelector('#recipient-user-select');
    var chipsContainer = picker.querySelector('[data-recipient-chips]');
    var hiddenInputsContainer = picker.querySelector('[data-recipient-hidden-inputs]');
    if (!select || !chipsContainer || !hiddenInputsContainer) {
        return;
    }

    var selectedUsers = new Map();

    function renderChips() {
        chipsContainer.innerHTML = '';
        hiddenInputsContainer.innerHTML = '';

        selectedUsers.forEach(function(userData, userId) {
            var chip = document.createElement('span');
            chip.className = 'recipient-chip';
            chip.innerHTML = '<span>' + userData.name + ' (' + userData.email + ')</span>';

            var removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.setAttribute('aria-label', 'Eliminar ' + userData.name);
            removeButton.textContent = '×';
            removeButton.addEventListener('click', function() {
                selectedUsers.delete(userId);
                renderChips();
            });

            chip.appendChild(removeButton);
            chipsContainer.appendChild(chip);

            var hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'destinatarios_usuarios';
            hiddenInput.value = userId;
            hiddenInputsContainer.appendChild(hiddenInput);
        });
    }

    select.addEventListener('change', function() {
        var option = select.options[select.selectedIndex];
        if (!option || !option.value) {
            return;
        }

        var userId = option.value;
        if (!selectedUsers.has(userId)) {
            selectedUsers.set(userId, {
                name: option.getAttribute('data-name') || option.textContent.trim(),
                email: option.getAttribute('data-email') || ''
            });
            renderChips();
        }

        select.value = '';
    });

    renderChips();
}

function inicializarLeyendaFrecuenciaAvisos() {
    var inputFrecuencia = document.querySelector('[data-frequency-days]');
    var leyendaFrecuencia = document.querySelector('[data-frequency-legend]');
    if (!inputFrecuencia || !leyendaFrecuencia) {
        return;
    }

    function actualizarLeyenda() {
        var valor = parseInt(inputFrecuencia.value, 10);
        if (!valor || valor < 1) {
            valor = 1;
        }
        leyendaFrecuencia.textContent = 'Cada ' + valor + ' días se enviará el aviso';
    }

    inputFrecuencia.addEventListener('input', actualizarLeyenda);
    inputFrecuencia.addEventListener('change', actualizarLeyenda);
    actualizarLeyenda();
}

function mostrarEstadoMapaGuardado() {
    var kmlSaved = document.body ? document.body.dataset.kmlSaved : '';
    if (kmlSaved === '1') {
        alert('Mapa subido correctamente.');
    } else if (kmlSaved === '0') {
        alert('Error: el Mapa no pudo guardarse. Revisa el formato.');
    }
}

let chartDashboardCultivos = null;
let chartDashboardActividades = null;
let slotsJerarquiaDashboard = [];

function inicializarDropdownAdminDashboard() {
    var adminMenu = document.getElementById('adminMenu');
    var adminDropdown = document.getElementById('adminDropdown');

    if (!adminMenu || !adminDropdown) {
        return;
    }

    adminMenu.addEventListener('click', function(event) {
        event.preventDefault();
        event.stopPropagation();
        adminDropdown.style.display = adminDropdown.style.display === 'block' ? 'none' : 'block';
    });

    document.addEventListener('click', function(event) {
        if (!adminDropdown.contains(event.target) && event.target !== adminMenu) {
            adminDropdown.style.display = 'none';
        }
    });
}

async function cargarResumenKPIsDashboard() {
    var container = document.getElementById('kpis-container');
    if (!container) {
        return;
    }

    try {
        var response = await fetch('/api/dashboard/kpis');
        if (!response.ok) throw new Error('Error HTTP ' + response.status);
        var data = await response.json();

        var superficieTotal = (data.superficie && data.superficie.total_hectareas) || 0;
        var enOperacion = (data.superficie && data.superficie.en_operacion) || 0;
        var actividadesPendientes = (data.actividades && data.actividades.pendientes) || 0;
        var actividadesCompletadas = (data.actividades && data.actividades.completadas) || 0;

        container.innerHTML = '' +
            '<div class="kpi-card success">' +
                '<p class="kpi-title">Superficie Total</p>' +
                '<div class="kpi-value">' + superficieTotal + '</div>' +
                '<p class="kpi-subtitle">hectáreas</p>' +
            '</div>' +
            '<div class="kpi-card warning">' +
                '<p class="kpi-title">En Operación</p>' +
                '<div class="kpi-value">' + Math.round(enOperacion) + '</div>' +
                '<p class="kpi-subtitle">hectáreas activas</p>' +
            '</div>' +
            '<div class="kpi-card">' +
                '<p class="kpi-title">Actividades Completadas</p>' +
                '<div class="kpi-value">' + actividadesCompletadas + '</div>' +
                '<p class="kpi-subtitle">del total</p>' +
            '</div>' +
            '<div class="kpi-card danger">' +
                '<p class="kpi-title">Actividades Pendientes</p>' +
                '<div class="kpi-value">' + actividadesPendientes + '</div>' +
                '<p class="kpi-subtitle">próximos 30 días</p>' +
            '</div>';
    } catch (error) {
        container.innerHTML = '<div class="error">Error cargando KPIs</div>';
    }
}

async function cargarResumenGraficosDashboard() {
    var container = document.getElementById('charts-container');
    if (!container) {
        return;
    }

    try {
        var response = await fetch('/api/dashboard/graficos');
        if (!response.ok) throw new Error('Error HTTP ' + response.status);
        var data = await response.json();

        container.innerHTML = '' +
            '<div class="chart-card">' +
                '<h3>Distribución de Cultivos</h3>' +
                '<div class="chart-canvas"><canvas id="chartResumenCultivos"></canvas></div>' +
            '</div>' +
            '<div class="chart-card">' +
                '<h3>Estado de Actividades</h3>' +
                '<div class="chart-canvas"><canvas id="chartResumenActividades"></canvas></div>' +
            '</div>';

        dibujarGraficoCultivosResumen(data.distribucion_cultivos || {});
        dibujarGraficoActividadesResumen(data.estado_actividades || {});
    } catch (error) {
        container.innerHTML = '<div class="error">Error cargando gráficos</div>';
    }
}

function dibujarGraficoCultivosResumen(data) {
    var ctx = document.getElementById('chartResumenCultivos');
    if (!ctx || typeof Chart === 'undefined') {
        return;
    }

    if (chartDashboardCultivos) {
        chartDashboardCultivos.destroy();
    }

    chartDashboardCultivos = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels || [],
            datasets: [{
                data: data.data || [],
                backgroundColor: data.colors || [],
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function dibujarGraficoActividadesResumen(data) {
    var ctx = document.getElementById('chartResumenActividades');
    if (!ctx || typeof Chart === 'undefined') {
        return;
    }

    if (chartDashboardActividades) {
        chartDashboardActividades.destroy();
    }

    chartDashboardActividades = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels || [],
            datasets: [{
                label: 'Cantidad',
                data: data.data || [],
                backgroundColor: data.colors || [],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

async function cargarActividadesDashboard() {
    var container = document.getElementById('actividades-container');
    if (!container) {
        return;
    }

    try {
        var response = await fetch('/api/dashboard/proximas?dias=7');
        if (!response.ok) throw new Error('Error HTTP ' + response.status);

        var actividades = await response.json();
        renderActividadesDashboard(actividades, container);
    } catch (error) {
        container.innerHTML = '<div class="error">Error cargando actividades</div>';
    }
}

function renderActividadesDashboard(actividades, container) {
    if (!actividades || actividades.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay actividades próximas</p>';
        return;
    }

    var iconMap = {
        siembra: '🌱',
        riego: '💧',
        fertilizacion: '🥗',
        herbicida: '🧪',
        evaluacion: '📋',
        cosecha: '🚜',
        sanidad: '⚕️',
        default: '📌'
    };

    var html = actividades.map(function(act) {
        var icon = iconMap[act.tipo] || iconMap.default;
        return '' +
            '<div class="activity-item ' + act.estado + '">' +
                '<div class="activity-icon">' + icon + '</div>' +
                '<div class="activity-info">' +
                    '<p class="activity-name">' + (act.nombre || 'Actividad') + '</p>' +
                    '<p class="activity-date">' + (act.fecha_programada || 'Sin fecha') + '</p>' +
                '</div>' +
                '<div class="activity-status ' + act.estado + '">' + act.estado + '</div>' +
            '</div>';
    }).join('');

    container.innerHTML = html;
}

async function cargarCronogramasDashboard() {
    var container = document.getElementById('cronogramas-container');
    if (!container) {
        return;
    }

    try {
        var response = await fetch('/api/slots-hierarquia');
        if (!response.ok) throw new Error('Error HTTP ' + response.status);

        var jerarquia = await response.json();
        slotsJerarquiaDashboard = Array.isArray(jerarquia) ? jerarquia : [];
        renderCronogramasDashboard(slotsJerarquiaDashboard, container);
    } catch (error) {
        container.innerHTML = '<div class="error">Error cargando cronogramas</div>';
    }
}

function renderCronogramasDashboard(slots, container) {
    var cards = [];

    cards.push('' +
        '<div class="lote-card" style="display:flex; align-items:center; justify-content:center; min-height:140px; cursor:pointer;" onclick="abrirModalCronogramaDashboard()">' +
            '<div style="text-align:center;">' +
                '<div style="font-size:44px; line-height:1; color:#667eea;">+</div>' +
                '<div style="margin-top:8px; font-weight:600; color:#334155;">Nuevo Plan</div>' +
            '</div>' +
        '</div>'
    );

    (slots || []).forEach(function(slot) {
        var planes = Array.isArray(slot.planes) ? slot.planes : [];
        planes.forEach(function(plan) {
            cards.push('' +
                '<div class="lote-card">' +
                    '<h4>' + escaparHtml(plan.nombre || 'Plan') + '</h4>' +
                    '<div class="status-badge con-cronograma">Slot: ' + escaparHtml(slot.slot_nombre || ('Slot ' + slot.slot_id)) + '</div>' +
                    '<div style="margin-top:8px; font-size:12px; color:#475569;">' +
                        '<div><strong>Padre:</strong> ' + escaparHtml(plan.lote_padre || '-') + '</div>' +
                        '<div><strong>Hijos:</strong> ' + escaparHtml((plan.lotes_hijos || []).join(', ') || '-') + '</div>' +
                        '<div><strong>Inicio:</strong> ' + escaparHtml(plan.fecha_inicio || '-') + '</div>' +
                    '</div>' +
                    '<div class="lote-card-actions lote-card-actions-spaced">' +
                        '<button class="btn-small btn-small-secondary" onclick="verTimelineDashboard(' + slot.slot_id + ')">Ver</button>' +
                        '<button class="btn-small btn-small-download" onclick="descargarCronogramaDashboard(' + slot.slot_id + ')">Descargar</button>' +
                    '</div>' +
                '</div>'
            );
        });
    });

    container.innerHTML = cards.join('');
}

function abrirModalCronogramaDashboard() {
    var modal = document.getElementById('modal-cronograma-dashboard');
    var fechaInicio = document.getElementById('fecha-inicio-plan-dashboard');
    if (!modal || !fechaInicio) {
        return;
    }

    inicializarFormularioPlanDashboard();
    modal.classList.add('show');
    fechaInicio.value = new Date().toISOString().split('T')[0];
    cargarResumenEtapasPlanDashboard();
}

async function cargarResumenEtapasPlanDashboard() {
    var box = document.getElementById('etapas-resumen-plan-dashboard');
    if (!box) return;

    box.innerHTML = '<p class="panel-help">Cargando resumen del catálogo...</p>';
    try {
        var response = await fetch('/api/catalogo/etapas-resumen', { headers: { 'Accept': 'application/json' } });
        var data = await response.json();
        if (!response.ok) {
            box.innerHTML = '<p class="panel-help">No se pudo cargar el resumen por etapas.</p>';
            return;
        }

        var etapas = Array.isArray(data.etapas) ? data.etapas : [];
        if (!etapas.length) {
            box.innerHTML = '<p class="panel-help">No hay actividades activas en el catálogo.</p>';
            return;
        }

        var chips = etapas.map(function(item) {
            return '<span class="etapa-pill"><strong>' + escaparHtml(item.etapa || 'Sin etapa') + '</strong> <em>(' + Number(item.cantidad || 0) + ')</em></span>';
        }).join('');

        box.innerHTML =
            '<div class="etapas-preview-total">Total: ' + Number(data.total_actividades || 0) + ' actividades</div>' +
            '<div class="etapas-preview-list">' + chips + '</div>';
    } catch (error) {
        box.innerHTML = '<p class="panel-help">No se pudo cargar el resumen por etapas.</p>';
    }
}

function cerrarModalCronogramaDashboard() {
    var modal = document.getElementById('modal-cronograma-dashboard');
    if (modal) {
        modal.classList.remove('show');
    }
}

function inicializarFormularioPlanDashboard() {
    var selSlot = document.getElementById('slot-plan-dashboard');
    var selPadre = document.getElementById('lote-padre-dashboard');
    if (!selSlot || !selPadre) return;

    selSlot.innerHTML = (slotsJerarquiaDashboard || []).map(function(slot) {
        return '<option value="' + slot.slot_id + '">' + escaparHtml(slot.slot_nombre || ('Slot ' + slot.slot_id)) + '</option>';
    }).join('');

    selSlot.onchange = actualizarFormularioPadresDashboard;
    selPadre.onchange = actualizarFormularioHijosDashboard;

    actualizarFormularioPadresDashboard();
}

function _slotSeleccionadoDashboard() {
    var selSlot = document.getElementById('slot-plan-dashboard');
    if (!selSlot) return null;
    var slotId = parseInt(selSlot.value || '0', 10);
    return (slotsJerarquiaDashboard || []).find(function(s) { return Number(s.slot_id) === Number(slotId); }) || null;
}

function actualizarFormularioPadresDashboard() {
    var selPadre = document.getElementById('lote-padre-dashboard');
    if (!selPadre) return;
    var slot = _slotSeleccionadoDashboard();
    var padres = slot && Array.isArray(slot.padres) ? slot.padres : [];

    selPadre.innerHTML = padres.map(function(p) {
        return '<option value="' + escaparHtml(p) + '">' + escaparHtml(p) + '</option>';
    }).join('');

    actualizarFormularioHijosDashboard();
}

function actualizarFormularioHijosDashboard() {
    var box = document.getElementById('lotes-hijos-dashboard');
    var selPadre = document.getElementById('lote-padre-dashboard');
    if (!box || !selPadre) return;

    var slot = _slotSeleccionadoDashboard();
    var padre = selPadre.value;
    var hijos = (slot && slot.hijos_por_padre && slot.hijos_por_padre[padre]) ? slot.hijos_por_padre[padre] : [];

    if (!hijos.length) {
        box.innerHTML = '<p class="panel-help">Este padre no tiene lotes hijos.</p>';
        return;
    }

    box.innerHTML = hijos.map(function(h) {
        return '<label class="checkbox-option"><input type="checkbox" class="chk-hijo-plan" value="' + escaparHtml(h) + '"><span>' + escaparHtml(h) + '</span></label>';
    }).join('');
}

async function crearPlanDashboard() {
    var nombre = document.getElementById('nombre-plan-dashboard');
    var selSlot = document.getElementById('slot-plan-dashboard');
    var selPadre = document.getElementById('lote-padre-dashboard');
    var fechaInicio = document.getElementById('fecha-inicio-plan-dashboard');

    if (!nombre || !selSlot || !selPadre || !fechaInicio || !nombre.value.trim() || !selSlot.value || !selPadre.value || !fechaInicio.value) {
        alert('Completa todos los campos obligatorios del plan.');
        return;
    }

    var hijos = Array.from(document.querySelectorAll('.chk-hijo-plan:checked')).map(function(cb) { return cb.value; });

    try {
        var response = await fetch('/api/planes/aplicar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre: nombre.value.trim(),
                slot_id: Number(selSlot.value),
                lote_padre: selPadre.value,
                lotes_hijos: hijos,
                fecha_inicio: fechaInicio.value
            })
        });

        var data = await response.json();
        if (!response.ok || !data.ok) {
            alert(data.error || 'No se pudo crear el plan');
            return;
        }

        alert('Plan creado y aplicado. Tareas agregadas a calendario y Gantt del mapa.');
        cerrarModalCronogramaDashboard();
        cargarCronogramasDashboard();
        cargarResumenKPIsDashboard();
        cargarActividadesDashboard();
    } catch (error) {
        alert('Error creando el plan');
    }
}

function verTimelineDashboard(slotId) {
    window.location.href = '/dashboard/timeline/' + slotId;
}

async function descargarCronogramaDashboard(slotId) {
    try {
        var response = await fetch('/api/actividades/descargar/' + slotId + '?formato=csv');
        if (!response.ok) throw new Error('Error HTTP ' + response.status);

        var blob = await response.blob();
        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'cronograma_lote_' + slotId + '.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert('Error descargando cronograma');
    }
}

function inicializarDashboardUnificado() {
    cargarResumenKPIsDashboard();
    cargarResumenGraficosDashboard();
    cargarActividadesDashboard();
    cargarCronogramasDashboard();

    setInterval(cargarResumenKPIsDashboard, 5 * 60 * 1000);
    setInterval(cargarActividadesDashboard, 5 * 60 * 1000);
    setInterval(cargarCronogramasDashboard, 10 * 60 * 1000);
}

function escaparHtml(texto) {
    return String(texto || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Lógica para cerrar los modales si se hace clic en el área oscura del fondo
window.onclick = function(event) {
    var modalEliminar = document.getElementById("modalEliminar");
    var modalPass = document.getElementById("modalPass");
    var modalCorreo = document.getElementById("modalCorreo");
    var modalNombreSlot = document.getElementById("modalNombreSlot");
    var modalCronogramaDashboard = document.getElementById('modal-cronograma-dashboard');
    
    if (event.target == modalEliminar) {
        cerrarModal();
    } else if (event.target == modalPass) {
        cerrarModalPass();
    } else if (event.target == modalCorreo) {
        cerrarModalCorreo();
    } else if (event.target == modalCronogramaDashboard) {
        cerrarModalCronogramaDashboard();
    }
}

document.addEventListener('DOMContentLoaded', inicializarSelectorDestinatarios);
document.addEventListener('DOMContentLoaded', inicializarLeyendaFrecuenciaAvisos);
document.addEventListener('DOMContentLoaded', mostrarEstadoMapaGuardado);
document.addEventListener('DOMContentLoaded', inicializarDropdownAdminDashboard);
document.addEventListener('DOMContentLoaded', inicializarDashboardUnificado);
document.addEventListener('DOMContentLoaded', inicializarModalNombreSlot);
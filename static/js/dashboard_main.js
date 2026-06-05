// Variables globales
let chartCultivos = null;
let chartActividades = null;
let slotIdActual = null;

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', () => {
    inicializarDropdownAdmin();
    cargarKPIs();
    cargarGraficos();
    cargarActividades();
    cargarCronogramas();

    // Recargar cada 5 minutos
    setInterval(cargarKPIs, 5 * 60 * 1000);
    setInterval(cargarActividades, 5 * 60 * 1000);
    setInterval(cargarCronogramas, 10 * 60 * 1000);
});

// Cargar KPIs
async function cargarKPIs() {
    try {
        const response = await fetch('/api/dashboard/kpis');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        renderKPIs(data);
    } catch (error) {
        console.error('Error cargando KPIs:', error);
        mostrarError('Error cargando KPIs');
    }
}

// Renderizar KPIs
function renderKPIs(data) {
    const container = document.getElementById('kpis-container');

    // Calcular datos
    const superficieTotal = data.superficie.total_hectareas || 0;
    const enOperacion = data.superficie.en_operacion || 0;
    const actividadesPendientes = data.actividades.pendientes || 0;
    const actividadesCompletadas = data.actividades.completadas || 0;

    const html = `
        <div class="kpi-card success">
            <p class="kpi-title">📍 Superficie Total</p>
            <div class="kpi-value">${superficieTotal}</div>
            <p class="kpi-subtitle">hectáreas</p>
        </div>

        <div class="kpi-card warning">
            <p class="kpi-title">🌱 En Operación</p>
            <div class="kpi-value">${Math.round(enOperacion)}</div>
            <p class="kpi-subtitle">hectáreas activas</p>
        </div>

        <div class="kpi-card">
            <p class="kpi-title">✅ Actividades Completadas</p>
            <div class="kpi-value">${actividadesCompletadas}</div>
            <p class="kpi-subtitle">del total</p>
        </div>

        <div class="kpi-card danger">
            <p class="kpi-title">⏳ Actividades Pendientes</p>
            <div class="kpi-value">${actividadesPendientes}</div>
            <p class="kpi-subtitle">próximos 30 días</p>
        </div>
    `;

    container.innerHTML = html;
}

// Cargar Gráficos
async function cargarGraficos() {
    try {
        const response = await fetch('/api/dashboard/graficos');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        renderGraficos(data);
    } catch (error) {
        console.error('Error cargando gráficos:', error);
    }
}

// Renderizar Gráficos
function renderGraficos(data) {
    const container = document.getElementById('charts-container');

    const html = `
        <div class="chart-card">
            <h3>📊 Distribución de Cultivos</h3>
            <div class="chart-canvas">
                <canvas id="chartCultivos"></canvas>
            </div>
        </div>

        <div class="chart-card">
            <h3>📈 Estado de Actividades</h3>
            <div class="chart-canvas">
                <canvas id="chartActividades"></canvas>
            </div>
        </div>
    `;

    container.innerHTML = html;

    // Esperar a que el DOM se actualice
    setTimeout(() => {
        crearGraficosCultivos(data.distribucion_cultivos);
        crearGraficosActividades(data.estado_actividades);
    }, 0);
}

// Crear gráfico de cultivos
function crearGraficosCultivos(data) {
    const ctx = document.getElementById('chartCultivos');
    if (!ctx) return;

    if (chartCultivos) chartCultivos.destroy();

    chartCultivos = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.data,
                backgroundColor: data.colors,
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                }
            }
        }
    });
}

// Crear gráfico de actividades
function crearGraficosActividades(data) {
    const ctx = document.getElementById('chartActividades');
    if (!ctx) return;

    if (chartActividades) chartActividades.destroy();

    chartActividades = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Cantidad',
                data: data.data,
                backgroundColor: data.colors,
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

// Cargar Actividades Próximas
async function cargarActividades() {
    try {
        const response = await fetch('/api/dashboard/proximas?dias=7');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        renderActividades(data);
    } catch (error) {
        console.error('Error cargando actividades:', error);
        mostrarError('Error cargando actividades');
    }
}

// Renderizar Actividades
function renderActividades(actividades) {
    const container = document.getElementById('actividades-container');

    if (actividades.length === 0) {
        container.innerHTML = '<p class="empty-state">No hay actividades próximas</p>';
        return;
    }

    const html = actividades.map(act => {
        const iconMap = {
            'siembra': '🌱',
            'riego': '💧',
            'fertilizacion': '🥗',
            'herbicida': '🧪',
            'evaluacion': '📋',
            'cosecha': '🚜',
            'sanidad': '⚕️',
            'default': '📌'
        };

        const icon = iconMap[act.tipo] || iconMap.default;

        return `
            <div class="activity-item ${act.estado}">
                <div class="activity-icon">${icon}</div>
                <div class="activity-info">
                    <p class="activity-name">${act.nombre}</p>
                    <p class="activity-date">${act.fecha_programada || 'Sin fecha'}</p>
                </div>
                <div class="activity-status ${act.estado}">${act.estado}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

// Cargar Cronogramas (Lotes)
async function cargarCronogramas() {
    try {
        const response = await fetch('/api/slots-info');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const slots = await response.json();
        renderCronogramas(slots);
    } catch (error) {
        console.error('Error cargando cronogramas:', error);
        mostrarError('Error cargando información de lotes');
    }
}

// Renderizar Cronogramas
function renderCronogramas(slots) {
    const container = document.getElementById('cronogramas-container');

    if (!slots || slots.length === 0) {
        container.innerHTML = '<p class="empty-state empty-state-grid">No hay lotes disponibles</p>';
        return;
    }

    const html = slots.map(slot => {
        const tieneActividades = slot.tiene_actividades || false;
        const badge = tieneActividades
            ? '<div class="status-badge con-cronograma">✓ Con cronograma</div>'
            : '<div class="status-badge sin-cronograma">Sin cronograma</div>';

        return `
            <div class="lote-card">
                <h4>${slot.nombre || 'Lote ' + slot.id}</h4>
                ${badge}
                <div class="lote-card-actions lote-card-actions-spaced">
                    <button class="btn-small btn-small-primary" onclick="abrirModalCronograma(${slot.id})">
                        Generar
                    </button>
                    <button class="btn-small btn-small-secondary" onclick="verTimeline(${slot.id})">
                        Ver
                    </button>
                    ${tieneActividades ? `<button class="btn-small btn-small-download" onclick="descargarCronograma(${slot.id})">Descargar</button>` : ''}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

// Funciones de Modal
function abrirModalCronograma(slotId) {
    slotIdActual = slotId;
    document.getElementById('modal-cronograma').classList.add('show');
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('fecha-siembra').value = today;
}

function cerrarModal() {
    document.getElementById('modal-cronograma').classList.remove('show');
    slotIdActual = null;
}

async function generarCronograma() {
    const tipoCultivo = document.getElementById('tipo-cultivo').value;
    const fechaSiembra = document.getElementById('fecha-siembra').value;

    if (!tipoCultivo || !fechaSiembra) {
        alert('Por favor completa todos los campos');
        return;
    }

    try {
        const response = await fetch(`/api/actividades/generar-cronograma/${slotIdActual}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo_cultivo: tipoCultivo,
                fecha_siembra: fechaSiembra
            })
        });

        const data = await response.json();

        if (data.exitoso) {
            alert(`✓ Cronograma generado exitosamente\n${data.actividades_creadas} actividades creadas`);
            cerrarModal();
            cargarCronogramas();
            cargarKPIs();
            cargarActividades();
        } else {
            alert('Error: ' + (data.error || 'No se pudo generar el cronograma'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error generando cronograma');
    }
}

function verTimeline(slotId) {
    window.location.href = `/dashboard/timeline/${slotId}`;
}

async function descargarCronograma(slotId) {
    try {
        const response = await fetch(`/api/actividades/descargar/${slotId}?formato=csv`);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cronograma_lote_${slotId}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Error descargando cronograma:', error);
        alert('Error descargando cronograma');
    }
}

// Mostrar error
function mostrarError(mensaje) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = mensaje;
    document.querySelector('.dashboard-container').prepend(error);
    setTimeout(() => error.remove(), 5000);
}

// Cerrar modal con ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') cerrarModal();
});

function inicializarDropdownAdmin() {
    var btn = document.getElementById('adminMenu');
    var dropdown = document.getElementById('adminDropdown');
    if (!btn || !dropdown) {
        return;
    }

    document.addEventListener('click', function(e) {
        if (e.target === btn) {
            dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
        } else if (!dropdown.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });
}
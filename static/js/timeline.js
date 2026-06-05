const slotId = document.body ? document.body.dataset.slotId : null;

// Cargar timeline al iniciar
document.addEventListener('DOMContentLoaded', () => {
    cargarTimeline();
});

async function cargarTimeline() {
    try {
        const response = await fetch(`/api/actividades/por-lote/${slotId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const actividades = await response.json();
        renderTimeline(actividades);
    } catch (error) {
        console.error('Error cargando timeline:', error);
        document.getElementById('timeline-container').innerHTML =
            '<div class="error">Error cargando el timeline. Por favor, recarga la página.</div>';
    }
}

function renderTimeline(actividades) {
    const container = document.getElementById('timeline-container');

    if (actividades.length === 0) {
        container.innerHTML = '<p class="timeline-empty-state">No hay actividades programadas para este lote</p>';
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
            'post_cosecha': '📦',
            'preparacion': '🏗️',
            'maleza': '🌿',
            'default': '📌'
        };

        const icon = iconMap[act.tipo] || iconMap.default;
        const completadaEn = act.completada_en ? new Date(act.completada_en).toLocaleDateString('es-MX') : '-';

        // Determinar botones disponibles según estado
        let botonesHtml = '';
        if (act.estado === 'pendiente' || act.estado === 'en_progreso') {
            botonesHtml += `<button class="btn btn-success" onclick="completarActividad(${act.id})">Completar</button>`;
        }
        if (act.estado !== 'cancelada') {
            botonesHtml += `<button class="btn btn-danger" onclick="cancelarActividad(${act.id})">Cancelar</button>`;
        }

        return `
            <div class="timeline-item ${act.estado}">
                <div class="timeline-content">
                    <h3 class="timeline-title">${icon} ${act.nombre}</h3>
                    <span class="status-badge ${act.estado}">${act.estado}</span>

                    <div class="timeline-details">
                        <div class="timeline-detail">
                            <strong>Programada:</strong>
                            <span>${act.fecha_programada || 'N/A'}</span>
                        </div>
                        <div class="timeline-detail">
                            <strong>Vencimiento:</strong>
                            <span>${act.fecha_vencimiento || 'N/A'}</span>
                        </div>
                        <div class="timeline-detail">
                            <strong>Prioridad:</strong>
                            <span>${act.prioridad || 'normal'}</span>
                        </div>
                        <div class="timeline-detail">
                            <strong>Completada:</strong>
                            <span>${completadaEn}</span>
                        </div>
                    </div>

                    ${act.descripcion ? `<p class="timeline-description">${act.descripcion}</p>` : ''}

                    <div class="timeline-actions">
                        ${botonesHtml}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

async function completarActividad(actividadId) {
    try {
        const response = await fetch(`/api/actividades/${actividadId}/completar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            cargarTimeline(); // Recargar
        } else {
            alert('Error completando la actividad');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error completando la actividad');
    }
}

async function cancelarActividad(actividadId) {
    if (!confirm('¿Estás seguro de que deseas cancelar esta actividad?')) return;

    try {
        const response = await fetch(`/api/actividades/${actividadId}/cambiar-estado`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: 'cancelada' })
        });

        if (response.ok) {
            cargarTimeline(); // Recargar
        } else {
            alert('Error cancelando la actividad');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error cancelando la actividad');
    }
}
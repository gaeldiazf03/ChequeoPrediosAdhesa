// Autoguardado y guardado manual extraído desde mapa.js
var guardando = typeof guardando !== 'undefined' ? guardando : false;
var _temporizadorGuardado = null;

function registrarCambio() {
    cambiosPendientes = true;
    actualizarEstado('Cambios pendientes');

    if (_temporizadorGuardado) {
        clearTimeout(_temporizadorGuardado);
    }

    _temporizadorGuardado = setTimeout(function () {
        guardarAutomaticamente();
    }, 1200);
}

function guardarAutomaticamente() {
    if (!slotId || !cambiosPendientes || guardando) return;
    if (!tienePermisoDeGuardado()) return;

    guardando = true;
    actualizarEstado('Guardando...');

    // Sincronizar tareas del calendario en el GeoJSON antes de enviar.
    try { if (typeof window.syncTareasToFeatures === 'function') window.syncTareasToFeatures(); } catch(e) { console.warn('sync error', e); }

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

// Activar autoguardado periódico
setInterval(guardarAutomaticamente, 300000);

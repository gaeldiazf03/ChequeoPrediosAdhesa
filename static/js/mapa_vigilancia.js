// Vigilancia periódica de permisos (extraído de mapa.js)
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
}, 300000);

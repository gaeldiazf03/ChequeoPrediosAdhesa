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
function abrirModalPass(userId, username) {
    document.getElementById('formCambiarPass').action = '/admin/cambiar_password/' + userId;
    document.getElementById('nombreUsuarioPass').innerText = username;
    document.getElementById('modalPass').style.display = 'flex';
}

function cerrarModalPass() {
    document.getElementById('modalPass').style.display = 'none';
    document.querySelector('#formCambiarPass input[name="nueva_password"]').value = '';
}
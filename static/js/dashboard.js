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

// Lógica para cerrar los modales si se hace clic en el área oscura del fondo
window.onclick = function(event) {
    var modalEliminar = document.getElementById("modalEliminar");
    var modalPass = document.getElementById("modalPass");
    var modalCorreo = document.getElementById("modalCorreo");
    
    if (event.target == modalEliminar) {
        cerrarModal();
    } else if (event.target == modalPass) {
        cerrarModalPass();
    } else if (event.target == modalCorreo) {
        cerrarModalCorreo();
    }
}

document.addEventListener('DOMContentLoaded', inicializarSelectorDestinatarios);
document.addEventListener('DOMContentLoaded', function(){
  const slotSelect = document.getElementById('slotSelectNot');
  const cargarBtn = document.getElementById('cargarNotBtn');
  const aplicarFiltrosBtn = document.getElementById('aplicarFiltrosBtn');
  const filtroCanal = document.getElementById('filtroCanal');
  const filtroEstado = document.getElementById('filtroEstado');
  const filtroDesde = document.getElementById('filtroDesde');
  const filtroHasta = document.getElementById('filtroHasta');
  const tbody = document.querySelector('#notTable tbody');

  fetch('/api/slots')
    .then(r => r.json())
    .then(slots => {
      slotSelect.innerHTML = '';
      slots.forEach(s => {
        const opt = document.createElement('option'); opt.value = s.id; opt.textContent = s.nombre_real || s.slug || (`Slot ${s.id}`); slotSelect.appendChild(opt);
      });
    }).catch(()=>{})

  function cargar(){
    const slotId = slotSelect.value || 1;
    const params = new URLSearchParams({ slot_id: slotId });
    if (filtroCanal.value) params.set('canal', filtroCanal.value);
    if (filtroEstado.value) params.set('estado', filtroEstado.value);
    if (filtroDesde.value) params.set('desde', `${filtroDesde.value} 00:00:00`);
    if (filtroHasta.value) params.set('hasta', `${filtroHasta.value} 23:59:59`);

    fetch(`/admin/notificaciones?${params.toString()}`, { headers: { 'Accept': 'application/json' } })
      .then(r=>r.json()).then(data=>{
        tbody.innerHTML = '';
        data.notificaciones.forEach(n=>{
            const tr = document.createElement('tr');
          tr.innerHTML = `<td>${n.id}</td><td>${n.estado || 'pendiente'}</td><td>${n.intentos || 0}</td><td>${n.origen || 'alerta'}</td><td>${n.canal}</td><td>${n.destino || ''}</td><td>${n.tipo}</td><td>${n.titulo}</td><td>${n.mensaje}</td><td><pre style="max-width:300px;white-space:pre-wrap">${n.resultado_json}</pre></td><td>${n.creada_en || ''}</td><td>${n.ultimo_intento_en || ''}</td><td><button class="retryBtn" data-id="${n.id}">Reintentar</button></td>`;
          tbody.appendChild(tr);
        })
          attachRetryButtons();
      }).catch(e=>{console.error(e); alert('Error cargando notificaciones')})
  }

  cargarBtn.addEventListener('click', cargar);
  aplicarFiltrosBtn.addEventListener('click', cargar);
  setTimeout(cargar, 200);

    function attachRetryButtons(){
      document.querySelectorAll('.retryBtn').forEach(btn=>{
        btn.removeEventListener('click', onRetryClick);
        btn.addEventListener('click', onRetryClick);
      })
    }

    function onRetryClick(e){
      const id = e.currentTarget.dataset.id;
      if(!confirm('Reintentar envío para la notificación ' + id + '?')) return;
      fetch(`/admin/notificaciones/${id}/reintentar`, { method: 'POST' })
        .then(r=>r.json()).then(resp=>{
          if(resp.ok){ alert('Reintento ejecutado'); cargar(); }
          else alert('Error: ' + (resp.error || JSON.stringify(resp)));
        }).catch(e=>{ console.error(e); alert('Error reintentando'); })
    }
});

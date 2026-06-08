document.addEventListener('DOMContentLoaded', function(){
  const tablaBody = document.querySelector('#tablaTractores tbody');
  const btnAgregar = document.getElementById('btnAgregarTractor');
  const modal = document.getElementById('modalTractor');
  const cerrarModal = document.getElementById('cerrarModal');
  const cancelarModal = document.getElementById('cancelarModal');
  const guardarBtn = document.getElementById('guardarTractor');

  function normalizarEstado(estado){
    if(estado === 'activo') return 'disponible';
    if(estado === 'no disponible') return 'no_disponible';
    return estado || 'disponible';
  }

  function etiquetaEstado(estado){
    const estadoNormalizado = normalizarEstado(estado);
    const etiquetas = {
      disponible: 'Disponible',
      mantenimiento: 'Mantenimiento',
      no_disponible: 'No disponible'
    };
    return etiquetas[estadoNormalizado] || estado;
  }

  function mostrarModal(data){
    document.getElementById('tractor_id').value = data?.id || '';
    document.getElementById('placa').value = data?.placa || '';
    document.getElementById('modelo').value = data?.modelo || '';
    document.getElementById('ano').value = data?.ano || '';
    document.getElementById('estado').value = normalizarEstado(data?.estado);
    modal.style.display = 'flex';
  }

  function ocultarModal(){
    modal.style.display = 'none';
  }

  cerrarModal?.addEventListener('click', ocultarModal);
  cancelarModal?.addEventListener('click', ocultarModal);

  btnAgregar?.addEventListener('click', function(){ mostrarModal(); });

  guardarBtn?.addEventListener('click', async function(){
    const id = document.getElementById('tractor_id').value;
    const payload = {
      placa: document.getElementById('placa').value,
      modelo: document.getElementById('modelo').value,
      ano: document.getElementById('ano').value || null,
      estado: document.getElementById('estado').value
    };

    try{
      if(id){
        const res = await fetch(`/admin/tractores/${id}`, {method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error actualizando');
      } else {
        const res = await fetch('/admin/tractores', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error creando');
      }
      ocultarModal();
      cargarTractores();
    }catch(err){
      alert('Error: '+err.message);
    }
  });

  async function cargarTractores(){
    tablaBody.innerHTML = '';
    try{
      const res = await fetch('/admin/tractores', {headers: {'Accept':'application/json'}});
      const data = await res.json();
      data.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${t.id}</td>
          <td>${t.placa}</td>
          <td>${t.modelo || ''}</td>
          <td>${t.ano || ''}</td>
          <td>${etiquetaEstado(t.estado)}</td>
          <td>${t.slot_id || ''}</td>
          <td>
            <button class="btn btn-sm btn-secondary btn-edit" data-id="${t.id}">Editar</button>
            <button class="btn btn-sm btn-info btn-link" data-id="${t.id}" data-unidad="${t.metadata_json ? '' : ''}">Vincular</button>
            <button class="btn btn-sm btn-danger btn-del" data-id="${t.id}">Eliminar</button>
          </td>
        `;
        tablaBody.appendChild(tr);
      });

      document.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', async (e)=>{
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/tractores/${id}`);
        const d = await res.json();
        mostrarModal(d);
      }));

      document.querySelectorAll('.btn-link').forEach(b => b.addEventListener('click', async (e)=>{
        const id = e.target.dataset.id;
        const unidad = prompt('Unidad ID (ej. dispositivo o placa) a vincular a este tractor:');
        if(!unidad) return;
        const res = await fetch(`/admin/tractores/${id}/vincular`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({unidad_id: unidad})});
        if(res.ok) { alert('Vinculado'); cargarTractores(); } else { const d = await res.json(); alert(d.error || 'Error vinculando'); }
      }));

      document.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', async (e)=>{
        if(!confirm('Eliminar tractor?')) return;
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/tractores/${id}`, {method:'DELETE'});
        if(res.ok) cargarTractores(); else alert('Error eliminando');
      }));

    }catch(err){
      console.error(err);
      tablaBody.innerHTML = '<tr><td colspan="7">Error cargando tractores</td></tr>';
    }
  }

  cargarTractores();
});

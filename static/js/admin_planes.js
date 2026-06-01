document.addEventListener('DOMContentLoaded', function(){
  const tablaBody = document.querySelector('#tablaPlanes tbody');
  const btnAgregar = document.getElementById('btnAgregarPlan');
  const modal = document.getElementById('modalPlan');
  const cerrarModal = document.getElementById('cerrarModalPlan');
  const cancelarModal = document.getElementById('cancelarModalPlan');
  const guardarBtn = document.getElementById('guardarPlan');

  function mostrarModal(data){
    document.getElementById('plan_id').value = data?.id || '';
    document.getElementById('nombre').value = data?.nombre || '';
    document.getElementById('slot_id').value = data?.slot_id || '';
    document.getElementById('fecha_inicio').value = data?.fecha_inicio || '';
    document.getElementById('fecha_fin').value = data?.fecha_fin || '';
    modal.style.display = 'block';
  }
  function ocultarModal(){ modal.style.display = 'none'; }
  cerrarModal?.addEventListener('click', ocultarModal);
  cancelarModal?.addEventListener('click', ocultarModal);
  btnAgregar?.addEventListener('click', function(){ mostrarModal(); });

  guardarBtn?.addEventListener('click', async function(){
    const id = document.getElementById('plan_id').value;
    const payload = {
      nombre: document.getElementById('nombre').value,
      slot_id: document.getElementById('slot_id').value,
      fecha_inicio: document.getElementById('fecha_inicio').value || null,
      fecha_fin: document.getElementById('fecha_fin').value || null
    };
    try{
      if(id){
        const res = await fetch(`/admin/planes/${id}`, {method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error actualizando');
      } else {
        const res = await fetch('/admin/planes', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error creando');
      }
      ocultarModal(); cargarPlanes();
    }catch(err){ alert('Error: '+err.message); }
  });

  async function cargarPlanes(){
    tablaBody.innerHTML = '';
    try{
      // by default load all planes for slot 1 to show something
      const res = await fetch('/admin/planes?slot_id=1', {headers: {'Accept':'application/json'}});
      const data = await res.json();
      data.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${p.id}</td>
          <td>${p.nombre}</td>
          <td>${p.slot_id}</td>
          <td>${p.fecha_inicio || ''}</td>
          <td>${p.fecha_fin || ''}</td>
          <td>${p.estado || ''}</td>
          <td>
            <button class="btn btn-sm btn-secondary btn-edit" data-id="${p.id}">Editar</button>
            <button class="btn btn-sm btn-danger btn-del" data-id="${p.id}">Eliminar</button>
          </td>
        `;
        tablaBody.appendChild(tr);
      });

      document.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', async (e)=>{
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/planes/${id}`);
        const d = await res.json();
        mostrarModal(d);
      }));

      document.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', async (e)=>{
        if(!confirm('Eliminar plan?')) return;
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/planes/${id}`, {method:'DELETE'});
        if(res.ok) cargarPlanes(); else alert('Error eliminando');
      }));

    }catch(err){ console.error(err); tablaBody.innerHTML = '<tr><td colspan="7">Error cargando planes</td></tr>'; }
  }

  cargarPlanes();
});

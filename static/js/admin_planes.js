document.addEventListener('DOMContentLoaded', function(){
  const tablaBody = document.querySelector('#tablaPlanes tbody');
  const btnAgregar = document.getElementById('btnAgregarPlan');
  const modal = document.getElementById('modalPlan');
  const cerrarModal = document.getElementById('cerrarModalPlan');
  const cancelarModal = document.getElementById('cancelarModalPlan');
  const guardarBtn = document.getElementById('guardarPlan');

  function esc(v){
    return String(v || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function mostrarModal(data){
    document.getElementById('plan_id').value = data?.id || '';
    document.getElementById('nombre').value = data?.nombre || '';
    document.getElementById('etapa').value = data?.etapa || '';
    document.getElementById('descripcion').value = data?.descripcion || '';
    document.getElementById('como_se_realiza').value = data?.como_se_realiza || '';
    document.getElementById('programacion_recomendada').value = data?.programacion_recomendada || '';
    modal.style.display = 'flex';
  }
  function ocultarModal(){ modal.style.display = 'none'; }
  cerrarModal?.addEventListener('click', ocultarModal);
  cancelarModal?.addEventListener('click', ocultarModal);
  window.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && modal.style.display !== 'none'){
      ocultarModal();
    }
  });
  modal?.addEventListener('click', function(e){
    if(e.target === modal) ocultarModal();
  });
  btnAgregar?.addEventListener('click', function(){ mostrarModal(); });

  guardarBtn?.addEventListener('click', async function(){
    const id = document.getElementById('plan_id').value;
    const payload = {
      nombre: document.getElementById('nombre').value,
      etapa: document.getElementById('etapa').value,
      descripcion: document.getElementById('descripcion').value,
      como_se_realiza: document.getElementById('como_se_realiza').value,
      programacion_recomendada: document.getElementById('programacion_recomendada').value
    };
    try{
      if(id){
        const res = await fetch(`/admin/actividades-catalogo/${id}`, {method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error actualizando');
      } else {
        const res = await fetch('/admin/actividades-catalogo', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        if(!res.ok) throw new Error('Error creando');
      }
      ocultarModal(); cargarPlanes();
    }catch(err){ alert('Error: '+err.message); }
  });

  async function cargarPlanes(){
    tablaBody.innerHTML = '';
    try{
      const res = await fetch('/admin/actividades-catalogo', {headers: {'Accept':'application/json'}});
      const data = await res.json();
      const grupos = new Map();
      data.forEach(p => {
        const etapa = (p.etapa && String(p.etapa).trim()) ? String(p.etapa).trim() : 'Sin etapa';
        if(!grupos.has(etapa)) grupos.set(etapa, []);
        grupos.get(etapa).push(p);
      });

      grupos.forEach((items, etapa) => {
        const trGrupo = document.createElement('tr');
        trGrupo.className = 'row-etapa';
        trGrupo.innerHTML = `<td colspan="7"><strong>Etapa: ${esc(etapa)}</strong> <span class="etapa-count">(${items.length})</span></td>`;
        tablaBody.appendChild(trGrupo);

        items.forEach(p => {
        const tr = document.createElement('tr');
        const descripcion = p.descripcion || '';
        const como = p.como_se_realiza || '';
        const programacion = p.programacion_recomendada || '';
        tr.innerHTML = `
          <td>${p.id}</td>
          <td>${esc(p.nombre)}</td>
          <td>${esc(p.etapa || '')}</td>
          <td title="${esc(descripcion)}">${esc(descripcion)}</td>
          <td title="${esc(como)}">${esc(como)}</td>
          <td title="${esc(programacion)}">${esc(programacion)}</td>
          <td>
            <button class="btn btn-sm btn-secondary btn-edit" data-id="${p.id}">Editar</button>
            <button class="btn btn-sm btn-danger btn-del" data-id="${p.id}">Eliminar</button>
          </td>
        `;
        tablaBody.appendChild(tr);
        });
      });

      document.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', async (e)=>{
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/actividades-catalogo/${id}`);
        const d = await res.json();
        mostrarModal(d);
      }));

      document.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', async (e)=>{
        if(!confirm('Eliminar proceso del catálogo?')) return;
        const id = e.target.dataset.id;
        const res = await fetch(`/admin/actividades-catalogo/${id}`, {method:'DELETE'});
        if(res.ok) cargarPlanes(); else alert('Error eliminando');
      }));

    }catch(err){ console.error(err); tablaBody.innerHTML = '<tr><td colspan="7">Error cargando procesos</td></tr>'; }
  }

  cargarPlanes();
});

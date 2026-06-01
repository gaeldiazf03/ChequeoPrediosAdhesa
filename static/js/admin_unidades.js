document.addEventListener('DOMContentLoaded', function(){
  const slotSelect = document.getElementById('slotSelect');
  const cargarBtn = document.getElementById('cargarBtn');
  const tbody = document.querySelector('#unidadesTable tbody');

  // Cargar slots disponibles
  fetch('/api/slots')
    .then(r => r.json())
    .then(slots => {
      slotSelect.innerHTML = '';
      slots.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.nombre_real || s.slug || (`Slot ${s.id}`);
        slotSelect.appendChild(opt);
      });
    }).catch(()=>{})

  function cargarUnidades(){
    const slotId = slotSelect.value || 1;
    fetch(`/admin/unidades?slot_id=${slotId}`, { headers: { 'Accept': 'application/json' } })
      .then(r => r.json())
      .then(unidades => {
        tbody.innerHTML = '';
        unidades.forEach(u => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><input type="checkbox" class="selUnidad" data-unidad="${u.unidad_id}"></td>
            <td>${u.unidad_id}</td>
            <td>${u.lat}</td>
            <td>${u.lng}</td>
            <td>${u.velocidad_kmh || 0}</td>
            <td>${u.nivel_bateria || '-'}</td>
            <td>${u.timestamp || '-'}</td>
            <td>${u.tractor_placa || '-'}</td>
            <td><button class="vincularBtn" data-unidad="${u.unidad_id}" data-slot="${slotId}">Vincular</button></td>
          `;
          tbody.appendChild(tr);
        });
        attachButtons();
      }).catch(e => { console.error(e); alert('Error cargando unidades') })
  }

  function attachButtons(){
    document.querySelectorAll('.vincularBtn').forEach(btn => {
      btn.removeEventListener('click', onVincularClick);
      btn.addEventListener('click', onVincularClick);
    })
  }

  function onVincularClick(e){
    const unidad = e.currentTarget.dataset.unidad;
    const slotId = e.currentTarget.dataset.slot;
    // Pedir lista de tractores para este slot
    fetch(`/admin/tractores?slot_id=${slotId}`, { headers: { 'Accept': 'application/json' } })
      .then(r => r.json())
      .then(tractores => {
        // Construir prompt simple: mostrar placas y ids
        let opciones = tractores.map(t => `${t.id}:${t.placa}`).join('\n');
        const seleccion = prompt('Selecciona tractor (formato id:placa)\n' + opciones);
        if(!seleccion) return;
        const tractorId = seleccion.split(':')[0];
        fetch(`/admin/unidades/${encodeURIComponent(unidad)}/vincular`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tractor_id: tractorId })
        }).then(r => r.json()).then(resp => {
          if(resp.ok){ alert('Vinculado'); cargarUnidades(); }
          else alert('Error: ' + (resp.error || ''))
        }).catch(e => { console.error(e); alert('Error vincular') })
      }).catch(e => { console.error(e); alert('Error cargando tractores') })
  }

  // Bulk vincular: seleccionar filas y asignar el mismo tractor
  const bulkBtn = document.getElementById('bulkVincularBtn');
  bulkBtn.addEventListener('click', function(){
    const selected = Array.from(document.querySelectorAll('.selUnidad:checked')).map(ch => ch.dataset.unidad);
    if(!selected.length){ alert('Selecciona al menos una unidad'); return; }
    const tractorId = prompt('Ingresa tractor_id para vincular a las unidades seleccionadas');
    if(!tractorId) return;
    const mappings = selected.map(u => ({ unidad_id: u, tractor_id: parseInt(tractorId) }));
    fetch('/admin/unidades/bulk_vincular', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mappings })
    }).then(r => r.json()).then(resp => {
      if(resp.ok){ alert(`Procesadas=${resp.procesadas} exitosas=${resp.exitosas}`); cargarUnidades(); }
      else alert('Error: ' + (resp.error || ''))
    }).catch(e => { console.error(e); alert('Error bulk vincular') })
  });

  // Upload CSV and call bulk endpoint
  const uploadInput = document.getElementById('uploadInput');
  const uploadBtn = document.getElementById('uploadBtn');
  uploadBtn.addEventListener('click', function(){
    const f = uploadInput.files[0];
    if(!f){ alert('Selecciona un archivo CSV'); return; }
    const reader = new FileReader();
    reader.onload = function(ev){
      const text = ev.target.result;
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length>0);
      if(!lines.length){ alert('CSV vacío'); return; }
      // detectar header
      let start = 0;
      const firstCols = lines[0].split(',').map(c=>c.trim().toLowerCase());
      if(firstCols.includes('unidad') || firstCols.includes('unidad_id') || firstCols.includes('tractor') || firstCols.includes('tractor_id')) start = 1;
      const mappings = [];
      for(let i=start;i<lines.length;i++){
        const cols = lines[i].split(',').map(c=>c.trim());
        if(cols.length < 2) continue;
        const unidad = cols[0];
        const tractor = parseInt(cols[1]);
        if(!unidad || isNaN(tractor)) continue;
        mappings.push({ unidad_id: unidad, tractor_id: tractor });
      }
      if(!mappings.length){ alert('No se detectaron mappings válidos'); return; }
      fetch('/admin/unidades/bulk_vincular', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mappings }) })
        .then(r=>r.json()).then(resp=>{
          if(resp.ok){ alert(`Procesadas=${resp.procesadas} exitosas=${resp.exitosas}`); cargarUnidades(); }
          else alert('Error: '+(resp.error||''));
        }).catch(e=>{ console.error(e); alert('Error enviando mappings'); });
    };
    reader.readAsText(f);
  });

  cargarBtn.addEventListener('click', cargarUnidades);
  // cargar por defecto
  setTimeout(cargarUnidades, 300);
});

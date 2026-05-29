let _uploadEventId = null;
let _uploadSessionKey = null;
let _uploadQueue = [];

function renderUpload(eventId, eventName) {
  _uploadEventId = eventId;
  _uploadSessionKey = `${getUser()?.id}_${eventId}`;

  return `
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        <div>
          <div class="card-title">📤 Upload de Fotos</div>
          <div class="card-subtitle">Arraste fotos ou clique para selecionar. QR Codes detectados automaticamente.</div>
        </div>
        <span class="badge badge-blue">Sessão ativa</span>
      </div>

      <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <p>Arraste fotos aqui ou clique para selecionar</p>
        <small>JPG, PNG, WEBP, HEIC — sem limite de quantidade</small>
      </div>
      <input type="file" id="file-input" multiple accept="image/*,.heic,.heif"
             style="display:none" onchange="handleFileSelect(this.files)" />

      <div id="upload-progress-list" class="upload-progress-list"></div>

      <div id="upload-stats" style="display:none;margin-top:14px" class="flex gap-3">
        <span class="badge badge-green" id="stat-ok">0 enviadas</span>
        <span class="badge badge-orange" id="stat-pending">0 na fila</span>
      </div>
    </div>
  `;
}

function initUploadDrop() {
  const zone = document.getElementById('upload-zone');
  if (!zone) return;
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    handleFileSelect(e.dataTransfer.files);
  });
}

function handleFileSelect(files) {
  const list = [...files];
  if (!list.length) return;

  const container = document.getElementById('upload-progress-list');
  const stats = document.getElementById('upload-stats');
  stats.style.display = 'flex';

  list.forEach(file => {
    const id = 'up_' + Math.random().toString(36).slice(2);
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.id = id;
    item.innerHTML = `
      <span class="upload-item-name">${file.name}</span>
      <div class="upload-item-bar"><div class="upload-item-fill" id="${id}-fill" style="width:0%"></div></div>
      <span class="upload-item-status" id="${id}-status">0%</span>
    `;
    container.appendChild(item);
    uploadFile(file, id);
  });
}

let _okCount = 0;
async function uploadFile(file, itemId) {
  const fill = document.getElementById(`${itemId}-fill`);
  const status = document.getElementById(`${itemId}-status`);

  try {
    await api.uploadPhoto(_uploadEventId, file, _uploadSessionKey, (pct) => {
      if (fill) fill.style.width = pct + '%';
      if (status) status.textContent = pct + '%';
    });
    if (fill) fill.style.background = 'var(--green)';
    if (status) status.textContent = '✓';
    _okCount++;
    const okEl = document.getElementById('stat-ok');
    if (okEl) okEl.textContent = `${_okCount} enviadas`;
  } catch (err) {
    if (fill) fill.style.background = 'var(--red)';
    if (status) status.textContent = '✗';
    toast.error(`Erro: ${file.name}`);
  }
}

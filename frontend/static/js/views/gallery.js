async function renderGallery(params) {
  const { lead_id } = params;

  setContent(`
    <div class="page">
      ${navbarHTML(false)}
      <div class="gallery-hero">
        <div class="animate-pulse text-muted">Carregando sua galeria…</div>
      </div>
    </div>
  `);

  let lead, photos, event;
  try {
    lead = await api.getLead(lead_id);
    [photos, event] = await Promise.all([
      api.listLeadPhotos(lead_id),
      api.getEvent(lead.event_id)
    ]);
  } catch {
    document.querySelector('.gallery-hero').innerHTML = `
      <p style="color:var(--red)">Galeria não encontrada. Verifique o link.</p>`;
    return;
  }

  const container = document.querySelector('.page');
  container.innerHTML = `
    ${navbarHTML(false)}
    <div class="gallery-hero">
      <h1>📸 Suas fotos, ${lead.name.split(' ')[0]}!</h1>
      <p>${event.name}</p>
      <div class="gallery-meta">
        <span class="badge badge-orange">Lead #${lead.lead_number}</span>
        <span class="badge badge-green">${photos.length} foto${photos.length !== 1 ? 's' : ''}</span>
        <span class="text-xs text-muted">${event.date}</span>
      </div>
      ${photos.length > 0 ? `
        <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
          <button class="btn btn-primary btn-sm" onclick="downloadAll('${lead_id}', '${event.name}', '${lead.lead_number}')">
            ⬇️ Baixar todas
          </button>
          <button class="btn btn-ghost btn-sm" onclick="shareGallery()">
            🔗 Compartilhar
          </button>
        </div>
      ` : ''}
    </div>

    ${photos.length === 0
      ? `<div class="gallery-empty">
           <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
             <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
             <path d="m21 15-5-5L5 21"/>
           </svg>
           <p>Nenhuma foto ainda.<br>Em breve você receberá as fotos aqui!</p>
         </div>`
      : `<div class="photo-grid" id="photo-grid">
           ${photos.map(p => photoThumb(p)).join('')}
         </div>`
    }

    <div class="lightbox hidden" id="lightbox">
      <button class="lightbox-close" onclick="closeLightbox()">✕</button>
      <img id="lightbox-img" src="" alt="foto" />
      <div class="lightbox-actions">
        <a id="lightbox-dl" href="" download class="btn btn-primary btn-sm">⬇️ Baixar</a>
      </div>
    </div>
  `;
}

function photoThumb(photo) {
  return `
    <div class="photo-item" onclick="openLightbox('${photo.preview_url}', '${photo.original_url}', '${photo.filename}')">
      <img src="${photo.thumbnail_url}" alt="${photo.filename}" loading="lazy" />
      <div class="photo-overlay">
        <button class="photo-dl-btn" onclick="event.stopPropagation();downloadPhoto('${photo.original_url}','${photo.filename}')">
          ⬇️ Baixar
        </button>
      </div>
    </div>
  `;
}

function openLightbox(previewUrl, originalUrl, filename) {
  const lb = document.getElementById('lightbox');
  document.getElementById('lightbox-img').src = previewUrl;
  const dl = document.getElementById('lightbox-dl');
  dl.href = originalUrl;
  dl.download = filename;
  lb.classList.remove('hidden');
}

function closeLightbox() {
  document.getElementById('lightbox')?.classList.add('hidden');
}

document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLightbox(); });

function downloadPhoto(url, filename) {
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
}

async function downloadAll(leadId, eventName, leadNum) {
  toast.info('Preparando download…');
  const a = document.createElement('a');
  a.href = `/api/photos/event/${leadId}/download`;
  a.download = `${eventName}-lead-${leadNum}.zip`;
  a.click();
}

function shareGallery() {
  const url = location.href;
  if (navigator.share) {
    navigator.share({ title: 'Minhas fotos — Shared Pics', url });
  } else {
    navigator.clipboard.writeText(url).then(() => toast.success('Link copiado!'));
  }
}

function navbarHTML(showAdmin = true) {
  const user = getUser();
  return `
    <nav class="navbar">
      <a class="navbar-brand" ${showAdmin ? `data-route="/admin"` : `href="/"`}>
        ${logoSVG(28)}
        <span>Shared Pics</span>
      </a>
      <div class="navbar-actions">
        ${showAdmin && user
          ? `<span class="text-sm text-muted">${user.name}</span>
             <button class="btn btn-ghost btn-sm" onclick="logout()">Sair</button>`
          : ''}
      </div>
    </nav>
  `;
}

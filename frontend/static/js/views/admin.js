// ── Admin Shell ───────────────────────────────────────────────
function adminShell(activeSection, content) {
  const user = getUser();
  return `
    <div class="admin-layout">
      <aside class="sidebar">
        <div class="sidebar-brand">
          ${logoSVG(28)}
          <span>Shared Pics</span>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-label">Principal</div>
          <a class="sidebar-link ${activeSection === 'dashboard' ? 'active' : ''}" data-route="/admin">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
            Dashboard
            ${activeSection === 'dashboard' ? '<span class="dot"></span>' : ''}
          </a>
          <a class="sidebar-link ${activeSection === 'events' ? 'active' : ''}" data-route="/admin/events">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
            </svg>
            Eventos
          </a>
          <a class="sidebar-link ${activeSection === 'upload' ? 'active' : ''}" data-route="/admin/upload">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            Upload
          </a>
        </div>
        <div style="margin-top:auto;padding:16px 12px;border-top:1px solid var(--border)">
          <div style="font-size:0.82rem;color:var(--text-3);margin-bottom:8px">${user?.name || ''}</div>
          <button class="btn btn-ghost btn-sm btn-full" onclick="logout()">Sair</button>
        </div>
      </aside>

      <div class="admin-main">
        <div class="admin-topbar">
          <span class="admin-page-title">${pageTitles[activeSection] || 'Admin'}</span>
          <button class="btn btn-primary btn-sm" onclick="openNewEventModal()">+ Novo Evento</button>
        </div>
        <div class="admin-content">${content}</div>
      </div>
    </div>

    ${newEventModalHTML()}
    ${eventDetailModalHTML()}
    <div id="toast-container"></div>
  `;
}

const pageTitles = {
  dashboard: 'Dashboard',
  events: 'Eventos',
  upload: 'Upload de Fotos',
  leads: 'Participantes',
};

// ── Dashboard ───────────────────────────────────────────────
async function renderAdminDashboard() {
  if (!requireAuth()) return;
  setContent(adminShell('dashboard', `<div class="animate-pulse text-muted">Carregando…</div>`));

  try {
    const events = await api.listEvents();
    const totalLeads = events.reduce((s, e) => s + e.lead_count, 0);
    const totalPhotos = events.reduce((s, e) => s + e.photo_count, 0);

    const content = `
      <div class="stats-grid" style="margin-bottom:28px">
        <div class="stat-card">
          <div class="stat-value">${events.length}</div>
          <div class="stat-label">Eventos</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${totalLeads}</div>
          <div class="stat-label">Leads capturados</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${totalPhotos}</div>
          <div class="stat-label">Fotos enviadas</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${events.filter(e => e.photo_count > 0).length}</div>
          <div class="stat-label">Eventos com fotos</div>
        </div>
      </div>

      <div class="section-header">
        <div class="section-title">Eventos recentes</div>
        <button class="btn btn-ghost btn-sm" data-route="/admin/events">Ver todos</button>
      </div>

      ${events.length === 0
        ? `<div class="gallery-empty" style="padding:48px 0">
             <p>Nenhum evento ainda.<br>Crie seu primeiro evento!</p>
             <button class="btn btn-primary btn-sm" onclick="openNewEventModal()">+ Criar evento</button>
           </div>`
        : `<div class="events-list">${events.slice(0, 5).map(eventCard).join('')}</div>`
      }
    `;
    setContent(adminShell('dashboard', content));
    initNewEventModal();
  } catch (err) {
    toast.error('Erro ao carregar dashboard');
  }
}

// ── Events List ───────────────────────────────────────────────
async function renderAdminEvents() {
  if (!requireAuth()) return;
  setContent(adminShell('events', `<div class="animate-pulse text-muted">Carregando eventos…</div>`));

  try {
    const events = await api.listEvents();
    const content = `
      <div class="section-header" style="margin-bottom:20px">
        <div class="section-title">Todos os Eventos</div>
        <button class="btn btn-primary btn-sm" onclick="openNewEventModal()">+ Novo Evento</button>
      </div>
      ${events.length === 0
        ? `<div class="gallery-empty" style="padding:64px 0">
             <p>Nenhum evento ainda. Crie seu primeiro!</p>
             <button class="btn btn-primary" onclick="openNewEventModal()">+ Criar evento</button>
           </div>`
        : `<div class="events-list">${events.map(eventCard).join('')}</div>`
      }
    `;
    setContent(adminShell('events', content));
    initNewEventModal();
  } catch {
    toast.error('Erro ao listar eventos');
  }
}

function eventCard(ev) {
  return `
    <div class="event-card" onclick="openEventDetail('${ev.id}')">
      <div class="event-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
        </svg>
      </div>
      <div class="event-info">
        <div class="event-name">${ev.name}</div>
        <div class="event-meta">${ev.date} ${ev.location ? '· ' + ev.location : ''}</div>
      </div>
      <div class="event-stats">
        <div class="event-stat"><strong>${ev.lead_count}</strong><span>leads</span></div>
        <div class="event-stat"><strong>${ev.photo_count}</strong><span>fotos</span></div>
      </div>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-3)">
        <polyline points="9 18 15 12 9 6"/>
      </svg>
    </div>
  `;
}

// ── Event Detail ───────────────────────────────────────────────
async function openEventDetail(eventId) {
  const modal = document.getElementById('event-detail-modal');
  const body = document.getElementById('event-detail-body');
  if (!modal) return;
  modal.classList.remove('hidden');
  body.innerHTML = `<div class="animate-pulse text-muted" style="padding:24px 0">Carregando…</div>`;

  try {
    const [stats, leads, photos] = await Promise.all([
      api.eventStats(eventId),
      api.listLeads(eventId),
      api.listPhotos(eventId),
    ]);
    const ev = stats.event;

    body.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:20px">
        <!-- Stats -->
        <div class="stats-grid">
          <div class="stat-card"><div class="stat-value">${stats.total_leads}</div><div class="stat-label">Leads</div></div>
          <div class="stat-card"><div class="stat-value">${stats.total_photos}</div><div class="stat-label">Fotos</div></div>
          <div class="stat-card"><div class="stat-value">${stats.tagged_photos}</div><div class="stat-label">Associadas</div></div>
          <div class="stat-card"><div class="stat-value">${stats.leads_with_photos}</div><div class="stat-label">Leads c/ fotos</div></div>
        </div>

        <!-- QR do evento -->
        ${ev.qr_code_url ? `
        <div>
          <div class="section-title" style="margin-bottom:12px">QR Code do Evento</div>
          <div class="qr-card" style="flex-direction:row;align-items:center;gap:20px;justify-content:flex-start">
            <img src="${ev.qr_code_url}" alt="QR" style="width:110px;height:110px" />
            <div>
              <p class="text-sm">Exiba este QR Code na entrada do evento para os participantes se cadastrarem.</p>
              <div style="display:flex;gap:8px;margin-top:10px">
                <a href="${ev.qr_code_url}" download="qr-${ev.name}.png" class="btn btn-ghost btn-sm">⬇️ Baixar QR</a>
                <button class="btn btn-primary btn-sm" onclick="notifyAll('${eventId}')">📱 Notificar todos</button>
                <a href="/api/photos/event/${eventId}/download" class="btn btn-ghost btn-sm">📦 Baixar ZIP</a>
              </div>
            </div>
          </div>
        </div>
        ` : ''}

        <!-- Leads table -->
        <div>
          <div class="section-header" style="margin-bottom:12px">
            <div class="section-title">Participantes (${leads.length})</div>
          </div>
          <div style="overflow-x:auto">
            <table class="leads-table">
              <thead>
                <tr><th>Lead</th><th>Nome</th><th>WhatsApp</th><th>Fotos</th><th>Ações</th></tr>
              </thead>
              <tbody>
                ${leads.map(l => `
                  <tr>
                    <td><span class="badge badge-orange">#${l.lead_number}</span></td>
                    <td>
                      <div style="display:flex;align-items:center;gap:10px">
                        <div class="leads-avatar">${l.name.charAt(0).toUpperCase()}</div>
                        ${l.name}
                      </div>
                    </td>
                    <td class="text-muted">${l.phone}</td>
                    <td>
                      <span class="badge ${l.photo_count > 0 ? 'badge-green' : 'badge-blue'}">${l.photo_count} foto${l.photo_count !== 1 ? 's' : ''}</span>
                    </td>
                    <td>
                      <div style="display:flex;gap:6px">
                        ${l.gallery_url ? `<a href="${l.gallery_url}" target="_blank" class="btn btn-ghost btn-sm">Ver galeria</a>` : ''}
                        <button class="btn btn-ghost btn-sm" onclick="notifyLead('${l.id}')">📱</button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Upload inline -->
        <div>
          <div class="section-title" style="margin-bottom:12px">Upload para este evento</div>
          ${renderUpload(eventId, ev.name)}
        </div>
      </div>
    `;
    setTimeout(initUploadDrop, 50);
  } catch (err) {
    body.innerHTML = `<p style="color:var(--red)">Erro: ${err.message}</p>`;
  }
}

async function notifyLead(leadId) {
  try {
    await api.notifyLead(leadId);
    toast.success('Notificação enviada!');
  } catch {
    toast.error('Erro ao notificar');
  }
}

async function notifyAll(eventId) {
  try {
    const r = await api.notifyAll(eventId);
    toast.success(`${r.queued} participantes notificados!`);
  } catch {
    toast.error('Erro ao notificar');
  }
}

// ── Upload Page ───────────────────────────────────────────────
async function renderAdminUpload() {
  if (!requireAuth()) return;
  const events = await api.listEvents().catch(() => []);

  const content = `
    <div class="section-title" style="margin-bottom:20px">Upload de Fotos</div>
    ${events.length === 0
      ? `<div class="card"><p class="text-muted">Crie um evento primeiro para fazer upload.</p></div>`
      : `
        <div class="form-group" style="max-width:400px;margin-bottom:20px">
          <label class="form-label">Selecionar evento</label>
          <select class="form-input" id="upload-event-select" onchange="changeUploadEvent(this.value)">
            ${events.map(e => `<option value="${e.id}">${e.name} (${e.date})</option>`).join('')}
          </select>
        </div>
        <div id="upload-area">
          ${renderUpload(events[0].id, events[0].name)}
        </div>
      `
    }
  `;

  setContent(adminShell('upload', content));
  setTimeout(initUploadDrop, 50);
  initNewEventModal();
}

function changeUploadEvent(eventId) {
  const event = _cachedEvents?.find(e => e.id === eventId);
  document.getElementById('upload-area').innerHTML = renderUpload(eventId, event?.name || '');
  setTimeout(initUploadDrop, 50);
}

// ── New Event Modal ───────────────────────────────────────────
function newEventModalHTML() {
  return `
    <div class="modal-backdrop hidden" id="new-event-modal">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">Criar novo evento</span>
          <button class="modal-close" onclick="closeNewEventModal()">✕</button>
        </div>
        <form id="new-event-form">
          <div class="form-group">
            <label class="form-label">Nome do evento *</label>
            <input class="form-input" name="name" placeholder="Ex: Conferência Tech 2025" required />
          </div>
          <div class="form-group">
            <label class="form-label">Data *</label>
            <input class="form-input" type="date" name="date" required />
          </div>
          <div class="form-group">
            <label class="form-label">Local</label>
            <input class="form-input" name="location" placeholder="Ex: São Paulo, SP" />
          </div>
          <div class="form-group">
            <label class="form-label">Descrição</label>
            <input class="form-input" name="description" placeholder="Breve descrição opcional" />
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="create-event-btn">
            Criar Evento
          </button>
        </form>
      </div>
    </div>
  `;
}

function eventDetailModalHTML() {
  return `
    <div class="modal-backdrop hidden" id="event-detail-modal" style="align-items:flex-start;overflow-y:auto;padding:40px 24px">
      <div class="modal" style="max-width:860px;width:100%">
        <div class="modal-header">
          <span class="modal-title">Detalhes do Evento</span>
          <button class="modal-close" onclick="document.getElementById('event-detail-modal').classList.add('hidden')">✕</button>
        </div>
        <div id="event-detail-body"></div>
      </div>
    </div>
  `;
}

function openNewEventModal() {
  document.getElementById('new-event-modal')?.classList.remove('hidden');
}
function closeNewEventModal() {
  document.getElementById('new-event-modal')?.classList.add('hidden');
}

function initNewEventModal() {
  const form = document.getElementById('new-event-form');
  if (!form || form._bound) return;
  form._bound = true;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('create-event-btn');
    const fd = new FormData(e.target);
    btn.disabled = true; btn.textContent = 'Criando…';
    try {
      const user = getUser();
      await api.createEvent({
        name: fd.get('name'), date: fd.get('date'),
        location: fd.get('location') || '', description: fd.get('description') || '',
        organizer_id: user.id
      });
      toast.success('Evento criado!');
      closeNewEventModal();
      renderAdminDashboard();
    } catch (err) {
      toast.error(err.message);
      btn.disabled = false; btn.textContent = 'Criar Evento';
    }
  });
}

let _cachedEvents = [];

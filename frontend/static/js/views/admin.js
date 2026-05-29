// ── Admin Shell ───────────────────────────────────────────────
function adminShell(activeSection, content) {
  const user = getUser();

  // Profile button (shown on all pages)
  const profileBtn = `
    <button class="btn btn-ghost btn-icon" onclick="openProfileModal()" title="Perfil">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
      </svg>
    </button>`;

  // Topbar right button
  let topbarRight = profileBtn;
  if (activeSection !== 'dashboard') {
    // Show + Novo Evento on events/upload pages
    if (activeSection === 'events' || activeSection === 'upload') {
      topbarRight = `<button class="btn btn-primary btn-sm" onclick="openNewEventModal()" style="margin-right:8px">+ Novo Evento</button>` + profileBtn;
    }
  }

  // Back navigation per section
  const backRoutes = {
    events: '/admin',
    upload: '/admin',
    equipment: '/admin',
    event: '/admin/events',
  };
  const backRoute = backRoutes[activeSection];
  const backBtn = backRoute
    ? `<button class="topbar-back" data-route="${backRoute}">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>`
    : '';

  // Topbar title
  const topbarTitle = pageTitles[activeSection] || 'Admin';

  return `
    <div class="admin-layout">
      <aside class="sidebar">
        <div class="sidebar-brand" data-route="/admin" style="cursor:pointer">
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
          <div style="display:flex;align-items:center;gap:8px">
            ${backBtn}
            <button class="topbar-logo" data-route="/admin" title="Início">
              ${logoSVG(22)}
            </button>
            <span class="admin-page-title">${topbarTitle}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;position:relative">${topbarRight}</div>
        </div>
        <div class="admin-content">${content}</div>
      </div>
    </div>

    ${newEventModalHTML()}
    ${whatsappModalHTML()}
    ${profileOverlayHTML()}
    <div id="toast-container"></div>
  `;
}

function toggleProfileMenu() {
  const menu = document.getElementById('profile-menu');
  if (menu) menu.classList.toggle('hidden');
  setTimeout(() => {
    document.addEventListener('click', function closeMenu(e) {
      if (!e.target.closest('#profile-menu') && !e.target.closest('.btn-icon')) {
        menu?.classList.add('hidden');
        document.removeEventListener('click', closeMenu);
      }
    });
  }, 10);
}

async function openProfileModal() {
  const user = getUser();
  const overlay = document.getElementById('profile-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  document.getElementById('profile-overlay-body').innerHTML = `<div class="animate-pulse text-muted">Carregando…</div>`;
  try {
    const events = await api.listEvents();
    const totalPhotos = events.reduce((s, e) => s + e.photo_count, 0);
    const totalLeads = events.reduce((s, e) => s + e.lead_count, 0);
    document.getElementById('profile-overlay-body').innerHTML = `
      <div style="text-align:center;margin-bottom:24px">
        <div class="profile-avatar-big">${(user?.name || 'U').charAt(0).toUpperCase()}</div>
        <div style="font-weight:700;font-size:1.1rem;margin-top:10px">${user?.name || 'Usuário'}</div>
        <div style="color:var(--text-3);font-size:0.85rem">${user?.email || ''}</div>
      </div>
      <div class="stats-grid" style="margin-bottom:20px">
        <div class="stat-card"><div class="stat-value">${events.length}</div><div class="stat-label">Eventos</div></div>
        <div class="stat-card"><div class="stat-value">${totalPhotos}</div><div class="stat-label">Fotos</div></div>
        <div class="stat-card"><div class="stat-value">${totalLeads}</div><div class="stat-label">Leads</div></div>
        <div class="stat-card"><div class="stat-value">${events.filter(e=>e.photo_count>0).length}</div><div class="stat-label">Com fotos</div></div>
      </div>
      <button class="btn btn-ghost btn-full" onclick="logout()">Sair da conta</button>
    `;
  } catch {
    document.getElementById('profile-overlay-body').innerHTML = `<button class="btn btn-ghost btn-full" onclick="logout()">Sair</button>`;
  }
}

const pageTitles = {
  dashboard: 'SharePics',
  events: 'Eventos',
  upload: 'Upload de Fotos',
  leads: 'Participantes',
  equipment: 'Novo Evento',
  event: '',  // set dynamically
};

// ── Dashboard ───────────────────────────────────────────────
async function renderAdminDashboard() {
  if (!requireAuth()) return;
  setContent(adminShell('dashboard', `<div class="animate-pulse text-muted">Carregando…</div>`));

  try {
    const events = await api.listEvents();
    _cachedEvents = events;

    const content = `
      <!-- 4 Action Buttons -->
      <div class="action-grid">

        <button class="action-btn" data-route="/admin/equipment">
          <div class="action-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
              <line x1="12" y1="14" x2="12" y2="18"/><line x1="10" y1="16" x2="14" y2="16"/>
            </svg>
          </div>
          <span class="action-label">Criar Evento</span>
        </button>

        <button class="action-btn" data-route="/admin/upload">
          <div class="action-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <span class="action-label">Upload de Fotos</span>
        </button>

        <button class="action-btn" data-route="/admin/events">
          <div class="action-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>
              <line x1="8" y1="18" x2="21" y2="18"/>
              <circle cx="3.5" cy="6" r="1.5" fill="currentColor"/>
              <circle cx="3.5" cy="12" r="1.5" fill="currentColor"/>
              <circle cx="3.5" cy="18" r="1.5" fill="currentColor"/>
            </svg>
          </div>
          <span class="action-label">Todos os Eventos</span>
        </button>

        <button class="action-btn" onclick="showLatestQR()">
          <div class="action-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="5" y="5" width="3" height="3" fill="currentColor" stroke="none"/>
              <rect x="16" y="5" width="3" height="3" fill="currentColor" stroke="none"/>
              <rect x="16" y="16" width="3" height="3" fill="currentColor" stroke="none"/>
            </svg>
          </div>
          <span class="action-label">QR do Evento</span>
        </button>

      </div>

      <!-- Recent events -->
      <div class="section-header">
        <div class="section-title">Eventos recentes</div>
        <button class="btn btn-ghost btn-sm" data-route="/admin/events">Ver todos</button>
      </div>

      ${events.length === 0
        ? `<div class="gallery-empty" style="padding:32px 0">
             <p>Nenhum evento ainda.<br>Crie seu primeiro evento!</p>
             <button class="btn btn-primary btn-sm" data-route="/admin/equipment">+ Criar evento</button>
           </div>`
        : `<div class="events-list">${events.slice(0, 5).map(eventCard).join('')}</div>`
      }

      <!-- QR fullscreen overlay -->
      <div class="qr-overlay hidden" id="qr-overlay" onclick="this.classList.add('hidden')">
        <div class="qr-overlay-inner" onclick="event.stopPropagation()">
          <button onclick="document.getElementById('qr-overlay').classList.add('hidden')" style="position:absolute;top:12px;right:12px;background:none;border:none;color:var(--text-1);font-size:1.4rem;cursor:pointer">✕</button>
          <div id="qr-overlay-content"></div>
        </div>
      </div>
    `;
    setContent(adminShell('dashboard', content));
    initNewEventModal();
  } catch (err) {
    toast.error('Erro ao carregar dashboard');
  }
}

async function showLatestQR() {
  const events = _cachedEvents || [];
  if (events.length === 0) { toast.error('Nenhum evento criado ainda'); return; }
  const ev = events[0]; // most recent
  try {
    const stats = await api.eventStats(ev.id);
    const e = stats.event;
    const overlay = document.getElementById('qr-overlay');
    const content = document.getElementById('qr-overlay-content');
    if (!overlay) return;
    content.innerHTML = e.qr_code_url
      ? `<div style="text-align:center">
           <div style="font-size:1.1rem;font-weight:700;margin-bottom:8px">${e.name}</div>
           <div style="font-size:0.85rem;color:var(--text-3);margin-bottom:16px">${e.date}${e.location ? ' · ' + e.location : ''}</div>
           <img src="${e.qr_code_url}" style="width:220px;height:220px;border-radius:12px" />
           <div style="margin-top:16px;display:flex;flex-direction:column;gap:8px">
             <a href="${e.qr_code_url}" download="qr-${e.name}.png" class="btn btn-ghost btn-sm">⬇️ Baixar QR</a>
             <button class="btn btn-primary btn-sm" onclick="notifyAll('${e.id}')">📱 Notificar todos via WhatsApp</button>
           </div>
         </div>`
      : `<p class="text-muted">QR Code não disponível</p>`;
    overlay.classList.remove('hidden');
  } catch { toast.error('Erro ao carregar QR'); }
}

// ── Equipment Selection ────────────────────────────────────────
function renderEquipmentSelect() {
  if (!requireAuth()) return;

  const equipments = [
    {
      key: 'dslr',
      label: 'DSLR / Mirrorless',
      icon: `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
        <circle cx="12" cy="13" r="4"/>
      </svg>`
    },
    {
      key: 'mobile',
      label: 'Celular / iPad',
      icon: `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="5" y="2" width="14" height="20" rx="2"/>
        <circle cx="12" cy="17" r="1" fill="currentColor" stroke="none"/>
      </svg>`
    },
    {
      key: 'video',
      label: 'Câmera de Vídeo',
      icon: `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="23 7 16 12 23 17 23 7"/>
        <rect x="1" y="5" width="15" height="14" rx="2"/>
      </svg>`
    },
    {
      key: 'cam360',
      label: 'Câmera 360°',
      icon: `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M2 12c3-4 7-6 10-6s7 2 10 6"/>
        <path d="M2 12c3 4 7 6 10 6s7-2 10-6"/>
        <line x1="12" y1="2" x2="12" y2="22"/>
      </svg>`
    },
  ];

  const content = `
    <div style="margin-bottom:20px">
      <p class="text-muted" style="font-size:0.9rem">Selecione o equipamento para registrar no evento</p>
    </div>
    <div class="action-grid">
      ${equipments.map(eq => `
        <button class="action-btn" onclick="openNewEventModal('${eq.key}')">
          <div class="action-icon action-icon-lg">${eq.icon}</div>
          <span class="action-label">${eq.label}</span>
        </button>
      `).join('')}
    </div>
  `;

  setContent(adminShell('equipment', content));
  initNewEventModal();
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

// ── Event Detail: navigate to full page ────────────────────────
function openEventDetail(eventId) {
  Router.navigate(`/admin/event/${eventId}`);
}

async function _legacyEventDetail(eventId) {
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
          <div class="qr-card" style="align-items:center;gap:16px">
            <img src="${ev.qr_code_url}" alt="QR" style="width:130px;height:130px;border-radius:8px" />
            <p class="text-sm" style="text-align:center;color:var(--text-3)">Exiba este QR Code na entrada para os participantes se cadastrarem.</p>
            <div style="display:flex;flex-direction:column;gap:10px;width:100%">
              <a href="${ev.qr_code_url}" download="qr-${ev.name}.png" class="btn btn-ghost btn-sm btn-full">⬇️ Baixar QR Code</a>
              <button class="btn btn-primary btn-sm btn-full" onclick="notifyAll('${eventId}')">📱 Notificar todos via WhatsApp</button>
              <a href="/api/photos/event/${eventId}/download" class="btn btn-ghost btn-sm btn-full">📦 Baixar ZIP das Fotos</a>
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
        <div style="margin-bottom:12px">
          <span class="badge badge-orange equipment-badge" style="font-size:0.85rem;padding:4px 10px"></span>
        </div>
        <form id="new-event-form">
          <div class="form-group">
            <label class="form-label">Nome do evento *</label>
            <input class="form-input" name="name" placeholder="Ex: Casamento Silva 2025" required />
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

function whatsappModalHTML() {
  return `
    <div class="modal-backdrop hidden" id="whatsapp-modal">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">📱 Enviar via WhatsApp</span>
          <button class="modal-close" onclick="closeWhatsappModal()">✕</button>
        </div>
        <div style="margin-bottom:14px;color:var(--text-3);font-size:0.85rem">
          As fotos selecionadas serão enviadas para este número.
        </div>
        <form id="whatsapp-form">
          <div class="form-group">
            <label class="form-label">Nome do participante *</label>
            <input class="form-input" id="wa-name" placeholder="Ex: Maria Silva" required />
          </div>
          <div class="form-group">
            <label class="form-label">DDD + Número WhatsApp *</label>
            <input class="form-input" id="wa-phone" type="tel"
              placeholder="Ex: 11987654321" required />
          </div>
          <div class="form-group" style="display:flex;align-items:flex-start;gap:10px">
            <input type="checkbox" id="wa-consent" style="margin-top:3px;width:18px;height:18px;flex-shrink:0" required />
            <label for="wa-consent" style="font-size:0.85rem;color:var(--text-2);cursor:pointer">
              Autorizo o uso deste número para envio das fotos via WhatsApp
            </label>
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="wa-send-btn">
            📤 Enviar fotos
          </button>
        </form>
      </div>
    </div>
  `;
}

function profileOverlayHTML() {
  return `
    <div class="modal-backdrop hidden" id="profile-overlay" onclick="if(event.target===this)this.classList.add('hidden')">
      <div class="modal" style="max-width:400px">
        <div class="modal-header">
          <span class="modal-title">Perfil</span>
          <button class="modal-close" onclick="document.getElementById('profile-overlay').classList.add('hidden')">✕</button>
        </div>
        <div id="profile-overlay-body"><div class="animate-pulse text-muted">Carregando…</div></div>
      </div>
    </div>
  `;
}

let _waEventId = null;
let _waPendingPhotoIds = [];

function openWhatsappModal(eventId, photoIds = []) {
  _waEventId = eventId;
  _waPendingPhotoIds = photoIds;
  const modal = document.getElementById('whatsapp-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  document.getElementById('wa-name').value = '';
  document.getElementById('wa-phone').value = '';
  document.getElementById('wa-consent').checked = false;

  const form = document.getElementById('whatsapp-form');
  if (form && !form._bound) {
    form._bound = true;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('wa-send-btn');
      const name = document.getElementById('wa-name').value.trim();
      const phone = document.getElementById('wa-phone').value.trim();
      const consent = document.getElementById('wa-consent').checked;
      if (!consent) { toast.error('Autorize o uso do número'); return; }
      btn.disabled = true; btn.textContent = 'Enviando…';
      try {
        await api.directSend(phone, name, _waEventId, _waPendingPhotoIds);
        toast.success('✅ Enviado com sucesso!');
        closeWhatsappModal();
      } catch (err) {
        toast.error(err.message);
        btn.disabled = false; btn.textContent = '📤 Enviar fotos';
      }
    });
  }
}

function closeWhatsappModal() {
  document.getElementById('whatsapp-modal')?.classList.add('hidden');
}

function openNewEventModal(equipment) {
  const modal = document.getElementById('new-event-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  // Store equipment for form submission
  if (equipment) modal.dataset.equipment = equipment;
  const label = modal.querySelector('.equipment-badge');
  const equipLabels = { dslr: '📷 DSLR/Mirrorless', mobile: '📱 Celular/iPad', video: '🎥 Vídeo', cam360: '🌐 360°' };
  if (label) label.textContent = equipment ? equipLabels[equipment] || '' : '';
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
      const newEvent = await api.createEvent({
        name: fd.get('name'), date: fd.get('date'),
        location: fd.get('location') || '', description: fd.get('description') || '',
        organizer_id: user.id
      });
      toast.success('Evento criado!');
      closeNewEventModal();
      Router.navigate(`/admin/event/${newEvent.id}`);
    } catch (err) {
      toast.error(err.message);
      btn.disabled = false; btn.textContent = 'Criar Evento';
    }
  });
}

let _cachedEvents = [];

// ── Event Page (full page) ────────────────────────────────────
let _eventPageId = null;
let _eventPageUploaded = [];     // photos uploaded this session
let _eventPageSelected = new Set(); // selected photo IDs in folder

async function renderEventPage(params) {
  if (!requireAuth()) return;
  const eventId = params.id;
  _eventPageId = eventId;
  _eventPageUploaded = [];
  _eventPageSelected = new Set();

  setContent(adminShell('event', `<div class="animate-pulse text-muted">Carregando evento…</div>`));

  try {
    const stats = await api.eventStats(eventId);
    const ev = stats.event;

    // Update page title dynamically
    document.querySelector('.admin-page-title').textContent = ev.name;

    const content = `
      <!-- Event Header Info -->
      <div class="event-page-header">
        <div style="font-size:0.85rem;color:var(--text-3)">${ev.date}${ev.location ? ' · ' + ev.location : ''}</div>
        <div class="event-mini-stats">
          <span>${stats.total_photos} fotos</span>
          <span>·</span>
          <span>${stats.total_leads} leads</span>
          <span>·</span>
          <span>${stats.tagged_photos} associadas</span>
        </div>
      </div>

      <!-- Section 1: Upload -->
      <div class="ep-section">
        <div class="ep-section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          Upload de Fotos
        </div>

        <div class="upload-zone" id="upload-zone" onclick="document.getElementById('ep-file-input').click()">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p>Arraste fotos aqui ou toque para selecionar</p>
          <small>JPG, PNG, WEBP, HEIC</small>
        </div>
        <input type="file" id="ep-file-input" multiple accept="image/*,.heic,.heif"
               style="display:none" onchange="epHandleFiles(this.files)" />

        <!-- Uploaded photos queue -->
        <div id="ep-upload-queue"></div>
      </div>

      <!-- Section 2: Pasta do Evento -->
      <div class="ep-section">
        <button class="folder-toggle" id="folder-toggle-btn" onclick="toggleEventFolder()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          Pasta do Evento
          <svg class="folder-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div id="event-folder-content" class="folder-content hidden">
          <div class="animate-pulse text-muted" style="padding:16px 0">Carregando fotos…</div>
        </div>
      </div>

      <!-- QR do evento -->
      ${ev.qr_code_url ? `
      <div class="ep-section">
        <div class="ep-section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>
          </svg>
          QR Code do Evento
        </div>
        <div class="qr-card">
          <img src="${ev.qr_code_url}" style="width:150px;height:150px;border-radius:8px" />
          <p class="text-sm" style="color:var(--text-3);text-align:center">Exiba este QR para os convidados se cadastrarem</p>
          <div style="display:flex;flex-direction:column;gap:10px;width:100%">
            <a href="${ev.qr_code_url}" download="qr-${ev.name}.png" class="btn btn-ghost btn-sm btn-full">⬇️ Baixar QR Code</a>
            <button class="btn btn-primary btn-sm btn-full" onclick="openWhatsappModal('${eventId}')">📱 Enviar via WhatsApp</button>
            <a href="/api/photos/event/${eventId}/download" class="btn btn-ghost btn-sm btn-full">📦 Baixar ZIP das Fotos</a>
          </div>
        </div>
      </div>` : ''}

      <!-- Fullscreen photo viewer -->
      <div class="photo-fullscreen hidden" id="photo-fullscreen" onclick="closeFullscreen()">
        <button onclick="closeFullscreen()" style="position:fixed;top:16px;right:16px;background:rgba(0,0,0,0.5);border:none;color:#fff;font-size:1.5rem;width:44px;height:44px;border-radius:50%;cursor:pointer;z-index:10">✕</button>
        <img id="fullscreen-img" src="" style="max-width:95vw;max-height:90vh;border-radius:8px;object-fit:contain" />
      </div>

      <!-- Floating selection bar -->
      <div class="selection-bar hidden" id="selection-bar">
        <span id="selection-count">0 fotos selecionadas</span>
        <button class="btn btn-primary btn-sm" onclick="sendSelectedPhotos()">📱 Enviar via WhatsApp</button>
        <button class="btn btn-ghost btn-sm" onclick="clearSelection()">✕</button>
      </div>
    `;

    setContent(adminShell('event', content));
    document.querySelector('.admin-page-title').textContent = ev.name;

    // Init upload drop
    const zone = document.getElementById('upload-zone');
    if (zone) {
      zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
      zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
      zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('drag-over'); epHandleFiles(e.dataTransfer.files); });
    }
    initNewEventModal();
  } catch (err) {
    toast.error('Erro ao carregar evento');
  }
}

async function epHandleFiles(files) {
  const queue = document.getElementById('ep-upload-queue');
  if (!queue) return;

  for (const file of [...files]) {
    const id = 'ep_' + Math.random().toString(36).slice(2);
    const previewUrl = URL.createObjectURL(file);

    const item = document.createElement('div');
    item.className = 'ep-upload-item';
    item.id = id;
    item.innerHTML = `
      <div class="ep-thumb-wrap">
        <img src="${previewUrl}" class="ep-thumb" />
        <div class="ep-upload-overlay" id="${id}-overlay">
          <div class="ep-upload-bar"><div class="ep-upload-fill" id="${id}-fill" style="width:0%"></div></div>
          <span id="${id}-pct">0%</span>
        </div>
      </div>
      <div class="ep-upload-info">
        <div class="ep-upload-name">${file.name}</div>
        <div id="${id}-actions" class="ep-upload-actions" style="display:none">
          <div id="${id}-qr-wrap" style="text-align:center"></div>
          <button class="btn btn-primary btn-sm btn-full" onclick="openWhatsappModal('${_eventPageId}', ['${id}-photoid'])">
            📱 Enviar via WhatsApp
          </button>
        </div>
      </div>
    `;
    queue.prepend(item);

    // Upload
    try {
      const photo = await api.uploadPhoto(_eventPageId, file, `${getUser()?.id}_${_eventPageId}`, (pct) => {
        const fill = document.getElementById(`${id}-fill`);
        const pctEl = document.getElementById(`${id}-pct`);
        if (fill) fill.style.width = pct + '%';
        if (pctEl) pctEl.textContent = pct + '%';
      });

      _eventPageUploaded.push(photo);

      const overlay = document.getElementById(`${id}-overlay`);
      if (overlay) overlay.style.display = 'none';

      const actions = document.getElementById(`${id}-actions`);
      if (actions) {
        actions.style.display = 'flex';
        actions.style.flexDirection = 'column';
        actions.style.gap = '8px';
        // Show event QR for quick scan
        const qrWrap = document.getElementById(`${id}-qr-wrap`);
        const ev = await api.getEvent(_eventPageId);
        if (qrWrap && ev.qr_code_url) {
          qrWrap.innerHTML = `
            <img src="${ev.qr_code_url}" style="width:80px;height:80px;border-radius:6px" title="QR do Evento" />
            <div style="font-size:0.75rem;color:var(--text-3);margin-top:4px">QR do evento</div>
          `;
        }
        // Fix the WhatsApp button with real photo ID
        const waBtn = actions.querySelector('.btn-primary');
        if (waBtn) waBtn.onclick = () => openWhatsappModal(_eventPageId, [photo.id]);
      }
    } catch (err) {
      const overlay = document.getElementById(`${id}-overlay`);
      if (overlay) overlay.innerHTML = `<span style="color:var(--red)">✗ Erro</span>`;
      toast.error(`Erro: ${file.name}`);
    }
  }
}

async function toggleEventFolder() {
  const content = document.getElementById('event-folder-content');
  const btn = document.getElementById('folder-toggle-btn');
  const arrow = btn?.querySelector('.folder-arrow');
  if (!content) return;

  const isHidden = content.classList.contains('hidden');
  content.classList.toggle('hidden', !isHidden);
  arrow?.style && (arrow.style.transform = isHidden ? 'rotate(180deg)' : '');

  if (isHidden) {
    content.innerHTML = `<div class="animate-pulse text-muted" style="padding:16px 0">Carregando fotos…</div>`;
    try {
      const photos = await api.listPhotos(_eventPageId);
      if (photos.length === 0) {
        content.innerHTML = `<p class="text-muted" style="padding:12px 0">Nenhuma foto enviada ainda.</p>`;
        return;
      }
      content.innerHTML = `<div class="photo-folder-grid" id="photo-folder-grid">${photos.map(p => photoFolderCard(p)).join('')}</div>`;
    } catch {
      content.innerHTML = `<p style="color:var(--red)">Erro ao carregar fotos</p>`;
    }
  }
}

function photoFolderCard(photo) {
  const preview = (photo.preview_url || photo.original_url || '').replace(/'/g, "\\'");
  return `
    <div class="folder-photo-item" id="fpi-${photo.id}"
         onclick="togglePhotoSelect('${photo.id}', event)"
         ondblclick="openFullscreen('${preview}')">
      <img src="${photo.thumbnail_url}" class="folder-photo-thumb" loading="lazy" />
      <div class="folder-photo-check hidden" id="fcheck-${photo.id}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      ${photo.lead_number ? `<div class="folder-photo-badge">#${photo.lead_number}</div>` : ''}
    </div>
  `;
}

function togglePhotoSelect(photoId, ev) {
  if (_eventPageSelected.has(photoId)) {
    _eventPageSelected.delete(photoId);
    document.getElementById(`fpi-${photoId}`)?.classList.remove('selected');
    document.getElementById(`fcheck-${photoId}`)?.classList.add('hidden');
  } else {
    _eventPageSelected.add(photoId);
    document.getElementById(`fpi-${photoId}`)?.classList.add('selected');
    document.getElementById(`fcheck-${photoId}`)?.classList.remove('hidden');
  }
  updateSelectionBar();
}

function openFullscreen(src) {
  const fs = document.getElementById('photo-fullscreen');
  const img = document.getElementById('fullscreen-img');
  if (!fs || !img) return;
  img.src = src;
  fs.classList.remove('hidden');
}

function closeFullscreen() {
  document.getElementById('photo-fullscreen')?.classList.add('hidden');
}

function updateSelectionBar() {
  const bar = document.getElementById('selection-bar');
  const count = document.getElementById('selection-count');
  if (!bar) return;
  if (_eventPageSelected.size === 0) {
    bar.classList.add('hidden');
  } else {
    bar.classList.remove('hidden');
    count.textContent = `${_eventPageSelected.size} foto${_eventPageSelected.size !== 1 ? 's' : ''} selecionada${_eventPageSelected.size !== 1 ? 's' : ''}`;
  }
}

function clearSelection() {
  _eventPageSelected.forEach(id => {
    document.getElementById(`fpi-${id}`)?.classList.remove('selected');
    document.getElementById(`fcheck-${id}`)?.classList.add('hidden');
  });
  _eventPageSelected.clear();
  updateSelectionBar();
}

function sendSelectedPhotos() {
  openWhatsappModal(_eventPageId, [..._eventPageSelected]);
}

async function renderRegister(params) {
  const { event_id } = params;

  setContent(`
    <div class="register-page">
      <div class="register-box">
        <div class="auth-logo" style="margin-bottom:20px">
          ${logoSVG(36)}
          <span style="font-size:1.2rem;font-weight:700">Shared Pics</span>
        </div>
        <div id="reg-state">
          <div style="text-align:center;color:var(--text-2);padding:32px 0">
            <div class="animate-pulse">Carregando evento…</div>
          </div>
        </div>
      </div>
    </div>
  `);

  let event;
  try {
    event = await api.getEvent(event_id);
  } catch {
    document.getElementById('reg-state').innerHTML = `
      <div style="text-align:center;padding:32px;color:var(--red)">
        Evento não encontrado ou link inválido.
      </div>`;
    return;
  }

  document.getElementById('reg-state').innerHTML = `
    <div class="register-event-badge">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--orange);flex-shrink:0">
        <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
      </svg>
      <div>
        <div class="ev-name">${event.name}</div>
        <div class="ev-date">${event.date} ${event.location ? '· ' + event.location : ''}</div>
      </div>
    </div>

    <h2 style="font-size:1.15rem;font-weight:700;margin-bottom:6px">Cadastrar para receber suas fotos</h2>
    <p class="text-sm text-muted mb-4" style="margin-bottom:20px">
      Preencha os dados abaixo. O fotógrafo vai escanear seu QR antes de fotografar.
    </p>

    <form id="reg-form">
      <div class="form-group">
        <label class="form-label">Nome completo</label>
        <input class="form-input" type="text" name="name" placeholder="Como você quer ser chamado" required />
      </div>
      <div class="form-group">
        <label class="form-label">WhatsApp</label>
        <input class="form-input" type="tel" name="phone" placeholder="(11) 99999-9999" required />
      </div>
      <div class="form-group">
        <label class="form-label">Email <span class="text-muted">(opcional)</span></label>
        <input class="form-input" type="email" name="email" placeholder="seu@email.com" />
      </div>
      <button class="btn btn-primary btn-full btn-lg" type="submit" id="reg-btn">
        📸 Quero receber minhas fotos
      </button>
    </form>
  `;

  document.getElementById('reg-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    const fd = new FormData(e.target);
    btn.disabled = true;
    btn.textContent = 'Cadastrando…';

    try {
      const lead = await api.createLead({
        name: fd.get('name'),
        phone: fd.get('phone'),
        email: fd.get('email') || '',
        event_id: event_id
      });
      renderLeadQR(lead, event);
    } catch (err) {
      toast.error(err.message);
      btn.disabled = false;
      btn.textContent = '📸 Quero receber minhas fotos';
    }
  });
}

function renderLeadQR(lead, event) {
  document.getElementById('reg-state').innerHTML = `
    <div class="qr-result">
      <div class="qr-lead-num">Lead #${lead.lead_number}</div>
      <div class="qr-lead-name">Olá, ${lead.name}! 👋</div>
      <img src="${lead.qr_code_url}" alt="Seu QR Code" />
      <div class="qr-instructions">
        📱 <strong>Mostre este QR Code para o fotógrafo</strong> antes de posar para a foto.<br>
        Suas fotos serão enviadas automaticamente para o seu WhatsApp!
      </div>
      <button class="btn btn-ghost btn-sm" onclick="downloadQR('${lead.qr_code_url}', '${lead.lead_number}')">
        ⬇️ Baixar meu QR Code
      </button>
    </div>
  `;
}

function downloadQR(url, number) {
  const a = document.createElement('a');
  a.href = url;
  a.download = `shared-pics-lead-${number}.png`;
  a.click();
}

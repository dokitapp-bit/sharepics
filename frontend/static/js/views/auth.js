function renderAuth(mode = 'login') {
  const isLogin = mode === 'login';
  setContent(`
    <div class="auth-page">
      <div class="auth-box">
        <div class="auth-logo">
          ${logoSVG(40)}
          <span>Shared Pics</span>
        </div>
        <h1 class="auth-title">${isLogin ? 'Entrar na plataforma' : 'Criar conta'}</h1>
        <p class="auth-sub">${isLogin ? 'Acesse seu painel de eventos e fotos.' : 'Comece a automatizar seu pós-evento.'}</p>

        <form id="auth-form">
          ${!isLogin ? `
          <div class="form-group">
            <label class="form-label">Nome completo</label>
            <input class="form-input" type="text" name="name" placeholder="Seu nome" required />
          </div>
          ` : ''}
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" type="email" name="email" placeholder="seu@email.com" required />
          </div>
          <div class="form-group">
            <label class="form-label">Senha</label>
            <input class="form-input" type="password" name="password" placeholder="••••••••" required minlength="6" />
          </div>
          ${!isLogin ? `
          <div class="form-group">
            <label class="form-label">Perfil</label>
            <select class="form-input" name="role">
              <option value="photographer">Fotógrafo</option>
              <option value="organizer">Organizador</option>
            </select>
          </div>
          ` : ''}
          <button class="btn btn-primary btn-full btn-lg mt-3" type="submit" id="auth-btn">
            ${isLogin ? 'Entrar' : 'Criar conta'}
          </button>
        </form>

        <div class="auth-toggle">
          ${isLogin
            ? `Não tem conta? <a onclick="renderAuth('register')">Criar grátis</a>`
            : `Já tem conta? <a onclick="renderAuth('login')">Entrar</a>`
          }
        </div>
      </div>
    </div>
  `);

  document.getElementById('auth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('auth-btn');
    const fd = new FormData(e.target);
    btn.disabled = true;
    btn.textContent = 'Aguarde…';
    try {
      let data;
      if (isLogin) {
        data = await api.login(fd.get('email'), fd.get('password'));
      } else {
        data = await api.register(fd.get('name'), fd.get('email'), fd.get('password'), fd.get('role'));
      }
      api.setToken(data.access_token);
      localStorage.setItem('sp_user', JSON.stringify({ id: data.user_id, name: data.name, role: data.role }));
      toast.success(`Bem-vindo, ${data.name}!`);
      Router.navigate('/admin');
    } catch (err) {
      toast.error(err.message);
      btn.disabled = false;
      btn.textContent = isLogin ? 'Entrar' : 'Criar conta';
    }
  });
}

function logoSVG(size = 32) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 64 64" fill="none">
    <rect width="64" height="64" rx="14" fill="#f97316"/>
    <path d="M32 14 L44 22 L32 30 L20 22 Z" fill="white" opacity="0.9"/>
    <path d="M20 22 L20 38 L32 46 L32 30 Z" fill="white" opacity="0.6"/>
    <path d="M44 22 L44 38 L32 46 L32 30 Z" fill="white" opacity="0.75"/>
  </svg>`;
}

function getUser() {
  try { return JSON.parse(localStorage.getItem('sp_user')); }
  catch { return null; }
}

function requireAuth() {
  if (!api._token || !getUser()) {
    Router.navigate('/login', false);
    return false;
  }
  return true;
}

function logout() {
  api.setToken(null);
  localStorage.removeItem('sp_user');
  Router.navigate('/login');
}

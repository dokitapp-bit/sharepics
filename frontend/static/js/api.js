const API_BASE = '/api';

const api = {
  _token: localStorage.getItem('sp_token'),

  _headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    if (this._token) h['Authorization'] = `Bearer ${this._token}`;
    return h;
  },

  setToken(token) {
    this._token = token;
    if (token) localStorage.setItem('sp_token', token);
    else localStorage.removeItem('sp_token');
  },

  async request(method, path, body = null) {
    const opts = { method, headers: this._headers() };
    if (body && method !== 'GET') opts.body = JSON.stringify(body);
    const res = await fetch(API_BASE + path, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async upload(path, formData) {
    const headers = {};
    if (this._token) headers['Authorization'] = `Bearer ${this._token}`;
    const res = await fetch(API_BASE + path, { method: 'POST', headers, body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro no upload' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Auth
  login: (email, password) => api.request('POST', '/auth/login', { email, password }),
  register: (name, email, password, role) => api.request('POST', '/auth/register', { name, email, password, role }),

  // Events
  createEvent: (data) => api.request('POST', '/events', data),
  listEvents: () => api.request('GET', '/events'),
  getEvent: (id) => api.request('GET', `/events/${id}`),
  eventStats: (id) => api.request('GET', `/events/${id}/stats`),

  // Leads
  createLead: (data) => api.request('POST', '/leads', data),
  listLeads: (eventId) => api.request('GET', `/leads/event/${eventId}`),
  getLead: (id) => api.request('GET', `/leads/${id}`),
  notifyLead: (id) => api.request('POST', `/leads/${id}/notify`),
  notifyAll: (eventId) => api.request('POST', `/leads/event/${eventId}/notify-all`),

  // Photos
  listPhotos: (eventId, leadId = null) => {
    const qs = leadId ? `?lead_id=${leadId}` : '';
    return api.request('GET', `/photos/event/${eventId}${qs}`);
  },
  listLeadPhotos: (leadId) => api.request('GET', `/photos/lead/${leadId}`),

  uploadPhoto(eventId, file, sessionKey, onProgress) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('event_id', eventId);
      if (sessionKey) fd.append('session_key', sessionKey);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', API_BASE + '/photos/upload');
      if (this._token) xhr.setRequestHeader('Authorization', `Bearer ${this._token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round(e.loaded / e.total * 100));
      };
      xhr.onload = () => {
        if (xhr.status === 200) resolve(JSON.parse(xhr.responseText));
        else reject(new Error(JSON.parse(xhr.responseText)?.detail || `HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error('Erro de rede'));
      xhr.send(fd);
    });
  },
};

// Toast utility
const toast = {
  show(msg, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  },
  success: (m) => toast.show(m, 'success'),
  error:   (m) => toast.show(m, 'error'),
  info:    (m) => toast.show(m, 'info'),
};

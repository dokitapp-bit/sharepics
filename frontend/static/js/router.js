const Router = {
  routes: {},
  current: null,

  on(pattern, handler) {
    this.routes[pattern] = handler;
  },

  match(path) {
    for (const [pattern, handler] of Object.entries(this.routes)) {
      const keys = [];
      const regex = new RegExp(
        '^' + pattern.replace(/:([^/]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '$'
      );
      const m = path.match(regex);
      if (m) {
        const params = {};
        keys.forEach((k, i) => params[k] = m[i + 1]);
        return { handler, params };
      }
    }
    return null;
  },

  navigate(path, push = true) {
    if (push) history.pushState({}, '', path);
    const match = this.match(path);
    if (match) {
      this.current = path;
      match.handler(match.params);
    } else {
      this.navigate('/admin', false);
    }
  },

  init() {
    window.addEventListener('popstate', () => this.navigate(location.pathname, false));
    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-route]');
      if (a) { e.preventDefault(); this.navigate(a.dataset.route); }
    });
    this.navigate(location.pathname, false);
  }
};

function setContent(html) {
  document.getElementById('app').innerHTML = html;
}

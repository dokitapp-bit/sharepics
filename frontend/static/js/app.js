// Bootstrap
document.addEventListener('DOMContentLoaded', () => {
  Router.on('/login', () => renderAuth('login'));
  Router.on('/register', () => renderAuth('register'));
  Router.on('/register/:event_id', (p) => renderRegister(p));
  Router.on('/gallery/:lead_id', (p) => renderGallery(p));
  Router.on('/admin', () => renderAdminDashboard());
  Router.on('/admin/events', () => renderAdminEvents());
  Router.on('/admin/upload', () => renderAdminUpload());
  Router.on('/admin/equipment', () => renderEquipmentSelect());
  Router.on('/admin/event/:id', (p) => renderEventPage(p));
  Router.on('/', () => {
    if (api._token && getUser()) Router.navigate('/admin', false);
    else Router.navigate('/login', false);
  });

  // Hide splash after short delay
  setTimeout(() => {
    document.getElementById('splash')?.classList.add('hidden');
    Router.init();
  }, 900);
});

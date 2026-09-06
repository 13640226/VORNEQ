class ProfileDashboard {
  constructor(manager) { this.manager = manager; }
  init() {
    const root = this.manager.root;
    root.querySelectorAll('[data-mark-read]').forEach((button) => button.addEventListener('click', async () => {
      const item = button.closest('[data-notification]');
      if (!item) return;
      item.dataset.read = 'true';
      button.disabled = true;
      const id = item.dataset.notification;
      try {
        await this.manager.request(`${this.manager.endpoints.notifications}${id}/read/`, { method: 'POST', body: '{}' });
      } catch (error) {
        item.dataset.read = 'false';
        button.disabled = false;
        console.warn(error);
      }
    }));
  }
}
window.ProfileDashboard = ProfileDashboard;

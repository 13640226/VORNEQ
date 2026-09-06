class ProfileManager {
  constructor(root = document.querySelector('[data-profile]')) {
    this.root = root;
    this.endpoints = {
      profile: '/api/profile/',
      activity: '/api/profile/activity/',
      library: '/api/profile/library/',
      goals: '/api/profile/goals/',
      settings: '/api/profile/settings/',
      notifications: '/api/profile/notifications/'
    };
    this.modules = [];
  }

  register(module) {
    if (module && typeof module.init === 'function') this.modules.push(module);
    return this;
  }

  init() {
    if (!this.root) return;
    this.bindNavigation();
    this.modules.forEach((module) => module.init());
  }

  bindNavigation() {
    const buttons = this.root.querySelectorAll('[data-profile-tab]');
    const sections = this.root.querySelectorAll('[data-profile-section]');
    buttons.forEach((button) => button.addEventListener('click', () => {
      const target = button.dataset.profileTab;
      buttons.forEach((item) => item.setAttribute('aria-selected', String(item === button)));
      sections.forEach((section) => { section.hidden = section.dataset.profileSection !== target; });
      this.root.dispatchEvent(new CustomEvent('profile:sectionchange', { detail: { section: target } }));
    }));
  }

  async request(endpoint, options = {}) {
    const response = await fetch(endpoint, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    });
    if (!response.ok) throw new Error(`Profile request failed: ${response.status}`);
    return response.status === 204 ? null : response.json();
  }
}

window.ProfileManager = ProfileManager;
document.addEventListener('DOMContentLoaded', () => {
  const manager = new ProfileManager();
  if (window.ProfileDashboard) manager.register(new window.ProfileDashboard(manager));
  if (window.ProfileLibrary) manager.register(new window.ProfileLibrary(manager));
  if (window.ProfileSettings) manager.register(new window.ProfileSettings(manager));
  manager.init();
  window.vorneqProfile = manager;
});

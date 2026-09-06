class ProfileSettings {
  constructor(manager) { this.manager = manager; }
  init() {
    const form = this.manager.root.querySelector('[data-settings-form]');
    if (!form) return;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      const data = Object.fromEntries(new FormData(form).entries());
      form.querySelectorAll('input[type="checkbox"][name]').forEach((input) => { data[input.name] = input.checked; });
      if (submit) submit.disabled = true;
      try {
        await this.manager.request(this.manager.endpoints.settings, { method: 'PATCH', body: JSON.stringify(data) });
        form.dispatchEvent(new CustomEvent('profile:settingssaved', { bubbles: true }));
      } catch (error) {
        console.warn(error);
      } finally {
        if (submit) submit.disabled = false;
      }
    });
  }
}
window.ProfileSettings = ProfileSettings;

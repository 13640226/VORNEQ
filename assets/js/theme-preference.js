(function () {
  const STORAGE_KEY = 'vorneq-theme';
  const VALID_PREFERENCES = new Set(['light', 'dark', 'system']);
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function readPreference() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return VALID_PREFERENCES.has(stored) ? stored : 'system';
    } catch (error) {
      return 'system';
    }
  }

  function resolveTheme(preference) {
    if (preference === 'system') {
      return media && media.matches ? 'dark' : 'light';
    }
    return preference;
  }

  function applyTheme(preference) {
    const resolved = resolveTheme(preference);
    const root = document.documentElement;

    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    root.style.colorScheme = resolved;

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.content = resolved === 'dark' ? '#0b1120' : '#ffffff';
    }

    document.querySelectorAll('[data-theme-option]').forEach((button) => {
      const selected = button.dataset.themeOption === preference;
      button.classList.toggle('profile-preference-option--active', selected);
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
  }

  function storePreference(preference) {
    if (!VALID_PREFERENCES.has(preference)) return;
    try {
      localStorage.setItem(STORAGE_KEY, preference);
    } catch (error) {
      // The current page still gets the preference even when storage is unavailable.
    }
    applyTheme(preference);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const preference = readPreference();
    applyTheme(preference);

    document.querySelectorAll('[data-theme-option]').forEach((button) => {
      button.addEventListener('click', () => {
        storePreference(button.dataset.themeOption);
      });
    });
  });

  const handleSystemChange = () => {
    if (readPreference() === 'system') {
      applyTheme('system');
    }
  };

  if (media) {
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', handleSystemChange);
    } else if (typeof media.addListener === 'function') {
      media.addListener(handleSystemChange);
    }
  }
}());

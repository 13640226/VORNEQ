(function () {
  const STORAGE_KEY = 'vorneq-theme';
  const DEFAULT_THEME = 'vorneq';
  const VALID_PREFERENCES = new Set([
    'vorneq',
    'light',
    'dark',
    'blue',
    'gold',
    'emerald',
    'purple',
    'system',
  ]);
  const THEME_COLORS = {
    vorneq: '#f7f8fa',
    light: '#f8f6f2',
    dark: '#0d1117',
    blue: '#0b1a2e',
    gold: '#1a140e',
    emerald: '#0d1f1a',
    purple: '#1a0f2e',
  };
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function readPreference() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return VALID_PREFERENCES.has(stored) ? stored : DEFAULT_THEME;
    } catch (error) {
      return DEFAULT_THEME;
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
    const nativeScheme = (resolved === 'light' || resolved === 'vorneq') ? 'light' : 'dark';

    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    root.style.colorScheme = nativeScheme;

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.content = THEME_COLORS[resolved] || THEME_COLORS.vorneq;
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
    document.dispatchEvent(new CustomEvent('vorneq:theme-changed', {
      detail: { preference, resolved: resolveTheme(preference) },
    }));
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

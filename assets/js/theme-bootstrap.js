(function () {
    var valid = ['navy', 'vorneq', 'light', 'dark', 'blue', 'gold', 'emerald', 'purple', 'system'];
    var preference = 'navy';
    try {
        preference = localStorage.getItem('vorneq-theme') || 'navy';
    } catch (error) {
        preference = 'navy';
    }

    if (valid.indexOf(preference) === -1) preference = 'navy';
    var systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
    var root = document.documentElement;
    var nativeScheme = (resolved === 'light' || resolved === 'vorneq') ? 'light' : 'dark';
    var themeColors = {
        navy: '#071426',
        vorneq: '#f7f8fa',
        light: '#f8f6f2',
        dark: '#0d1117',
        blue: '#0b1a2e',
        gold: '#1a140e',
        emerald: '#0d1f1a',
        purple: '#1a0f2e'
    };

    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    root.style.colorScheme = nativeScheme;

    var themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = themeColors[resolved] || '#071426';
})();

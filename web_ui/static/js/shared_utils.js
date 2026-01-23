// Shared utility for storage and theme handling used by multiple UI scripts.
(() => {
  const THEME_KEY = 'ua_config_theme';

  const uaStorage = {
    get(key) {
      try {
        return localStorage.getItem(key);
      } catch (error) {
        return null;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch (error) {
        // Ignore storage failures (private mode, blocked storage, etc.).
      }
    },
    remove(key) {
      try {
        localStorage.removeItem(key);
      } catch (error) {
        // Ignore storage failures.
      }
    }
  };

  function getUAStoredTheme() {
    const stored = uaStorage.get(THEME_KEY);
    if (stored === 'dark') return true;
    if (stored === 'light') return false;
    return typeof window !== 'undefined' && typeof window.UA_DEFAULT_THEME === 'boolean' ? window.UA_DEFAULT_THEME : true;
  }

  // Expose as globals for non-module usage by existing scripts.
  if (typeof window !== 'undefined') {
    window.UAStorage = window.UAStorage || uaStorage;
    window.getUAStoredTheme = window.getUAStoredTheme || getUAStoredTheme;
  }
})();

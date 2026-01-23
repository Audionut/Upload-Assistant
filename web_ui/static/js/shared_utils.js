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

  // CSRF + apiFetch helpers with automatic refresh on 401/403 responses.
  let uaCsrfToken = null;

  async function loadCsrfToken(force = false) {
    if (uaCsrfToken && !force) return;
    try {
      const r = await fetch('/api/csrf_token', { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      uaCsrfToken = d && d.csrf_token ? String(d.csrf_token) : null;
    } catch (e) {
      // ignore
    }
  }

  function clearCsrfToken() {
    uaCsrfToken = null;
  }

  async function uaApiFetch(url, options = {}, retryOnAuthFail = true) {
    await loadCsrfToken();
    const headers = { ...(options.headers || {}) };
    if (uaCsrfToken) headers['X-CSRF-Token'] = uaCsrfToken;
    const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
    if (retryOnAuthFail && (response.status === 401 || response.status === 403)) {
      // Attempt a single refresh and retry
      clearCsrfToken();
      await loadCsrfToken(true);
      const headers2 = { ...(options.headers || {}) };
      if (uaCsrfToken) headers2['X-CSRF-Token'] = uaCsrfToken;
      return fetch(url, { ...options, headers: headers2, credentials: 'same-origin' });
    }
    return response;
  }

  // Shared HTML sanitizer. Uses DOMPurify when available; falls back to DOMParser-based sanitizer.
  function sanitizeHtml(html) {
    const rawHtml = String(html || '');
    if (typeof window !== 'undefined' && window.DOMPurify) {
      const dangerousTags = ['script', 'style', 'img', 'svg', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'meta', 'link'];
      const forbiddenAttrs = ['srcset', 'onerror', 'onload', 'onclick', 'onmouseover', 'onmouseenter', 'onmouseleave', 'onkeydown', 'onkeypress', 'onkeyup'];
      return DOMPurify.sanitize(rawHtml, {
        ALLOWED_ATTR: ['class', 'href', 'src', 'title', 'alt', 'rel', 'style'],
        FORBID_TAGS: dangerousTags,
        FORBID_ATTR: forbiddenAttrs,
      });
    }
    try {
      const doc = new DOMParser().parseFromString(rawHtml, 'text/html');
      const dangerousTags = ['script', 'style', 'img', 'svg', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'meta', 'link'];
      dangerousTags.forEach(tag => {
        doc.querySelectorAll(tag).forEach(el => el.remove());
      });
      doc.querySelectorAll('*').forEach((el) => {
        [...el.attributes].forEach((attr) => {
          const attrName = attr.name.toLowerCase();
          const attrValue = String(attr.value).toLowerCase().trim();
          if (attrName.startsWith('on')) {
            el.removeAttribute(attr.name);
          } else if ((attrName === 'href' || attrName === 'src') && (attrValue.startsWith('javascript:') || attrValue.startsWith('data:') || attrValue.startsWith('vbscript:'))) {
            el.removeAttribute(attr.name);
          } else if (attrName === 'srcset' || (attrName === 'style' && attrValue.includes('url('))) {
            el.removeAttribute(attr.name);
          }
        });
      });
      return doc.body.innerHTML;
    } catch (e) {
      return rawHtml.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
  }

  // Expose as globals for non-module usage by existing scripts.
  if (typeof window !== 'undefined') {
    window.UAStorage = window.UAStorage || uaStorage;
    window.getUAStoredTheme = window.getUAStoredTheme || getUAStoredTheme;
    window.loadCsrfToken = window.loadCsrfToken || loadCsrfToken;
    window.clearCsrfToken = window.clearCsrfToken || clearCsrfToken;
    window.uaApiFetch = window.uaApiFetch || uaApiFetch;
    window.sanitizeHtml = window.sanitizeHtml || sanitizeHtml;
  }
})();

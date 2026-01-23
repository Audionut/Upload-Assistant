(function () {
  const API_BASE = window.location.origin + '/api';
  const statusEl = document.getElementById('config-status');
  const container = document.getElementById('config-container');
  const headerEl = document.getElementById('page-header');
  const titleEl = document.getElementById('page-title');
  const pageRoot = document.getElementById('page-root');
  const themeToggle = document.getElementById('theme-toggle');
  const themeKnob = document.getElementById('theme-knob');
  const themeLabel = document.getElementById('theme-label');

  const THEME_KEY = 'ua_config_theme';

  const storage = {
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
        // Ignore storage failures.
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

  const getAuthHeader = () => {
    // Authentication is handled via session cookies, no auth header needed
    return null;
  };

  let csrfToken = null;
  const _maybeLoadCsrf = async () => {
    if (csrfToken) return;
    try {
      const r = await fetch(`${API_BASE}/csrf_token`, { credentials: 'include' });
      if (!r.ok) return;
      const d = await r.json();
      csrfToken = d && d.csrf_token ? String(d.csrf_token) : null;
    } catch (e) {
      // ignore
    }
  };

  const apiFetch = async (url, options = {}) => {
    await _maybeLoadCsrf();
    const headers = { ...(options.headers || {}) };
    const authHeader = getAuthHeader();
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    const response = await fetch(url, { ...options, headers, credentials: 'include' });
    return response;
  };

  const getStoredTheme = () => {
    const stored = storage.get(THEME_KEY);
    if (stored === 'dark') {
      return true;
    }
    if (stored === 'light') {
      return false;
    }
    return false;
  };

  let cachedSections = [];
  let isDarkMode = getStoredTheme();

  const applyTheme = () => {
    if (isDarkMode) {
      document.body.className = 'bg-gray-900 text-gray-100';
      pageRoot.className = 'min-h-screen flex flex-col bg-gray-900';
      headerEl.className = 'border-b border-gray-700 bg-gray-800 sticky top-0 z-50';
      titleEl.className = 'text-2xl font-bold text-white';
      statusEl.className = 'text-sm text-gray-300';
      container.className = 'mt-4 rounded-lg border border-gray-700 bg-gray-800 overflow-hidden';
      themeToggle.className = 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors bg-purple-600';
      themeKnob.className = 'inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-6';
      themeLabel.textContent = '🌙 Dark';
    } else {
      document.body.className = 'bg-gray-100 text-gray-900';
      pageRoot.className = 'min-h-screen flex flex-col bg-gray-100';
      headerEl.className = 'border-b border-gray-200 bg-white sticky top-0 z-50';
      titleEl.className = 'text-2xl font-bold text-gray-800';
      statusEl.className = 'text-sm text-gray-600';
      container.className = 'mt-4 rounded-lg border border-gray-300 bg-white overflow-hidden';
      themeToggle.className = 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors bg-gray-300';
      themeKnob.className = 'inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-1';
      themeLabel.textContent = '☀️ Light';
    }
  };

  const isPlainObject = (value) => value && typeof value === 'object' && !Array.isArray(value);
  const sensitiveKeyPattern = /(api|username|password|aanounce_url|announce_url|rss_key|passkey|discord_bot_token|discord_channel_id|qui_proxy_url)/i;
  const isSensitiveKey = (key) => sensitiveKeyPattern.test(key || '');
  const isTorrentClientUserPass = (key, pathParts) =>
    pathParts.includes('TORRENT_CLIENTS') && /(user|pass)/i.test(key || '');
  const isSensitiveKeyForPath = (key, pathParts) => isSensitiveKey(key) || isTorrentClientUserPass(key, pathParts);
  const isReadOnlyKeyForPath = (key, pathParts) =>
    pathParts.includes('TORRENT_CLIENTS') && key === 'torrent_client';

  const getImageHostOptions = (item, allHosts, usedHosts) => {
    if (!item || !item.key || !item.key.startsWith('img_host_')) {
      return [];
    }
    if (!allHosts.length) {
      return [];
    }
    const currentValue = String(item.value || '').trim().toLowerCase();
    return allHosts.filter((host) => {
      const normalizedHost = String(host).trim().toLowerCase();
      return !usedHosts.has(normalizedHost) || currentValue === normalizedHost;
    });
  };

  const getAvailableTrackers = (item) => {
    if (!item || !item.help || !item.help.length) {
      return [];
    }
    const helpLine = item.help.find((line) => line.toLowerCase().includes('available tracker'));
    if (!helpLine) {
      return [];
    }
    const parts = helpLine.split(':');
    if (parts.length < 2) {
      return [];
    }
    return parts[1]
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
  };

  const imageHostApiKeys = {
    imgbb: ['imgbb_api'],
    ptpimg: ['ptpimg_api'],
    lensdump: ['lensdump_api'],
    ptscreens: ['ptscreens_api'],
    onlyimage: ['onlyimage_api'],
    dalexni: ['dalexni_api'],
    passtheimage: ['passtheima_ge_api'],
    zipline: ['zipline_url', 'zipline_api_key'],
    seedpool_cdn: ['seedpool_cdn_api'],
    sharex: ['sharex_url', 'sharex_api_key']
  };

  const getImageHostForApiKey = (key) => {
    if (!key) {
      return null;
    }
    const normalizedKey = String(key);
    for (const [host, keys] of Object.entries(imageHostApiKeys)) {
      if (keys.includes(normalizedKey)) {
        return host;
      }
    }
    return null;
  };

  const saveConfigValue = async (path, value, statusEl, options = {}) => {
    const { refresh = true, clearAfterMs = 0 } = options;
    statusEl.textContent = 'Saving...';
    statusEl.className = isDarkMode ? 'text-xs text-gray-400' : 'text-xs text-gray-500';

    try {
      const response = await apiFetch(`${API_BASE}/config_update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, value })
      });
      // Read response body as text first so we can handle non-JSON responses
      const contentType = response.headers.get('content-type') || '';
      const rawBody = await response.text();
      let data;
      if (contentType.includes('application/json')) {
        try {
          data = JSON.parse(rawBody);
        } catch (err) {
          const msg = `Invalid JSON response (status ${response.status}): ${rawBody}`;
          statusEl.textContent = msg;
          statusEl.className = isDarkMode ? 'text-xs text-red-400' : 'text-xs text-red-500';
          console.error('Failed to parse JSON from config_update:', err, rawBody);
          return;
        }
      } else {
        data = rawBody;
      }

      if (!response.ok) {
        const bodyMsg = typeof data === 'string' ? data : JSON.stringify(data);
        throw new Error(`Server returned ${response.status}: ${bodyMsg}`);
      }

      if (isPlainObject(data) && !data.success) {
        throw new Error(data.error || 'Failed to save');
      }
      statusEl.textContent = 'Saved';
      statusEl.className = isDarkMode ? 'text-xs text-green-400' : 'text-xs text-green-600';
      if (clearAfterMs > 0) {
        window.setTimeout(() => {
          statusEl.textContent = '';
        }, clearAfterMs);
      }
      if (refresh) {
        await loadConfigOptions();
      }
    } catch (error) {
      const msg = error && error.message ? error.message : 'Failed to save';
      statusEl.textContent = msg;
      statusEl.className = isDarkMode ? 'text-xs text-red-400' : 'text-xs text-red-500';
      console.error('saveConfigValue error:', error);
    }
  };

  const renderItems = (
    items,
    pathParts,
    depth = 0,
    allImageHosts = [],
    usedImageHosts = new Set(),
    fullWidth = false
  ) => {
    const list = document.createElement('div');
    list.className = isDarkMode ? 'divide-y divide-gray-700/40' : 'divide-y divide-gray-200';

    items.forEach((item) => {
      const isSubsection = item.subsection === true;
      const currentPath = isSubsection ? pathParts : [...pathParts, item.key];
      const apiHost = getImageHostForApiKey(item.key);
      if (apiHost && !usedImageHosts.has(apiHost)) {
        return;
      }
      const row = document.createElement('div');
      row.className = 'px-4 py-3 grid grid-cols-12 gap-3 items-start';

      const keyCol = document.createElement('div');
      keyCol.className = isDarkMode
        ? (fullWidth ? 'col-span-12 text-sm font-mono text-purple-300 break-all' : 'col-span-4 text-sm font-mono text-purple-300 break-all')
        : (fullWidth ? 'col-span-12 text-sm font-mono text-purple-700 break-all' : 'col-span-4 text-sm font-mono text-purple-700 break-all');

      const valueCol = document.createElement('div');
      valueCol.className = isDarkMode
        ? (fullWidth ? 'col-span-12 text-sm text-gray-200 break-all' : 'col-span-7 text-sm text-gray-200 break-all')
        : (fullWidth ? 'col-span-12 text-sm text-gray-700 break-all' : 'col-span-7 text-sm text-gray-700 break-all');

      if (item.help && item.help.length) {
        const helpText = document.createElement('div');
        helpText.className = isDarkMode
          ? 'mb-2 text-xs text-gray-400'
          : 'mb-2 text-xs text-gray-500';
        helpText.style.whiteSpace = 'pre-wrap';
        helpText.textContent = item.help.join('\n');
        valueCol.appendChild(helpText);
      }

      let inputEl = null;
      let skipSaveButton = false;

      if (item.children && item.children.length) {
        const isTrackerConfig = pathParts.includes('TRACKERS') && depth === 0;
        const isTorrentClientConfig = pathParts.includes('TORRENT_CLIENTS') && depth === 0;
        const isCollapsible = isSubsection || isTrackerConfig || isTorrentClientConfig;
        const nextPath = isSubsection ? pathParts : currentPath;
        const nextDepth = isSubsection ? depth : depth + 1;
        const nested = renderItems(item.children, nextPath, nextDepth, allImageHosts, usedImageHosts, isCollapsible);
        nested.className += isDarkMode
          ? ' mt-2 border border-gray-700 rounded-lg bg-gray-900/40'
          : ' mt-2 border border-gray-200 rounded-lg bg-gray-50';

        if (isCollapsible) {
          keyCol.className = isDarkMode
            ? 'col-span-12 text-sm font-mono text-purple-300 break-all'
            : 'col-span-12 text-sm font-mono text-purple-700 break-all';
          keyCol.textContent = '';

          const toggle = document.createElement('button');
          toggle.type = 'button';
          toggle.className = isDarkMode
            ? 'flex items-center gap-2 text-left w-full text-sm font-semibold text-gray-100'
            : 'flex items-center gap-2 text-left w-full text-sm font-semibold text-gray-800';
          toggle.setAttribute('aria-expanded', 'false');

          const caret = document.createElement('span');
          caret.textContent = '▸';
          caret.className = 'transition-transform';

          const label = document.createElement('span');
          label.textContent = item.key;

          toggle.appendChild(caret);
          toggle.appendChild(label);

          if (depth === 0 && !isSubsection) {
            const badge = document.createElement('span');
            badge.className = item.source === 'config'
              ? 'ml-2 text-xs px-2 py-0.5 rounded-full bg-green-600 text-white'
              : 'ml-2 text-xs px-2 py-0.5 rounded-full bg-gray-600 text-white';
            badge.textContent = item.source || '';
            toggle.appendChild(badge);
          }

          keyCol.appendChild(toggle);

          const nestedWrapper = document.createElement('div');
          nestedWrapper.className = isDarkMode
            ? 'col-span-12 rounded-lg border border-gray-700 bg-gray-900/30 p-2 mt-2'
            : 'col-span-12 rounded-lg border border-gray-200 bg-gray-50 p-2 mt-2';
          nestedWrapper.hidden = true;
          nestedWrapper.appendChild(nested);

          toggle.addEventListener('click', () => {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!expanded));
            caret.style.transform = expanded ? 'rotate(0deg)' : 'rotate(90deg)';
            nestedWrapper.hidden = expanded;
          });

          row.appendChild(keyCol);
          row.appendChild(nestedWrapper);
          list.appendChild(row);
          return;
        } else {
          keyCol.textContent = item.key;
          valueCol.appendChild(nested);
        }
      } else if (typeof item.value === 'boolean') {
        const toggleWrapper = document.createElement('label');
        toggleWrapper.className = 'inline-flex items-center gap-2 text-sm';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = item.value;
        checkbox.className = isDarkMode
          ? 'h-4 w-4 accent-purple-500'
          : 'h-4 w-4 accent-purple-600';

        const toggleLabel = document.createElement('span');
        toggleLabel.className = isDarkMode ? 'text-gray-200' : 'text-gray-700';
        toggleLabel.textContent = item.value ? 'True' : 'False';

        checkbox.addEventListener('change', () => {
          toggleLabel.textContent = checkbox.checked ? 'True' : 'False';
        });

        toggleWrapper.appendChild(checkbox);
        toggleWrapper.appendChild(toggleLabel);
        valueCol.appendChild(toggleWrapper);
        inputEl = checkbox;
      } else if (item.key && item.key.startsWith('img_host_')) {
        const options = getImageHostOptions(item, allImageHosts, usedImageHosts);
        const select = document.createElement('select');
        select.className = isDarkMode
          ? 'w-full px-2 py-1 rounded border border-gray-700 bg-gray-900 text-gray-100 text-sm font-mono'
          : 'w-full px-2 py-1 rounded border border-gray-300 bg-white text-gray-800 text-sm font-mono';

        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '';
        select.appendChild(emptyOption);

        options.forEach((host) => {
          const option = document.createElement('option');
          option.value = host;
          option.textContent = host;
          select.appendChild(option);
        });

        const currentValue = item.value === null || item.value === undefined
          ? ''
          : String(item.value).trim().toLowerCase();
        select.value = currentValue;
        valueCol.appendChild(select);
        inputEl = select;
      } else if (item.key === 'default_trackers') {
        const availableTrackers = getAvailableTrackers(item);
        const selected = new Set(
          String(item.value || '')
            .split(',')
            .map((t) => t.trim().toUpperCase())
            .filter(Boolean)
        );

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-2 md:grid-cols-3 gap-2';

        const status = document.createElement('div');
        status.className = isDarkMode ? 'text-xs text-gray-400 mt-2' : 'text-xs text-gray-500 mt-2';

        const persistSelections = () => {
          const selections = Array.from(
            grid.querySelectorAll('input[type="checkbox"][data-tracker]')
          )
            .filter((cb) => cb.checked)
            .map((cb) => cb.dataset.tracker)
            .filter(Boolean)
            .map((t) => String(t).toUpperCase());
          saveConfigValue(currentPath, selections.join(', '), status, { refresh: false, clearAfterMs: 1500 });
        };

        availableTrackers.forEach((tracker) => {
          const label = document.createElement('label');
          label.className = isDarkMode
            ? 'flex items-center gap-2 text-xs text-gray-200'
            : 'flex items-center gap-2 text-xs text-gray-700';

          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.dataset.tracker = tracker;
          checkbox.checked = selected.has(tracker.toUpperCase());
          checkbox.className = isDarkMode
            ? 'h-4 w-4 accent-purple-500'
            : 'h-4 w-4 accent-purple-600';
          checkbox.addEventListener('change', persistSelections);

          const text = document.createElement('span');
          text.textContent = tracker;

          label.appendChild(checkbox);
          label.appendChild(text);
          grid.appendChild(label);
        });

        const details = document.createElement('details');
        details.className = isDarkMode
          ? 'rounded-lg border border-gray-700 bg-gray-900/30'
          : 'rounded-lg border border-gray-200 bg-gray-50';

        const summary = document.createElement('summary');
        summary.className = isDarkMode
          ? 'cursor-pointer select-none px-3 py-2 text-xs font-semibold text-gray-200'
          : 'cursor-pointer select-none px-3 py-2 text-xs font-semibold text-gray-700';
        summary.textContent = 'Show trackers';

        details.appendChild(summary);
        details.appendChild(grid);
        valueCol.appendChild(details);
        valueCol.appendChild(status);
        skipSaveButton = true;
      } else {
        const input = document.createElement('input');
        input.type = 'text';
        const rawValue = item.value === null || item.value === undefined
          ? ''
          : (typeof item.value === 'string' ? item.value : JSON.stringify(item.value));
        const hasSensitiveValue = isSensitiveKeyForPath(item.key, currentPath) && String(rawValue).trim() !== '';
        input.value = hasSensitiveValue ? '<REDACTED>' : rawValue;
        if (hasSensitiveValue) {
          input.dataset.redacted = 'true';
        }
        input.className = isDarkMode
          ? 'w-full px-2 py-1 rounded border border-gray-700 bg-gray-900 text-gray-100 text-sm font-mono'
          : 'w-full px-2 py-1 rounded border border-gray-300 bg-white text-gray-800 text-sm font-mono';
        if (isReadOnlyKeyForPath(item.key, currentPath)) {
          input.disabled = true;
          input.className += ' opacity-70 cursor-not-allowed';
        }
        if (hasSensitiveValue) {
          input.addEventListener('focus', () => {
            if (input.dataset.redacted === 'true') {
              input.value = '';
              input.dataset.redacted = 'false';
            }
          });
        }
        valueCol.appendChild(input);
        inputEl = input;
      }

      const sourceCol = document.createElement('div');
      sourceCol.className = 'col-span-1 text-right';
      let saveButton = null;

        const isCollapsibleRow = item.children && item.children.length && (
        isSubsection || (pathParts.includes('TRACKERS') && depth === 0) || (pathParts.includes('TORRENT_CLIENTS') && depth === 0)
      );

      if (depth === 0 && !isSubsection && !isCollapsibleRow) {
        const badge = document.createElement('span');
        badge.className = item.source === 'config'
          ? 'text-xs px-2 py-1 rounded-full bg-green-600 text-white'
          : 'text-xs px-2 py-1 rounded-full bg-gray-600 text-white';
        badge.textContent = item.source || '';
        sourceCol.appendChild(badge);
      } else if (!(item.children && item.children.length)) {
        if (skipSaveButton) {
          row.appendChild(keyCol);
          row.appendChild(valueCol);
          row.appendChild(sourceCol);
          list.appendChild(row);
          return;
        }
        if (isReadOnlyKeyForPath(item.key, currentPath)) {
          row.appendChild(keyCol);
          row.appendChild(valueCol);
          row.appendChild(sourceCol);
          list.appendChild(row);
          return;
        }
        saveButton = document.createElement('button');
        saveButton.type = 'button';
        saveButton.textContent = 'Save';
        saveButton.className = isDarkMode
          ? 'px-2 py-1 rounded text-xs bg-purple-600 text-white hover:bg-purple-700'
          : 'px-2 py-1 rounded text-xs bg-purple-600 text-white hover:bg-purple-700';

        const status = document.createElement('div');
        status.className = isDarkMode ? 'text-xs text-gray-400 mt-1' : 'text-xs text-gray-500 mt-1';

        const updateSaveState = () => {
          if (!saveButton || !inputEl) {
            return;
          }
          if (inputEl.type !== 'checkbox' && inputEl.dataset && inputEl.dataset.redacted === 'true') {
            saveButton.disabled = true;
            if (!saveButton.className.includes('opacity-50')) {
              saveButton.className += ' opacity-50 cursor-not-allowed';
            }
            return;
          }
          if (isSensitiveKeyForPath(item.key, currentPath) && inputEl.type !== 'checkbox') {
            const hasValue = inputEl.value.trim() !== '';
            saveButton.disabled = !hasValue;
          } else {
            saveButton.disabled = false;
          }
          if (saveButton.disabled) {
            if (!saveButton.className.includes('opacity-50')) {
              saveButton.className += ' opacity-50 cursor-not-allowed';
            }
          } else {
            saveButton.className = saveButton.className.replace('opacity-50', '').replace('cursor-not-allowed', '');
          }
        };

        saveButton.addEventListener('click', () => {
          let nextValue = '';
          if (inputEl) {
            if (inputEl.type === 'checkbox') {
              nextValue = inputEl.checked;
            } else {
              if (inputEl.dataset && inputEl.dataset.redacted === 'true') {
                return;
              }
              nextValue = inputEl.value;
            }
          } else if (item.key === 'default_trackers') {
            const selections = Array.from(
              valueCol.querySelectorAll('input[type="checkbox"][data-tracker]')
            )
              .filter((cb) => cb.checked)
              .map((cb) => cb.dataset.tracker)
              .filter(Boolean);
            nextValue = selections.map((t) => String(t).toUpperCase()).join(', ');
          }
          saveConfigValue(currentPath, nextValue, status);
        });

        if (inputEl && inputEl.type === 'text') {
          inputEl.addEventListener('input', updateSaveState);
          updateSaveState();
        }

        sourceCol.appendChild(saveButton);
        sourceCol.appendChild(status);
      }
      row.appendChild(keyCol);
      row.appendChild(valueCol);
      if (!isCollapsibleRow && !fullWidth) {
        row.appendChild(sourceCol);
      }
      list.appendChild(row);
    });

    return list;
  };

  const extractAllImageHosts = (sections) => {
    const collectFromItems = (items) => {
      for (const item of items || []) {
        if (item.children && item.children.length) {
          const found = collectFromItems(item.children);
          if (found.length) {
            return found;
          }
        }
        if (item.key && item.key.startsWith('img_host_') && item.help) {
          const helpLine = item.help.find((line) => line.toLowerCase().includes('available image hosts'));
          if (helpLine) {
            const parts = helpLine.split(':');
            if (parts.length >= 2) {
              return parts[1]
                .split(',')
                .map((host) => host.trim().toLowerCase())
                .filter(Boolean);
            }
          }
        }
      }
      return [];
    };

    for (const section of sections) {
      const found = collectFromItems(section.items || []);
      if (found.length) {
        return found;
      }
    }
    return [];
  };

  const extractUsedImageHosts = (sections) => {
    const used = new Set();
    const collectFromItems = (items) => {
      for (const item of items || []) {
        if (item.children && item.children.length) {
          collectFromItems(item.children);
        }
        if (item.key && item.key.startsWith('img_host_') && item.value) {
          const normalized = String(item.value).trim().toLowerCase();
          if (normalized) {
            used.add(normalized);
          }
        }
      }
    };

    for (const section of sections) {
      collectFromItems(section.items || []);
    }
    return used;
  };

  const renderSections = (sections) => {
    container.innerHTML = '';
    const allImageHosts = extractAllImageHosts(sections);
    const usedImageHosts = extractUsedImageHosts(sections);

    sections.forEach((section) => {
      const sectionWrapper = document.createElement('div');
      sectionWrapper.className = isDarkMode ? 'border-b border-gray-700/40' : 'border-b border-gray-200';

      const details = document.createElement('details');
      details.className = isDarkMode
        ? 'bg-gray-900'
        : 'bg-gray-100';

      const summary = document.createElement('summary');
      summary.className = isDarkMode
        ? 'cursor-pointer select-none px-4 py-3 font-semibold text-white'
        : 'cursor-pointer select-none px-4 py-3 font-semibold text-gray-800';
      summary.textContent = section.section;

      const list = renderItems(section.items || [], [section.section], 0, allImageHosts, usedImageHosts, true);
      details.appendChild(summary);
      details.appendChild(list);
      sectionWrapper.appendChild(details);
      container.appendChild(sectionWrapper);
    });
  };

  const loadConfigOptions = async () => {
    try {
      const response = await apiFetch(`${API_BASE}/config_options`);
      // Read response body as text first to handle non-JSON responses safely
      const contentType = response.headers.get('content-type') || '';
      const rawBody = await response.text();
      let data;
      if (contentType.includes('application/json')) {
        try {
          data = JSON.parse(rawBody);
        } catch (err) {
          throw new Error(`Invalid JSON response (status ${response.status}): ${rawBody}`);
        }
      } else {
        data = rawBody;
      }

      if (!response.ok) {
        const bodyMsg = typeof data === 'string' ? data : JSON.stringify(data);
        throw new Error(`HTTP ${response.status}: ${bodyMsg || 'Request failed'}`);
      }

      if (isPlainObject(data) && !data.success) {
        throw new Error(data.error || 'Failed to load config options');
      }

      cachedSections = data.sections || [];
      statusEl.textContent = '';
      renderSections(cachedSections);
    } catch (error) {
      statusEl.textContent = error.message || 'Failed to load config options';
      statusEl.className = isDarkMode ? 'text-sm text-red-400' : 'text-sm text-red-500';
    }
  };

  themeToggle.addEventListener('click', () => {
    isDarkMode = !isDarkMode;
    storage.set(THEME_KEY, isDarkMode ? 'dark' : 'light');
    applyTheme();
    renderSections(cachedSections);
  });

  applyTheme();
  loadConfigOptions();
})();

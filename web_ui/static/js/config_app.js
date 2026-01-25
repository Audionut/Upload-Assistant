const { useEffect, useMemo, useRef, useState } = React;

// Helper to lazily load a QR code library (UMD build) and return the module
function loadQRCodeLib() {
  return new Promise((resolve, reject) => {
    // If already present, resolve immediately
    if (window.qrcode || window.QRCode || window.qrcodeModule) {
      return resolve(window.qrcode || window.QRCode || window.qrcodeModule);
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js';
    script.integrity = 'sha384-HGmnkDZJy7mRkoARekrrj0VjEFSh9a0Z8qxGri/kTTAJkgR8hqD1lHsYSh3JdzRi';
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.onload = () => resolve(window.qrcode || window.QRCode || window.qrcodeModule);
    script.onerror = () => reject(new Error('Failed to load qrcode library'));
    document.head.appendChild(script);
  });
}

// Info icon component (similar to lucide-react Info icon)
const InfoIcon = ({ className = "" }) => {
  return React.createElement('svg', {
    xmlns: 'http://www.w3.org/2000/svg',
    width: '16',
    height: '16',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '2',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className: className
  },
    React.createElement('circle', { cx: '12', cy: '12', r: '10' }),
    React.createElement('path', { d: 'M12 16v-4' }),
    React.createElement('path', { d: 'M12 8h.01' })
  );
};

// Tooltip component
const Tooltip = ({ children, content, className = "" }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);

  const showTooltip = () => setIsVisible(true);
  const hideTooltip = () => setIsVisible(false);

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;

      let top = triggerRect.top - tooltipRect.height - 8;
      let left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2);

      // Adjust if tooltip goes off screen
      if (top < 8) {
        top = triggerRect.bottom + 8;
      }

      if (left < 8) {
        left = 8;
      } else if (left + tooltipRect.width > viewportWidth - 8) {
        left = viewportWidth - tooltipRect.width - 8;
      }

      setPosition({ top, left });
    }
  }, [isVisible]);

  return React.createElement('div', { className: 'relative inline-block' },
    React.createElement('div', {
      ref: triggerRef,
      onMouseEnter: showTooltip,
      onMouseLeave: hideTooltip,
      className: className
    }, children),
    isVisible && React.createElement('div', {
      ref: tooltipRef,
      className: 'fixed z-50 px-3 py-2 text-sm text-white bg-gray-900 rounded-md shadow-lg pointer-events-none max-w-xs break-words',
      style: {
        top: `${position.top}px`,
        left: `${position.left}px`,
        whiteSpace: 'pre-wrap',
      }
    }, content,
      React.createElement('div', {
        className: 'absolute w-2 h-2 bg-gray-900 transform rotate-45',
        style: {
          top: position.top > (triggerRef.current?.getBoundingClientRect().top || 0) ? '-4px' : '100%',
          left: '50%',
          marginLeft: '-4px',
        }
      })
    )
  );
};

const API_BASE = window.location.origin + '/api';
const THEME_KEY = 'ua_config_theme';
const storage = window.UAStorage;
const getStoredTheme = window.getUAStoredTheme;

// Prefer shared `uaApiFetch` when available (provides CSRF handling and retry-on-auth-fail),
// otherwise fall back to a local implementation.
const apiFetch = (typeof window !== 'undefined' && window.uaApiFetch) || (async (url, options = {}) => {
  // Local fallback: load CSRF token once and retry on 401/403 once.
  let localCsrf = null;
  const loadLocalCsrf = async (force = false) => {
    if (localCsrf && !force) return;
    try {
      const r = await fetch(`${API_BASE}/csrf_token`, { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      localCsrf = d && d.csrf_token ? String(d.csrf_token) : null;
    } catch (e) {
      // ignore
    }
  };

  await loadLocalCsrf();
  const headers = { ...(options.headers || {}) };
  if (localCsrf) headers['X-CSRF-Token'] = localCsrf;
  let response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 401 || response.status === 403) {
    await loadLocalCsrf(true);
    const headers2 = { ...(options.headers || {}) };
    if (localCsrf) headers2['X-CSRF-Token'] = localCsrf;
    response = await fetch(url, { ...options, headers: headers2, credentials: 'same-origin' });
  }
  return response;
});

// Use shared loader when available; otherwise provide a no-op fallback.
const loadCsrfToken = (typeof window !== 'undefined' && window.loadCsrfToken) || (async () => {});

const sensitiveKeyPattern = /(api|username|password|announce_url|rss_key|passkey|discord_bot_token|discord_channel_id|qui_proxy_url)/i;
const isSensitiveKey = (key) => sensitiveKeyPattern.test(key || '');
const isTorrentClientUserPass = (key, pathParts) =>
  pathParts.includes('TORRENT_CLIENTS') && /(user|pass)/i.test(key || '');
const isSensitiveKeyForPath = (key, pathParts) => isSensitiveKey(key) || isTorrentClientUserPass(key, pathParts);
const isReadOnlyKeyForPath = (key, pathParts) =>
  pathParts.includes('TORRENT_CLIENTS') && key === 'torrent_client';
const formatDisplayLabel = (key) => {
  if (!key) return key;
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
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
  sharex: ['sharex_url', 'sharex_api_key'],
  utppm: ['utppm_api']
};

// Mapping from tracker acronyms to full names
const trackerNameMap = {
  'AITHER': 'Aither',
  'AR': 'Alpharatio',
  'ASC': 'Amigos-Share',
  'ANT': 'Anthelion',
  'ACM': 'AsianCinema',
  'A4K': 'Aura4K',
  'AZ': 'AvistaZ',
  'BHD': 'Beyond-HD',
  'BHDTV': 'BitHDTV',
  'BLU': 'Blutopia',
  'BJS': 'BrasilJapão-Share',
  'BT': 'BrasilTracker',
  'CBR': 'CapybaraBR',
  'CZ': 'CinemaZ',
  'TIK': 'Cinematik',
  'DP': 'DarkPeers',
  'DC': 'DigitalCore',
  'EMUW': 'Emuwarez',
  'FNP': 'FearNoPeer',
  'FL': 'FileList',
  'FRIKI': 'Friki',
  'FF': 'FunFile',
  'GPW': 'GreatPosterWall',
  'HUNO': 'hawke-uno',
  'HDB': 'HDBits',
  'HDS': 'HD-Space',
  'HDT': 'HD-Torrents',
  'HHD': 'HomieHelpDesk',
  'IS': 'ImmortalSeed',
  'IHD': 'InfinityHD',
  'ITT': 'ItaTorrents',
  'LDU': 'LastDigitalUnderground',
  'LT': 'Lat-Team',
  'LCD': 'Locadora',
  'LST': 'LST',
  'LUME': 'Luminarr',
  'MTV': 'MoreThanTV',
  'NBL': 'Nebulance',
  'OTW': 'OldToonsWorld',
  'OE': 'OnlyEncodes+',
  'PTP': 'PassThePopcorn',
  'PTT': 'PolishTorrent',
  'PT': 'Portugas',
  'PHD': 'PrivateHD',
  'PTER': 'PTerClub',
  'PTS': 'PTSKIT',
  'R4E': 'Racing4Everyone',
  'RAS': 'Rastastugan',
  'RF': 'ReelFLiX',
  'RTF': 'RetroFlix',
  'SAM': 'Samaritano',
  'SP': 'seedpool',
  'SHRI': 'ShareIsland',
  'STC': 'SkipTheCommercials',
  'SPD': 'SpeedApp',
  'SN': 'Swarmazon',
  'TLZ': 'The Leach Zone',
  'TOS': 'TheOldSchool',
  'TTG': 'ToTheGlory',
  'THR': 'TorrentHR',
  'TTR': 'Torrenteros',
  'TL': 'TorrentLeech',
  'TVC': 'TVChaosUK',
  'ULCX': 'ULCX',
  'UTP': 'UTOPIA',
  'YOINK': 'YOiNKED',
  'YUS': 'YUSCENE'
};

const getTrackerDisplayName = (acronym) => {
  return trackerNameMap[acronym.toUpperCase()] || acronym;
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

const statusClassFor = (type, isDarkMode) => {
  if (type === 'success') {
    return isDarkMode ? 'text-green-400' : 'text-green-600';
  }
  if (type === 'error') {
    return isDarkMode ? 'text-red-400' : 'text-red-500';
  }
  if (type === 'warn') {
    return isDarkMode ? 'text-yellow-400' : 'text-yellow-600';
  }
  return isDarkMode ? 'text-gray-400' : 'text-gray-500';
};

// NumberInput component - styled number input using browser's built-in controls
const NumberInput = ({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  className = "",
  isDarkMode = false
}) => {
  const currentValue = value === null || value === undefined || value === '' ? min : Number(value);

  const handleInputChange = (e) => {
    const inputValue = e.target.value;
    if (inputValue === '') {
      onChange(min);
    } else {
      const numValue = Number(inputValue);
      if (!isNaN(numValue)) {
        onChange(Math.max(min, Math.min(max, numValue)));
      }
    }
  };

  const inputClass = isDarkMode
    ? 'px-3 py-2 border border-gray-700 bg-gray-900 text-gray-100 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent'
    : 'px-3 py-2 border border-gray-300 bg-white text-gray-800 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent';

  return (
    <input
      type="number"
      value={currentValue}
      onChange={handleInputChange}
      min={min}
      max={max}
      step={step}
      className={`${inputClass} ${className}`}
      style={{ width: '100px' }}
    />
  );
};

// SelectDropdown component - styled select dropdown for categorical options
const SelectDropdown = ({
  value,
  onChange,
  options = [],
  className = "",
  isDarkMode = false
}) => {
  const currentValue = value === null || value === undefined ? '' : String(value);

  const handleSelectChange = (e) => {
    onChange(e.target.value);
  };

  const selectClass = isDarkMode
    ? 'w-full px-3 py-2 border border-gray-700 bg-gray-900 text-gray-100 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent'
    : 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-800 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent';

  return (
    <select
      value={currentValue}
      onChange={handleSelectChange}
      className={`${selectClass} ${className}`}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
};

function ConfigLeaf({
  item,
  pathParts,
  isDarkMode,
  fullWidth,
  allImageHosts,
  usedImageHosts,
  torrentClients,
  onValueChange
}) {
  const path = [...pathParts, item.key];

  const helpText = item.help && item.help.length ? item.help.join('\n') : '';
  const labelClass = isDarkMode
    ? 'text-sm font-medium text-gray-200'
    : 'text-sm font-medium text-gray-700';


  const inputClass = isDarkMode
    ? 'w-full px-3 py-2 border border-gray-700 bg-gray-900 text-gray-100 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent'
    : 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-800 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent';

  // Check if this is a numeric field that should use NumberInput
  const isNumericField = (key) => {
    // Define which fields should be treated as numeric
    const numericFields = [
      'tracker_pass_checks',
      'mkbrr_threads',
      'ffmpeg_compression',
      'screens',
      'cutoff_screens',
      'thumbnail_size',
      'process_limit',
      'threads',
      'multiScreens',
      'pack_thumb_size',
      'charLimit',
      'fileLimit',
      'processLimit',
      'desat',
      'min_successful_image_uploads',
      'overlay_text_size',
      'logo_size',
      'bluray_image_size',
      'bluray_score',
      'bluray_single_score',
      'rehash_cooldown',
      'custom_layout',
      'screens_per_row'
    ];
    return numericFields.includes(key);
  };

  // Check if this is a linking field that should use SelectDropdown
  const isLinkingField = (key, pathParts) => {
    return key === 'linking' && pathParts.includes('TORRENT_CLIENTS');
  };

  // Hooks for boolean values
  const [checked, setChecked] = useState(Boolean(item.value));

  useEffect(() => {
    if (typeof item.value === 'boolean') setChecked(Boolean(item.value));
  }, [item.value]);

  // Hooks for numeric values
  const getDefaultValue = (key) => {
    switch (key) {
      case 'mkbrr_threads':
      case 'rehash_cooldown':
        return 0;
      case 'multiScreens':
        return 2;
      case 'tracker_pass_checks':
      case 'screens':
      case 'cutoff_screens':
      case 'process_limit':
      case 'threads':
      case 'min_successful_image_uploads':
      case 'overlay_text_size':
      case 'logo_size':
      case 'thumbnail_size':
      case 'pack_thumb_size':
      case 'charLimit':
      case 'fileLimit':
      case 'processLimit':
      case 'bluray_image_size':
      case 'bluray_score':
      case 'bluray_single_score':
      case 'desat':
        return 10;
      case 'screens_per_row':
        return 2;
      case 'custom_layout':
        return 1;
      case 'ffmpeg_compression':
        return 6;
      default:
        return 1;
    }
  };

  const [numericValue, setNumericValue] = useState(() => {
    if (isNumericField(item.key)) {
      const val = item.value;
      if (val === null || val === undefined || val === '') return getDefaultValue(item.key);
      const num = Number(val);
      return isNaN(num) ? getDefaultValue(item.key) : num;
    }
    return 1;
  });

  useEffect(() => {
    if (!isNumericField(item.key)) return;
    const val = item.value;
    if (val === null || val === undefined || val === '') {
      setNumericValue(getDefaultValue(item.key));
    } else {
      const num = Number(val);
      setNumericValue(isNaN(num) ? getDefaultValue(item.key) : num);
    }
  }, [item.value, item.key, pathParts]);

  // Hooks for select values (always declared to follow Rules of Hooks)
  const [selectedValue, setSelectedValue] = useState(() => (item == null || item.value == null ? '' : String(item.value)));

  useEffect(() => {
    setSelectedValue(item == null || item.value == null ? '' : String(item.value));
  }, [item.value]);

  // Helpers and hooks for `default_trackers` (must run unconditionally to obey Rules of Hooks)
  const normalizeTrackers = (value) => (
    String(value || '')
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean)
  );

  const [selected, setSelected] = useState(() => new Set(normalizeTrackers(item.value)));
  const prevDefaultRef = useRef(normalizeTrackers(item.value).join(', '));

  useEffect(() => {
    setSelected(new Set(normalizeTrackers(item.value)));
  }, [item.value]);

  // Observer: whenever the selected set changes, persist the default_trackers value
  useEffect(() => {
    // Only run this persistence effect for the actual `default_trackers` field.
    if (item.key !== 'default_trackers') return;
    const nextValue = Array.from(selected).map((t) => String(t).toUpperCase()).join(', ');
    const originalValue = normalizeTrackers(item.value).join(', ');
    if (prevDefaultRef.current === nextValue) return;
    prevDefaultRef.current = nextValue;
    onValueChange(path, nextValue, {
      originalValue,
      isSensitive: false,
      isRedacted: false,
      readOnly: false
    });
  }, [selected, onValueChange, path, item.value]);

  const toggleTracker = (tracker, checked) => {
    const selections = new Set(selected);
    if (checked) {
      selections.add(tracker.toUpperCase());
    } else {
      selections.delete(tracker.toUpperCase());
    }
    setSelected(selections);
  };


  if (typeof item.value === 'boolean') {
    const originalValue = Boolean(item.value);

    return (
      <div className="grid grid-cols-12 gap-3 items-start px-4 py-3">
        <div className={fullWidth ? 'col-span-12' : 'col-span-4'}>
          <div className="flex items-center gap-2">
            <div className={labelClass}>{formatDisplayLabel(item.key)}</div>
            {helpText && (
              <Tooltip content={helpText}>
                <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
              </Tooltip>
            )}
          </div>
        </div>
        <div className={fullWidth ? 'col-span-12' : 'col-span-7'}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const nextValue = !checked;
                setChecked(nextValue);
                onValueChange(path, nextValue, {
                  originalValue,
                  isSensitive: false,
                  isRedacted: false,
                  readOnly: false
                });
              }}
              aria-pressed={checked}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${checked ? 'bg-purple-600' : 'bg-gray-300'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
            <span className={isDarkMode ? 'text-gray-200' : 'text-gray-700'}>{checked ? 'True' : 'False'}</span>
          </div>
        </div>
        {!fullWidth && (
          <div className="col-span-1 text-right">
          </div>
        )}
      </div>
    );
  }

  if (isNumericField(item.key)) {
    const originalValue = String(item.value);

    // Define min/max for different fields
    const getFieldLimits = (key) => {
      switch (key) {
        case 'tracker_pass_checks':
          return { min: 1, max: 20, step: 1 };
        case 'mkbrr_threads':
          return { min: 0, max: 32, step: 1 };
        case 'ffmpeg_compression':
          return { min: 0, max: 9, step: 1 };
        case 'screens':
          return { min: 1, max: 50, step: 1 };
        case 'cutoff_screens':
          return { min: 1, max: 50, step: 1 };
        case 'thumbnail_size':
          return { min: 100, max: 1000, step: 50 };
        case 'process_limit':
          return { min: 1, max: 100, step: 1 };
        case 'threads':
          return { min: 1, max: 32, step: 1 };
        case 'multiScreens':
          return { min: 0, max: 20, step: 1 };
        case 'pack_thumb_size':
          return { min: 100, max: 1000, step: 50 };
        case 'charLimit':
          return { min: 100, max: 50000, step: 100 };
        case 'fileLimit':
          return { min: 1, max: 1000, step: 1 };
        case 'processLimit':
          return { min: 1, max: 100, step: 1 };
        case 'desat':
          return { min: 0, max: 20, step: 0.1 };
        case 'min_successful_image_uploads':
          return { min: 1, max: 10, step: 1 };
        case 'overlay_text_size':
          return { min: 10, max: 50, step: 1 };
        case 'logo_size':
          return { min: 100, max: 1000, step: 50 };
        case 'bluray_image_size':
          return { min: 100, max: 1000, step: 50 };
        case 'bluray_score':
          return { min: 0, max: 100, step: 0.1 };
        case 'bluray_single_score':
          return { min: 0, max: 100, step: 0.1 };
        case 'rehash_cooldown':
          return { min: 0, max: 300, step: 5 };
        case 'screens_per_row':
          return { min: 1, max: 10, step: 1 };
        case 'custom_layout':
          return { min: 1, max: 10, step: 1 };
        default:
          return { min: 0, max: 100, step: 1 };
      }
    };

    const limits = getFieldLimits(item.key);

    return (
      <div className="grid grid-cols-12 gap-3 items-start px-4 py-3">
        <div className={fullWidth ? 'col-span-12' : 'col-span-4'}>
          <div className="flex items-center gap-2">
            <div className={labelClass}>{formatDisplayLabel(item.key)}</div>
            {helpText && (
              <Tooltip content={helpText}>
                <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
              </Tooltip>
            )}
          </div>
        </div>
        <div className={fullWidth ? 'col-span-12' : 'col-span-7'}>
          <NumberInput
            value={numericValue}
            onChange={(newValue) => {
              setNumericValue(newValue);
              onValueChange(path, String(newValue), {
                originalValue,
                isSensitive: false,
                isRedacted: false,
                readOnly: false
              });
            }}
            min={limits.min}
            max={limits.max}
            step={limits.step}
            isDarkMode={isDarkMode}
          />
        </div>
        {!fullWidth && (
          <div className="col-span-1 text-right">
          </div>
        )}
      </div>
    );
  }

  if (isLinkingField(item.key, pathParts)) {
    const linkingOptions = [
      { value: '', label: 'None (Original Path)' },
      { value: 'symlink', label: 'Symbolic Link' },
      { value: 'hardlink', label: 'Hard Link' }
    ];

    const originalValue = String(item.value || '');

    return (
      <div className="grid grid-cols-12 gap-3 items-start px-4 py-3">
        <div className={fullWidth ? 'col-span-12' : 'col-span-4'}>
          <div className="flex items-center gap-2">
            <div className={labelClass}>{formatDisplayLabel(item.key)}</div>
            {helpText && (
              <Tooltip content={helpText}>
                <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
              </Tooltip>
            )}
          </div>
        </div>
        <div className={fullWidth ? 'col-span-12' : 'col-span-7'}>
          <SelectDropdown
            value={selectedValue}
            onChange={(newValue) => {
              setSelectedValue(newValue);
              onValueChange(path, newValue, {
                originalValue,
                isSensitive: false,
                isRedacted: false,
                readOnly: false
              });
            }}
            options={linkingOptions}
            isDarkMode={isDarkMode}
          />
        </div>
        {!fullWidth && (
          <div className="col-span-1 text-right">
          </div>
        )}
      </div>
    );
  }

  if (item.key === 'default_trackers') {
    const availableTrackers = getAvailableTrackers(item);

    return (
      <div className="col-span-full px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <div className={labelClass}>{formatDisplayLabel(item.key)}</div>
          {helpText && (
            <Tooltip content={helpText}>
              <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
            </Tooltip>
          )}
        </div>
        <div className={`rounded-lg border p-3 ${isDarkMode ? 'border-gray-700 bg-gray-900/30' : 'border-gray-200 bg-gray-50'}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
            {availableTrackers.map((tracker) => (
              <label key={tracker} className={`flex items-center gap-2 text-xs ${isDarkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                <input
                  type="checkbox"
                  checked={selected.has(tracker.toUpperCase())}
                  onChange={(e) => toggleTracker(tracker, e.target.checked)}
                  className={isDarkMode ? 'h-4 w-4 accent-purple-500' : 'h-4 w-4 accent-purple-600'}
                />
                <span>{getTrackerDisplayName(tracker)}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (item.key && item.key.startsWith('img_host_')) {
    const options = getImageHostOptions(item, allImageHosts, usedImageHosts);
    const [value, setValue] = useState(item.value === null || item.value === undefined
      ? ''
      : String(item.value).trim().toLowerCase());

    useEffect(() => {
      setValue(item.value === null || item.value === undefined
        ? ''
        : String(item.value).trim().toLowerCase());
    }, [item.value]);

    const originalValue = item.value === null || item.value === undefined
      ? ''
      : String(item.value).trim().toLowerCase();

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label htmlFor={item.key} className={labelClass}>{formatDisplayLabel(item.key)}</label>
          {helpText && (
            <Tooltip content={helpText}>
              <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
            </Tooltip>
          )}
        </div>
        <select
          id={item.key}
          value={value}
          onChange={(e) => {
            const nextValue = e.target.value;
            setValue(nextValue);
            onValueChange(path, nextValue, {
              originalValue,
              isSensitive: false,
              isRedacted: false,
              readOnly: false
            });
          }}
          className={inputClass}
        >
          <option value=""></option>
          {options.map((host) => (
            <option key={host} value={host}>{host}</option>
          ))}
        </select>
      </div>
    );
  }

  if (item.key === 'injecting_client_list' || item.key === 'searching_client_list') {
    const normalizeClients = (value) => {
      if (Array.isArray(value)) {
        return value.filter(client => client && typeof client === 'string').map(client => client.trim());
      }
      if (typeof value === 'string' && value.trim()) {
        try {
          const parsed = JSON.parse(value);
          if (Array.isArray(parsed)) {
            return parsed.filter(client => client && typeof client === 'string').map(client => client.trim());
          }
        } catch (e) {
          // If not valid JSON, treat as comma-separated string
          return value.split(',').map(client => client.trim()).filter(client => client);
        }
      }
      return [];
    };

    const [selected, setSelected] = useState(() => normalizeClients(item.value));
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    useEffect(() => {
      setSelected(normalizeClients(item.value));
    }, [item.value]);

    useEffect(() => {
      const handleClickOutside = (event) => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
          setIsOpen(false);
        }
      };

      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const originalValue = normalizeClients(item.value);

    const toggleClient = (client) => {
      const newSelected = selected.includes(client)
        ? selected.filter(c => c !== client)
        : [...selected, client];
      setSelected(newSelected);
      onValueChange(path, newSelected, {
        originalValue,
        isSensitive: false,
        isRedacted: false,
        readOnly: false
      });
    };

    const removeClient = (clientToRemove, e) => {
      e.stopPropagation();
      const newSelected = selected.filter(c => c !== clientToRemove);
      setSelected(newSelected);
      onValueChange(path, newSelected, {
        originalValue,
        isSensitive: false,
        isRedacted: false,
        readOnly: false
      });
    };

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className={labelClass}>{formatDisplayLabel(item.key)}</label>
          {helpText && (
            <Tooltip content={helpText}>
              <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
            </Tooltip>
          )}
        </div>
        <div className="relative" ref={dropdownRef}>
          <div
            className={`${inputClass} cursor-pointer flex items-center justify-between`}
            onClick={() => setIsOpen(!isOpen)}
          >
            <div className="flex flex-wrap gap-1 flex-1">
              {selected.length === 0 ? (
                <span className={isDarkMode ? 'text-gray-500' : 'text-gray-400'}>Select clients...</span>
              ) : (
                selected.map(client => (
                  <span
                    key={client}
                    className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs ${
                      isDarkMode ? 'bg-purple-600 text-white' : 'bg-purple-100 text-purple-800'
                    }`}
                  >
                    {client}
                    <button
                      type="button"
                      onClick={(e) => removeClient(client, e)}
                      className={`hover:${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
            </div>
            <span className={`transition-transform ${isOpen ? 'rotate-180' : 'rotate-0'}`}>▼</span>
          </div>
          {isOpen && (
            <div className={`absolute z-10 w-full mt-1 border rounded-md shadow-lg max-h-60 overflow-auto ${
              isDarkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-300'
            }`}>
              {torrentClients.length === 0 ? (
                <div className={`px-3 py-2 text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  No torrent clients configured
                </div>
              ) : (
                torrentClients.map((client) => (
                  <div
                    key={client}
                    className={`px-3 py-2 cursor-pointer hover:${
                      isDarkMode ? 'bg-gray-800' : 'bg-gray-100'
                    } ${selected.includes(client) ? (isDarkMode ? 'bg-purple-900' : 'bg-purple-50') : ''}`}
                    onClick={() => toggleClient(client)}
                  >
                    <label className={`flex items-center gap-2 text-sm cursor-pointer ${
                      isDarkMode ? 'text-gray-200' : 'text-gray-700'
                    }`}>
                      <input
                        type="checkbox"
                        checked={selected.includes(client)}
                        onChange={() => {}} // Handled by parent div
                        className={isDarkMode ? 'h-4 w-4 accent-purple-500' : 'h-4 w-4 accent-purple-600'}
                      />
                      {client}
                    </label>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Special-case: render a dropdown for tonemapping algorithm selection
  if (item.key === 'algorithm') {
    const algoOptions = [
      { value: '', label: '' },
      { value: 'none', label: 'none — Do not apply any tone map, only desaturate overbright pixels.' },
      { value: 'clip', label: 'clip — Hard-clip out-of-range values; accurate in-range colors.' },
      { value: 'linear', label: 'linear — Stretch reference gamut to a linear multiple of the display.' },
      { value: 'gamma', label: 'gamma — Fit a logarithmic transfer between the tone curves.' },
      { value: 'reinhard', label: 'reinhard — Preserve brightness with a simple curve; may flatten details.' },
      { value: 'hable', label: 'hable — Preserve dark/bright details better than reinhard.' },
      { value: 'mobius', label: 'mobius — Smoothly map out-of-range values while retaining colors.' }
    ];

    const originalValue = item.value === null || item.value === undefined ? '' : String(item.value);

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className={labelClass}>{formatDisplayLabel(item.key)}</label>
          {helpText && (
            <Tooltip content={helpText}>
              <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
            </Tooltip>
          )}
        </div>
        <SelectDropdown
          value={selectedValue}
          onChange={(newValue) => {
            setSelectedValue(newValue);
            onValueChange(path, newValue, {
              originalValue,
              isSensitive: false,
              isRedacted: false,
              readOnly: false
            });
          }}
          options={algoOptions}
          isDarkMode={isDarkMode}
        />
      </div>
    );
  }

  const rawValue = item.value === null || item.value === undefined
    ? ''
    : (typeof item.value === 'string' ? item.value : JSON.stringify(item.value));
  const sensitive = isSensitiveKeyForPath(item.key, pathParts);
  const readOnly = isReadOnlyKeyForPath(item.key, pathParts);
  const originalValue = sensitive && String(rawValue).trim() !== '' ? '<REDACTED>' : rawValue;

  const [textValue, setTextValue] = useState(rawValue);
  const [redacted, setRedacted] = useState(sensitive && String(rawValue).trim() !== '');

  useEffect(() => {
    const nextRaw = item.value === null || item.value === undefined
      ? ''
      : (typeof item.value === 'string' ? item.value : JSON.stringify(item.value));
    const isRedacted = sensitive && String(nextRaw).trim() !== '';
    setTextValue(isRedacted ? '<REDACTED>' : nextRaw);
    setRedacted(isRedacted);
  }, [item.value, sensitive]);

  const onFocus = () => {
    if (redacted) {
      setTextValue('');
      setRedacted(false);
    }
  };


  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label htmlFor={item.key} className={labelClass}>{formatDisplayLabel(item.key)}</label>
        {helpText && (
          <Tooltip content={helpText}>
            <InfoIcon className={`w-4 h-4 ${isDarkMode ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-600'}`} />
          </Tooltip>
        )}
      </div>
      <input
        id={item.key}
        type="text"
        value={textValue}
        onChange={(e) => {
          const nextValue = e.target.value;
          setTextValue(nextValue);
          onValueChange(path, nextValue, {
            originalValue,
            isSensitive: sensitive,
            isRedacted: redacted,
            readOnly
          });
        }}
        onFocus={onFocus}
        disabled={readOnly}
        className={`${inputClass}${readOnly ? ' opacity-70 cursor-not-allowed' : ''}`}
      />
    </div>
  );
}

function ItemList({
  items,
  pathParts,
  depth,
  isDarkMode,
  allImageHosts,
  usedImageHosts,
  fullWidth,
  expandedGroups,
  toggleGroup,
  torrentClients,
  onValueChange
}) {
  // Group items into regular fields and subsections
  const regularItems = [];
  const subsections = [];

  for (const item of items || []) {
    const apiHost = getImageHostForApiKey(item.key);
    if (apiHost && !usedImageHosts.has(apiHost)) {
      continue;
    }

    if (item.children && item.children.length) {
      subsections.push(item);
    } else {
      regularItems.push(item);
    }
  }

  // If we're in the top-level TRACKERS section, extract the default_trackers item
  // This must happen before we partition/group regularItems so the default_trackers
  // field is not rendered twice (once in the tracker tabs and once in the grid).
  const isTrackerConfig = pathParts.includes('TRACKERS') && depth === 0;
  let defaultTrackersItem = null;
  if (isTrackerConfig) {
    const idx = regularItems.findIndex((it) => it.key === 'default_trackers');
    if (idx >= 0) {
      defaultTrackersItem = regularItems.splice(idx, 1)[0];
    }
  }

  // Define known subgroupings for better visual breakdown (screenshots-related)
  const subgroupDefinitions = {
    'General ffmpeg': ['ffmpeg_compression', 'process_limit', 'ffmpeg_limit'],
    'Overlay': ['frame_overlay', 'overlay_text_size'],
    'HDR Tonemapping': ['tone_map', 'algorithm', 'desat', 'use_libplacebo', 'ffmpeg_is_good', 'ffmpeg_warmup'],
    'Bluray & DVD': ['use_largest_playlist', 'get_bluray_info', 'bluray_score', 'bluray_single_score', 'ping_unit3d'],
    'Extra': ['btn_api', 'user_overrides'],
    'Logos': ['add_logo', 'logo_size', 'logo_language'],
    'Bluray/DVD': ['add_bluray_link', 'use_bluray_images', 'bluray_image_size', 'disc_menu_header'],
    'multi-file/disc': ['multiScreens', 'pack_thumb_size', 'fileLimit', 'processLimit', 'charLimit'],
    'Headers': ['custom_description_header', 'tonemapped_header', 'screenshot_header'],
    'Signature': ['custom_signature'],
    'Sonarr': ['use_sonarr', 'sonarr_url', 'sonarr_api_key', 'sonarr_url_1', 'sonarr_api_key_1'],
    'Radarr': ['use_radarr', 'radarr_url', 'radarr_api_key', 'radarr_url_1', 'radarr_api_key_1'],
  };

  // Partition regularItems into subgroups and an "Other" bucket
  const grouped = {};
  const ungrouped = [];
  // Ensure image host groups appear first
  grouped['Image Hosts'] = [];
  grouped['Image Host API Keys'] = [];
  // Pre-create keys for consistent ordering for other subgroup definitions
  for (const g of Object.keys(subgroupDefinitions)) grouped[g] = [];

  for (const it of regularItems) {
    // Image host selection fields (e.g., img_host_1) should be top-level Image Hosts
    if (it.key && it.key.startsWith && it.key.startsWith('img_host_')) {
      grouped['Image Hosts'].push(it);
      continue;
    }

    // API key fields for image hosts (recognized via helper) go into Image Host API Keys
    const apiHost = getImageHostForApiKey(it.key);
    if (apiHost) {
      grouped['Image Host API Keys'].push(it);
      continue;
    }

    let placed = false;
    for (const [gname, keys] of Object.entries(subgroupDefinitions)) {
      if (keys.includes(it.key)) {
        grouped[gname].push(it);
        placed = true;
        break;
      }
    }
    if (!placed) ungrouped.push(it);
  }

  // Track user choices to add available-only trackers into default_trackers
  const [pendingDefaultAdds, setPendingDefaultAdds] = useState(() => new Set());
  const [trackerTab, setTrackerTab] = useState(() => {
    try {
      return sessionStorage.getItem('ua_tracker_tab') || 'default';
    } catch (e) {
      return 'default';
    }
  });

  const normalizeTrackers = (value) => (
    String(value || '')
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean)
  );

  let availableFromExample = [];
  let selectedFromDefault = new Set();
  let configuredFromSubsections = new Set();
  let configuredSet = new Set();
  let availableRemaining = [];
  let configuredArray = [];
  let availableArray = [];
  if (isTrackerConfig && defaultTrackersItem) {
    availableFromExample = getAvailableTrackers(defaultTrackersItem).map((t) => String(t).toUpperCase());
    selectedFromDefault = new Set(normalizeTrackers(defaultTrackersItem.value));
    configuredFromSubsections = new Set((subsections || [])
      .filter(s => Array.isArray(s.children) && s.children.some(c => c.source === 'config'))
      .map(s => String(s.key).toUpperCase())
    );
    configuredSet = new Set([...selectedFromDefault, ...configuredFromSubsections]);
    availableRemaining = availableFromExample.filter((t) => !configuredSet.has(t));
    // Present configured and available lists in alphabetical order by display name
    configuredArray = Array.from(configuredSet).sort((a, b) => getTrackerDisplayName(a).localeCompare(getTrackerDisplayName(b)));
    availableArray = (availableRemaining || []).slice().sort((a, b) => getTrackerDisplayName(a).localeCompare(getTrackerDisplayName(b)));
  }
  // Ensure arrays are defined in outer scope for rendering even when not tracker config
  if (!configuredArray) configuredArray = [];
  if (!availableArray) availableArray = [];

  return (
    <div className="space-y-6">
      {/* TRACKERS tabbed subsections: Default / Configured / Available */}
      {isTrackerConfig && defaultTrackersItem && (
        <div>
          <div className="flex space-x-1 rounded-lg p-1 bg-gray-700 mb-3">
            <button
              type="button"
              onClick={() => setTrackerTab('default')}
              className={trackerTab === 'default'
                ? 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors bg-gray-600 text-white'
                : 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors text-gray-400 hover:text-white hover:bg-gray-600'}
            >
              Default trackers
            </button>
            <button
              type="button"
              onClick={() => setTrackerTab('configured')}
              className={trackerTab === 'configured'
                ? 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors bg-gray-600 text-white'
                : 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors text-gray-400 hover:text-white hover:bg-gray-600'}
            >
              Configured trackers
            </button>
            <button
              type="button"
              onClick={() => setTrackerTab('available')}
              className={trackerTab === 'available'
                ? 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors bg-gray-600 text-white'
                : 'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors text-gray-400 hover:text-white hover:bg-gray-600'}
            >
              Available trackers
            </button>
          </div>

          <div>
            <div className={trackerTab === 'default' ? '' : 'hidden'}>
              <ConfigLeaf
                key={[...pathParts, defaultTrackersItem.key].join('/')}
                item={defaultTrackersItem}
                pathParts={pathParts}
                depth={depth}
                isDarkMode={isDarkMode}
                fullWidth={true}
                allImageHosts={allImageHosts}
                usedImageHosts={usedImageHosts}
                torrentClients={torrentClients}
                onValueChange={onValueChange}
              />
            </div>

            <div className={trackerTab === 'configured' ? 'space-y-4' : 'hidden'}>
              {/* configured tab content */}
              <div className="space-y-4">
                <div className={isDarkMode ? 'text-sm font-medium text-gray-200 mb-2' : 'text-sm font-medium text-gray-700 mb-2'}>Configured trackers</div>
                <div className={`rounded-lg border p-3 ${isDarkMode ? 'border-gray-700 bg-gray-900/30' : 'border-gray-200 bg-gray-50'}`}>
                  <div className="space-y-2">
                    {configuredArray.length === 0 && (
                      <div className={isDarkMode ? 'text-gray-400' : 'text-gray-500'}>No configured trackers</div>
                    )}
                    {configuredArray.map((tr) => {
                      const subsection = subsections.find(s => String(s.key).toUpperCase() === tr);
                      if (subsection) {
                        const groupKey = [...pathParts, subsection.key].join('/');
                        const isOpen = expandedGroups.has(groupKey);
                        return (
                          <div key={tr} className="mb-2">
                            <div className="flex items-center justify-between">
                              <button
                              type="button"
                              onClick={() => toggleGroup(groupKey)}
                              aria-expanded={isOpen}
                              className={`flex items-center justify-between w-full px-3 py-2 text-sm font-medium rounded ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}
                            >
                              <span className={isDarkMode ? 'text-xs font-mono text-purple-300' : 'text-xs font-mono text-purple-700'}>{getTrackerDisplayName(tr)}</span>
                              <span className="transition-transform" style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>&gt;</span>
                            </button>
                            </div>
                            {isOpen && (
                              <div className={`rounded-lg border p-3 mt-2 ${isDarkMode ? 'border-gray-700 bg-gray-900/20' : 'border-gray-200 bg-white'}`}>
                                <ItemList
                                  items={subsection.children}
                                  pathParts={[...pathParts, subsection.key]}
                                  depth={depth + 1}
                                  isDarkMode={isDarkMode}
                                  allImageHosts={allImageHosts}
                                  usedImageHosts={usedImageHosts}
                                  fullWidth={true}
                                  expandedGroups={expandedGroups}
                                  toggleGroup={toggleGroup}
                                  torrentClients={torrentClients}
                                  onValueChange={onValueChange}
                                />
                                <div className="mt-2 flex items-center justify-end">
                                  <button
                                    type="button"
                                    onClick={async () => {
                                      const ok = await showConfirmModal(`Remove configured tracker ${tr}? This will remove the user's overrides for this tracker.`);
                                      if (!ok) return;
                                      try {
                                        const resp = await apiFetch(`${API_BASE}/config_remove_subsection`, {
                                          method: 'POST',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({ path: [...pathParts, subsection.key] })
                                        });
                                        const data = await resp.json();
                                        if (!data.success) throw new Error(data.error || 'Failed');

                                        // If this tracker is also in default_trackers, remove it there as well
                                        try {
                                          if (selectedFromDefault && selectedFromDefault.has(tr)) {
                                            const nextDefault = Array.from(selectedFromDefault).filter(x => x !== tr).join(', ');
                                            const resp2 = await apiFetch(`${API_BASE}/config_update`, {
                                              method: 'POST',
                                              headers: { 'Content-Type': 'application/json' },
                                              body: JSON.stringify({ path: [...pathParts, 'default_trackers'], value: nextDefault })
                                            });
                                            const data2 = await resp2.json();
                                            if (!data2.success) throw new Error(data2.error || 'Failed to update default_trackers');
                                          }
                                        } catch (err) {
                                          console.warn('Failed to update default_trackers after removing subsection', err);
                                        }

                                        try {
                                          sessionStorage.setItem('ua_active_tab', String(pathParts[0] || '').toLowerCase());
                                          sessionStorage.setItem('ua_tracker_tab', trackerTab || 'configured');
                                        } catch (e) { /* ignore */ }
                                        window.location.reload();
                                      } catch (err) {
                                        alert(err.message || 'Failed to remove subsection');
                                      }
                                    }}
                                    className="ml-2 px-2 py-1 text-xs rounded bg-red-600 text-white"
                                  >Remove</button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      }
                      // Tracker selected in default but not configured in file - allow removing from default
                      return (
                        <div key={tr} className="inline-flex items-center mr-2 mb-2 px-2 py-1 rounded text-xs">
                          <div className={isDarkMode ? 'bg-purple-700 text-white px-2 py-1 rounded' : 'bg-purple-100 text-purple-800 px-2 py-1 rounded'}>{getTrackerDisplayName(tr)}</div>
                          <button
                            type="button"
                            onClick={async () => {
                              const ok = await showConfirmModal({ message: `Remove ${tr} from default trackers?`, confirmLabel: 'Remove' });
                              if (!ok) return;
                              try {
                                const next = Array.from(selectedFromDefault).filter(x => x !== tr).join(', ');
                                const resp = await apiFetch(`${API_BASE}/config_update`, {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ path: [...pathParts, 'default_trackers'], value: next })
                                });
                                const data = await resp.json();
                                if (!data.success) throw new Error(data.error || 'Failed');
                                try {
                                  sessionStorage.setItem('ua_active_tab', String(pathParts[0] || '').toLowerCase());
                                  sessionStorage.setItem('ua_tracker_tab', trackerTab || 'default');
                                } catch (e) { /* ignore */ }
                                window.location.reload();
                              } catch (err) {
                                alert(err.message || 'Failed to update default trackers');
                              }
                            }}
                            className="ml-2 px-2 py-1 text-xs rounded bg-red-600 text-white"
                          >Remove</button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            <div className={trackerTab === 'available' ? '' : 'hidden'}>
              <div>
                <div className={isDarkMode ? 'text-sm font-medium text-gray-200 mb-2' : 'text-sm font-medium text-gray-700 mb-2'}>Available trackers</div>
                <div className={`rounded-lg border p-3 ${isDarkMode ? 'border-gray-700 bg-gray-900/30' : 'border-gray-200 bg-gray-50'}`}>
                  {availableArray.length === 0 && (
                    <div className={isDarkMode ? 'text-gray-400' : 'text-gray-500'}>No additional available trackers</div>
                  )}
                  <div className="space-y-2">
                    {availableArray.map((t) => {
                      const subsection = subsections.find(s => String(s.key).toUpperCase() === t);
                      const isInDefault = selectedFromDefault && selectedFromDefault.has(t);
                      const isPending = pendingDefaultAdds.has(t);
                      if (subsection) {
                        const groupKey = [...pathParts, subsection.key].join('/');
                        const isOpen = expandedGroups.has(groupKey);
                        return (
                          <div key={t} className="mb-2">
                            <button
                              type="button"
                              onClick={() => toggleGroup(groupKey)}
                              aria-expanded={isOpen}
                              className={`flex items-center justify-between w-full px-3 py-2 text-sm font-medium rounded ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}
                            >
                              <span className={isDarkMode ? 'text-xs font-mono text-gray-200' : 'text-xs font-mono text-gray-700'}>{getTrackerDisplayName(t)}</span>
                              <span className="transition-transform" style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>&gt;</span>
                            </button>
                              {isOpen && (
                                <div className={`rounded-lg border p-3 mt-2 ${isDarkMode ? 'border-gray-700 bg-gray-900/20' : 'border-gray-200 bg-white'}`}>
                                  <ItemList
                                    items={subsection.children}
                                    pathParts={[...pathParts, subsection.key]}
                                    depth={depth + 1}
                                    isDarkMode={isDarkMode}
                                    allImageHosts={allImageHosts}
                                    usedImageHosts={usedImageHosts}
                                    fullWidth={true}
                                    expandedGroups={expandedGroups}
                                    toggleGroup={toggleGroup}
                                    torrentClients={torrentClients}
                                    onValueChange={onValueChange}
                                  />
                                  <div className="mt-2">
                                    <label className="inline-flex items-center text-xs mr-2">
                                      <input
                                        type="checkbox"
                                        checked={isInDefault || isPending}
                                        onChange={async (e) => {
                                          const checked = e.target.checked;
                                          const nextPending = new Set(pendingDefaultAdds);
                                          if (checked) {
                                            nextPending.add(t);
                                          } else {
                                            nextPending.delete(t);
                                          }
                                          setPendingDefaultAdds(nextPending);
                                          // Compute next default trackers value and queue change
                                          const nextDefaultSet = new Set(selectedFromDefault || []);
                                          for (const x of nextPending) nextDefaultSet.add(x);
                                          // If user unchecked an already-selected default, remove it
                                          if (!checked && selectedFromDefault && selectedFromDefault.has(t)) {
                                            nextDefaultSet.delete(t);
                                          }
                                          const nextDefault = Array.from(nextDefaultSet).join(', ');
                                          const originalDefault = normalizeTrackers(defaultTrackersItem.value).join(', ');
                                          onValueChange([...pathParts, 'default_trackers'], nextDefault, {
                                            originalValue: originalDefault,
                                            isSensitive: false,
                                            isRedacted: false,
                                            readOnly: false
                                          });
                                        }}
                                        className="h-4 w-4 mr-2"
                                      />
                                      <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>Add to default trackers</span>
                                    </label>
                                  </div>
                                </div>
                              )}
                          </div>
                        );
                      }
                      return (
                        <div key={t} className={isDarkMode ? 'inline-block px-2 py-1 bg-gray-800 text-gray-200 rounded text-xs' : 'inline-block px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs'}>
                          <div className="flex items-center gap-2">
                            <div>{getTrackerDisplayName(t)}</div>
                            <label className="inline-flex items-center text-xs">
                              <input
                                type="checkbox"
                                checked={(selectedFromDefault && selectedFromDefault.has(t)) || pendingDefaultAdds.has(t)}
                                onChange={(e) => {
                                  const checked = e.target.checked;
                                  const nextPending = new Set(pendingDefaultAdds);
                                  if (checked) nextPending.add(t); else nextPending.delete(t);
                                  setPendingDefaultAdds(nextPending);
                                  const nextDefaultSet = new Set(selectedFromDefault || []);
                                  for (const x of nextPending) nextDefaultSet.add(x);
                                  if (!checked && selectedFromDefault && selectedFromDefault.has(t)) {
                                    nextDefaultSet.delete(t);
                                  }
                                  const nextDefault = Array.from(nextDefaultSet).join(', ');
                                  const originalDefault = normalizeTrackers(defaultTrackersItem.value).join(', ');
                                  onValueChange([...pathParts, 'default_trackers'], nextDefault, {
                                    originalValue: originalDefault,
                                    isSensitive: false,
                                    isRedacted: false,
                                    readOnly: false
                                  });
                                }}
                                className="h-4 w-4"
                              />
                              <span className="ml-1">Add to defaults</span>
                            </label>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Regular form fields, optionally grouped into subheaders */}
      {(ungrouped.length > 0 || Object.values(grouped).some(g => g.length > 0)) && (
        <div className="space-y-4">
          {/* Ungrouped items */}
          {ungrouped.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {ungrouped.map((item) => {
                const leafPath = [...pathParts, item.key].join('/');
                return (
                  <ConfigLeaf
                    key={leafPath}
                    item={item}
                    pathParts={pathParts}
                    depth={depth}
                    isDarkMode={isDarkMode}
                    fullWidth={fullWidth}
                    allImageHosts={allImageHosts}
                    usedImageHosts={usedImageHosts}
                    torrentClients={torrentClients}
                    onValueChange={onValueChange}
                  />
                );
              })}
            </div>
          )}

          {/* Grouped subheaders */}
          {Object.keys(grouped).map((gname) => {
            const itemsInGroup = grouped[gname] || [];
            if (!itemsInGroup.length) return null;
            const headerClass = isDarkMode ? 'text-sm font-semibold text-gray-200 border-b pb-1 mb-3' : 'text-sm font-semibold text-gray-700 border-b pb-1 mb-3';
            return (
              <div key={gname}>
                <div className={headerClass}>{gname}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                  {itemsInGroup.map((item) => {
                    const leafPath = [...pathParts, item.key].join('/');
                    return (
                      <ConfigLeaf
                        key={leafPath}
                        item={item}
                        pathParts={pathParts}
                        depth={depth}
                        isDarkMode={isDarkMode}
                        fullWidth={fullWidth}
                        allImageHosts={allImageHosts}
                        usedImageHosts={usedImageHosts}
                        torrentClients={torrentClients}
                        onValueChange={onValueChange}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      

      {/* Subsections */}
      {subsections.map((item) => {
        // When rendering the top-level TRACKERS section we handle tracker subsections
        // inside the tabbed UI above, so skip the generic subsections rendering
        // to avoid duplicate lists.
        if (pathParts.includes('TRACKERS') && depth === 0) {
          return null;
        }
        const isTorrentClientConfig = pathParts.includes('TORRENT_CLIENTS') && depth === 0;
        const isCollapsible = item.subsection === true || isTrackerConfig || isTorrentClientConfig;
        const nextPath = item.subsection ? pathParts : [...pathParts, item.key];
        const nextDepth = item.subsection ? depth : depth + 1;
        const groupKey = [...pathParts, item.key].join('/');
        const isOpen = expandedGroups.has(groupKey);

        const nested = (
          <ItemList
            items={item.children}
            pathParts={nextPath}
            depth={nextDepth}
            isDarkMode={isDarkMode}
            allImageHosts={allImageHosts}
            usedImageHosts={usedImageHosts}
            fullWidth={isCollapsible}
            expandedGroups={expandedGroups}
            toggleGroup={toggleGroup}
            torrentClients={torrentClients}
            onValueChange={onValueChange}
          />
        );

        // For subsection items that are being displayed as sub-tabs, show content directly
        if (item.subsection === true) {
          return (
            <div key={groupKey} className="space-y-4">
              {nested}
            </div>
          );
        }

        if (isCollapsible) {
          return (
            <div key={groupKey} className="space-y-4">
              <button
                type="button"
                onClick={() => toggleGroup(groupKey)}
                className={`flex items-center gap-2 text-left w-full text-sm font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}
                aria-expanded={isOpen}
              >
                <span className="transition-transform" style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>&gt;</span>
                <span className={isDarkMode ? 'text-purple-300 font-mono' : 'text-purple-700 font-mono'}>{getTrackerDisplayName(item.key)}</span>
              </button>
              {isOpen && (
                <div className={`rounded-lg border p-4 ${isDarkMode ? 'border-gray-700 bg-gray-900/30' : 'border-gray-200 bg-gray-50'}`}>
                  {nested}
                </div>
              )}
            </div>
          );
        }

        return (
          <div key={groupKey}>
            {nested}
          </div>
        );
      })}
    </div>
  );
}

// Promise-based confirmation modal to avoid blocking `confirm()`.
// Returns a Promise that resolves to true (confirmed) or false (cancelled).
function showConfirmModal(opts) {
  // Accept either a string (message) or an options object { title, message, confirmLabel }
  const options = typeof opts === 'string' ? { message: opts } : (opts || {});
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'ua-confirm-overlay fixed inset-0 z-50 flex items-center justify-center';
    overlay.style.background = 'rgba(0,0,0,0.4)';

    const dlg = document.createElement('div');
    dlg.className = 'ua-confirm-dialog max-w-md w-full rounded-lg p-4 bg-white text-gray-900';
    dlg.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';

    const msg = document.createElement('div');
    msg.className = 'mb-4 text-sm';
    msg.textContent = options.message || '';

    if (options.title) {
      const titleEl = document.createElement('div');
      titleEl.className = 'mb-2 font-semibold';
      titleEl.textContent = options.title;
      dlg.appendChild(titleEl);
    }

    const btnRow = document.createElement('div');
    btnRow.className = 'flex justify-end gap-2';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'px-3 py-1 rounded bg-gray-200';
    cancelBtn.textContent = 'Cancel';

    const okBtn = document.createElement('button');
    okBtn.type = 'button';
    okBtn.className = 'px-3 py-1 rounded bg-red-600 text-white';
    okBtn.textContent = options.confirmLabel || 'Remove';

    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(okBtn);
    dlg.appendChild(msg);
    dlg.appendChild(btnRow);
    overlay.appendChild(dlg);
    document.body.appendChild(overlay);

    // Focus management
    okBtn.focus();

    function cleanup(result) {
        try { document.body.removeChild(overlay); } catch (e) { /* ignore */ }
        try { window.removeEventListener('keydown', keyHandler); } catch (e) { /* ignore */ }
        resolve(result);
      }

    cancelBtn.addEventListener('click', () => cleanup(false));
    okBtn.addEventListener('click', () => cleanup(true));
    overlay.addEventListener('click', (ev) => {
      if (ev.target === overlay) cleanup(false);
    });
    // Keyboard handling
    function keyHandler(ev) {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        cleanup(false);
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        cleanup(true);
      }
    }
    window.addEventListener('keydown', keyHandler, { once: true });
  });
}

function SecurityTab({ isDarkMode }) {
  const [twofaStatus, setTwofaStatus] = useState(null);
  const [setupData, setSetupData] = useState(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  // API tokens
  const [tokens, setTokens] = useState([]);
  const [tokensLoading, setTokensLoading] = useState(false);
  const [tokensReadOnly, setTokensReadOnly] = useState(false);
  const [newTokenLabel, setNewTokenLabel] = useState('');
  const [createdTokenRaw, setCreatedTokenRaw] = useState(null);
  const [tokenMessage, setTokenMessage] = useState('');
  const [createdTokenCopied, setCreatedTokenCopied] = useState(false);
  
  

  useEffect(() => {
    loadTwofaStatus();
    loadTokens();
  }, []);

  const loadTwofaStatus = async () => {
    try {
      const response = await apiFetch(`${API_BASE}/2fa/status`);
      if (!response.ok) {
        console.error(`Failed to load 2FA status: HTTP ${response.status}`);
        return;
      }
      const data = await response.json();
      if (data && typeof data.enabled === 'boolean') {
        setTwofaStatus(data.enabled);
      } else {
        console.warn('Unexpected 2FA status response shape, defaulting to disabled', data);
        setTwofaStatus(false);
      }
    } catch (error) {
      console.error('Failed to load 2FA status:', error);
    }
  };

  const handleSetup2FA = async () => {
    setLoading(true);
    setMessage('');
    try {
      const response = await apiFetch(`${API_BASE}/2fa/setup`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setSetupData(data);
        setRecoveryCodes(data.recovery_codes || null);
        setMessage('Scan the QR code with your authenticator app, then enter the 6-digit code below.');
      } else {
        setMessage(data.error || 'Failed to setup 2FA');
      }
    } catch (error) {
      setMessage('Failed to setup 2FA');
    }
    setLoading(false);
  };

  const handleVerifyAndEnable = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setMessage('Please enter a valid 6-digit code');
      return;
    }

    setLoading(true);
    setMessage('');
    try {
      const response = await apiFetch(`${API_BASE}/2fa/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: verificationCode })
      });
      const data = await response.json();
      if (data.success) {
        setTwofaStatus(true);
        setSetupData(null);
        setVerificationCode('');
        setRecoveryCodes(data.recovery_codes || null);
        setMessage('2FA has been enabled successfully!');
      } else {
        setMessage(data.error || 'Failed to enable 2FA');
      }
    } catch (error) {
      setMessage('Failed to enable 2FA');
    }
    setLoading(false);
  };

  const handleDisable2FA = async () => {
    const confirmed = await showConfirmModal({
      title: 'Disable Two-Factor Authentication',
      message: 'Are you sure you want to disable 2FA? This will make your account less secure.',
      confirmLabel: 'Disable'
    });
    if (!confirmed) return;

    setLoading(true);
    setMessage('');
    try {
      const response = await apiFetch(`${API_BASE}/2fa/disable`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setTwofaStatus(false);
        setMessage('2FA has been disabled.');
      } else {
        setMessage(data.error || 'Failed to disable 2FA');
      }
    } catch (error) {
      setMessage('Failed to disable 2FA');
    }
    setLoading(false);
  };

  const loadTokens = async () => {
    setTokensLoading(true);
    setTokenMessage('');
    try {
      const resp = await apiFetch(`${API_BASE}/tokens`);
      const data = await resp.json();
      if (data && data.success) {
        setTokens(data.tokens || []);
        setTokensReadOnly(Boolean(data.read_only));
      } else {
        setTokenMessage(data.error || 'Failed to load tokens');
      }
    } catch (err) {
      setTokenMessage('Failed to load tokens');
    }
    setTokensLoading(false);
  };

  const handleCreateToken = async () => {
    setTokenMessage('');
    setCreatedTokenRaw(null);
    try {
      const resp = await apiFetch(`${API_BASE}/tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'generate', label: newTokenLabel || '', persist: false })
      });
      const data = await resp.json();
      if (data && data.success && data.token) {
        setCreatedTokenRaw(data.token);
        if (!data.persisted) {
          setTokenMessage('Generated token (not yet stored). Click "Store" to persist, or copy it now.');
        } else {
          setTokenMessage('Token created and persisted.');
        }
      } else {
        setTokenMessage(data.error || 'Failed to create token');
      }
    } catch (err) {
      setTokenMessage('Failed to create token');
    }
  };

  const handleStoreToken = async (token) => {
    if (!token) return;
    setTokenMessage('');
    try {
      const resp = await apiFetch(`${API_BASE}/tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'store', token, label: newTokenLabel || '' })
      });
      const data = await resp.json();
      if (data && data.success) {
        setTokenMessage('Token stored successfully');
        setCreatedTokenRaw(null);
        setNewTokenLabel('');
        await loadTokens();
      } else {
        setTokenMessage(data.error || 'Failed to store token');
      }
    } catch (err) {
      setTokenMessage('Failed to store token');
    }
  };

  const handleRevokeToken = async (id) => {
    const ok = await showConfirmModal({ message: `Revoke token ${id.slice(0, 8)}...?`, confirmLabel: 'Revoke' });
    if (!ok) return;
    setTokenMessage('');
    try {
      const resp = await apiFetch(`${API_BASE}/tokens`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      const data = await resp.json();
      if (data && data.success) {
        await loadTokens();
      } else {
        setTokenMessage(data.error || 'Failed to revoke token');
      }
    } catch (err) {
      setTokenMessage('Failed to revoke token');
    }
  };

  // QR code data URL for setup (generated client-side to avoid leaking the TOTP secret
  // to third-party QR services). We lazily load a small QR library and generate a
  // data URL from the provided `setupData.uri`.
  const [qrDataUrl, setQrDataUrl] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function gen() {
      if (!setupData || !setupData.uri) {
        setQrDataUrl(null);
        return;
      }
      try {
        const lib = await loadQRCodeLib();
        // The UMD exposes either `qrcode` or `QRCode`; both provide `toDataURL`
        const toDataURL = (lib && lib.toDataURL) || (lib && lib.QRCode && lib.QRCode.toDataURL) || (window.qrcode && window.qrcode.toDataURL) || (window.QRCode && window.QRCode.toDataURL);
        if (!toDataURL) {
          setQrDataUrl(null);
          return;
        }
        const dataUrl = await toDataURL(setupData.uri, { width: 200, margin: 1 });
        if (!cancelled) setQrDataUrl(dataUrl);
      } catch (err) {
        // Fail silently; optional fallback could request a backend-provided image
        setQrDataUrl(null);
      }
    }
    gen();
    return () => {
      cancelled = true;
    };
  }, [setupData?.uri]);

  return (
    <div className={`rounded-lg border p-6 ${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
      <h2 className={`text-xl font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Two-Factor Authentication (2FA)</h2>
      
      <div className="space-y-4">
        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-gray-700' : 'bg-gray-50'}`}>
          <div className="flex items-center justify-between">
            <div>
              <h3 className={`font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                2FA Status: {twofaStatus === null ? 'Loading...' : twofaStatus ? 'Enabled' : 'Disabled'}
              </h3>
              <p className={`text-sm mt-1 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                {twofaStatus ? 'Your account is protected with time-based one-time passwords.' : 'Enable 2FA to add an extra layer of security to your account.'}
              </p>
            </div>
            <div className="flex gap-2">
              {!twofaStatus && (
                <button
                  onClick={handleSetup2FA}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Setting up...' : 'Enable 2FA'}
                </button>
              )}
              {twofaStatus && (
                <button
                  onClick={handleDisable2FA}
                  disabled={loading}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {loading ? 'Disabling...' : 'Disable 2FA'}
                </button>
              )}
            </div>
          </div>
        </div>

        {setupData && (
          <div className={`p-4 rounded-lg border ${isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-yellow-50 border-yellow-200'}`}>
            <h4 className={`font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Setup 2FA</h4>
            <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.):
            </p>
            <div className="mb-4">
              {qrDataUrl ? (
                React.createElement('img', { src: qrDataUrl, alt: '2FA QR Code', className: 'mx-auto border rounded' })
              ) : (
                React.createElement('div', { className: 'mx-auto border rounded w-48 h-48 flex items-center justify-center text-sm text-gray-500', role: 'status' }, 'QR unavailable — please copy the secret manually')
              )}
            </div>
            <p className={`text-xs mb-4 text-center ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              Or manually enter: <code className={`px-2 py-1 rounded ${isDarkMode ? 'bg-gray-600' : 'bg-gray-200'}`}>{setupData.secret}</code>
            </p>
            <p className={`text-xs mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              <strong>To store in environment variable:</strong> Set <code className={`px-1 py-0.5 rounded text-xs ${isDarkMode ? 'bg-gray-600' : 'bg-gray-200'}`}>UA_WEBUI_TOTP_SECRET={setupData.secret}</code><br />
              <strong>To copy to password manager:</strong> Save the secret &quot;{setupData.secret}&quot; in your password manager&#39;s TOTP field.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className={`flex-1 px-3 py-2 border rounded-lg ${isDarkMode ? 'bg-gray-600 border-gray-500 text-white' : 'bg-white border-gray-300'}`}
                maxLength="6"
              />
              <button
                onClick={handleVerifyAndEnable}
                disabled={loading || verificationCode.length !== 6}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                Verify & Enable
              </button>
            </div>
            {recoveryCodes && (
              <div className={`mt-4 p-3 rounded text-sm ${isDarkMode ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-900'}`}>
                <div className="font-medium mb-2">One-time recovery codes (store these safely)</div>
                <div className="grid grid-cols-2 gap-2">
                  {recoveryCodes.map((c, idx) => (
                    React.createElement('div', { key: idx, className: `${isDarkMode ? 'px-2 py-1 bg-gray-700 text-white rounded text-xs' : 'px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs'}` }, c)
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {message && (
          <div className={`p-3 rounded-lg ${message.includes('success') || message.includes('enabled') ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {message}
          </div>
        )}
        
        {/* API Tokens management */}
        <div className="mt-6">
          <h2 className={`text-lg font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>API Access Tokens</h2>
          <p className={`text-sm mb-3 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>Create opaque bearer tokens for automation and API clients. Tokens are shown once when created — store them securely.</p>

          {createdTokenRaw && (
            <div className={`p-3 mb-3 rounded ${isDarkMode ? 'bg-gray-700 text-white' : 'bg-yellow-50 text-gray-900'}`}>
              <div className="font-medium mb-2">New token (store this now)</div>
                <div className="flex items-center gap-2">
                <input readOnly value={createdTokenRaw} className={isDarkMode ? 'flex-1 px-2 py-1 rounded border border-gray-700 bg-gray-900 text-gray-100' : 'flex-1 px-2 py-1 rounded border border-gray-300 bg-white text-gray-800'} />
                <button
                  onClick={async () => {
                    try {
                      if (navigator.clipboard && createdTokenRaw) {
                        await navigator.clipboard.writeText(createdTokenRaw);
                        setCreatedTokenCopied(true);
                        setTokenMessage('Token copied to clipboard');
                        setTimeout(() => setCreatedTokenCopied(false), 2000);
                      } else {
                        setTokenMessage('Clipboard unavailable');
                      }
                    } catch (err) {
                      setTokenMessage('Failed to copy token');
                    }
                  }}
                  className="px-3 py-1 bg-gray-800 text-white rounded"
                >
                  {createdTokenCopied ? 'Copied!' : 'Copy'}
                </button>
                <button onClick={() => handleStoreToken(createdTokenRaw)} className="px-3 py-1 bg-blue-600 text-white rounded">Store</button>
              </div>
            </div>
          )}
          <div className={`p-3 mb-3 rounded ${isDarkMode ? 'bg-gray-800 text-white' : 'bg-white text-gray-900'}`}>
            <div className="mb-2 font-medium">Token label</div>
            <input value={newTokenLabel} onChange={(e) => setNewTokenLabel(e.target.value)} placeholder="Optional label" className={`w-full px-3 py-2 rounded border ${isDarkMode ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}`} />

            

            <div className="mt-3 flex gap-2">
              <button onClick={handleCreateToken} className="px-3 py-1 bg-green-600 text-white rounded">Generate</button>
              <button onClick={() => { if (createdTokenRaw) handleStoreToken(createdTokenRaw); else setTokenMessage('No token to store'); }} className="px-3 py-1 bg-blue-600 text-white rounded">Store</button>
            </div>
          </div>

          <div className={`p-3 rounded border ${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
            {tokenMessage && <div className="text-sm text-red-600">{tokenMessage}</div>}
            <div className="mt-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium mb-2">Existing tokens</div>
                {tokensReadOnly && (
                  <div className="text-xs text-yellow-400">Read-only token store (env)</div>
                )}
              </div>
              {tokensLoading ? (
                <div className="text-sm">Loading...</div>
              ) : tokens.length === 0 ? (
                <div className="text-sm text-gray-500">No tokens</div>
              ) : (
                <div className="space-y-2">
                  {tokens.map((t) => (
                    <div key={t.id} className={`flex items-center justify-between p-2 rounded ${isDarkMode ? 'bg-gray-700' : 'bg-gray-50'}`}>
                      <div className="text-xs font-mono">{t.id.slice(0, 8)}..</div>
                      <div className="flex-1 px-3 text-sm">{t.label || '(no label)'} — {t.user}</div>
                      <div className="text-sm text-gray-500 mr-3">{t.expiry ? new Date(t.expiry * 1000).toLocaleString() : 'no expiry'}</div>
                      <button onClick={() => handleRevokeToken(t.id)} className="px-2 py-1 bg-red-600 text-white rounded text-sm">Revoke</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {isDarkMode && (
            <div className="mt-3 p-3 rounded text-sm bg-gray-900 border-gray-700">
              <div className="font-medium mb-1">Docker persistence</div>
              <div className="text-xs text-gray-400">
                Persist a token in Docker by setting the environment variable <code className="px-1 py-0.5 rounded bg-gray-700">UA_TOKEN</code> to the raw token, then restart the container.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ConfigApp() {
  const [sections, setSections] = useState([]);
  // Keep a ref to the latest sections to avoid stale closures inside async loaders
  const currentSectionsRef = useRef(sections);
  useEffect(() => {
    currentSectionsRef.current = sections;
  }, [sections]);
  const [status, setStatus] = useState({ text: 'Loading config options...', type: 'info' });
  const [isDarkMode, setIsDarkMode] = useState(getStoredTheme);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [pendingChanges, setPendingChanges] = useState(new Map());
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    try {
      return sessionStorage.getItem('ua_active_tab') || 'general';
    } catch (e) {
      return 'general';
    }
  });
  const [activeSubTab, setActiveSubTab] = useState(() => {
    try {
      return sessionStorage.getItem('ua_active_subtab') || '';
    } catch (e) {
      return '';
    }
  });
  const [torrentClients, setTorrentClients] = useState([]);
  const getSubTabsForSection = (section) => {
    if (section.client_types) {
      return section.client_types.map(type => {
        let label = type.charAt(0).toUpperCase() + type.slice(1);
        if (type === 'qbit') label = 'qBitTorrent';
        return { id: type, label };
      });
    }
    const subTabs = [];
    const seenSubsections = new Set();
    
    section.items.forEach(item => {
      let subsectionName = null;
      
      // Check for string subsections
      if (item.subsection && typeof item.subsection === 'string') {
        subsectionName = formatDisplayLabel(item.subsection);
      }
      // Check for collapsible subsections (subsection === true)
      else if (item.subsection === true) {
        subsectionName = formatDisplayLabel(item.key);
      }
      
      if (subsectionName && !seenSubsections.has(subsectionName)) {
        seenSubsections.add(subsectionName);
        subTabs.push({
          id: subsectionName.toLowerCase().replace(/\s+/g, '-'),
          label: subsectionName
        });
      }
    });
    
    return subTabs;
  };

  const setStatusWithClear = (text, type = 'info', clearAfterMs = 0) => {
    setStatus({ text, type });
    if (clearAfterMs > 0) {
      window.setTimeout(() => {
        setStatus({ text: '', type: 'info' });
      }, clearAfterMs);
    }
  };

  const toggleGroup = (groupKey) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  };

  const loadConfigOptions = async () => {
    try {
      const response = await apiFetch(`${API_BASE}/config_options`);
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'Failed to load config options');
      }
      const newSections = data.sections || [];
      setSections(newSections);
      setPendingChanges(new Map());
      setStatus({ text: '', type: 'info' });

      // Restore tab state after operations (preserve which section/tab the user was on)
      let didRestoreTab = false;
      try {
        const storedActive = sessionStorage.getItem('ua_active_tab');
        const storedSub = sessionStorage.getItem('ua_active_subtab');
        if (storedActive && newSections.length > 0) {
          setActiveTab(storedActive);
          const activeSection = newSections.find(section => section.section.toLowerCase() === storedActive);
          const subTabs = activeSection ? getSubTabsForSection(activeSection) : [];
          if (storedSub && subTabs.some(s => s.id === storedSub)) {
            setActiveSubTab(storedSub);
          } else if (subTabs.length > 0) {
            setActiveSubTab(subTabs[0].id);
          } else {
            setActiveSubTab('');
          }
          sessionStorage.removeItem('ua_active_tab');
          sessionStorage.removeItem('ua_active_subtab');
          // keep ua_tracker_tab; ItemList reads it directly on mount
          didRestoreTab = true;
        }
      } catch (e) {
        // ignore storage errors
      }

      // Load torrent clients
      try {
        const clientsResponse = await apiFetch(`${API_BASE}/torrent_clients`);
        const clientsData = await clientsResponse.json();
        if (clientsData.success) {
          setTorrentClients(clientsData.clients || []);
        }
      } catch (error) {
        console.warn('Failed to load torrent clients:', error);
        setTorrentClients([]);
      }
      
      // Only set default tabs if we don't have any sections loaded yet
      const currentlyHaveSections = (currentSectionsRef && currentSectionsRef.current && currentSectionsRef.current.length) ? currentSectionsRef.current.length : (sections ? sections.length : 0);
      if (currentlyHaveSections === 0 && newSections.length > 0) {
        // If we restored a tab from sessionStorage above, don't override it.
        if (!didRestoreTab) {
          setActiveTab(newSections[0].section.toLowerCase());
          // Set first sub-tab if available
          const firstSection = newSections[0];
          const subTabs = getSubTabsForSection(firstSection);
          if (subTabs.length > 0) {
            setActiveSubTab(subTabs[0].id);
          }
        }
      } else if (newSections.length > 0) {
        // Validate that current active tab still exists
        const currentTabExists = newSections.some(section => 
          section.section.toLowerCase() === activeTab
        );
        if (!currentTabExists) {
          // Reset to first tab if current tab no longer exists
          setActiveTab(newSections[0].section.toLowerCase());
          const firstSection = newSections[0];
          const subTabs = getSubTabsForSection(firstSection);
          if (subTabs.length > 0) {
            setActiveSubTab(subTabs[0].id);
          } else {
            setActiveSubTab('');
          }
        } else {
          // Validate that current sub-tab still exists for the active tab
          const activeSection = newSections.find(section => 
            section.section.toLowerCase() === activeTab
          );
          if (activeSection) {
            const subTabs = getSubTabsForSection(activeSection);
            const currentSubTabExists = subTabs.some(subTab => subTab.id === activeSubTab);
            if (!currentSubTabExists && subTabs.length > 0) {
              setActiveSubTab(subTabs[0].id);
            } else if (!currentSubTabExists) {
              setActiveSubTab('');
            }
          }
        }
      }
    } catch (error) {
      setStatus({ text: error.message || 'Failed to load config options', type: 'error' });
    }
  };

  const onValueChange = (path, value, meta) => {
    const pathKey = path.join('/');
    setPendingChanges((prev) => {
      const next = new Map(prev);
      if (meta.readOnly) {
        return prev;
      }
      if (meta.isSensitive && meta.isRedacted) {
        next.delete(pathKey);
        return next;
      }
      if (value === meta.originalValue) {
        next.delete(pathKey);
      } else {
        next.set(pathKey, { path, value });
      }
      return next;
    });
  };

  const saveAllChanges = async () => {
    if (pendingChanges.size === 0) {
      setStatusWithClear('No changes to save.', 'warn', 1500);
      return;
    }
    setIsSaving(true);
    setStatusWithClear(`Saving ${pendingChanges.size} change${pendingChanges.size === 1 ? '' : 's'}...`, 'info');
    try {
      // Some updates may target keys inside subsections that only exist in the example-config.
      // Ensure we create an empty subsection object in the user's config first so subsequent
      // nested updates succeed. Collect unique subsection creations needed.
      const pending = Array.from(pendingChanges.values());
      const toCreate = [];
      const createdKeys = new Set();
      for (const update of pending) {
        if (Array.isArray(update.path) && update.path.length >= 2) {
          const sectionName = String(update.path[0]);
          const subsectionName = String(update.path[1]);
          const section = sections.find(s => s.section && String(s.section).toLowerCase() === sectionName.toLowerCase());
          if (section && Array.isArray(section.items)) {
            const subsectionItem = section.items.find(it => it.key && String(it.key).toUpperCase() === subsectionName.toUpperCase());
            if (subsectionItem && subsectionItem.children && subsectionItem.source === 'example') {
              const keyId = `${sectionName}/${subsectionName}`;
              if (!createdKeys.has(keyId)) {
                toCreate.push([sectionName, subsectionName]);
                createdKeys.add(keyId);
              }
            }
          }
        }
      }

      // Create missing subsections in the user's config (as empty dicts)
      for (const createPath of toCreate) {
        const respCreate = await apiFetch(`${API_BASE}/config_update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: createPath, value: '{}'
          })
        });
        const dataCreate = await respCreate.json();
        if (!dataCreate.success) {
          throw new Error(dataCreate.error || 'Failed to create subsection');
        }
      }

      // Now save the actual pending updates
      for (const update of pending) {
        const response = await apiFetch(`${API_BASE}/config_update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: update.path, value: update.value })
        });
        const data = await response.json();
        if (!data.success) {
          throw new Error(data.error || 'Failed to save');
        }
      }
      setStatusWithClear('Saved', 'success', 1500);
      await loadConfigOptions();
    } catch (error) {
      setStatusWithClear(error.message || 'Failed to save', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    (async () => {
      await loadCsrfToken();
      await loadConfigOptions();
    })();
  }, []);

  useEffect(() => {
    storage.set(THEME_KEY, isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === THEME_KEY) {
        setIsDarkMode(event.newValue === 'dark');
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const allImageHosts = useMemo(() => {
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
  }, [sections]);

  const usedImageHosts = useMemo(() => {
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
  }, [sections]);

  const pageRootClass = isDarkMode ? 'min-h-screen flex flex-col bg-gray-900 text-gray-100' : 'min-h-screen flex flex-col bg-gray-100 text-gray-900';
  const headerClass = isDarkMode ? 'border-b border-gray-700 bg-gray-800' : 'border-b border-gray-200 bg-white';
  const titleClass = isDarkMode ? 'text-2xl font-bold text-white' : 'text-2xl font-bold text-gray-800';
  const statusClass = isDarkMode ? 'text-sm text-gray-300' : 'text-sm text-gray-600';
  const themeToggleClass = isDarkMode ? 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors bg-purple-600' : 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors bg-gray-300';
  const themeKnobClass = isDarkMode ? 'inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-6' : 'inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-1';
  const saveDisabled = isSaving || pendingChanges.size === 0;
  const saveButtonClass = isDarkMode
    ? `px-3 py-1.5 rounded-lg text-sm font-semibold bg-purple-600 text-white hover:bg-purple-700${saveDisabled ? ' opacity-50 cursor-not-allowed' : ''}`
    : `px-3 py-1.5 rounded-lg text-sm font-semibold bg-purple-600 text-white hover:bg-purple-700${saveDisabled ? ' opacity-50 cursor-not-allowed' : ''}`;
  const statusTypeClass = statusClassFor(status.type, isDarkMode);

  const handleLogout = async () => {
    try {
      const resp = await apiFetch('/logout', { method: 'POST' });
      if (resp && resp.redirected) {
        window.location = resp.url;
      } else {
        window.location = '/login';
      }
    } catch (err) {
      // Fallback to hard redirect
      window.location = '/login';
    }
  };

  return (
    <div className={pageRootClass}>
      <header className={headerClass}>
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className={titleClass}>Upload Assistant Config</h1>
            <button type="button" onClick={handleLogout} className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700">Logout</button>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className={saveButtonClass}
              onClick={saveAllChanges}
              disabled={saveDisabled}
            >
              {isSaving ? 'Saving...' : 'Save Config'}
            </button>
            <a href="/" className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-gray-700 text-white hover:bg-gray-600">Back to Upload</a>
            <span className="text-sm">{isDarkMode ? '🌙 Dark' : '☀️ Light'}</span>
            <button
              className={themeToggleClass}
              type="button"
              aria-label="Toggle theme"
              onClick={() => setIsDarkMode((prev) => !prev)}
            >
              <span className={themeKnobClass}></span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-4 py-6">
          {status.text && (
            <div className={`${statusClass} ${statusTypeClass} mb-6`}>{status.text}</div>
          )}
          
          {sections.length > 0 && (
            <div className="space-y-6">
              {/* Tab Navigation */}
              <div className={`flex space-x-1 rounded-lg p-1 ${isDarkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
                <button
                  onClick={() => setActiveTab('security')}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    activeTab === 'security'
                      ? isDarkMode
                        ? 'bg-gray-700 text-white'
                        : 'bg-white text-gray-900 shadow-sm'
                      : isDarkMode
                        ? 'text-gray-400 hover:text-white hover:bg-gray-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
                  }`}
                >
                  Security
                </button>
                {sections.map((section) => {
                  const sectionId = section.section.toLowerCase();
                  const isActive = activeTab === sectionId;
                  return (
                    <button
                      key={sectionId}
                      onClick={() => {
                        setActiveTab(sectionId);
                        const subTabs = getSubTabsForSection(section);
                        if (subTabs.length > 0) {
                          setActiveSubTab(subTabs[0].id);
                        }
                      }}
                      className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive
                          ? isDarkMode
                            ? 'bg-gray-700 text-white'
                            : 'bg-white text-gray-900 shadow-sm'
                          : isDarkMode
                            ? 'text-gray-400 hover:text-white hover:bg-gray-700'
                            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
                      }`}
                    >
                      {section.section}
                    </button>
                  );
                })}
              </div>

              {/* Tab Content */}
              <div className="space-y-4">
                {activeTab === 'security' && <SecurityTab isDarkMode={isDarkMode} />}
                {sections.map((section) => {
                  const sectionId = section.section.toLowerCase();
                  if (activeTab !== sectionId) return null;
                  
                  const subTabs = getSubTabsForSection(section);
                  const hasSubTabs = subTabs.length > 0;
                  
                  return (
                    <div key={sectionId} className="space-y-4">
                      {/* Sub-tab Navigation */}
                      {hasSubTabs && (
                        <div className={`flex space-x-1 rounded-lg p-1 ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`}>
                          {subTabs.map((subTab) => {
                            const isActive = activeSubTab === subTab.id;
                            return (
                              <button
                                key={subTab.id}
                                onClick={() => setActiveSubTab(subTab.id)}
                                className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                                  isActive
                                    ? isDarkMode
                                      ? 'bg-gray-600 text-white'
                                      : 'bg-white text-gray-900 shadow-sm'
                                    : isDarkMode
                                      ? 'text-gray-400 hover:text-white hover:bg-gray-600'
                                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-300'
                                }`}
                              >
                                {subTab.label}
                              </button>
                            );
                          })}
                        </div>
                      )}
                      
                      {/* Content */}
                      <ItemList
                        items={hasSubTabs ? section.items.filter((item) => {
                          if (section.section === 'TORRENT_CLIENTS') {
                            const clientTypeItem = item.children && item.children.find(c => c.key === 'torrent_client');
                            return clientTypeItem && clientTypeItem.value === activeSubTab;
                          }
                          if (item.subsection && typeof item.subsection === 'string') {
                            return formatDisplayLabel(item.subsection).toLowerCase().replace(/\s+/g, '-') === activeSubTab;
                          }
                          if (item.subsection === true) {
                            return formatDisplayLabel(item.key).toLowerCase().replace(/\s+/g, '-') === activeSubTab;
                          }
                          return false;
                        }) : section.items}
                        pathParts={[section.section]}
                        depth={0}
                        isDarkMode={isDarkMode}
                        allImageHosts={allImageHosts}
                        usedImageHosts={usedImageHosts}
                        fullWidth={true}
                        expandedGroups={expandedGroups}
                        toggleGroup={toggleGroup}
                        torrentClients={torrentClients}
                        onValueChange={onValueChange}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('page-root')).render(<ConfigApp />);

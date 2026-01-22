const { useEffect, useMemo, useRef, useState } = React;

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
      const viewportHeight = window.innerHeight;

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

const apiFetch = async (url, options = {}) => {
  const headers = { ...(options.headers || {}) };
  const response = await fetch(url, { ...options, headers });
  return response;
};

const isPlainObject = (value) => value && typeof value === 'object' && !Array.isArray(value);
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
  depth,
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

  const valueWrapperClass = isDarkMode
    ? 'text-sm text-gray-200'
    : 'text-sm text-gray-700';

  const inputClass = isDarkMode
    ? 'w-full px-3 py-2 border border-gray-700 bg-gray-900 text-gray-100 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent'
    : 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-800 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent';


  if (typeof item.value === 'boolean') {
    const [checked, setChecked] = useState(Boolean(item.value));

    useEffect(() => {
      setChecked(Boolean(item.value));
    }, [item.value]);

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

  // Check if this is a numeric field that should use NumberInput
  const isNumericField = (key, pathParts) => {
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
      'min_successful_image_uploads',
      'overlay_text_size',
      'logo_size',
      'bluray_image_size',
      'rehash_cooldown',
      'custom_layout'
    ];
    return numericFields.includes(key);
  };

  // Check if this is a linking field that should use SelectDropdown
  const isLinkingField = (key, pathParts) => {
    return key === 'linking' && pathParts.includes('TORRENT_CLIENTS');
  };

  if (isNumericField(item.key, pathParts)) {
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
        case 'custom_layout':
          return 1;
        case 'ffmpeg_compression':
          return 6;
        default:
          return 1;
      }
    };

    const [numericValue, setNumericValue] = useState(() => {
      const val = item.value;
      if (val === null || val === undefined || val === '') return getDefaultValue(item.key);
      const num = Number(val);
      return isNaN(num) ? getDefaultValue(item.key) : num;
    });

    useEffect(() => {
      const val = item.value;
      if (val === null || val === undefined || val === '') {
        setNumericValue(1);
      } else {
        const num = Number(val);
        setNumericValue(isNaN(num) ? 1 : num);
      }
    }, [item.value]);

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
        case 'min_successful_image_uploads':
          return { min: 1, max: 10, step: 1 };
        case 'overlay_text_size':
          return { min: 10, max: 50, step: 1 };
        case 'logo_size':
          return { min: 100, max: 1000, step: 50 };
        case 'bluray_image_size':
          return { min: 100, max: 1000, step: 50 };
        case 'rehash_cooldown':
          return { min: 0, max: 300, step: 5 };
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

    const [selectedValue, setSelectedValue] = useState(() => {
      const val = item.value;
      if (val === null || val === undefined) return '';
      return String(val);
    });

    useEffect(() => {
      const val = item.value;
      if (val === null || val === undefined) {
        setSelectedValue('');
      } else {
        setSelectedValue(String(val));
      }
    }, [item.value]);

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
    const normalizeTrackers = (value) => (
      String(value || '')
        .split(',')
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean)
    );

    const [selected, setSelected] = useState(() => new Set(normalizeTrackers(item.value)));

    useEffect(() => {
      setSelected(new Set(normalizeTrackers(item.value)));
    }, [item.value]);

    const originalValue = normalizeTrackers(item.value).join(', ');

    const toggleTracker = (tracker, checked) => {
      const selections = new Set(selected);
      if (checked) {
        selections.add(tracker.toUpperCase());
      } else {
        selections.delete(tracker.toUpperCase());
      }
      setSelected(selections);
      const nextValue = Array.from(selections).map((t) => String(t).toUpperCase()).join(', ');
      onValueChange(path, nextValue, {
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
        <details className={isDarkMode ? 'rounded-lg border border-gray-700 bg-gray-900/30' : 'rounded-lg border border-gray-200 bg-gray-50'}>
          <summary className={`cursor-pointer select-none px-3 py-2 text-xs font-semibold ${isDarkMode ? 'text-gray-200' : 'text-gray-700'}`}>
            Show trackers
          </summary>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-3">
            {availableTrackers.map((tracker) => (
              <label key={tracker} className={`flex items-center gap-2 text-xs ${isDarkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                <input
                  type="checkbox"
                  checked={selected.has(tracker.toUpperCase())}
                  onChange={(e) => toggleTracker(tracker, e.target.checked)}
                  className={isDarkMode ? 'h-4 w-4 accent-purple-500' : 'h-4 w-4 accent-purple-600'}
                />
                <span>{tracker}</span>
              </label>
            ))}
          </div>
        </details>
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

  return (
    <div className="space-y-6">
      {/* Regular form fields in a grid */}
      {regularItems.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {regularItems.map((item) => {
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

      {/* Subsections */}
      {subsections.map((item) => {
        const isTrackerConfig = pathParts.includes('TRACKERS') && depth === 0;
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
                <span className={isDarkMode ? 'text-purple-300 font-mono' : 'text-purple-700 font-mono'}>{formatDisplayLabel(item.key)}</span>
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

function ConfigApp() {
  const [sections, setSections] = useState([]);
  const [status, setStatus] = useState({ text: 'Loading config options...', type: 'info' });
  const [isDarkMode, setIsDarkMode] = useState(getStoredTheme);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [pendingChanges, setPendingChanges] = useState(new Map());
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('general');
  const [activeSubTab, setActiveSubTab] = useState('');
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
      if (sections.length === 0 && newSections.length > 0) {
        setActiveTab(newSections[0].section.toLowerCase());
        // Set first sub-tab if available
        const firstSection = newSections[0];
        const subTabs = getSubTabsForSection(firstSection);
        if (subTabs.length > 0) {
          setActiveSubTab(subTabs[0].id);
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
      for (const update of pendingChanges.values()) {
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
    loadConfigOptions();
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

  return (
    <div className={pageRootClass}>
      <header className={headerClass}>
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className={titleClass}>Upload Assistant Config</h1>
            <a href="/logout" className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700">Logout</a>
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
                        items={hasSubTabs ? section.items.filter(item => {
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

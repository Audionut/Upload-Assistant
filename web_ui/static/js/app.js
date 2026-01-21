const { useState, useRef, useEffect } = React;

// Icon components
const FolderIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
  </svg>
);

const FolderOpenIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
  </svg>
);

const FileIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const TerminalIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

const PlayIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const UploadIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
  </svg>
);

function AudionutsUAGUI() {
  const API_BASE = window.location.origin + '/api';
  
  const [directories, setDirectories] = useState([
    { name: 'data', type: 'folder', path: '/data', children: [] },
    { name: 'torrent_storage_dir', type: 'folder', path: '/torrent_storage_dir', children: [] },
    { name: 'Upload-Assistant', type: 'folder', path: '/Upload-Assistant', children: [] }
  ]);
  
  const [selectedPath, setSelectedPath] = useState('');
  const [selectedName, setSelectedName] = useState('');
  const [customArgs, setCustomArgs] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [expandedFolders, setExpandedFolders] = useState(new Set(['/data', '/torrent_storage_dir']));
  const [sessionId, setSessionId] = useState('');
  const [sidebarWidth, setSidebarWidth] = useState(320);
  const [isResizing, setIsResizing] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [isDarkMode, setIsDarkMode] = useState(true); // Default to dark mode
  
  const terminalRef = useRef(null);
  const terminalContainerRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);
  const inputRef = useRef(null);

  const loadBrowseRoots = async () => {
    try {
      const response = await fetch(`${API_BASE}/browse_roots`);
      const data = await response.json();

      if (data.success && data.items) {
        setDirectories(data.items);
        setExpandedFolders(new Set());
      }
    } catch (error) {
      console.error('Failed to load browse roots:', error);
    }
  };

  // Initialize xterm.js terminal
  useEffect(() => {
    if (terminalContainerRef.current && !xtermRef.current) {
      // Create terminal instance with dynamic theme
      const getTerminalTheme = () => {
        if (isDarkMode) {
          return {
            background: '#000000',
            foreground: '#ffffff',
            cursor: '#ffffff',
            black: '#000000',
            red: '#e06c75',
            green: '#98c379',
            yellow: '#d19a66',
            blue: '#61afef',
            magenta: '#c678dd',
            cyan: '#56b6c2',
            white: '#abb2bf',
            brightBlack: '#5c6370',
            brightRed: '#e06c75',
            brightGreen: '#98c379',
            brightYellow: '#d19a66',
            brightBlue: '#61afef',
            brightMagenta: '#c678dd',
            brightCyan: '#56b6c2',
            brightWhite: '#ffffff'
          };
        } else {
          return {
            background: '#ffffff',
            foreground: '#000000',
            cursor: '#000000',
            black: '#000000',
            red: '#c91b00',
            green: '#00c200',
            yellow: '#c7c400',
            blue: '#0037da',
            magenta: '#c930c7',
            cyan: '#00c5c7',
            white: '#c7c7c7',
            brightBlack: '#686868',
            brightRed: '#ff6d67',
            brightGreen: '#5ff967',
            brightYellow: '#fefb67',
            brightBlue: '#6871ff',
            brightMagenta: '#ff76ff',
            brightCyan: '#5ffdff',
            brightWhite: '#ffffff'
          };
        }
      };

      const term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        theme: getTerminalTheme(),
        scrollback: 10000,
        convertEol: true
      });

      // Add fit addon for responsive sizing
      const fitAddon = new FitAddon.FitAddon();
      term.loadAddon(fitAddon);

      // Open terminal in container
      term.open(terminalContainerRef.current);
      fitAddon.fit();

      // Handle user input from terminal - DISABLED for now, use input bar instead
      // We'll keep terminal read-only and use the input field below
      term.onData(data => {
        // Do nothing - input handled by input field below
      });

      // Welcome message
      term.writeln('\x1b[1;36m╔═══════════════════════════════════════════════════════════════╗\x1b[0m');
      term.writeln('\x1b[1;36m║\x1b[0m  \x1b[1;35mUpload Assistant Interactive Terminal\x1b[0m                      \x1b[1;36m║\x1b[0m');
      term.writeln('\x1b[1;36m╚═══════════════════════════════════════════════════════════════╝\x1b[0m');
      term.writeln('');
      term.writeln('\x1b[1;33m📋 Quick Start:\x1b[0m');
      term.writeln('  1. Select a file or folder from the left panel');
      term.writeln('  2. Add Upload Assistant arguments (optional)');
      term.writeln('  3. Click "Execute Upload" to start');
      term.writeln('  4. Type responses directly in this terminal');
      term.writeln('');

      xtermRef.current = term;
      fitAddonRef.current = fitAddon;

      // Resize terminal on window resize
      const handleResize = () => {
        if (fitAddonRef.current) {
          fitAddonRef.current.fit();
        }
      };
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (xtermRef.current) {
          xtermRef.current.dispose();
        }
      };
    }
  }, []);

  // Update terminal theme when dark mode changes
  useEffect(() => {
    if (xtermRef.current) {
      const getTerminalTheme = () => {
        if (isDarkMode) {
          return {
            background: '#000000',
            foreground: '#ffffff',
            cursor: '#ffffff',
            black: '#000000',
            red: '#e06c75',
            green: '#98c379',
            yellow: '#d19a66',
            blue: '#61afef',
            magenta: '#c678dd',
            cyan: '#56b6c2',
            white: '#abb2bf',
            brightBlack: '#5c6370',
            brightRed: '#e06c75',
            brightGreen: '#98c379',
            brightYellow: '#d19a66',
            brightBlue: '#61afef',
            brightMagenta: '#c678dd',
            brightCyan: '#56b6c2',
            brightWhite: '#ffffff'
          };
        } else {
          return {
            background: '#ffffff',
            foreground: '#000000',
            cursor: '#000000',
            black: '#000000',
            red: '#c91b00',
            green: '#00c200',
            yellow: '#c7c400',
            blue: '#0037da',
            magenta: '#c930c7',
            cyan: '#00c5c7',
            white: '#c7c7c7',
            brightBlack: '#686868',
            brightRed: '#ff6d67',
            brightGreen: '#5ff967',
            brightYellow: '#fefb67',
            brightBlue: '#6871ff',
            brightMagenta: '#ff76ff',
            brightCyan: '#5ffdff',
            brightWhite: '#ffffff'
          };
        }
      };
      
      xtermRef.current.options.theme = getTerminalTheme();
    }
  }, [isDarkMode]);

  useEffect(() => {
    loadBrowseRoots();
  }, []);

  // Focus input when executing
  useEffect(() => {
    if (isExecuting && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isExecuting]);

  const sendInput = async () => {
    if (!sessionId) return;

    const term = xtermRef.current;
    
    // If input is empty, just send Enter (newline)
    const inputToSend = userInput.trim() === '' ? '' : userInput;
    
    setUserInput('');
    
    // Show what user typed in terminal (only if not empty)
    if (term && inputToSend !== '') {
      term.writeln('\x1b[1;36m> ' + inputToSend + '\x1b[0m');
    }

    try {
      // Send the input (empty string sends just Enter)
      await fetch(`${API_BASE}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          input: inputToSend
        })
      });
    } catch (error) {
      if (term) {
        term.writeln('\x1b[1;31mFailed to send input: ' + error.message + '\x1b[0m');
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      sendInput();
    }
  };
  useEffect(() => {
    if (fitAddonRef.current && !isResizing) {
      setTimeout(() => {
        fitAddonRef.current.fit();
      }, 100);
    }
  }, [sidebarWidth, isResizing]);

  const toggleFolder = async (path) => {
    const newExpanded = new Set(expandedFolders);
    
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
      await loadFolderContents(path);
    }
    
    setExpandedFolders(newExpanded);
  };

  const loadFolderContents = async (path) => {
    try {
      const response = await fetch(`${API_BASE}/browse?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      
      if (data.success && data.items) {
        updateDirectoryTree(path, data.items);
      }
    } catch (error) {
      console.error('Failed to load folder:', error);
    }
  };

  const updateDirectoryTree = (path, items) => {
    const updateTree = (nodes) => {
      return nodes.map(node => {
        if (node.path === path) {
          return { ...node, children: items };
        } else if (node.children) {
          return { ...node, children: updateTree(node.children) };
        }
        return node;
      });
    };
    
    setDirectories(updateTree(directories));
  };

  const renderFileTree = (items, level = 0) => {
    return items.map((item, idx) => (
      <div key={idx}>
        <div
          className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors ${
            selectedPath === item.path 
              ? isDarkMode 
                ? 'bg-purple-900 border-l-4 border-purple-500' 
                : 'bg-blue-100 border-l-4 border-blue-500'
              : isDarkMode
                ? 'hover:bg-gray-700'
                : 'hover:bg-gray-100'
          }`}
          style={{ paddingLeft: `${level * 20 + 12}px` }}
          onClick={() => {
            if (item.type === 'folder') {
              toggleFolder(item.path);
            }
            setSelectedPath(item.path);
            setSelectedName(item.name);
          }}
        >
          <span className="text-yellow-600">
            {item.type === 'folder' ? (
              expandedFolders.has(item.path) ? <FolderOpenIcon /> : <FolderIcon />
            ) : (
              <span className="text-blue-600"><FileIcon /></span>
            )}
          </span>
          <span className={`text-sm font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-700'}`}>{item.name}</span>
        </div>
        {item.type === 'folder' && expandedFolders.has(item.path) && item.children && item.children.length > 0 && (
          <div>{renderFileTree(item.children, level + 1)}</div>
        )}
      </div>
    ));
  };

  const executeCommand = async () => {
    if (!selectedPath) {
      if (xtermRef.current) {
        xtermRef.current.writeln('\x1b[1;31m✗ Please select a file or folder first\x1b[0m');
      }
      return;
    }

    const term = xtermRef.current;
    if (!term) return;

    const newSessionId = 'session_' + Date.now();
    setSessionId(newSessionId);
    setIsExecuting(true);

    term.writeln('');
    term.writeln('\x1b[1;33m$ python upload.py "' + selectedPath + '" ' + customArgs + '\x1b[0m');
    term.writeln('\x1b[1;34m→ Starting execution...\x1b[0m');

    try {
      const response = await fetch(`${API_BASE}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: selectedPath,
          args: customArgs,
          session_id: newSessionId
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue;
          
          try {
            const data = JSON.parse(line.substring(6));
            
            if (data.type === 'stdout' || data.type === 'stderr') {
              // Write raw output with ANSI codes preserved
              term.write(data.data);
            } else if (data.type === 'exit') {
              term.writeln('');
              term.writeln(`\x1b[1;34m✓ Process exited with code ${data.code}\x1b[0m`);
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        }
      }

      term.writeln('\x1b[1;32m✓ Execution completed\x1b[0m');
      term.writeln('');
    } catch (error) {
      term.writeln('\x1b[1;31m✗ Execution error: ' + error.message + '\x1b[0m');
    } finally {
      setIsExecuting(false);
      setSessionId('');
    }
  };

  const clearTerminal = async () => {
    const term = xtermRef.current;
    
    // If a process is running, kill it first
    if (isExecuting && sessionId) {
      try {
        await fetch(`${API_BASE}/kill`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
        });
        
        if (term) {
          term.writeln('');
          term.writeln('\x1b[1;31m✗ Process terminated by user\x1b[0m');
          term.writeln('');
        }
        
        setIsExecuting(false);
        setSessionId('');
      } catch (error) {
        console.error('Failed to kill process:', error);
      }
    }
    
    // Clear the terminal
    if (term) {
      term.clear();
      
      // Re-show welcome message
      term.writeln('\x1b[1;36m╔═══════════════════════════════════════════════════════════════╗\x1b[0m');
      term.writeln('\x1b[1;36m║\x1b[0m  \x1b[1;35mUpload Assistant Interactive Terminal\x1b[0m                      \x1b[1;36m║\x1b[0m');
      term.writeln('\x1b[1;36m╚═══════════════════════════════════════════════════════════════╝\x1b[0m');
      term.writeln('');
      term.writeln('\x1b[1;33m📋 Quick Start:\x1b[0m');
      term.writeln('  1. Select a file or folder from the left panel');
      term.writeln('  2. Add Upload Assistant arguments (optional)');
      term.writeln('  3. Click "Execute Upload" to start');
      term.writeln('  4. Type responses in the input field below');
      term.writeln('');
    }
  };

  // Sidebar resizing
  const startResizing = () => {
    setIsResizing(true);
  };

  const stopResizing = () => {
    setIsResizing(false);
  };

  const resize = (e) => {
    if (isResizing) {
      const newWidth = e.clientX;
      if (newWidth >= 200 && newWidth <= 600) {
        setSidebarWidth(newWidth);
      }
    }
  };

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
      return () => {
        window.removeEventListener('mousemove', resize);
        window.removeEventListener('mouseup', stopResizing);
      };
    }
  }, [isResizing]);

  return (
    <div className={`flex h-screen ${isDarkMode ? 'bg-gray-900' : 'bg-gray-50'} overflow-hidden`}>
      {/* Left Sidebar - Resizable */}
      <div 
        className={`${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-r flex flex-col`}
        style={{ width: `${sidebarWidth}px`, minWidth: '200px', maxWidth: '600px' }}
      >
        <div className={`p-4 border-b ${isDarkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-gradient-to-r from-purple-50 to-blue-50'}`}>
          <h2 className={`text-lg font-bold ${isDarkMode ? 'text-white' : 'text-gray-800'} flex items-center gap-2`}>
            <FolderIcon />
            File Browser
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {renderFileTree(directories)}
        </div>
      </div>

      {/* Resize Handle */}
      <div
        className={`w-1 ${isDarkMode ? 'bg-gray-700 hover:bg-purple-500' : 'bg-gray-300 hover:bg-purple-500'} cursor-col-resize transition-colors`}
        onMouseDown={startResizing}
        style={{ userSelect: 'none' }}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Panel */}
        <div className={`${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b p-4 flex-shrink-0`}>
          <div className="max-w-6xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h1 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-800'} flex items-center gap-2`}>
                <UploadIcon />
                Upload Assistant Web UI
              </h1>
              
              {/* Dark Mode Toggle */}
              <div className="flex items-center gap-3">
                <span className={`text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                  {isDarkMode ? '🌙 Dark' : '☀️ Light'}
                </span>
                <button
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    isDarkMode ? 'bg-purple-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      isDarkMode ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Selected Path Display */}
            {selectedPath && (
              <div className={`p-3 ${isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-blue-50 border-blue-200'} border rounded-lg`}>
                <p className={`text-xs font-semibold ${isDarkMode ? 'text-gray-300' : 'text-gray-600'} mb-1`}>Selected Path:</p>
                <p className={`text-sm ${isDarkMode ? 'text-white' : 'text-gray-800'} break-all font-mono`}>{selectedPath}</p>
              </div>
            )}

            {/* Arguments */}
            <div className="space-y-2">
              <label className={`text-sm font-semibold ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Additional Arguments:</label>
              <input
                type="text"
                value={customArgs}
                onChange={(e) => setCustomArgs(e.target.value)}
                placeholder="--tmdb movie/12345 --trackers ptp,aither,ulcx --no-edition --no-tag"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent ${
                  isDarkMode 
                    ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400' 
                    : 'bg-white border-gray-300 text-gray-900'
                }`}
                disabled={isExecuting}
              />
              <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Common: --tmdb movie/12345 --trackers ptp,aither,ulcx --no-edition --no-tag
              </p>
            </div>

            {/* Execute Button */}
            <div className="flex gap-2">
              <button
                onClick={executeCommand}
                disabled={!selectedPath || isExecuting}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium text-lg"
              >
                <PlayIcon />
                {isExecuting ? 'Executing...' : 'Execute Upload'}
              </button>
              <button
                onClick={clearTerminal}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  isExecuting 
                    ? 'bg-red-600 hover:bg-red-700 text-white' 
                    : 'bg-gray-600 hover:bg-gray-700 text-white'
                }`}
                title={isExecuting ? 'Kill process and clear terminal' : 'Clear terminal'}
              >
                <TrashIcon />
                {isExecuting ? 'Kill & Clear' : 'Clear'}
              </button>
            </div>
          </div>
        </div>

        {/* Terminal Container */}
        <div className={`flex-1 ${isDarkMode ? 'bg-gray-900' : 'bg-gray-100'} p-4 flex flex-col min-h-0 overflow-hidden`}>
          <div className="max-w-6xl mx-auto w-full flex-1 flex flex-col min-h-0">
            <div className="flex items-center gap-2 mb-3 flex-shrink-0">
              <TerminalIcon />
              <h3 className={`text-lg font-bold ${isDarkMode ? 'text-white' : 'text-gray-800'}`}>Interactive Terminal</h3>
              {isExecuting && (
                <span className="ml-auto text-sm text-green-400 animate-pulse">● Running</span>
              )}
            </div>
            
            {/* xterm.js terminal container */}
            <div 
              ref={terminalContainerRef}
              className="flex-1 rounded-t-lg overflow-hidden shadow-lg"
              style={{ minHeight: 0 }}
            />
            
            {/* Input Field */}
            <div className={`${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-200 border-gray-300'} rounded-b-lg p-3 flex gap-2 items-center border-t flex-shrink-0 mt-0`}>
              <span className="text-green-400 font-bold flex-shrink-0">$</span>
              <input
                ref={inputRef}
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={!isExecuting}
                placeholder={isExecuting ? "Type response and press Enter (or just press Enter to continue)..." : "Execute a command first"}
                className={`flex-1 px-3 py-2 rounded border focus:border-purple-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed font-mono text-sm ${
                  isDarkMode
                    ? 'bg-gray-900 text-white border-gray-700 placeholder-gray-500'
                    : 'bg-white text-gray-900 border-gray-400 placeholder-gray-400'
                }`}
              />
              <button
                onClick={sendInput}
                disabled={!isExecuting}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors flex items-center gap-2 flex-shrink-0"
                title="Send input (or press Enter on empty input to continue)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Render the app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<AudionutsUAGUI />);
